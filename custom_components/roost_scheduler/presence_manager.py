"""Presence management for the Roost Scheduler integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from homeassistant.core import HomeAssistant, State
from homeassistant.const import STATE_HOME, STATE_NOT_HOME

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
            return True
        
        time_since_update = datetime.now() - state.last_updated.replace(tzinfo=None)
        timeout = timedelta(seconds=self._timeout_seconds)
        
        return time_since_update > timeout
    
    async def register_mode_change_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback for mode changes."""
        self._mode_change_callbacks.append(callback)
        _LOGGER.debug("Registered mode change callback")
    
    def configure_presence(self, entities: List[str], rule: str, timeout_seconds: int) -> None:
        """Configure presence detection settings."""
        self._presence_entities = entities
        self._presence_rule = rule
        self._timeout_seconds = timeout_seconds
        
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
    
    def set_override(self, override_type: str, enabled: bool) -> None:
        """Set presence override."""
        if override_type not in self._override_entities:
            _LOGGER.error("Unknown override type: %s", override_type)
            return
        
        entity_id = self._override_entities[override_type]
        service_data = {
            "entity_id": entity_id,
            "state": "on" if enabled else "off"
        }
        
        # This would call the input_boolean service in a real implementation
        _LOGGER.info("Would set %s to %s", entity_id, "on" if enabled else "off")