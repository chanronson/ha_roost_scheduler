"""Presence management for the Roost Scheduler integration."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Dict, Any

from homeassistant.core import HomeAssistant, State, Event
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, EVENT_STATE_CHANGED
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.template import Template

from .const import MODE_HOME, MODE_AWAY, DEFAULT_PRESENCE_TIMEOUT_SECONDS
from .models import PresenceConfig

_LOGGER = logging.getLogger(__name__)

# Debug logging flags
DEBUG_PRESENCE_EVALUATION = False
DEBUG_ENTITY_STATES = False

# Performance monitoring
PERFORMANCE_MONITORING = False


class PresenceManager:
    """Manages presence detection and Home/Away mode determination."""
    
    def __init__(self, hass: HomeAssistant, storage_service=None) -> None:
        """Initialize the presence manager with storage integration."""
        self.hass = hass
        self.storage_service = storage_service
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
        self._custom_template: Optional[Template] = None
        self._template_entities: List[str] = []
        self._presence_config: Optional['PresenceConfig'] = None
    
    async def get_current_mode(self) -> str:
        """Get the current presence mode (home or away)."""
        if DEBUG_PRESENCE_EVALUATION:
            _LOGGER.debug("Evaluating presence mode")
            
        # Check for override entities first
        force_home_state = self.hass.states.get(self._override_entities["force_home"])
        force_away_state = self.hass.states.get(self._override_entities["force_away"])
        
        if DEBUG_ENTITY_STATES:
            _LOGGER.debug("Override states - force_home: %s, force_away: %s", 
                         force_home_state.state if force_home_state else "None",
                         force_away_state.state if force_away_state else "None")
        
        if force_home_state and force_home_state.state == "on":
            if DEBUG_PRESENCE_EVALUATION:
                _LOGGER.debug("Force home override active")
            return MODE_HOME
        
        if force_away_state and force_away_state.state == "on":
            if DEBUG_PRESENCE_EVALUATION:
                _LOGGER.debug("Force away override active")
            return MODE_AWAY
        
        # Evaluate presence entities
        is_home = await self.evaluate_presence_entities()
        mode = MODE_HOME if is_home else MODE_AWAY
        
        if DEBUG_PRESENCE_EVALUATION:
            _LOGGER.debug("Presence evaluation result: is_home=%s, mode=%s", is_home, mode)
        
        # Update current mode and notify callbacks if changed
        if mode != self._current_mode:
            old_mode = self._current_mode
            self._current_mode = mode
            _LOGGER.info("Presence mode changed from %s to %s", old_mode, mode)
            
            # Emit event for real-time updates
            from .const import DOMAIN
            self.hass.bus.async_fire(f"{DOMAIN}_presence_changed", {
                "old_mode": old_mode,
                "new_mode": mode,
                "timestamp": datetime.now().isoformat(),
                "trigger": "presence_evaluation"
            })
            
            # Notify callbacks
            for callback in self._mode_change_callbacks:
                try:
                    callback(mode)
                except Exception as e:
                    _LOGGER.error("Error in mode change callback: %s", e)
        
        return mode
    
    async def evaluate_presence_entities(self) -> bool:
        """Evaluate presence entities based on the configured rule or custom template."""
        # If custom template is configured, use it instead of standard rules
        if self._custom_template:
            return await self._evaluate_custom_template()
        
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
        elif self._presence_rule == "custom":
            # Custom rule without template - should not happen
            _LOGGER.error("Custom rule specified but no template configured")
            result = home_count > 0
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
        start_time = time.time()
        
        if self._initialized:
            _LOGGER.debug("PresenceManager already initialized, skipping")
            return
        
        _LOGGER.info("Initializing PresenceManager...")
        
        try:
            # Load configuration from storage
            config_start = time.time()
            await self.load_configuration()
            config_duration = time.time() - config_start
            
            if PERFORMANCE_MONITORING:
                _LOGGER.info("PERF: PresenceManager configuration loading completed in %.3fs", config_duration)
            
            # Set up state change listeners for presence entities and overrides
            listener_start = time.time()
            await self._setup_state_listeners()
            listener_duration = time.time() - listener_start
            
            if PERFORMANCE_MONITORING:
                _LOGGER.info("PERF: PresenceManager state listeners setup completed in %.3fs", listener_duration)
            
            # Get initial mode
            mode_start = time.time()
            self._current_mode = await self.get_current_mode()
            mode_duration = time.time() - mode_start
            
            if PERFORMANCE_MONITORING:
                _LOGGER.info("PERF: PresenceManager initial mode evaluation completed in %.3fs", mode_duration)
            
            self._initialized = True
            
            total_duration = time.time() - start_time
            _LOGGER.info("PresenceManager initialized successfully with mode: %s (total time: %.3fs)", 
                        self._current_mode, total_duration)
            
            # Log configuration summary
            config_summary = self.get_configuration_summary()
            _LOGGER.info("PresenceManager configuration: entities=%d, rule=%s, timeout=%ds, template=%s", 
                        len(config_summary['presence_entities']), 
                        config_summary['presence_rule'],
                        config_summary['timeout_seconds'],
                        bool(config_summary['custom_template']))
            
        except Exception as e:
            _LOGGER.error("Failed to initialize PresenceManager: %s", e, exc_info=True)
            # Set minimal state to prevent complete failure
            self._initialized = False
            raise
    
    async def _setup_state_listeners(self) -> None:
        """Set up state change listeners for presence entities and overrides."""
        # Listen to all presence entities
        all_entities = list(self._presence_entities)
        
        # Add template entities if using custom template
        if self._template_entities:
            all_entities.extend(self._template_entities)
        
        # Add override entities
        all_entities.extend(self._override_entities.values())
        
        # Remove duplicates
        all_entities = list(set(all_entities))
        
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
    
    async def configure_presence(self, entities: List[str], rule: str, timeout_seconds: int, 
                                custom_template: Optional[str] = None) -> None:
        """Configure presence detection settings."""
        # Clean up existing listeners
        for listener in self._state_listeners:
            listener()
        self._state_listeners.clear()
        
        # Update configuration
        self._presence_entities = entities
        self._presence_rule = rule
        self._timeout_seconds = timeout_seconds
        
        # Configure custom template if provided
        if custom_template:
            try:
                self._custom_template = Template(custom_template, self.hass)
                # Extract entities referenced in the template
                self._template_entities = self._extract_template_entities(custom_template)
                _LOGGER.info("Configured custom presence template with entities: %s", 
                           self._template_entities)
            except Exception as e:
                _LOGGER.error("Failed to configure custom template: %s", e)
                self._custom_template = None
                self._template_entities = []
        else:
            self._custom_template = None
            self._template_entities = []
        
        # Save configuration to storage
        try:
            await self.save_configuration()
        except Exception as e:
            _LOGGER.error("Failed to save presence configuration: %s", e)
        
        # Set up new listeners if initialized
        if self._initialized:
            await self._setup_state_listeners()
        
        _LOGGER.info("Configured presence: entities=%s, rule=%s, timeout=%ds, template=%s", 
                    entities, rule, timeout_seconds, bool(custom_template))
    
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
            "custom_template": self._custom_template.template if self._custom_template else None,
            "template_entities": self._template_entities,
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
    
    async def _evaluate_custom_template(self) -> bool:
        """Evaluate custom Jinja template for presence detection."""
        if not self._custom_template:
            _LOGGER.error("Custom template evaluation called but no template configured")
            return True
        
        try:
            # Render the template
            result = self._custom_template.async_render()
            
            # Convert result to boolean
            if isinstance(result, str):
                # Handle string results
                result_lower = result.lower().strip()
                is_home = result_lower in ['true', 'yes', 'on', '1', 'home']
            elif isinstance(result, bool):
                is_home = result
            elif isinstance(result, (int, float)):
                is_home = bool(result)
            else:
                _LOGGER.warning("Template returned unexpected type %s: %s", type(result), result)
                is_home = bool(result)
            
            _LOGGER.debug("Custom template evaluation result: %s -> %s", result, is_home)
            return is_home
            
        except Exception as e:
            _LOGGER.error("Error evaluating custom presence template: %s", e)
            # Fall back to standard evaluation
            return await self._evaluate_standard_presence()
    
    async def _evaluate_standard_presence(self) -> bool:
        """Evaluate presence using standard rules (fallback for template errors)."""
        if not self._presence_entities:
            return True
        
        home_count = 0
        total_valid = 0
        
        for entity_id in self._presence_entities:
            state = self.hass.states.get(entity_id)
            if not state or self.is_entity_stale(entity_id):
                total_valid += 1
                continue
            
            total_valid += 1
            if self._is_entity_home(state):
                home_count += 1
        
        if total_valid == 0:
            return False
        
        return home_count > 0  # Default to anyone_home rule
    
    def _extract_template_entities(self, template_str: str) -> List[str]:
        """Extract entity IDs referenced in a Jinja template."""
        import re
        
        # Pattern to match states('entity.id') or is_state('entity.id', 'value')
        patterns = [
            r"states\(['\"]([^'\"]+)['\"]\)",
            r"is_state\(['\"]([^'\"]+)['\"]",
            r"state_attr\(['\"]([^'\"]+)['\"]",
            r"states\.([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)",
        ]
        
        entities = set()
        for pattern in patterns:
            matches = re.findall(pattern, template_str)
            entities.update(matches)
        
        # Convert domain.entity format to entity_id format
        entity_list = []
        for entity in entities:
            if '.' in entity:
                entity_list.append(entity)
            else:
                # Handle states.domain.entity format
                _LOGGER.debug("Skipping malformed entity reference: %s", entity)
        
        return list(entity_list)
    
    def set_custom_template(self, template_str: str) -> bool:
        """Set a custom Jinja template for presence evaluation."""
        try:
            self._custom_template = Template(template_str, self.hass)
            self._template_entities = self._extract_template_entities(template_str)
            self._presence_rule = "custom"
            
            _LOGGER.info("Set custom presence template with entities: %s", self._template_entities)
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to set custom template: %s", e)
            return False
    
    def clear_custom_template(self) -> None:
        """Clear the custom template and revert to standard rules."""
        self._custom_template = None
        self._template_entities = []
        if self._presence_rule == "custom":
            self._presence_rule = "anyone_home"  # Revert to default
        
        _LOGGER.info("Cleared custom presence template")
    
    async def load_configuration(self) -> None:
        """Load presence configuration from storage with automatic migration."""
        start_time = time.time()
        _LOGGER.debug("Loading presence configuration from storage...")
        
        if not self.storage_service:
            _LOGGER.warning("No storage service available, using default configuration")
            await self._initialize_default_configuration()
            return
        
        try:
            await self._detect_and_migrate_configuration()
            duration = time.time() - start_time
            
            _LOGGER.info("Presence configuration loaded successfully in %.3fs", duration)
            self.log_performance_metric("load_configuration", duration)
            
            # Log configuration details
            _LOGGER.debug("Loaded presence configuration: entities=%d, rule=%s, timeout=%ds", 
                         len(self._presence_entities), self._presence_rule, self._timeout_seconds)
            
        except Exception as e:
            duration = time.time() - start_time
            _LOGGER.error("Failed to load presence configuration after %.3fs: %s", duration, e, exc_info=True)
            await self._initialize_default_configuration()
    
    async def save_configuration(self) -> None:
        """Save presence configuration to storage."""
        start_time = time.time()
        _LOGGER.debug("Saving presence configuration to storage...")
        
        if not self.storage_service:
            _LOGGER.warning("No storage service available, cannot save configuration")
            return
        
        try:
            # Create or update presence config
            if not self._presence_config:
                self._presence_config = PresenceConfig()
                _LOGGER.debug("Created new PresenceConfig instance")
            
            # Update config with current values
            self._presence_config.entities = self._presence_entities.copy()
            self._presence_config.rule = self._presence_rule
            self._presence_config.timeout_seconds = self._timeout_seconds
            self._presence_config.override_entities = self._override_entities.copy()
            self._presence_config.custom_template = self._custom_template.template if self._custom_template else None
            self._presence_config.template_entities = self._template_entities.copy()
            
            _LOGGER.debug("Updated PresenceConfig with current values: entities=%d, rule=%s", 
                         len(self._presence_entities), self._presence_rule)
            
            # Load existing schedule data or create new
            load_start = time.time()
            schedule_data = await self.storage_service.load_schedules()
            load_duration = time.time() - load_start
            
            if not schedule_data:
                _LOGGER.debug("No existing schedule data, creating new ScheduleData")
                # Create minimal schedule data with presence config
                from .models import ScheduleData
                schedule_data = ScheduleData(
                    version="0.3.0",
                    entities_tracked=[],
                    presence_entities=self._presence_entities.copy(),
                    presence_rule=self._presence_rule,
                    presence_timeout_seconds=self._timeout_seconds,
                    buffer={},
                    ui={},
                    schedules={"home": {}, "away": {}},
                    metadata={},
                    presence_config=self._presence_config
                )
            else:
                _LOGGER.debug("Updating existing schedule data with presence configuration")
                # Update existing schedule data
                schedule_data.presence_config = self._presence_config
                # Also update legacy fields for backward compatibility
                schedule_data.presence_entities = self._presence_entities.copy()
                schedule_data.presence_rule = self._presence_rule
                schedule_data.presence_timeout_seconds = self._timeout_seconds
            
            save_start = time.time()
            await self.storage_service.save_schedules(schedule_data)
            save_duration = time.time() - save_start
            
            total_duration = time.time() - start_time
            _LOGGER.info("Presence configuration saved successfully in %.3fs (load: %.3fs, save: %.3fs)", 
                        total_duration, load_duration, save_duration)
            self.log_performance_metric("save_configuration", total_duration, 
                                      load_time=load_duration, save_time=save_duration)
            
        except Exception as e:
            duration = time.time() - start_time
            _LOGGER.error("Failed to save presence configuration after %.3fs: %s", duration, e, exc_info=True)
    
    async def update_presence_entities(self, entities: List[str]) -> None:
        """Update presence entities and persist to storage."""
        old_entities = self._presence_entities.copy()
        try:
            # Validate entities
            for entity_id in entities:
                if not isinstance(entity_id, str) or '.' not in entity_id:
                    raise ValueError(f"Invalid entity_id: {entity_id}")
            
            # Update configuration
            self._presence_entities = entities.copy()
            
            # Save to storage
            await self.save_configuration()
            
            # Update state listeners if initialized
            if self._initialized:
                await self._setup_state_listeners()
            
            _LOGGER.info("Updated presence entities from %s to %s", old_entities, entities)
        except Exception as e:
            _LOGGER.error("Failed to update presence entities: %s", e)
            # Revert on error
            self._presence_entities = old_entities
            raise
    
    async def update_presence_rule(self, rule: str) -> None:
        """Update presence rule and persist to storage."""
        old_rule = self._presence_rule
        try:
            valid_rules = {"anyone_home", "everyone_home", "custom"}
            if rule not in valid_rules:
                raise ValueError(f"Invalid presence rule: {rule}. Must be one of {valid_rules}")
            
            self._presence_rule = rule
            
            # Save to storage
            await self.save_configuration()
            
            _LOGGER.info("Updated presence rule from %s to %s", old_rule, rule)
        except Exception as e:
            _LOGGER.error("Failed to update presence rule: %s", e)
            # Revert on error
            self._presence_rule = old_rule
            raise
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get current configuration for diagnostics."""
        return {
            "presence_entities": self._presence_entities.copy(),
            "presence_rule": self._presence_rule,
            "timeout_seconds": self._timeout_seconds,
            "override_entities": self._override_entities.copy(),
            "custom_template": self._custom_template.template if self._custom_template else None,
            "template_entities": self._template_entities.copy(),
            "current_mode": self._current_mode,
            "initialized": self._initialized,
            "storage_service_available": self.storage_service is not None,
            "presence_config_loaded": self._presence_config is not None
        }
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic information for troubleshooting."""
        diagnostic_info = {
            "manager_status": {
                "initialized": self._initialized,
                "current_mode": self._current_mode,
                "storage_available": self.storage_service is not None,
                "config_loaded": self._presence_config is not None,
                "listeners_count": len(self._state_listeners),
                "callbacks_count": len(self._mode_change_callbacks)
            },
            "configuration": self.get_configuration_summary(),
            "entity_states": {},
            "override_states": {},
            "validation_results": {},
            "performance_metrics": {},
            "troubleshooting": {
                "common_issues": [],
                "recommendations": []
            }
        }
        
        # Get detailed entity states
        for entity_id in self._presence_entities:
            state = self.hass.states.get(entity_id)
            if state:
                diagnostic_info["entity_states"][entity_id] = {
                    "state": state.state,
                    "domain": state.domain,
                    "is_home": self._is_entity_home(state),
                    "is_stale": self.is_entity_stale(entity_id),
                    "last_updated": state.last_updated.isoformat() if state.last_updated else None,
                    "last_changed": state.last_changed.isoformat() if state.last_changed else None,
                    "attributes": dict(state.attributes) if state.attributes else {}
                }
            else:
                diagnostic_info["entity_states"][entity_id] = {
                    "state": "not_found",
                    "error": "Entity not found in Home Assistant"
                }
        
        # Get override entity states
        for override_type, entity_id in self._override_entities.items():
            state = self.hass.states.get(entity_id)
            if state:
                diagnostic_info["override_states"][override_type] = {
                    "entity_id": entity_id,
                    "state": state.state,
                    "active": state.state == "on",
                    "last_updated": state.last_updated.isoformat() if state.last_updated else None
                }
            else:
                diagnostic_info["override_states"][override_type] = {
                    "entity_id": entity_id,
                    "state": "not_found",
                    "error": "Override entity not found in Home Assistant"
                }
        
        # Run validation
        is_valid, errors = self.validate_configuration()
        diagnostic_info["validation_results"] = {
            "is_valid": is_valid,
            "errors": errors
        }
        
        # Add troubleshooting information
        diagnostic_info["troubleshooting"] = self._generate_troubleshooting_info(diagnostic_info)
        
        return diagnostic_info
    
    def _generate_troubleshooting_info(self, diagnostic_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate troubleshooting information based on diagnostic data."""
        issues = []
        recommendations = []
        
        # Check for common issues
        if not diagnostic_info["manager_status"]["initialized"]:
            issues.append("PresenceManager is not initialized")
            recommendations.append("Check logs for initialization errors and restart the integration")
        
        if not diagnostic_info["manager_status"]["storage_available"]:
            issues.append("Storage service is not available")
            recommendations.append("Check Home Assistant storage permissions and disk space")
        
        if not diagnostic_info["configuration"]["presence_entities"]:
            issues.append("No presence entities configured")
            recommendations.append("Configure at least one presence entity (device_tracker, person, etc.)")
        
        # Check entity states
        missing_entities = []
        stale_entities = []
        for entity_id, entity_info in diagnostic_info["entity_states"].items():
            if entity_info.get("state") == "not_found":
                missing_entities.append(entity_id)
            elif entity_info.get("is_stale"):
                stale_entities.append(entity_id)
        
        if missing_entities:
            issues.append(f"Presence entities not found: {', '.join(missing_entities)}")
            recommendations.append("Remove non-existent entities or ensure they are properly configured")
        
        if stale_entities:
            issues.append(f"Stale presence entities (not updated recently): {', '.join(stale_entities)}")
            recommendations.append(f"Check if these entities are working properly or increase timeout from {diagnostic_info['configuration']['timeout_seconds']}s")
        
        # Check override entities
        missing_overrides = []
        for override_type, override_info in diagnostic_info["override_states"].items():
            if override_info.get("state") == "not_found":
                missing_overrides.append(f"{override_type}: {override_info['entity_id']}")
        
        if missing_overrides:
            issues.append(f"Override entities not found: {', '.join(missing_overrides)}")
            recommendations.append("Create the missing input_boolean entities or update override configuration")
        
        # Check validation errors
        if not diagnostic_info["validation_results"]["is_valid"]:
            issues.extend(diagnostic_info["validation_results"]["errors"])
            recommendations.append("Fix configuration validation errors listed above")
        
        # Check for template issues
        if diagnostic_info["configuration"]["custom_template"]:
            try:
                if self._custom_template:
                    self._custom_template.async_render()
            except Exception as e:
                issues.append(f"Custom template error: {e}")
                recommendations.append("Fix the custom template syntax or remove it to use standard rules")
        
        return {
            "common_issues": issues,
            "recommendations": recommendations,
            "health_score": max(0, 100 - len(issues) * 10),  # Simple health scoring
            "last_check": datetime.now().isoformat()
        }
    
    def log_performance_metric(self, operation: str, duration_seconds: float, **kwargs) -> None:
        """Log performance metrics if monitoring is enabled."""
        if not PERFORMANCE_MONITORING:
            return
        
        extra_info = ""
        for key, value in kwargs.items():
            extra_info += f" {key}={value}"
        
        _LOGGER.info("PERF: PresenceManager.%s completed in %.3fs%s", operation, duration_seconds, extra_info)
    
    async def run_diagnostics(self) -> Dict[str, Any]:
        """Run comprehensive diagnostics and return results."""
        _LOGGER.info("Running PresenceManager diagnostics...")
        
        start_time = time.time()
        diagnostic_info = self.get_diagnostic_info()
        
        # Test presence evaluation
        try:
            eval_start = time.time()
            current_mode = await self.get_current_mode()
            eval_duration = time.time() - eval_start
            
            diagnostic_info["performance_metrics"]["presence_evaluation"] = {
                "duration_seconds": eval_duration,
                "result": current_mode,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            diagnostic_info["performance_metrics"]["presence_evaluation"] = {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        
        # Test configuration loading
        if self.storage_service:
            try:
                load_start = time.time()
                await self.load_configuration()
                load_duration = time.time() - load_start
                
                diagnostic_info["performance_metrics"]["configuration_loading"] = {
                    "duration_seconds": load_duration,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                diagnostic_info["performance_metrics"]["configuration_loading"] = {
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        total_duration = time.time() - start_time
        diagnostic_info["performance_metrics"]["total_diagnostic_time"] = total_duration
        
        _LOGGER.info("PresenceManager diagnostics completed in %.3fs", total_duration)
        
        return diagnostic_info
    
    def validate_configuration(self) -> tuple[bool, List[str]]:
        """
        Validate current presence configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Validate presence entities
            if not isinstance(self._presence_entities, list):
                errors.append("presence_entities must be a list")
            else:
                for entity_id in self._presence_entities:
                    if not isinstance(entity_id, str) or not entity_id:
                        errors.append(f"Invalid entity_id in presence_entities: {entity_id}")
                    elif '.' not in entity_id:
                        errors.append(f"entity_id must be in format 'domain.entity': {entity_id}")
                    else:
                        # Check if entity exists in Home Assistant
                        state = self.hass.states.get(entity_id)
                        if not state:
                            errors.append(f"Presence entity not found in Home Assistant: {entity_id}")
                        else:
                            # Check if entity domain is suitable for presence detection
                            domain = entity_id.split('.')[0]
                            valid_domains = {'device_tracker', 'person', 'binary_sensor', 'input_boolean', 'zone'}
                            if domain not in valid_domains:
                                errors.append(f"Entity {entity_id} has domain '{domain}' which may not be suitable for presence detection. Valid domains: {valid_domains}")
            
            # Validate presence rule
            valid_rules = {"anyone_home", "everyone_home", "custom"}
            if self._presence_rule not in valid_rules:
                errors.append(f"presence_rule must be one of {valid_rules}, got {self._presence_rule}")
            
            # Validate timeout_seconds
            if not isinstance(self._timeout_seconds, int) or self._timeout_seconds < 0:
                errors.append(f"timeout_seconds must be a non-negative integer, got {self._timeout_seconds}")
            elif self._timeout_seconds > 86400:  # 24 hours
                errors.append(f"timeout_seconds cannot exceed 86400 (24 hours), got {self._timeout_seconds}")
            elif self._timeout_seconds < 60:  # Less than 1 minute might be too aggressive
                errors.append(f"timeout_seconds of {self._timeout_seconds} may be too short, consider at least 60 seconds")
            
            # Validate override entities
            if not isinstance(self._override_entities, dict):
                errors.append("override_entities must be a dictionary")
            else:
                for key, entity_id in self._override_entities.items():
                    if not isinstance(entity_id, str) or not entity_id:
                        errors.append(f"Invalid override entity_id for {key}: {entity_id}")
                    elif '.' not in entity_id:
                        errors.append(f"Override entity_id must be in format 'domain.entity': {entity_id}")
                    else:
                        # Check if override entity exists
                        state = self.hass.states.get(entity_id)
                        if not state:
                            errors.append(f"Override entity not found in Home Assistant: {entity_id}")
                        else:
                            # Check if override entity is input_boolean
                            domain = entity_id.split('.')[0]
                            if domain != 'input_boolean':
                                errors.append(f"Override entity {entity_id} should be input_boolean, got {domain}")
            
            # Validate custom template if present
            if self._custom_template:
                try:
                    # Try to render the template to check for syntax errors
                    self._custom_template.async_render()
                except Exception as e:
                    errors.append(f"Custom template has syntax error: {e}")
            
            # Validate template entities
            if not isinstance(self._template_entities, list):
                errors.append("template_entities must be a list")
            else:
                for entity_id in self._template_entities:
                    if not isinstance(entity_id, str) or not entity_id:
                        errors.append(f"Invalid entity_id in template_entities: {entity_id}")
                    elif '.' not in entity_id:
                        errors.append(f"Template entity_id must be in format 'domain.entity': {entity_id}")
                    else:
                        # Check if template entity exists
                        state = self.hass.states.get(entity_id)
                        if not state:
                            errors.append(f"Template entity not found in Home Assistant: {entity_id}")
            
            # Validate consistency between rule and template
            if self._presence_rule == "custom" and not self._custom_template:
                errors.append("Custom presence rule specified but no custom template configured")
            elif self._presence_rule != "custom" and self._custom_template:
                errors.append("Custom template configured but presence rule is not 'custom'")
            
            # Check for empty presence entities when not using custom template
            if not self._presence_entities and not self._custom_template:
                errors.append("No presence entities configured and no custom template specified")
            
        except Exception as e:
            errors.append(f"Unexpected error during validation: {e}")
        
        return len(errors) == 0, errors
    
    def repair_configuration(self) -> tuple[bool, List[str]]:
        """
        Attempt to repair common configuration issues.
        
        Returns:
            Tuple of (was_repaired, list_of_repairs_made)
        """
        repairs = []
        
        try:
            # Remove invalid presence entities
            if isinstance(self._presence_entities, list):
                valid_entities = []
                for entity_id in self._presence_entities:
                    if isinstance(entity_id, str) and '.' in entity_id:
                        state = self.hass.states.get(entity_id)
                        if state:
                            valid_entities.append(entity_id)
                        else:
                            repairs.append(f"Removed non-existent presence entity: {entity_id}")
                    else:
                        repairs.append(f"Removed invalid presence entity: {entity_id}")
                
                if len(valid_entities) != len(self._presence_entities):
                    self._presence_entities = valid_entities
            
            # Fix invalid presence rule
            valid_rules = {"anyone_home", "everyone_home", "custom"}
            if self._presence_rule not in valid_rules:
                old_rule = self._presence_rule
                self._presence_rule = "anyone_home"
                repairs.append(f"Fixed invalid presence rule from '{old_rule}' to 'anyone_home'")
            
            # Fix invalid timeout
            if not isinstance(self._timeout_seconds, int) or self._timeout_seconds < 0:
                old_timeout = self._timeout_seconds
                self._timeout_seconds = 600  # 10 minutes default
                repairs.append(f"Fixed invalid timeout from {old_timeout} to 600 seconds")
            elif self._timeout_seconds > 86400:
                old_timeout = self._timeout_seconds
                self._timeout_seconds = 86400
                repairs.append(f"Fixed excessive timeout from {old_timeout} to 86400 seconds (24 hours)")
            
            # Fix rule/template consistency
            if self._presence_rule == "custom" and not self._custom_template:
                self._presence_rule = "anyone_home"
                repairs.append("Fixed custom rule without template by changing to 'anyone_home'")
            elif self._presence_rule != "custom" and self._custom_template:
                self._custom_template = None
                self._template_entities = []
                repairs.append("Removed custom template since rule is not 'custom'")
            
            # Ensure we have some presence detection method
            if not self._presence_entities and not self._custom_template:
                # Can't automatically fix this, but we can log it
                repairs.append("Warning: No presence entities or custom template configured")
            
        except Exception as e:
            repairs.append(f"Error during configuration repair: {e}")
        
        return len(repairs) > 0, repairs
    
    def _load_from_presence_config(self, config: PresenceConfig) -> None:
        """Load configuration from PresenceConfig object."""
        try:
            self._presence_entities = config.entities.copy()
            self._presence_rule = config.rule
            self._timeout_seconds = config.timeout_seconds
            self._override_entities = config.override_entities.copy()
            self._template_entities = config.template_entities.copy()
            
            # Set up custom template if present
            if config.custom_template:
                try:
                    self._custom_template = Template(config.custom_template, self.hass)
                except Exception as e:
                    _LOGGER.error("Failed to load custom template: %s", e)
                    self._custom_template = None
            else:
                self._custom_template = None
            
            _LOGGER.debug("Loaded configuration from PresenceConfig")
        except Exception as e:
            _LOGGER.error("Error loading from PresenceConfig: %s", e)
            raise
    
    async def _migrate_from_legacy_fields(self, schedule_data) -> None:
        """Migrate configuration from legacy fields in ScheduleData."""
        try:
            _LOGGER.info("Migrating presence configuration from legacy fields")
            
            # Create PresenceConfig from legacy fields
            self._presence_config = PresenceConfig(
                entities=schedule_data.presence_entities.copy() if schedule_data.presence_entities else [],
                rule=schedule_data.presence_rule if schedule_data.presence_rule else "anyone_home",
                timeout_seconds=schedule_data.presence_timeout_seconds if schedule_data.presence_timeout_seconds else DEFAULT_PRESENCE_TIMEOUT_SECONDS,
                override_entities={
                    "force_home": "input_boolean.roost_force_home",
                    "force_away": "input_boolean.roost_force_away"
                },
                custom_template=None,
                template_entities=[]
            )
            
            # Load the migrated configuration
            self._load_from_presence_config(self._presence_config)
            
            # Save the migrated configuration
            await self.save_configuration()
            
            _LOGGER.info("Successfully migrated presence configuration")
        except Exception as e:
            _LOGGER.error("Failed to migrate presence configuration: %s", e)
            await self._initialize_default_configuration()
    
    async def _migrate_from_config_entry(self, config_entry_data: dict) -> None:
        """Migrate configuration from config entry data."""
        try:
            _LOGGER.info("Migrating presence configuration from config entry data")
            
            # Extract presence configuration from config entry
            presence_entities = config_entry_data.get('presence_entities', [])
            presence_rule = config_entry_data.get('presence_rule', 'anyone_home')
            presence_timeout = config_entry_data.get('presence_timeout_seconds', DEFAULT_PRESENCE_TIMEOUT_SECONDS)
            
            # Create PresenceConfig from config entry data
            self._presence_config = PresenceConfig(
                entities=presence_entities.copy() if presence_entities else [],
                rule=presence_rule,
                timeout_seconds=presence_timeout,
                override_entities={
                    "force_home": "input_boolean.roost_force_home",
                    "force_away": "input_boolean.roost_force_away"
                },
                custom_template=None,
                template_entities=[]
            )
            
            # Load the migrated configuration
            self._load_from_presence_config(self._presence_config)
            
            # Save the migrated configuration
            await self.save_configuration()
            
            _LOGGER.info("Successfully migrated presence configuration from config entry")
        except Exception as e:
            _LOGGER.error("Failed to migrate presence configuration from config entry: %s", e)
            await self._initialize_default_configuration()
    
    async def _detect_and_migrate_configuration(self) -> None:
        """Detect configuration version and migrate if needed."""
        try:
            # First try to load from storage
            schedule_data = await self.storage_service.load_schedules()
            
            if schedule_data and schedule_data.presence_config:
                # Modern configuration exists, use it
                self._presence_config = schedule_data.presence_config
                self._load_from_presence_config(schedule_data.presence_config)
                _LOGGER.debug("Loaded modern presence configuration from storage")
                return
            
            # Check for legacy fields in schedule data
            if schedule_data and (schedule_data.presence_entities or schedule_data.presence_rule):
                await self._migrate_from_legacy_fields(schedule_data)
                return
            
            # Try to migrate from config entry data
            if hasattr(self.storage_service, 'get_config_entry_data'):
                try:
                    config_entry_data = self.storage_service.get_config_entry_data()
                    if config_entry_data and ('presence_entities' in config_entry_data or 'presence_rule' in config_entry_data):
                        await self._migrate_from_config_entry(config_entry_data)
                        return
                except Exception as e:
                    _LOGGER.debug("Could not access config entry data: %s", e)
            
            # No configuration found, initialize defaults
            await self._initialize_default_configuration()
            
        except Exception as e:
            _LOGGER.error("Error during configuration detection and migration: %s", e)
            await self._initialize_default_configuration()
    
    async def _initialize_default_configuration(self) -> None:
        """Initialize with default configuration."""
        try:
            self._presence_config = PresenceConfig()
            self._presence_entities = []
            self._presence_rule = "anyone_home"
            self._timeout_seconds = DEFAULT_PRESENCE_TIMEOUT_SECONDS
            self._override_entities = {
                "force_home": "input_boolean.roost_force_home",
                "force_away": "input_boolean.roost_force_away"
            }
            self._custom_template = None
            self._template_entities = []
            
            _LOGGER.info("Initialized default presence configuration")
            
            # Try to save default configuration if storage is available
            if self.storage_service:
                try:
                    await self.save_configuration()
                except Exception as e:
                    _LOGGER.warning("Could not save default configuration: %s", e)
        except Exception as e:
            _LOGGER.error("Failed to initialize default configuration: %s", e)
            raise