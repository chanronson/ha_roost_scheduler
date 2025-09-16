"""Presence management for the Roost Scheduler integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from homeassistant.core import HomeAssistant, State, Event
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, EVENT_STATE_CHANGED
from homeassistant.helpers.event import async_track_state_change_event

from .const import MODE_HOME, MODE_AWAY, DEFAULT_PRESENCE_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


class PresenceManager:
    """Manages presence detection and Home/Away mode determination."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the presence manager."""
        self.hass = hass
        self._presence_entities: List[str] = []
        self._presence_rule = "anyone_home"
        self._timeout_seconds = DEFAULT_PRESENCE_TIMEOUT_SECONDS
        self._mode_change_callbacks: List[Callable[[str], None]] = []
        self._current_mode = MODE_HOME
        self._override_entities = {
            "force_home": "input_boolean.roost_force_home",
            "force_away": "input_boolean.roost_force_away"
        }
        self._state_listeners = []
        self._initialized = False
    
    async def get_current_mode(self) -> str:
        """Get the current presence mode (home or away)."""
        # Check for override entities first
        force_home_state = self.hass.states.get(self._override_entities["force_home"])
        force_away_state = self.hass.states.get(self._override_entities["force_away"])
        
        if force_home_state and force_home_state.state == "on":
            _LOGGER.debug("Force home override active")
            return MODE_HOME
        
        if force_away_state and force_away_state.state == "on":
            _LOGGER.debug("Force away override active")
            return MODE_AWAY
        
        # Evaluate presence entities
        is_home = await self.evaluate_presence_entities()
        mode = MODE_HOME if is_home else MODE_AWAY
        
        # Update current mode and notify callbacks if changed
        if mode != self._current_mode:
            old_mode = self._current_mode
            self._current_mode = mode
            _LOGGER.info("Presence mode changed from %s to %s", old_mode, mode)
            
            # Notify callbacks
            for callback in self._mode_change_callbacks:
                try:
                    callback(mode)
                except Exception as e:
                    _LOGGER.error("Error in mode change callback: %s", e)
        
        return mode
    
    async def evaluate_presence_entities(self) -> bool:
        """Evaluate presence entities based on the configured rule."""
        if not self._presence_entities:
            _LOGGER.debug("No presence entities configured, defaulting to home")
            return True
        
        home_count = 0
        total_valid = 0
        
        for entity_id in self._presence_entities:
            state = self.hass.states.get(entity_id)
            if not state:
                _LOGGER.warning("Presence entity %s not found", entity_id)
                continue
            
            # Check if entity is stale
            if self.is_entity_stale(entity_id):
                _LOGGER.warning("Presence entity %s is stale, treating as away", entity_id)
                total_valid += 1
                continue
            
            total_valid += 1
            
            # Check if entity indicates home
            if self._is_entity_home(state):
                home_count += 1
        
        if total_valid == 0:
            _LOGGER.warning("No valid presence entities, defaulting to away")
            return False
        
        # Apply presence rule
        if self._presence_rule == "anyone_home":
            result = home_count > 0
        elif self._presence_rule == "everyone_home":
            result = home_count == total_valid
        else:
            _LOGGER.error("Unknown presence rule: %s", self._presence_rule)
            result = home_count > 0
        
        _LOGGER.debug("Presence evaluation: %d/%d entities home, rule=%s, result=%s", 
                     home_count, total_valid, self._presence_rule, result)
        
        return result
    
    def is_entity_stale(self, entity_id: str) -> bool:
        """Check if a presence entity is stale (hasn't updated recently)."""
        state = self.hass.states.get(entity_id)
        if not state or not state.last_updated:
            _LOGGER.debug("Entity %s has no state or last_updated, considering stale", entity_id)
            return True
        
        # Handle timezone-aware datetime comparison
        now = datetime.now()
        if state.last_updated.tzinfo is not None:
            # Convert to naive datetime for comparison
            last_updated = state.last_updated.replace(tzinfo=None)
        else:
            last_updated = state.last_updated
        
        time_since_update = now - last_updated
        timeout = timedelta(seconds=self._timeout_seconds)
        
        is_stale = time_since_update > timeout
        
        if is_stale:
            _LOGGER.debug("Entity %s is stale: %s since last update (timeout: %ds)", 
                         entity_id, time_since_update, self._timeout_seconds)
        
        return is_stale
    
    async def register_mode_change_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback for mode changes."""
        self._mode_change_callbacks.append(callback)
        _LOGGER.debug("Registered mode change callback")
    
    async def async_initialize(self) -> None:
        """Initialize the presence manager with state tracking."""
        if self._initialized:
            return
        
        # Set up state change listeners for presence entities and overrides
        await self._setup_state_listeners()
        
        # Get initial mode
        self._current_mode = await self.get_current_mode()
        self._initialized = True
        
        _LOGGER.info("PresenceManager initialized with mode: %s", self._current_mode)
    
    async def _setup_state_listeners(self) -> None:
        """Set up state change listeners for presence entities and overrides."""
        # Listen to all presence entities
        all_entities = list(self._presence_entities)
        
        # Add override entities
        all_entities.extend(self._override_entities.values())
        
        if all_entities:
            # Track state changes for all relevant entities
            listener = async_track_state_change_event(
                self.hass,
                all_entities,
                self._handle_state_change
            )
            self._state_listeners.append(listener)
            _LOGGER.debug("Set up state listeners for entities: %s", all_entities)
    
    async def _handle_state_change(self, event: Event) -> None:
        """Handle state changes for presence entities."""
        entity_id = event.data.get("entity_id")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        
        if not new_state:
            return
        
        _LOGGER.debug("State change for %s: %s -> %s", 
                     entity_id, 
                     old_state.state if old_state else "None", 
                     new_state.state)
        
        # Re-evaluate presence mode
        new_mode = await self.get_current_mode()
        
        # Mode change is handled in get_current_mode() method
    
    async def async_unload(self) -> None:
        """Unload the presence manager and clean up listeners."""
        for listener in self._state_listeners:
            listener()
        self._state_listeners.clear()
        self._initialized = False
        _LOGGER.debug("PresenceManager unloaded")
    
    async def configure_presence(self, entities: List[str], rule: str, timeout_seconds: int) -> None:
        """Configure presence detection settings."""
        # Clean up existing listeners
        for listener in self._state_listeners:
            listener()
        self._state_listeners.clear()
        
        # Update configuration
        self._presence_entities = entities
        self._presence_rule = rule
        self._timeout_seconds = timeout_seconds
        
        # Set up new listeners if initialized
        if self._initialized:
            await self._setup_state_listeners()
        
        _LOGGER.info("Configured presence: entities=%s, rule=%s, timeout=%ds", 
                    entities, rule, timeout_seconds)
    
    def _is_entity_home(self, state: State) -> bool:
        """Determine if an entity state indicates 'home'."""
        # Handle device trackers
        if state.domain == "device_tracker":
            return state.state == STATE_HOME
        
        # Handle input_boolean and binary_sensor
        if state.domain in ["input_boolean", "binary_sensor"]:
            return state.state == "on"
        
        # Handle person entities
        if state.domain == "person":
            return state.state == STATE_HOME
        
        # Handle zone entities (if state is 'home' zone)
        if state.state == STATE_HOME:
            return True
        
        # Default: treat any non-'away' state as home for unknown domains
        return state.state != STATE_NOT_HOME
    
    async def set_override(self, override_type: str, enabled: bool) -> None:
        """Set presence override."""
        if override_type not in self._override_entities:
            _LOGGER.error("Unknown override type: %s", override_type)
            return
        
        entity_id = self._override_entities[override_type]
        
        try:
            # Call the input_boolean service to set the override
            await self.hass.services.async_call(
                "input_boolean",
                "turn_on" if enabled else "turn_off",
                {"entity_id": entity_id}
            )
            _LOGGER.info("Set %s to %s", entity_id, "on" if enabled else "off")
        except Exception as e:
            _LOGGER.error("Failed to set override %s: %s", entity_id, e)
    
    def get_presence_status(self) -> dict:
        """Get detailed presence status for debugging."""
        status = {
            "current_mode": self._current_mode,
            "presence_rule": self._presence_rule,
            "timeout_seconds": self._timeout_seconds,
            "entities": {},
            "overrides": {}
        }
        
        # Check each presence entity
        for entity_id in self._presence_entities:
            state = self.hass.states.get(entity_id)
            if state:
                status["entities"][entity_id] = {
                    "state": state.state,
                    "is_home": self._is_entity_home(state),
                    "is_stale": self.is_entity_stale(entity_id),
                    "last_updated": state.last_updated.isoformat() if state.last_updated else None
                }
            else:
                status["entities"][entity_id] = {
                    "state": "unavailable",
                    "is_home": False,
                    "is_stale": True,
                    "last_updated": None
                }
        
        # Check override entities
        for override_type, entity_id in self._override_entities.items():
            state = self.hass.states.get(entity_id)
            status["overrides"][override_type] = {
                "entity_id": entity_id,
                "state": state.state if state else "unavailable",
                "active": state.state == "on" if state else False
            }
        
        return status