"""
Dashboard Integration Service for Roost Scheduler.

Handles automatic card installation, dashboard detection, and default card configuration.
Provides conflict resolution for existing cards and error handling for dashboard access failures.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import HomeAssistantError

try:
    from .const import DOMAIN, CARD_NAME
except ImportError:
    # Fallback for testing
    DOMAIN = "roost_scheduler"
    CARD_NAME = "roost-scheduler-card"

_LOGGER = logging.getLogger(__name__)


@dataclass
class DashboardCardConfig:
    """Configuration for automatic card installation."""
    dashboard_id: str
    view_id: Optional[str] = None
    card_position: Optional[int] = None
    default_entity: Optional[str] = None
    card_settings: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.card_settings is None:
            self.card_settings = {}


@dataclass
class DashboardIntegrationStatus:
    """Status of dashboard integration process."""
    resources_registered: bool = False
    card_available_in_picker: bool = False
    card_added_to_dashboard: bool = False
    dashboard_id: Optional[str] = None
    error_messages: List[str] = None
    next_steps: List[str] = None
    
    def __post_init__(self):
        if self.error_messages is None:
            self.error_messages = []
        if self.next_steps is None:
            self.next_steps = []


@dataclass
class CardInstallationResult:
    """Result of card installation attempt."""
    success: bool
    dashboard_id: str
    view_id: Optional[str] = None
    card_position: Optional[int] = None
    error_message: Optional[str] = None
    conflict_resolved: bool = False
    existing_card_updated: bool = False


class DashboardIntegrationService:
    """Service for automatic dashboard card installation and management."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the dashboard integration service."""
        self.hass = hass
        self._default_card_config = {
            "type": f"custom:{CARD_NAME}",
            "title": "Roost Scheduler",
            "show_header_toggle": False,
            "theme": "default"
        }
    
    async def add_card_to_dashboard(
        self, 
        entities: List[str],
        dashboard_id: Optional[str] = None,
        view_id: Optional[str] = None,
        card_position: Optional[int] = None
    ) -> CardInstallationResult:
        """
        Add Roost Scheduler card to specified dashboard.
        
        Args:
            entities: List of entities to include in the card
            dashboard_id: Target dashboard ID (defaults to main dashboard)
            view_id: Target view ID (defaults to first view)
            card_position: Position to insert card (defaults to end)
            
        Returns:
            CardInstallationResult with installation details
        """
        _LOGGER.info("Adding Roost Scheduler card to dashboard %s", dashboard_id or "default")
        
        try:
            # Get target dashboard
            if not dashboard_id:
                dashboard_id = await self.get_default_dashboard()
            
            # Load dashboard configuration
            dashboard_config = await self._load_dashboard_config(dashboard_id)
            if not dashboard_config:
                return CardInstallationResult(
                    success=False,
                    dashboard_id=dashboard_id,
                    error_message=f"Could not load dashboard configuration for {dashboard_id}"
                )
            
            # Get target view
            target_view, view_index = await self._get_target_view(dashboard_config, view_id)
            if not target_view:
                return CardInstallationResult(
                    success=False,
                    dashboard_id=dashboard_id,
                    error_message=f"Could not find or create target view {view_id or 'default'}"
                )
            
            # Check for existing cards and handle conflicts
            conflict_result = await self._handle_card_conflicts(target_view, entities)
            
            # Create card configuration
            card_config = await self.create_default_card_config(entities)
            
            # Add card to view
            if card_position is not None and 0 <= card_position <= len(target_view.get("cards", [])):
                target_view.setdefault("cards", []).insert(card_position, card_config)
            else:
                target_view.setdefault("cards", []).append(card_config)
                card_position = len(target_view["cards"]) - 1
            
            # Save dashboard configuration
            await self._save_dashboard_config(dashboard_id, dashboard_config)
            
            _LOGGER.info(
                "Successfully added Roost Scheduler card to dashboard %s, view %s at position %d",
                dashboard_id, target_view.get("title", "default"), card_position
            )
            
            return CardInstallationResult(
                success=True,
                dashboard_id=dashboard_id,
                view_id=target_view.get("path") or target_view.get("title"),
                card_position=card_position,
                conflict_resolved=conflict_result["conflicts_found"],
                existing_card_updated=conflict_result["existing_updated"]
            )
            
        except Exception as e:
            error_msg = f"Failed to add card to dashboard: {str(e)}"
            _LOGGER.error(error_msg, exc_info=True)
            return CardInstallationResult(
                success=False,
                dashboard_id=dashboard_id or "unknown",
                error_message=error_msg
            )
    
    async def get_default_dashboard(self) -> str:
        """
        Identify the user's primary/default dashboard.
        
        Returns:
            Dashboard ID of the default dashboard
        """
        try:
            # Check if default Lovelace dashboard exists and is accessible
            default_dashboard = "lovelace"
            
            try:
                config = await self._load_dashboard_config(default_dashboard)
                if config is not None:
                    _LOGGER.debug("Using default Lovelace dashboard")
                    return default_dashboard
            except Exception as e:
                _LOGGER.debug("Default Lovelace dashboard not accessible: %s", str(e))
            
            # Try to find other available dashboards
            available_dashboards = await self._get_available_dashboards()
            if available_dashboards:
                selected_dashboard = available_dashboards[0]
                _LOGGER.info("Using first available dashboard: %s", selected_dashboard)
                return selected_dashboard
            
            # Fallback to default even if not accessible
            _LOGGER.warning("No accessible dashboards found, falling back to default")
            return default_dashboard
            
        except Exception as e:
            _LOGGER.error("Error determining default dashboard: %s", str(e))
            return "lovelace"  # Ultimate fallback
    
    async def create_default_card_config(self, entities: List[str]) -> Dict[str, Any]:
        """
        Generate sensible default card configuration.
        
        Args:
            entities: List of entities to include in the card
            
        Returns:
            Dictionary containing default card configuration
        """
        card_config = self._default_card_config.copy()
        
        # Add entities to card configuration
        if entities:
            card_config["entities"] = entities
            
            # Set a more specific title if we have entities
            if len(entities) == 1:
                entity_state = self.hass.states.get(entities[0])
                if entity_state:
                    friendly_name = entity_state.attributes.get("friendly_name", entities[0])
                    card_config["title"] = f"Roost Scheduler - {friendly_name}"
            elif len(entities) <= 3:
                card_config["title"] = f"Roost Scheduler ({len(entities)} devices)"
            else:
                card_config["title"] = f"Roost Scheduler ({len(entities)} devices)"
        
        # Add default view settings
        card_config.update({
            "show_current_temperature": True,
            "show_target_temperature": True,
            "show_schedule_preview": True,
            "compact_mode": False
        })
        
        _LOGGER.debug("Created default card configuration: %s", card_config)
        return card_config
    
    async def handle_dashboard_conflicts(
        self, 
        dashboard_config: Dict[str, Any],
        entities: List[str]
    ) -> Dict[str, Any]:
        """
        Handle conflicts with existing cards and dashboard configurations.
        
        Args:
            dashboard_config: Current dashboard configuration
            entities: Entities for the new card
            
        Returns:
            Dictionary containing conflict resolution results
        """
        conflict_result = {
            "conflicts_found": False,
            "existing_cards": [],
            "resolution_actions": [],
            "existing_updated": False
        }
        
        try:
            # Check all views for existing Roost Scheduler cards
            for view_index, view in enumerate(dashboard_config.get("views", [])):
                cards = view.get("cards", [])
                
                for card_index, card in enumerate(cards):
                    if self._is_roost_scheduler_card(card):
                        conflict_result["conflicts_found"] = True
                        conflict_result["existing_cards"].append({
                            "view_index": view_index,
                            "card_index": card_index,
                            "view_title": view.get("title", f"View {view_index}"),
                            "card_config": card
                        })
            
            # If conflicts found, decide on resolution strategy
            if conflict_result["conflicts_found"]:
                resolution_strategy = await self._determine_conflict_resolution_strategy(
                    conflict_result["existing_cards"], entities
                )
                
                if resolution_strategy == "update_existing":
                    # Update the first existing card with new entities
                    first_card = conflict_result["existing_cards"][0]
                    view_index = first_card["view_index"]
                    card_index = first_card["card_index"]
                    
                    # Merge entities
                    existing_entities = first_card["card_config"].get("entities", [])
                    merged_entities = list(set(existing_entities + entities))
                    
                    dashboard_config["views"][view_index]["cards"][card_index]["entities"] = merged_entities
                    
                    conflict_result["existing_updated"] = True
                    conflict_result["resolution_actions"].append(
                        f"Updated existing card in {first_card['view_title']} with new entities"
                    )
                    
                elif resolution_strategy == "remove_duplicates":
                    # Remove duplicate cards (keep the first one)
                    cards_to_remove = conflict_result["existing_cards"][1:]  # Skip first card
                    
                    # Remove cards in reverse order to maintain indices
                    for card_info in reversed(cards_to_remove):
                        view_index = card_info["view_index"]
                        card_index = card_info["card_index"]
                        dashboard_config["views"][view_index]["cards"].pop(card_index)
                        
                        conflict_result["resolution_actions"].append(
                            f"Removed duplicate card from {card_info['view_title']}"
                        )
            
        except Exception as e:
            _LOGGER.error("Error handling dashboard conflicts: %s", str(e))
            conflict_result["resolution_actions"].append(f"Error during conflict resolution: {str(e)}")
        
        return conflict_result
    
    async def handle_dashboard_access_failures(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle dashboard access failures with fallback strategies.
        
        Args:
            error_info: Dictionary containing error details
            
        Returns:
            Dictionary containing recovery actions and results
        """
        _LOGGER.info("Handling dashboard access failures: %s", error_info)
        
        recovery_result = {
            "recovery_attempted": False,
            "recovery_successful": False,
            "fallback_dashboard": None,
            "actions_taken": [],
            "manual_steps_required": []
        }
        
        try:
            recovery_result["recovery_attempted"] = True
            
            # Try alternative dashboards
            available_dashboards = await self._get_available_dashboards()
            
            for dashboard_id in available_dashboards:
                if dashboard_id != error_info.get("failed_dashboard"):
                    try:
                        config = await self._load_dashboard_config(dashboard_id)
                        if config is not None:
                            recovery_result["recovery_successful"] = True
                            recovery_result["fallback_dashboard"] = dashboard_id
                            recovery_result["actions_taken"].append(
                                f"Successfully accessed fallback dashboard: {dashboard_id}"
                            )
                            break
                    except Exception as e:
                        recovery_result["actions_taken"].append(
                            f"Failed to access dashboard {dashboard_id}: {str(e)}"
                        )
            
            # If no dashboards are accessible, provide manual steps
            if not recovery_result["recovery_successful"]:
                recovery_result["manual_steps_required"] = [
                    "Check Home Assistant dashboard configuration and permissions",
                    "Verify that Lovelace is properly configured and accessible",
                    "Try manually adding the Roost Scheduler card through the dashboard UI",
                    "Check Home Assistant logs for dashboard-related errors",
                    "Consider restarting Home Assistant if dashboard issues persist"
                ]
        
        except Exception as e:
            error_msg = f"Error during dashboard access failure handling: {str(e)}"
            recovery_result["actions_taken"].append(error_msg)
            _LOGGER.error(error_msg, exc_info=True)
        
        return recovery_result
    
    async def _load_dashboard_config(self, dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Load dashboard configuration from storage."""
        try:
            if dashboard_id == "lovelace":
                store = Store(self.hass, 1, "lovelace")
            else:
                store = Store(self.hass, 1, f"lovelace.{dashboard_id}")
            
            config = await store.async_load()
            return config or {}
            
        except Exception as e:
            _LOGGER.error("Failed to load dashboard config for %s: %s", dashboard_id, str(e))
            return None
    
    async def _save_dashboard_config(self, dashboard_id: str, config: Dict[str, Any]) -> None:
        """Save dashboard configuration to storage."""
        try:
            if dashboard_id == "lovelace":
                store = Store(self.hass, 1, "lovelace")
            else:
                store = Store(self.hass, 1, f"lovelace.{dashboard_id}")
            
            await store.async_save(config)
            _LOGGER.debug("Saved dashboard configuration for %s", dashboard_id)
            
        except Exception as e:
            _LOGGER.error("Failed to save dashboard config for %s: %s", dashboard_id, str(e))
            raise
    
    async def _get_target_view(
        self, 
        dashboard_config: Dict[str, Any], 
        view_id: Optional[str]
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """Get or create target view in dashboard."""
        views = dashboard_config.setdefault("views", [])
        
        # If no views exist, create a default one
        if not views:
            default_view = {
                "title": "Home",
                "path": "default",
                "cards": []
            }
            views.append(default_view)
            return default_view, 0
        
        # If specific view requested, try to find it
        if view_id:
            for index, view in enumerate(views):
                if (view.get("path") == view_id or 
                    view.get("title", "").lower() == view_id.lower()):
                    return view, index
        
        # Return first view as default
        return views[0], 0
    
    async def _handle_card_conflicts(
        self, 
        target_view: Dict[str, Any], 
        entities: List[str]
    ) -> Dict[str, Any]:
        """Handle conflicts with existing cards in the target view."""
        conflict_result = {
            "conflicts_found": False,
            "existing_updated": False
        }
        
        cards = target_view.get("cards", [])
        
        # Look for existing Roost Scheduler cards
        for card_index, card in enumerate(cards):
            if self._is_roost_scheduler_card(card):
                conflict_result["conflicts_found"] = True
                
                # Update existing card with new entities
                existing_entities = card.get("entities", [])
                merged_entities = list(set(existing_entities + entities))
                card["entities"] = merged_entities
                
                conflict_result["existing_updated"] = True
                _LOGGER.info("Updated existing Roost Scheduler card with merged entities")
                break
        
        return conflict_result
    
    def _is_roost_scheduler_card(self, card: Dict[str, Any]) -> bool:
        """Check if a card is a Roost Scheduler card."""
        card_type = card.get("type", "")
        return card_type == f"custom:{CARD_NAME}" or "roost-scheduler" in card_type.lower()
    
    async def _determine_conflict_resolution_strategy(
        self, 
        existing_cards: List[Dict[str, Any]], 
        new_entities: List[str]
    ) -> str:
        """Determine the best strategy for resolving card conflicts."""
        if len(existing_cards) == 1:
            # Single existing card - update it
            return "update_existing"
        elif len(existing_cards) > 1:
            # Multiple existing cards - remove duplicates
            return "remove_duplicates"
        else:
            # No conflicts
            return "no_action"
    
    async def _get_available_dashboards(self) -> List[str]:
        """Get list of available dashboard IDs."""
        dashboards = ["lovelace"]  # Always include default
        
        try:
            # Try to discover additional dashboards
            # This is a simplified approach - in a full implementation,
            # we might scan the storage directory for lovelace.* files
            pass
            
        except Exception as e:
            _LOGGER.debug("Error discovering additional dashboards: %s", str(e))
        
        return dashboards