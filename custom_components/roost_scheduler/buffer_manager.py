"""Buffer management for the Roost Scheduler integration."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from homeassistant.core import HomeAssistant

from .models import BufferConfig, EntityState, GlobalBufferConfig
from .const import DEFAULT_BUFFER_TIME_MINUTES, DEFAULT_BUFFER_VALUE_DELTA

_LOGGER = logging.getLogger(__name__)

# Debug logging flags
DEBUG_BUFFER_LOGIC = False
DEBUG_MANUAL_CHANGES = False

# Performance monitoring
PERFORMANCE_MONITORING = False


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
        """Load buffer configuration from storage with automatic migration."""
        start_time = time.time()
        _LOGGER.debug("Loading buffer configuration from storage...")
        
        if not self.storage_service:
            _LOGGER.debug("No storage service available, using default configuration")
            await self._initialize_default_configuration()
            return
        
        try:
            await self._detect_and_migrate_configuration()
            duration = time.time() - start_time
            
            _LOGGER.info("Buffer configuration loaded successfully in %.3fs", duration)
            self.log_performance_metric("load_configuration", duration)
            
            # Log configuration details
            _LOGGER.debug("Loaded buffer configuration: global_enabled=%s, time=%dm, delta=%.1f, entity_overrides=%d", 
                         self._global_buffer_config.enabled, 
                         self._global_buffer_config.time_minutes,
                         self._global_buffer_config.value_delta,
                         len(self._global_buffer_config.entity_overrides))
            
        except Exception as e:
            duration = time.time() - start_time
            _LOGGER.error("Failed to load buffer configuration after %.3fs: %s", duration, e, exc_info=True)
            await self._initialize_default_configuration()
    
    async def save_configuration(self) -> None:
        """Save buffer configuration to storage."""
        start_time = time.time()
        _LOGGER.debug("Saving buffer configuration to storage...")
        
        if not self.storage_service:
            _LOGGER.warning("No storage service available, cannot save configuration")
            return
        
        try:
            load_start = time.time()
            schedule_data = await self.storage_service.load_schedules()
            load_duration = time.time() - load_start
            
            if not schedule_data:
                _LOGGER.error("No schedule data available, cannot save buffer configuration")
                return
            
            _LOGGER.debug("Updating schedule data with buffer configuration: global_enabled=%s, entity_overrides=%d", 
                         self._global_buffer_config.enabled, len(self._global_buffer_config.entity_overrides))
            
            schedule_data.buffer_config = self._global_buffer_config
            
            save_start = time.time()
            await self.storage_service.save_schedules(schedule_data)
            save_duration = time.time() - save_start
            
            total_duration = time.time() - start_time
            _LOGGER.info("Buffer configuration saved successfully in %.3fs (load: %.3fs, save: %.3fs)", 
                        total_duration, load_duration, save_duration)
            self.log_performance_metric("save_configuration", total_duration, 
                                      load_time=load_duration, save_time=save_duration)
            
        except Exception as e:
            duration = time.time() - start_time
            _LOGGER.error("Failed to save buffer configuration after %.3fs: %s", duration, e, exc_info=True)
    
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
    
    def get_diagnostic_info(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic information for troubleshooting."""
        diagnostic_info = {
            "manager_status": {
                "storage_available": self.storage_service is not None,
                "entities_tracked": len(self._entity_states),
                "global_buffer_enabled": self._global_buffer_config.enabled,
                "entity_overrides_count": len(self._global_buffer_config.entity_overrides)
            },
            "configuration": self.get_configuration_summary(),
            "entity_states": {},
            "buffer_decisions": {},
            "validation_results": {},
            "performance_metrics": {},
            "troubleshooting": {
                "common_issues": [],
                "recommendations": []
            }
        }
        
        # Get detailed entity states
        for entity_id, entity_state in self._entity_states.items():
            ha_state = self.hass.states.get(entity_id)
            diagnostic_info["entity_states"][entity_id] = {
                "current_value": entity_state.current_value,
                "last_manual_change": entity_state.last_manual_change.isoformat() if entity_state.last_manual_change else None,
                "last_scheduled_change": entity_state.last_scheduled_change.isoformat() if entity_state.last_scheduled_change else None,
                "buffer_config": entity_state.buffer_config.to_dict() if entity_state.buffer_config else None,
                "ha_state": ha_state.state if ha_state else "not_found",
                "ha_domain": ha_state.domain if ha_state else None,
                "ha_last_updated": ha_state.last_updated.isoformat() if ha_state and ha_state.last_updated else None
            }
        
        # Test buffer decisions for tracked entities
        for entity_id in self._entity_states.keys():
            try:
                # Test with a hypothetical target value
                current_state = self._entity_states[entity_id]
                test_target = current_state.current_value + 5.0  # Test with +5 degree change
                
                # Test with default slot config
                should_suppress = self.should_suppress_change(entity_id, test_target, {})
                
                diagnostic_info["buffer_decisions"][entity_id] = {
                    "test_target": test_target,
                    "would_suppress": should_suppress,
                    "current_value": current_state.current_value,
                    "time_since_manual": str(self.get_time_since_last_manual_change(entity_id)) if self.get_time_since_last_manual_change(entity_id) else None,
                    "is_recent_manual": self.is_recent_manual_change(entity_id)
                }
            except Exception as e:
                diagnostic_info["buffer_decisions"][entity_id] = {
                    "error": str(e)
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
        if not diagnostic_info["manager_status"]["storage_available"]:
            issues.append("Storage service is not available")
            recommendations.append("Check Home Assistant storage permissions and disk space")
        
        if not diagnostic_info["manager_status"]["global_buffer_enabled"]:
            issues.append("Global buffer is disabled")
            recommendations.append("Enable buffer if you want to prevent conflicts with manual changes")
        
        # Check entity states
        missing_entities = []
        stale_entities = []
        for entity_id, entity_info in diagnostic_info["entity_states"].items():
            if entity_info.get("ha_state") == "not_found":
                missing_entities.append(entity_id)
            elif entity_info.get("ha_last_updated"):
                try:
                    last_updated = datetime.fromisoformat(entity_info["ha_last_updated"].replace('Z', '+00:00'))
                    if datetime.now().replace(tzinfo=last_updated.tzinfo) - last_updated > timedelta(hours=24):
                        stale_entities.append(entity_id)
                except Exception:
                    pass
        
        if missing_entities:
            issues.append(f"Tracked entities not found in Home Assistant: {', '.join(missing_entities)}")
            recommendations.append("Remove non-existent entities from tracking or ensure they are properly configured")
        
        if stale_entities:
            issues.append(f"Stale tracked entities (not updated in 24h): {', '.join(stale_entities)}")
            recommendations.append("Check if these entities are working properly")
        
        # Check buffer configuration
        global_config = diagnostic_info["configuration"]["global_config"]
        if global_config.get("time_minutes", 0) == 0 and global_config.get("enabled", False):
            issues.append("Buffer time is 0 minutes but buffering is enabled")
            recommendations.append("Set a reasonable buffer time (e.g., 15 minutes) or disable buffering")
        
        if global_config.get("value_delta", 0) == 0 and global_config.get("enabled", False):
            issues.append("Buffer value delta is 0 but buffering is enabled")
            recommendations.append("Set a reasonable value delta (e.g., 2.0 degrees) or disable buffering")
        
        # Check validation errors
        if not diagnostic_info["validation_results"]["is_valid"]:
            issues.extend(diagnostic_info["validation_results"]["errors"])
            recommendations.append("Fix configuration validation errors listed above")
        
        # Check for entities with no recent activity
        inactive_entities = []
        for entity_id, entity_info in diagnostic_info["entity_states"].items():
            if not entity_info.get("last_manual_change") and not entity_info.get("last_scheduled_change"):
                inactive_entities.append(entity_id)
        
        if inactive_entities:
            issues.append(f"Entities with no recorded activity: {', '.join(inactive_entities)}")
            recommendations.append("These entities may not be properly integrated with the scheduler")
        
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
        
        _LOGGER.info("PERF: BufferManager.%s completed in %.3fs%s", operation, duration_seconds, extra_info)
    
    async def run_diagnostics(self) -> Dict[str, Any]:
        """Run comprehensive diagnostics and return results."""
        _LOGGER.info("Running BufferManager diagnostics...")
        
        start_time = time.time()
        diagnostic_info = self.get_diagnostic_info()
        
        # Test buffer decision performance
        if self._entity_states:
            try:
                test_entity = next(iter(self._entity_states.keys()))
                test_start = time.time()
                
                # Test multiple buffer decisions
                for i in range(10):
                    self.should_suppress_change(test_entity, 20.0 + i, {})
                
                test_duration = time.time() - test_start
                
                diagnostic_info["performance_metrics"]["buffer_decisions"] = {
                    "duration_per_decision": test_duration / 10,
                    "total_test_duration": test_duration,
                    "test_entity": test_entity,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                diagnostic_info["performance_metrics"]["buffer_decisions"] = {
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
        
        _LOGGER.info("BufferManager diagnostics completed in %.3fs", total_duration)
        
        return diagnostic_info
    
    def validate_configuration(self) -> tuple[bool, List[str]]:
        """
        Validate current buffer configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        try:
            # Validate global buffer configuration
            try:
                self._global_buffer_config.validate()
            except ValueError as e:
                errors.append(f"Global buffer configuration error: {e}")
            
            # Validate legacy global buffer for compatibility
            try:
                self._global_buffer.validate()
            except ValueError as e:
                errors.append(f"Legacy global buffer configuration error: {e}")
            
            # Validate entity-specific overrides
            for entity_id, config in self._global_buffer_config.entity_overrides.items():
                # Check entity_id format
                if not isinstance(entity_id, str) or '.' not in entity_id:
                    errors.append(f"Invalid entity_id in buffer overrides: {entity_id}")
                    continue
                
                # Check if entity exists in Home Assistant
                state = self.hass.states.get(entity_id)
                if not state:
                    errors.append(f"Buffer override entity not found in Home Assistant: {entity_id}")
                else:
                    # Check if entity domain is suitable for buffering
                    domain = entity_id.split('.')[0]
                    suitable_domains = {'climate', 'input_number', 'number', 'fan', 'light'}
                    if domain not in suitable_domains:
                        errors.append(f"Entity {entity_id} has domain '{domain}' which may not be suitable for buffering. Suitable domains: {suitable_domains}")
                
                # Validate the buffer config itself
                try:
                    config.validate()
                except ValueError as e:
                    errors.append(f"Buffer override for {entity_id} is invalid: {e}")
            
            # Validate entity states
            for entity_id, entity_state in self._entity_states.items():
                try:
                    entity_state.validate()
                except ValueError as e:
                    errors.append(f"Entity state for {entity_id} is invalid: {e}")
                
                # Check if tracked entity still exists
                state = self.hass.states.get(entity_id)
                if not state:
                    errors.append(f"Tracked entity no longer exists in Home Assistant: {entity_id}")
            
            # Check for reasonable buffer values
            if self._global_buffer_config.time_minutes == 0 and self._global_buffer_config.enabled:
                errors.append("Buffer time is 0 minutes but buffering is enabled - this may cause unexpected behavior")
            
            if self._global_buffer_config.value_delta == 0 and self._global_buffer_config.enabled:
                errors.append("Buffer value delta is 0 but buffering is enabled - this may prevent all changes")
            
            # Check for consistency between global and legacy configs
            legacy_config = self._global_buffer_config.get_effective_config("")
            if (self._global_buffer.time_minutes != legacy_config.time_minutes or
                self._global_buffer.value_delta != legacy_config.value_delta or
                self._global_buffer.enabled != legacy_config.enabled):
                errors.append("Inconsistency detected between global and legacy buffer configurations")
            
        except Exception as e:
            errors.append(f"Unexpected error during validation: {e}")
        
        return len(errors) == 0, errors
    
    def repair_configuration(self) -> tuple[bool, List[str]]:
        """
        Attempt to repair common buffer configuration issues.
        
        Returns:
            Tuple of (was_repaired, list_of_repairs_made)
        """
        repairs = []
        
        try:
            # Fix global buffer configuration values
            if self._global_buffer_config.time_minutes < 0:
                old_value = self._global_buffer_config.time_minutes
                self._global_buffer_config.time_minutes = 15
                repairs.append(f"Fixed negative buffer time from {old_value} to 15 minutes")
            elif self._global_buffer_config.time_minutes > 1440:
                old_value = self._global_buffer_config.time_minutes
                self._global_buffer_config.time_minutes = 1440
                repairs.append(f"Fixed excessive buffer time from {old_value} to 1440 minutes (24 hours)")
            
            if self._global_buffer_config.value_delta < 0:
                old_value = self._global_buffer_config.value_delta
                self._global_buffer_config.value_delta = 2.0
                repairs.append(f"Fixed negative buffer delta from {old_value} to 2.0")
            elif self._global_buffer_config.value_delta > 50:
                old_value = self._global_buffer_config.value_delta
                self._global_buffer_config.value_delta = 50.0
                repairs.append(f"Fixed excessive buffer delta from {old_value} to 50.0")
            
            if not isinstance(self._global_buffer_config.enabled, bool):
                old_value = self._global_buffer_config.enabled
                self._global_buffer_config.enabled = True
                repairs.append(f"Fixed invalid buffer enabled value from {old_value} to True")
            
            if not isinstance(self._global_buffer_config.apply_to, str) or not self._global_buffer_config.apply_to:
                old_value = self._global_buffer_config.apply_to
                self._global_buffer_config.apply_to = "climate"
                repairs.append(f"Fixed invalid apply_to value from '{old_value}' to 'climate'")
            
            # Remove invalid entity overrides
            invalid_entities = []
            for entity_id, config in self._global_buffer_config.entity_overrides.items():
                if not isinstance(entity_id, str) or '.' not in entity_id:
                    invalid_entities.append(entity_id)
                    continue
                
                # Check if entity still exists
                state = self.hass.states.get(entity_id)
                if not state:
                    invalid_entities.append(entity_id)
                    continue
                
                # Try to fix the config if it's invalid
                try:
                    config.validate()
                except ValueError:
                    try:
                        # Attempt to repair the config
                        if config.time_minutes < 0:
                            config.time_minutes = 15
                        elif config.time_minutes > 1440:
                            config.time_minutes = 1440
                        
                        if config.value_delta < 0:
                            config.value_delta = 2.0
                        elif config.value_delta > 50:
                            config.value_delta = 50.0
                        
                        if not isinstance(config.enabled, bool):
                            config.enabled = True
                        
                        if not isinstance(config.apply_to, str) or not config.apply_to:
                            config.apply_to = "climate"
                        
                        config.validate()  # Validate again
                        repairs.append(f"Repaired buffer override configuration for {entity_id}")
                    except ValueError:
                        invalid_entities.append(entity_id)
            
            # Remove invalid entity overrides
            for entity_id in invalid_entities:
                self._global_buffer_config.entity_overrides.pop(entity_id, None)
                repairs.append(f"Removed invalid buffer override for entity: {entity_id}")
            
            # Remove invalid entity states
            invalid_states = []
            for entity_id, entity_state in self._entity_states.items():
                if not isinstance(entity_id, str) or '.' not in entity_id:
                    invalid_states.append(entity_id)
                    continue
                
                # Check if entity still exists
                state = self.hass.states.get(entity_id)
                if not state:
                    invalid_states.append(entity_id)
                    continue
                
                # Try to fix entity state
                try:
                    if not isinstance(entity_state.current_value, (int, float)):
                        entity_state.current_value = 0.0
                        repairs.append(f"Fixed invalid current_value for {entity_id}")
                    
                    entity_state.validate()
                except ValueError:
                    invalid_states.append(entity_id)
            
            # Remove invalid entity states
            for entity_id in invalid_states:
                self._entity_states.pop(entity_id, None)
                repairs.append(f"Removed invalid entity state for: {entity_id}")
            
            # Sync legacy buffer config with global config
            legacy_config = self._global_buffer_config.get_effective_config("")
            if (self._global_buffer.time_minutes != legacy_config.time_minutes or
                self._global_buffer.value_delta != legacy_config.value_delta or
                self._global_buffer.enabled != legacy_config.enabled):
                self._global_buffer = legacy_config
                repairs.append("Synchronized legacy buffer config with global config")
            
        except Exception as e:
            repairs.append(f"Error during configuration repair: {e}")
        
        return len(repairs) > 0, repairs
    
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
    
    async def _migrate_from_legacy_buffer_config(self, schedule_data) -> None:
        """Migrate configuration from legacy buffer fields in ScheduleData."""
        try:
            _LOGGER.info("Migrating buffer configuration from legacy fields")
            
            # Extract legacy buffer configuration
            legacy_buffer_obj = schedule_data.buffer.get('global') if schedule_data.buffer else None
            if legacy_buffer_obj and hasattr(legacy_buffer_obj, 'to_dict'):
                # It's a BufferConfig object, convert to dict
                legacy_buffer = legacy_buffer_obj.to_dict()
            elif isinstance(legacy_buffer_obj, dict):
                # It's already a dict
                legacy_buffer = legacy_buffer_obj
            else:
                # No valid buffer config found
                legacy_buffer = {}
            
            # Create GlobalBufferConfig from legacy fields
            self._global_buffer_config = GlobalBufferConfig(
                time_minutes=legacy_buffer.get('time_minutes', DEFAULT_BUFFER_TIME_MINUTES),
                value_delta=legacy_buffer.get('value_delta', DEFAULT_BUFFER_VALUE_DELTA),
                enabled=legacy_buffer.get('enabled', True),
                apply_to=legacy_buffer.get('apply_to', 'climate'),
                entity_overrides={}  # Legacy format didn't support entity overrides
            )
            
            # Update legacy _global_buffer for compatibility
            self._global_buffer = self._global_buffer_config.get_effective_config("")
            
            # Save the migrated configuration
            await self.save_configuration()
            
            _LOGGER.info("Successfully migrated buffer configuration from legacy fields")
        except Exception as e:
            _LOGGER.error("Failed to migrate buffer configuration from legacy fields: %s", e)
            await self._initialize_default_configuration()
    
    async def _migrate_from_config_entry(self, config_entry_data: dict) -> None:
        """Migrate configuration from config entry data."""
        try:
            _LOGGER.info("Migrating buffer configuration from config entry data")
            
            # Extract buffer configuration from config entry
            buffer_time = config_entry_data.get('buffer_time_minutes', DEFAULT_BUFFER_TIME_MINUTES)
            buffer_delta = config_entry_data.get('buffer_value_delta', DEFAULT_BUFFER_VALUE_DELTA)
            buffer_enabled = config_entry_data.get('buffer_enabled', True)
            
            # Create GlobalBufferConfig from config entry data
            self._global_buffer_config = GlobalBufferConfig(
                time_minutes=buffer_time,
                value_delta=buffer_delta,
                enabled=buffer_enabled,
                apply_to='climate',
                entity_overrides={}
            )
            
            # Update legacy _global_buffer for compatibility
            self._global_buffer = self._global_buffer_config.get_effective_config("")
            
            # Save the migrated configuration
            await self.save_configuration()
            
            _LOGGER.info("Successfully migrated buffer configuration from config entry")
        except Exception as e:
            _LOGGER.error("Failed to migrate buffer configuration from config entry: %s", e)
            await self._initialize_default_configuration()
    
    async def _detect_and_migrate_configuration(self) -> None:
        """Detect configuration version and migrate if needed."""
        try:
            # First try to load from storage
            schedule_data = await self.storage_service.load_schedules()
            
            if schedule_data and schedule_data.buffer_config:
                # Modern configuration exists, use it
                self._global_buffer_config = schedule_data.buffer_config
                # Update legacy _global_buffer for compatibility
                self._global_buffer = self._global_buffer_config.get_effective_config("")
                _LOGGER.debug("Loaded modern buffer configuration from storage")
                return
            
            # Check for legacy buffer fields in schedule data
            if schedule_data and schedule_data.buffer:
                await self._migrate_from_legacy_buffer_config(schedule_data)
                return
            
            # Try to migrate from config entry data
            if hasattr(self.storage_service, 'get_config_entry_data'):
                try:
                    config_entry_data = self.storage_service.get_config_entry_data()
                    if config_entry_data and ('buffer_time_minutes' in config_entry_data or 'buffer_value_delta' in config_entry_data):
                        await self._migrate_from_config_entry(config_entry_data)
                        return
                except Exception as e:
                    _LOGGER.debug("Could not access config entry data: %s", e)
            
            # No configuration found, initialize defaults
            await self._initialize_default_configuration()
            
        except Exception as e:
            _LOGGER.error("Error during buffer configuration detection and migration: %s", e)
            await self._initialize_default_configuration()