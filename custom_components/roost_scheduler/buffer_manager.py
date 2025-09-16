"""Buffer management for the Roost Scheduler integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from homeassistant.core import HomeAssistant

from .models import BufferConfig, EntityState
from .const import DEFAULT_BUFFER_TIME_MINUTES, DEFAULT_BUFFER_VALUE_DELTA

_LOGGER = logging.getLogger(__name__)


class BufferManager:
    """Manages intelligent buffering to avoid conflicts with manual changes."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the buffer manager."""
        self.hass = hass
        self._entity_states: Dict[str, EntityState] = {}
        self._global_buffer = BufferConfig(
            time_minutes=DEFAULT_BUFFER_TIME_MINUTES,
            value_delta=DEFAULT_BUFFER_VALUE_DELTA,
            enabled=True
        )
    
    def should_suppress_change(self, entity_id: str, target_value: float, 
                              slot_config: Dict[str, Any]) -> bool:
        """Determine if a scheduled change should be suppressed due to buffering."""
        entity_state = self._entity_states.get(entity_id)
        if not entity_state:
            # No state tracked yet, don't suppress
            return False
        
        buffer_config = self.get_buffer_config(slot_config)
        if not buffer_config.enabled:
            return False
        
        current_value = entity_state.current_value
        
        # Check if current value is within tolerance of target
        if abs(current_value - target_value) <= buffer_config.value_delta:
            _LOGGER.debug("Suppressing change for %s: current %.1f within tolerance of target %.1f", 
                         entity_id, current_value, target_value)
            return True
        
        # Check if there was a recent manual change
        if entity_state.last_manual_change:
            time_since_manual = datetime.now() - entity_state.last_manual_change
            buffer_time = timedelta(minutes=buffer_config.time_minutes)
            
            if time_since_manual < buffer_time:
                # Check if current value is close to the manual value
                # (This assumes the manual value is the current value, which is reasonable)
                if abs(current_value - target_value) <= buffer_config.value_delta:
                    _LOGGER.debug("Suppressing change for %s: manual change %s ago, within buffer time", 
                                 entity_id, time_since_manual)
                    return True
        
        return False
    
    def update_manual_change(self, entity_id: str, value: float) -> None:
        """Record a manual change for an entity."""
        now = datetime.now()
        
        if entity_id in self._entity_states:
            entity_state = self._entity_states[entity_id]
            entity_state.current_value = value
            entity_state.last_manual_change = now
        else:
            # Create new entity state
            entity_state = EntityState(
                entity_id=entity_id,
                current_value=value,
                last_manual_change=now,
                last_scheduled_change=None,
                buffer_config=self._global_buffer
            )
            self._entity_states[entity_id] = entity_state
        
        _LOGGER.debug("Recorded manual change for %s: value=%.1f at %s", 
                     entity_id, value, now)
    
    def update_scheduled_change(self, entity_id: str, value: float) -> None:
        """Record a scheduled change for an entity."""
        now = datetime.now()
        
        if entity_id in self._entity_states:
            entity_state = self._entity_states[entity_id]
            entity_state.current_value = value
            entity_state.last_scheduled_change = now
        else:
            # Create new entity state
            entity_state = EntityState(
                entity_id=entity_id,
                current_value=value,
                last_manual_change=None,
                last_scheduled_change=now,
                buffer_config=self._global_buffer
            )
            self._entity_states[entity_id] = entity_state
        
        _LOGGER.debug("Recorded scheduled change for %s: value=%.1f at %s", 
                     entity_id, value, now)
    
    def get_buffer_config(self, slot_config: Dict[str, Any]) -> BufferConfig:
        """Get the effective buffer configuration for a slot."""
        # Check for slot-specific override
        buffer_override = slot_config.get("buffer_override")
        if buffer_override:
            return BufferConfig.from_dict(buffer_override)
        
        # Use global buffer configuration
        return self._global_buffer
    
    def update_global_buffer(self, buffer_config: BufferConfig) -> None:
        """Update the global buffer configuration."""
        self._global_buffer = buffer_config
        _LOGGER.debug("Updated global buffer config: time=%d min, delta=%.1f", 
                     buffer_config.time_minutes, buffer_config.value_delta)
    
    def get_entity_state(self, entity_id: str) -> EntityState | None:
        """Get the current state for an entity."""
        return self._entity_states.get(entity_id)
    
    def update_current_value(self, entity_id: str, value: float) -> None:
        """Update the current value for an entity without marking as manual change."""
        if entity_id in self._entity_states:
            self._entity_states[entity_id].current_value = value
        else:
            # Create new entity state
            entity_state = EntityState(
                entity_id=entity_id,
                current_value=value,
                last_manual_change=None,
                last_scheduled_change=None,
                buffer_config=self._global_buffer
            )
            self._entity_states[entity_id] = entity_state