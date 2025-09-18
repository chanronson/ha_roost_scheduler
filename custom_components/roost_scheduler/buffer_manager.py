"""Buffer management for the Roost Scheduler integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from homeassistant.core import HomeAssistant

from .models import BufferConfig, EntityState, GlobalBufferConfig
from .const import DEFAULT_BUFFER_TIME_MINUTES, DEFAULT_BUFFER_VALUE_DELTA

_LOGGER = logging.getLogger(__name__)

# Debug logging flags
DEBUG_BUFFER_LOGIC = False
DEBUG_MANUAL_CHANGES = False


class BufferManager:
    """Manages intelligent buffering to avoid conflicts with manual changes."""
    
    def __init__(self, hass: HomeAssistant, storage_service=None) -> None:
        """Initialize the buffer manager with storage integration."""
        self.hass = hass
        self.storage_service = storage_service
        self._entity_states: Dict[str, EntityState] = {}
        self._global_buffer_config = GlobalBufferConfig(
            time_minutes=DEFAULT_BUFFER_TIME_MINUTES,
            value_delta=DEFAULT_BUFFER_VALUE_DELTA,
            enabled=True,
            apply_to="climate"
        )
        # Legacy compatibility - keep _global_buffer for existing code
        self._global_buffer = BufferConfig(
            time_minutes=DEFAULT_BUFFER_TIME_MINUTES,
            value_delta=DEFAULT_BUFFER_VALUE_DELTA,
            enabled=True,
            apply_to="climate"
        )
    
    def should_suppress_change(self, entity_id: str, target_value: float, 
                              slot_config: Dict[str, Any], force_apply: bool = False) -> bool:
        """
        Determine if a scheduled change should be suppressed due to buffering.
        
        Implements requirements 2.1, 2.2, 2.3, 2.5:
        - 2.1: Check if current value is within tolerance and skip if satisfied
        - 2.2: Check manual change within buffer time and suppress if within tolerance  
        - 2.3: Apply scheduled target when buffer conditions not met
        - 2.5: Force-apply bypass mechanism
        
        Args:
            entity_id: The entity to check
            target_value: The target value to apply
            slot_config: Configuration for the current slot (may contain buffer overrides)
            force_apply: If True, bypass all buffer logic (Requirement 2.5)
        """
        if DEBUG_BUFFER_LOGIC:
            _LOGGER.debug("Evaluating buffer suppression for %s (target: %.1f, force: %s)", 
                         entity_id, target_value, force_apply)
        
        # Requirement 2.5: Force-apply bypass mechanism
        if force_apply:
            if DEBUG_BUFFER_LOGIC:
                _LOGGER.debug("Force apply enabled for %s, bypassing all buffer logic", entity_id)
            return False
        
        entity_state = self._entity_states.get(entity_id)
        if not entity_state:
            # No state tracked yet, don't suppress (Requirement 2.3)
            if DEBUG_BUFFER_LOGIC:
                _LOGGER.debug("No entity state for %s, allowing change to %.1f", entity_id, target_value)
            return False
        
        buffer_config = self.get_buffer_config(slot_config, entity_id)
        if not buffer_config.enabled:
            if DEBUG_BUFFER_LOGIC:
                _LOGGER.debug("Buffer disabled for %s, allowing change to %.1f", entity_id, target_value)
            return False
        
        current_value = entity_state.current_value
        
        if DEBUG_BUFFER_LOGIC:
            _LOGGER.debug("Buffer evaluation for %s: current=%.1f, target=%.1f, tolerance=%.1f, time_buffer=%dm", 
                         entity_id, current_value, target_value, buffer_config.value_delta, buffer_config.time_minutes)
        
        # Requirement 2.1: Check if current value is within tolerance of target
        tolerance_delta = abs(current_value - target_value)
        if tolerance_delta <= buffer_config.value_delta:
            if DEBUG_BUFFER_LOGIC:
                _LOGGER.debug("Suppressing change for %s: current %.1f within tolerance %.1f of target %.1f (delta: %.1f)", 
                             entity_id, current_value, buffer_config.value_delta, target_value, tolerance_delta)
            return True
        
        # Requirement 2.2: Check if there was a recent manual change within buffer time
        if entity_state.last_manual_change:
            now = datetime.now()
            time_since_manual = now - entity_state.last_manual_change
            buffer_time = timedelta(minutes=buffer_config.time_minutes)
            
            if time_since_manual < buffer_time:
                # Manual change was recent, check if current value is within tolerance
                # This prevents "tug-of-war" between manual adjustments and schedule
                if tolerance_delta <= buffer_config.value_delta:
                    _LOGGER.debug(
                        "Suppressing change for %s: manual change %s ago (< %s buffer), "
                        "current %.1f within tolerance %.1f of target %.1f", 
                        entity_id, time_since_manual, buffer_time, 
                        current_value, buffer_config.value_delta, target_value
                    )
                    return True
                else:
                    _LOGGER.debug(
                        "Manual change %s ago for %s, but current %.1f not within tolerance %.1f of target %.1f, allowing change", 
                        time_since_manual, entity_id, current_value, buffer_config.value_delta, target_value
                    )
        
        # Requirement 2.3: Buffer conditions not met, allow scheduled change
        _LOGGER.debug(
            "Allowing scheduled change for %s: current %.1f -> target %.1f (delta: %.1f > tolerance: %.1f)", 
            entity_id, current_value, target_value, tolerance_delta, buffer_config.value_delta
        )
        return False
    
    def update_manual_change(self, entity_id: str, value: float) -> None:
        """
        Record a manual change for an entity with timestamp tracking.
        
        This is called when a user manually adjusts an entity outside of the scheduler,
        enabling the buffer system to avoid conflicts with manual adjustments.
        """
        if not isinstance(value, (int, float)):
            _LOGGER.warning("Invalid value type for manual change on %s: %s", entity_id, type(value))
            return
            
        now = datetime.now()
        
        if entity_id in self._entity_states:
            entity_state = self._entity_states[entity_id]
            old_value = entity_state.current_value
            entity_state.current_value = value
            entity_state.last_manual_change = now
            
            _LOGGER.debug(
                "Updated manual change for %s: %.1f -> %.1f at %s", 
                entity_id, old_value, value, now.strftime("%H:%M:%S")
            )
        else:
            # Create new entity state
            entity_state = EntityState(
                entity_id=entity_id,
                current_value=value,
                last_manual_change=now,
                last_scheduled_change=None,
                buffer_config=self._global_buffer_config.get_effective_config(entity_id)
            )
            self._entity_states[entity_id] = entity_state
            
            _LOGGER.debug(
                "Recorded new manual change for %s: value=%.1f at %s", 
                entity_id, value, now.strftime("%H:%M:%S")
            )
    
    def update_scheduled_change(self, entity_id: str, value: float) -> None:
        """
        Record a scheduled change for an entity with timestamp tracking.
        
        This is called when the scheduler applies a scheduled value to an entity,
        allowing the buffer system to track the difference between manual and scheduled changes.
        """
        if not isinstance(value, (int, float)):
            _LOGGER.warning("Invalid value type for scheduled change on %s: %s", entity_id, type(value))
            return
            
        now = datetime.now()
        
        if entity_id in self._entity_states:
            entity_state = self._entity_states[entity_id]
            old_value = entity_state.current_value
            entity_state.current_value = value
            entity_state.last_scheduled_change = now
            
            _LOGGER.debug(
                "Updated scheduled change for %s: %.1f -> %.1f at %s", 
                entity_id, old_value, value, now.strftime("%H:%M:%S")
            )
        else:
            # Create new entity state
            entity_state = EntityState(
                entity_id=entity_id,
                current_value=value,
                last_manual_change=None,
                last_scheduled_change=now,
                buffer_config=self._global_buffer_config.get_effective_config(entity_id)
            )
            self._entity_states[entity_id] = entity_state
            
            _LOGGER.debug(
                "Recorded new scheduled change for %s: value=%.1f at %s", 
                entity_id, value, now.strftime("%H:%M:%S")
            )
    
    def get_buffer_config(self, slot_config: Dict[str, Any], entity_id: str = None) -> BufferConfig:
        """
        Get the effective buffer configuration for a slot.
        
        Implements requirement 2.4: per-slot buffer overrides take precedence over entity-specific and global settings.
        Priority order: slot override > entity-specific > global
        """
        # Check for slot-specific override (Requirement 2.4) - highest priority
        buffer_override = slot_config.get("buffer_override")
        if buffer_override:
            try:
                if isinstance(buffer_override, BufferConfig):
                    # Already a BufferConfig object
                    override_config = buffer_override
                else:
                    # Convert from dictionary
                    override_config = BufferConfig.from_dict(buffer_override)
                
                _LOGGER.debug(
                    "Using slot-specific buffer override: time=%d min, delta=%.1f, enabled=%s",
                    override_config.time_minutes, override_config.value_delta, override_config.enabled
                )
                return override_config
                
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Invalid buffer override configuration in slot: %s. Using entity/global buffer config.", 
                    str(e)
                )
                # Fall through to entity/global configuration
        
        # Use entity-specific or global buffer configuration
        if entity_id:
            config = self._global_buffer_config.get_effective_config(entity_id)
            _LOGGER.debug(
                "Using %s buffer config for %s: time=%d min, delta=%.1f, enabled=%s",
                "entity-specific" if entity_id in self._global_buffer_config.entity_overrides else "global",
                entity_id, config.time_minutes, config.value_delta, config.enabled
            )
            return config
        else:
            # Fallback to legacy global buffer for compatibility
            _LOGGER.debug(
                "Using global buffer config: time=%d min, delta=%.1f, enabled=%s",
                self._global_buffer.time_minutes, self._global_buffer.value_delta, self._global_buffer.enabled
            )
            return self._global_buffer
    
    def update_global_buffer(self, buffer_config: BufferConfig) -> None:
        """Update the global buffer configuration (legacy method for compatibility)."""
        self._global_buffer = buffer_config
        # Also update the new global buffer config for consistency
        self._global_buffer_config.time_minutes = buffer_config.time_minutes
        self._global_buffer_config.value_delta = buffer_config.value_delta
        self._global_buffer_config.enabled = buffer_config.enabled
        if hasattr(buffer_config, 'apply_to'):
            self._global_buffer_config.apply_to = buffer_config.apply_to
        _LOGGER.debug("Updated global buffer config: time=%d min, delta=%.1f", 
                     buffer_config.time_minutes, buffer_config.value_delta)
    
    def get_entity_state(self, entity_id: str) -> EntityState | None:
        """Get the current state for an entity."""
        return self._entity_states.get(entity_id)
    
    def update_current_value(self, entity_id: str, value: float) -> None:
        """Update the current value for an entity without marking as manual change."""
        if not isinstance(value, (int, float)):
            _LOGGER.warning("Invalid value type for current value update on %s: %s", entity_id, type(value))
            return
            
        if entity_id in self._entity_states:
            self._entity_states[entity_id].current_value = value
        else:
            # Create new entity state
            entity_state = EntityState(
                entity_id=entity_id,
                current_value=value,
                last_manual_change=None,
                last_scheduled_change=None,
                buffer_config=self._global_buffer_config.get_effective_config(entity_id)
            )
            self._entity_states[entity_id] = entity_state
    
    def is_recent_manual_change(self, entity_id: str, threshold_minutes: int = None) -> bool:
        """
        Check if there was a recent manual change for an entity.
        
        Args:
            entity_id: The entity to check
            threshold_minutes: Custom threshold in minutes, uses buffer time if None
            
        Returns:
            True if there was a manual change within the threshold time
        """
        entity_state = self._entity_states.get(entity_id)
        if not entity_state or not entity_state.last_manual_change:
            return False
        
        if threshold_minutes is None:
            threshold_minutes = entity_state.buffer_config.time_minutes
        
        time_since_manual = datetime.now() - entity_state.last_manual_change
        threshold = timedelta(minutes=threshold_minutes)
        
        return time_since_manual < threshold
    
    def get_time_since_last_manual_change(self, entity_id: str) -> timedelta | None:
        """
        Get the time elapsed since the last manual change for an entity.
        
        Returns:
            timedelta since last manual change, or None if no manual change recorded
        """
        entity_state = self._entity_states.get(entity_id)
        if not entity_state or not entity_state.last_manual_change:
            return None
        
        return datetime.now() - entity_state.last_manual_change
    
    def validate_buffer_config(self, config: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate buffer configuration dictionary.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to create BufferConfig to validate
            BufferConfig.from_dict(config)
            return True, ""
        except (ValueError, TypeError) as e:
            return False, str(e)
    
    def create_default_buffer_config(self) -> BufferConfig:
        """Create a default buffer configuration."""
        return BufferConfig(
            time_minutes=DEFAULT_BUFFER_TIME_MINUTES,
            value_delta=DEFAULT_BUFFER_VALUE_DELTA,
            enabled=True,
            apply_to="climate"
        )
    
    def apply_buffer_defaults(self, config: Dict[str, Any]) -> BufferConfig:
        """
        Apply default values to incomplete buffer configuration.
        
        This ensures that partial buffer overrides work correctly by filling
        in missing values with sensible defaults.
        """
        defaults = {
            "time_minutes": DEFAULT_BUFFER_TIME_MINUTES,
            "value_delta": DEFAULT_BUFFER_VALUE_DELTA,
            "enabled": True,
            "apply_to": "climate"
        }
        
        # Merge provided config with defaults
        merged_config = {**defaults, **config}
        
        try:
            return BufferConfig.from_dict(merged_config)
        except (ValueError, TypeError) as e:
            _LOGGER.warning("Failed to create buffer config with defaults: %s", str(e))
            return self.create_default_buffer_config()
    
    async def load_configuration(self) -> None:
        """Load buffer configuration from storage."""
        if not self.storage_service:
            _LOGGER.debug("No storage service available, using default configuration")
            await self._initialize_default_configuration()
            return
        
        try:
            schedule_data = await self.storage_service.load_schedules()
            if schedule_data and schedule_data.buffer_config:
                self._global_buffer_config = schedule_data.buffer_config
                # Update legacy _global_buffer for compatibility
                self._global_buffer = self._global_buffer_config.get_effective_config("")
                _LOGGER.debug("Loaded buffer configuration from storage")
            else:
                _LOGGER.info("No stored buffer configuration found, using defaults")
                await self._initialize_default_configuration()
        except Exception as e:
            _LOGGER.error("Failed to load buffer configuration: %s", e)
            await self._initialize_default_configuration()
    
    async def save_configuration(self) -> None:
        """Save buffer configuration to storage."""
        if not self.storage_service:
            _LOGGER.warning("No storage service available, cannot save configuration")
            return
        
        try:
            schedule_data = await self.storage_service.load_schedules()
            if not schedule_data:
                _LOGGER.error("No schedule data available, cannot save buffer configuration")
                return
            
            schedule_data.buffer_config = self._global_buffer_config
            await self.storage_service.save_schedules(schedule_data)
            _LOGGER.debug("Saved buffer configuration to storage")
        except Exception as e:
            _LOGGER.error("Failed to save buffer configuration: %s", e)
    
    async def update_global_buffer_config(self, config: GlobalBufferConfig) -> None:
        """Update global buffer configuration and persist to storage."""
        try:
            config.validate()
            self._global_buffer_config = config
            # Update legacy _global_buffer for compatibility
            self._global_buffer = config.get_effective_config("")
            await self.save_configuration()
            _LOGGER.debug("Updated global buffer configuration")
        except Exception as e:
            _LOGGER.error("Failed to update global buffer configuration: %s", e)
            raise
    
    async def update_entity_buffer_config(self, entity_id: str, config: BufferConfig) -> None:
        """Update entity-specific buffer configuration and persist to storage."""
        try:
            config.validate()
            self._global_buffer_config.set_entity_override(entity_id, config)
            await self.save_configuration()
            _LOGGER.debug("Updated buffer configuration for entity %s", entity_id)
        except Exception as e:
            _LOGGER.error("Failed to update buffer configuration for entity %s: %s", entity_id, e)
            raise
    
    async def remove_entity_buffer_config(self, entity_id: str) -> bool:
        """Remove entity-specific buffer configuration and persist to storage."""
        try:
            removed = self._global_buffer_config.remove_entity_override(entity_id)
            if removed:
                await self.save_configuration()
                _LOGGER.debug("Removed buffer configuration for entity %s", entity_id)
            return removed
        except Exception as e:
            _LOGGER.error("Failed to remove buffer configuration for entity %s: %s", entity_id, e)
            return False
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get current configuration for diagnostics."""
        return {
            "global_config": self._global_buffer_config.to_dict(),
            "entity_count": len(self._entity_states),
            "entities_tracked": list(self._entity_states.keys()),
            "storage_available": self.storage_service is not None
        }
    
    def get_entity_buffer_config(self, entity_id: str) -> BufferConfig:
        """Get effective buffer configuration for a specific entity."""
        return self._global_buffer_config.get_effective_config(entity_id)
    
    async def _initialize_default_configuration(self) -> None:
        """Initialize default buffer configuration."""
        self._global_buffer_config = GlobalBufferConfig(
            time_minutes=DEFAULT_BUFFER_TIME_MINUTES,
            value_delta=DEFAULT_BUFFER_VALUE_DELTA,
            enabled=True,
            apply_to="climate"
        )
        # Update legacy _global_buffer for compatibility
        self._global_buffer = self._global_buffer_config.get_effective_config("")
        
        # Save default configuration if storage is available
        if self.storage_service:
            try:
                await self.save_configuration()
                _LOGGER.debug("Saved default buffer configuration to storage")
            except Exception as e:
                _LOGGER.warning("Failed to save default buffer configuration: %s", e)