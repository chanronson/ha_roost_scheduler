"""Configuration validation and consistency checks for Roost Scheduler managers."""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .presence_manager import PresenceManager
    from .buffer_manager import BufferManager
    from .schedule_manager import ScheduleManager

_LOGGER = logging.getLogger(__name__)


class ConfigurationValidator:
    """Cross-manager configuration validation and consistency checks."""
    
    def __init__(self, presence_manager: Optional['PresenceManager'] = None,
                 buffer_manager: Optional['BufferManager'] = None,
                 schedule_manager: Optional['ScheduleManager'] = None) -> None:
        """Initialize the configuration validator."""
        self.presence_manager = presence_manager
        self.buffer_manager = buffer_manager
        self.schedule_manager = schedule_manager
    
    def validate_all_configurations(self) -> tuple[bool, Dict[str, List[str]]]:
        """
        Validate all manager configurations and check for cross-manager consistency.
        
        Returns:
            Tuple of (all_valid, errors_by_manager)
        """
        all_errors = {}
        all_valid = True
        
        # Validate individual managers
        if self.presence_manager:
            try:
                is_valid, errors = self.presence_manager.validate_configuration()
                if not is_valid:
                    all_errors["presence_manager"] = errors
                    all_valid = False
            except Exception as e:
                all_errors["presence_manager"] = [f"Validation failed with exception: {e}"]
                all_valid = False
        
        if self.buffer_manager:
            try:
                is_valid, errors = self.buffer_manager.validate_configuration()
                if not is_valid:
                    all_errors["buffer_manager"] = errors
                    all_valid = False
            except Exception as e:
                all_errors["buffer_manager"] = [f"Validation failed with exception: {e}"]
                all_valid = False
        
        # Check cross-manager consistency
        consistency_errors = self._check_cross_manager_consistency()
        if consistency_errors:
            all_errors["cross_manager_consistency"] = consistency_errors
            all_valid = False
        
        return all_valid, all_errors
    
    def repair_all_configurations(self) -> tuple[bool, Dict[str, List[str]]]:
        """
        Attempt to repair all manager configurations and consistency issues.
        
        Returns:
            Tuple of (any_repairs_made, repairs_by_manager)
        """
        all_repairs = {}
        any_repairs = False
        
        # Repair individual managers
        if self.presence_manager:
            try:
                was_repaired, repairs = self.presence_manager.repair_configuration()
                if was_repaired:
                    all_repairs["presence_manager"] = repairs
                    any_repairs = True
            except Exception as e:
                all_repairs["presence_manager"] = [f"Repair failed with exception: {e}"]
                any_repairs = True
        
        if self.buffer_manager:
            try:
                was_repaired, repairs = self.buffer_manager.repair_configuration()
                if was_repaired:
                    all_repairs["buffer_manager"] = repairs
                    any_repairs = True
            except Exception as e:
                all_repairs["buffer_manager"] = [f"Repair failed with exception: {e}"]
                any_repairs = True
        
        # Repair cross-manager consistency issues
        consistency_repairs = self._repair_cross_manager_consistency()
        if consistency_repairs:
            all_repairs["cross_manager_consistency"] = consistency_repairs
            any_repairs = True
        
        return any_repairs, all_repairs
    
    def _check_cross_manager_consistency(self) -> List[str]:
        """Check for consistency issues between managers."""
        errors = []
        
        try:
            # Check presence and buffer manager entity consistency
            if self.presence_manager and self.buffer_manager:
                presence_entities = set(self.presence_manager._presence_entities)
                buffer_tracked_entities = set(self.buffer_manager._entity_states.keys())
                
                # Check if presence entities are being buffered unnecessarily
                presence_in_buffer = presence_entities.intersection(buffer_tracked_entities)
                if presence_in_buffer:
                    errors.append(f"Presence entities are being tracked by buffer manager (may cause conflicts): {list(presence_in_buffer)}")
                
                # Check if buffer overrides exist for non-existent entities
                buffer_override_entities = set(self.buffer_manager._global_buffer_config.entity_overrides.keys())
                if self.schedule_manager:
                    try:
                        schedule_data = self.schedule_manager.get_schedule_data()
                        if schedule_data:
                            tracked_entities = set(schedule_data.entities_tracked)
                            orphaned_overrides = buffer_override_entities - tracked_entities
                            if orphaned_overrides:
                                errors.append(f"Buffer overrides exist for entities not tracked by scheduler: {list(orphaned_overrides)}")
                    except Exception as e:
                        _LOGGER.debug("Could not check schedule data for consistency: %s", e)
            
            # Check presence configuration consistency with schedule manager
            if self.presence_manager and self.schedule_manager:
                try:
                    schedule_data = self.schedule_manager.get_schedule_data()
                    if schedule_data:
                        # Check if presence entities in schedule data match presence manager
                        schedule_presence_entities = set(schedule_data.presence_entities)
                        manager_presence_entities = set(self.presence_manager._presence_entities)
                        
                        if schedule_presence_entities != manager_presence_entities:
                            errors.append("Presence entities in schedule data don't match presence manager configuration")
                        
                        # Check presence rule consistency
                        if schedule_data.presence_rule != self.presence_manager._presence_rule:
                            errors.append(f"Presence rule mismatch: schedule='{schedule_data.presence_rule}', manager='{self.presence_manager._presence_rule}'")
                        
                        # Check timeout consistency
                        if schedule_data.presence_timeout_seconds != self.presence_manager._timeout_seconds:
                            errors.append(f"Presence timeout mismatch: schedule={schedule_data.presence_timeout_seconds}s, manager={self.presence_manager._timeout_seconds}s")
                except Exception as e:
                    _LOGGER.debug("Could not check schedule data for presence consistency: %s", e)
            
            # Check buffer configuration consistency with schedule manager
            if self.buffer_manager and self.schedule_manager:
                try:
                    schedule_data = self.schedule_manager.get_schedule_data()
                    if schedule_data and schedule_data.buffer_config:
                        # Check if buffer configs match
                        schedule_buffer = schedule_data.buffer_config
                        manager_buffer = self.buffer_manager._global_buffer_config
                        
                        if (schedule_buffer.time_minutes != manager_buffer.time_minutes or
                            schedule_buffer.value_delta != manager_buffer.value_delta or
                            schedule_buffer.enabled != manager_buffer.enabled):
                            errors.append("Buffer configuration in schedule data doesn't match buffer manager configuration")
                except Exception as e:
                    _LOGGER.debug("Could not check schedule data for buffer consistency: %s", e)
            
            # Check for conflicting entity domains
            if self.buffer_manager:
                for entity_id in self.buffer_manager._entity_states.keys():
                    domain = entity_id.split('.')[0]
                    
                    # Check if climate entities have reasonable buffer settings
                    if domain == 'climate':
                        entity_config = self.buffer_manager.get_entity_buffer_config(entity_id)
                        if entity_config.value_delta > 10:  # More than 10 degrees seems excessive
                            errors.append(f"Climate entity {entity_id} has excessive buffer delta: {entity_config.value_delta}°")
                        if entity_config.time_minutes > 120:  # More than 2 hours seems excessive
                            errors.append(f"Climate entity {entity_id} has excessive buffer time: {entity_config.time_minutes} minutes")
                    
                    # Check if input_number entities have reasonable ranges
                    elif domain in ['input_number', 'number']:
                        entity_config = self.buffer_manager.get_entity_buffer_config(entity_id)
                        if entity_config.value_delta > 100:  # Depends on the range, but 100 seems high
                            errors.append(f"Number entity {entity_id} has high buffer delta: {entity_config.value_delta}")
        
        except Exception as e:
            errors.append(f"Error during cross-manager consistency check: {e}")
        
        return errors
    
    def _repair_cross_manager_consistency(self) -> List[str]:
        """Attempt to repair cross-manager consistency issues."""
        repairs = []
        
        try:
            # Sync presence configuration between managers and schedule data
            if self.presence_manager and self.schedule_manager:
                try:
                    schedule_data = self.schedule_manager.get_schedule_data()
                    if schedule_data:
                        # Update schedule data to match presence manager (manager is authoritative)
                        if (set(schedule_data.presence_entities) != set(self.presence_manager._presence_entities) or
                            schedule_data.presence_rule != self.presence_manager._presence_rule or
                            schedule_data.presence_timeout_seconds != self.presence_manager._timeout_seconds):
                            
                            schedule_data.presence_entities = self.presence_manager._presence_entities.copy()
                            schedule_data.presence_rule = self.presence_manager._presence_rule
                            schedule_data.presence_timeout_seconds = self.presence_manager._timeout_seconds
                            
                            # Save the updated schedule data
                            self.schedule_manager.save_schedule_data(schedule_data)
                            repairs.append("Synchronized presence configuration between manager and schedule data")
                except Exception as e:
                    _LOGGER.debug("Could not repair presence configuration sync: %s", e)
            
            # Sync buffer configuration between managers and schedule data
            if self.buffer_manager and self.schedule_manager:
                try:
                    schedule_data = self.schedule_manager.get_schedule_data()
                    if schedule_data:
                        # Update schedule data to match buffer manager (manager is authoritative)
                        if not schedule_data.buffer_config or (
                            schedule_data.buffer_config.time_minutes != self.buffer_manager._global_buffer_config.time_minutes or
                            schedule_data.buffer_config.value_delta != self.buffer_manager._global_buffer_config.value_delta or
                            schedule_data.buffer_config.enabled != self.buffer_manager._global_buffer_config.enabled):
                            
                            schedule_data.buffer_config = self.buffer_manager._global_buffer_config
                            
                            # Save the updated schedule data
                            self.schedule_manager.save_schedule_data(schedule_data)
                            repairs.append("Synchronized buffer configuration between manager and schedule data")
                except Exception as e:
                    _LOGGER.debug("Could not repair buffer configuration sync: %s", e)
            
            # Remove buffer tracking for presence entities to avoid conflicts
            if self.presence_manager and self.buffer_manager:
                presence_entities = set(self.presence_manager._presence_entities)
                buffer_tracked_entities = set(self.buffer_manager._entity_states.keys())
                
                conflicts = presence_entities.intersection(buffer_tracked_entities)
                for entity_id in conflicts:
                    self.buffer_manager._entity_states.pop(entity_id, None)
                    repairs.append(f"Removed buffer tracking for presence entity: {entity_id}")
            
            # Fix excessive buffer values for climate entities
            if self.buffer_manager:
                for entity_id in list(self.buffer_manager._entity_states.keys()):
                    domain = entity_id.split('.')[0]
                    
                    if domain == 'climate':
                        entity_config = self.buffer_manager.get_entity_buffer_config(entity_id)
                        needs_repair = False
                        
                        if entity_config.value_delta > 10:
                            entity_config.value_delta = 5.0  # Reasonable for temperature
                            needs_repair = True
                        
                        if entity_config.time_minutes > 120:
                            entity_config.time_minutes = 60  # 1 hour max for climate
                            needs_repair = True
                        
                        if needs_repair:
                            if entity_id in self.buffer_manager._global_buffer_config.entity_overrides:
                                self.buffer_manager._global_buffer_config.entity_overrides[entity_id] = entity_config
                            repairs.append(f"Fixed excessive buffer values for climate entity: {entity_id}")
        
        except Exception as e:
            repairs.append(f"Error during cross-manager consistency repair: {e}")
        
        return repairs
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Get a comprehensive validation report for all managers."""
        report = {
            "timestamp": None,
            "overall_status": "unknown",
            "managers": {},
            "cross_manager_issues": [],
            "recommendations": []
        }
        
        try:
            from datetime import datetime
            report["timestamp"] = datetime.now().isoformat()
            
            # Validate all configurations
            all_valid, all_errors = self.validate_all_configurations()
            report["overall_status"] = "valid" if all_valid else "invalid"
            
            # Individual manager reports
            if self.presence_manager:
                is_valid, errors = self.presence_manager.validate_configuration()
                report["managers"]["presence"] = {
                    "status": "valid" if is_valid else "invalid",
                    "errors": errors,
                    "configuration": self.presence_manager.get_configuration_summary()
                }
            
            if self.buffer_manager:
                is_valid, errors = self.buffer_manager.validate_configuration()
                report["managers"]["buffer"] = {
                    "status": "valid" if is_valid else "invalid",
                    "errors": errors,
                    "configuration": self.buffer_manager.get_configuration_summary()
                }
            
            # Cross-manager issues
            report["cross_manager_issues"] = all_errors.get("cross_manager_consistency", [])
            
            # Generate recommendations
            recommendations = []
            if not all_valid:
                recommendations.append("Run configuration repair to fix detected issues")
            
            if self.presence_manager and not self.presence_manager._presence_entities and not self.presence_manager._custom_template:
                recommendations.append("Configure presence entities or custom template for presence detection")
            
            if self.buffer_manager and not self.buffer_manager._global_buffer_config.enabled:
                recommendations.append("Consider enabling buffer management to prevent conflicts with manual changes")
            
            report["recommendations"] = recommendations
            
        except Exception as e:
            report["error"] = f"Failed to generate validation report: {e}"
        
        return report