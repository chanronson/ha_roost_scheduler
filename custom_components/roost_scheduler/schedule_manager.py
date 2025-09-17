"""Schedule management for the Roost Scheduler integration."""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any, Dict, Optional, List

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from .models import ScheduleSlot, ScheduleData
from .storage import StorageService
from .presence_manager import PresenceManager
from .buffer_manager import BufferManager
from .const import MODE_HOME, MODE_AWAY, WEEKDAYS

_LOGGER = logging.getLogger(__name__)


class ScheduleManager:
    """Manages schedule evaluation and execution."""
    
    def __init__(self, hass: HomeAssistant, storage_service: StorageService, 
                 presence_manager: PresenceManager, buffer_manager: BufferManager) -> None:
        """Initialize the schedule manager."""
        self.hass = hass
        self.storage_service = storage_service
        self.presence_manager = presence_manager
        self.buffer_manager = buffer_manager
        self._schedule_data: Optional[ScheduleData] = None
    
    async def evaluate_current_slot(self, entity_id: str, mode: str = None) -> Optional[ScheduleSlot]:
        """
        Evaluate the current schedule slot for an entity and mode.
        
        Implements requirements 1.1, 1.2, 1.3:
        - 1.1: Evaluate schedules based on current time and presence mode
        - 1.2: Handle different time resolutions and day-based scheduling
        - 1.3: Return appropriate schedule slot for current conditions
        
        Args:
            entity_id: The entity to evaluate schedules for
            mode: The presence mode (home/away). If None, will get current mode from presence manager
            
        Returns:
            ScheduleSlot if found, None if no matching slot or no schedules
        """
        if not self._schedule_data:
            await self._load_schedule_data()
        
        if not self._schedule_data:
            _LOGGER.warning("No schedule data available for entity %s", entity_id)
            return None
        
        # Check if entity is tracked
        if entity_id not in self._schedule_data.entities_tracked:
            _LOGGER.debug("Entity %s is not tracked in schedules", entity_id)
            return None
        
        # Get current mode if not provided (Requirement 1.1)
        if mode is None:
            mode = await self.presence_manager.get_current_mode()
        
        now = datetime.now()
        current_day = WEEKDAYS[now.weekday()]
        current_time = now.time()
        
        _LOGGER.debug("Evaluating schedule for %s: day=%s, time=%s, mode=%s", 
                     entity_id, current_day, current_time.strftime("%H:%M"), mode)
        
        # Get schedules for the current mode and day (Requirement 1.2)
        mode_schedules = self._schedule_data.schedules.get(mode, {})
        day_schedules = mode_schedules.get(current_day, [])
        
        if not day_schedules:
            _LOGGER.debug("No schedules found for %s on %s in %s mode", entity_id, current_day, mode)
            return None
        
        # Find the slot that contains the current time (Requirement 1.3)
        for slot in day_schedules:
            if self._time_in_slot(current_time, slot.start_time, slot.end_time):
                _LOGGER.debug("Found matching slot for %s: %s-%s (target: %.1f)", 
                             entity_id, slot.start_time, slot.end_time, slot.target_value)
                return slot
        
        _LOGGER.debug("No matching time slot found for %s at %s", entity_id, current_time.strftime("%H:%M"))
        return None
    
    async def apply_schedule(self, entity_id: str, force: bool = False) -> bool:
        """
        Apply the current schedule for an entity with buffer manager integration.
        
        Implements requirements 1.4, 1.5:
        - 1.4: Apply schedule values to entities with proper error handling
        - 1.5: Integrate with buffer system to avoid conflicts with manual changes
        
        Args:
            entity_id: The entity to apply schedule to
            force: If True, bypass buffer logic and force application
            
        Returns:
            True if schedule was applied successfully, False otherwise
        """
        try:
            # Get current presence mode
            current_mode = await self.presence_manager.get_current_mode()
            
            # Evaluate current schedule slot
            current_slot = await self.evaluate_current_slot(entity_id, current_mode)
            
            if not current_slot:
                _LOGGER.debug("No active schedule slot for %s in %s mode", entity_id, current_mode)
                return False
            
            # Get current entity state
            entity_state = self.hass.states.get(entity_id)
            if not entity_state:
                _LOGGER.error("Entity %s not found in Home Assistant", entity_id)
                return False
            
            # Check if entity is available
            if entity_state.state in ["unavailable", "unknown"]:
                _LOGGER.warning("Entity %s is %s, skipping schedule application", 
                               entity_id, entity_state.state)
                return False
            
            target_value = current_slot.target_value
            
            # Update buffer manager with current entity value
            try:
                current_value = float(entity_state.attributes.get("temperature", entity_state.state))
                self.buffer_manager.update_current_value(entity_id, current_value)
            except (ValueError, TypeError):
                _LOGGER.warning("Could not parse current value for %s: %s", 
                               entity_id, entity_state.state)
                current_value = target_value  # Assume target is current for buffer logic
            
            # Check if change should be suppressed by buffer logic (Requirement 1.5)
            slot_config = current_slot.to_dict()
            should_suppress = self.buffer_manager.should_suppress_change(
                entity_id, target_value, slot_config, force
            )
            
            if should_suppress and not force:
                _LOGGER.debug("Schedule application suppressed by buffer logic for %s", entity_id)
                return True  # Not an error, just suppressed
            
            # Apply the schedule value (Requirement 1.4)
            success = await self._apply_entity_value(entity_id, target_value, current_slot)
            
            if success:
                # Record the scheduled change in buffer manager
                self.buffer_manager.update_scheduled_change(entity_id, target_value)
                _LOGGER.info("Applied schedule for %s: %.1f°C (slot: %s-%s, mode: %s)", 
                           entity_id, target_value, current_slot.start_time, 
                           current_slot.end_time, current_mode)
            
            return success
            
        except Exception as e:
            _LOGGER.error("Error applying schedule for %s: %s", entity_id, e)
            return False
    
    async def update_slot(self, entity_id: str, mode: str, day: str, time_slot: str, target: Dict[str, Any]) -> bool:
        """
        Update a specific schedule slot for individual schedule modifications.
        
        Implements requirement 1.4: Allow individual schedule slot modifications.
        
        Args:
            entity_id: The entity to update schedule for
            mode: The presence mode (home/away)
            day: Day of week (monday, tuesday, etc.)
            time_slot: Time slot identifier (e.g., "08:00-09:00")
            target: Target configuration including temperature and domain
            
        Returns:
            True if slot was updated successfully, False otherwise
        """
        try:
            if not self._schedule_data:
                await self._load_schedule_data()
            
            if not self._schedule_data:
                _LOGGER.error("No schedule data available for slot update")
                return False
            
            # Validate inputs
            if day.lower() not in [d.lower() for d in WEEKDAYS]:
                _LOGGER.error("Invalid day: %s", day)
                return False
            
            if entity_id not in self._schedule_data.entities_tracked:
                _LOGGER.error("Entity %s is not tracked in schedules", entity_id)
                return False
            
            # Parse time slot (format: "HH:MM-HH:MM")
            try:
                start_time, end_time = time_slot.split('-')
                start_time = start_time.strip()
                end_time = end_time.strip()
            except ValueError:
                _LOGGER.error("Invalid time slot format: %s (expected HH:MM-HH:MM)", time_slot)
                return False
            
            # Validate target configuration
            if not isinstance(target, dict):
                _LOGGER.error("Target must be a dictionary")
                return False
            
            target_temp = target.get("temperature")
            if target_temp is None:
                _LOGGER.error("Target temperature is required")
                return False
            
            try:
                target_temp = float(target_temp)
            except (ValueError, TypeError):
                _LOGGER.error("Invalid target temperature: %s", target_temp)
                return False
            
            # Use provided mode for slot updates
            if mode not in [MODE_HOME, MODE_AWAY]:
                _LOGGER.error("Invalid mode: %s", mode)
                return False
            
            # Create new schedule slot
            new_slot = ScheduleSlot(
                day=day.lower(),
                start_time=start_time,
                end_time=end_time,
                target_value=target_temp,
                entity_domain=target.get("domain", "climate"),
                buffer_override=None  # Will be set if provided
            )
            
            # Add buffer override if provided
            if "buffer_override" in target:
                try:
                    from .models import BufferConfig
                    new_slot.buffer_override = BufferConfig.from_dict(target["buffer_override"])
                except Exception as e:
                    _LOGGER.warning("Invalid buffer override in slot update: %s", e)
            
            # Update the schedule data
            if mode not in self._schedule_data.schedules:
                self._schedule_data.schedules[mode] = {}
            
            if day.lower() not in self._schedule_data.schedules[mode]:
                self._schedule_data.schedules[mode][day.lower()] = []
            
            day_slots = self._schedule_data.schedules[mode][day.lower()]
            
            # Find and replace existing slot or add new one
            slot_updated = False
            for i, existing_slot in enumerate(day_slots):
                if (existing_slot.start_time == start_time and 
                    existing_slot.end_time == end_time):
                    day_slots[i] = new_slot
                    slot_updated = True
                    break
            
            if not slot_updated:
                # Add new slot and sort by start time
                day_slots.append(new_slot)
                day_slots.sort(key=lambda s: s.start_time)
            
            # Validate no overlaps
            for i in range(len(day_slots) - 1):
                if day_slots[i].overlaps_with(day_slots[i + 1]):
                    _LOGGER.error("Slot update would create overlap on %s", day)
                    return False
            
            # Save updated schedule data
            await self.storage_service.save_schedules(self._schedule_data.to_dict())
            
            # Emit event for real-time updates
            from .const import DOMAIN
            self.hass.bus.async_fire(f"{DOMAIN}_schedule_updated", {
                "entity_id": entity_id,
                "mode": mode,
                "day": day.lower(),
                "time_slot": time_slot,
                "target_value": target_temp,
                "changes": [{
                    "day": day.lower(),
                    "time": time_slot,
                    "value": target_temp
                }]
            })
            
            _LOGGER.info("Updated schedule slot for %s on %s: %s (%.1f°C)", 
                        entity_id, day, time_slot, target_temp)
            
            return True
            
        except Exception as e:
            _LOGGER.error("Error updating slot for %s: %s", entity_id, e)
            return False
    
    async def get_schedule_grid(self, entity_id: str, mode: str) -> Dict[str, Any]:
        """
        Get the schedule grid for display in the frontend.
        
        Implements requirement 1.1: Display schedule grid with configurable time resolution.
        
        Args:
            entity_id: The entity to get schedules for
            mode: The presence mode (home/away)
            
        Returns:
            Dictionary containing grid data for frontend consumption
        """
        if not self._schedule_data:
            await self._load_schedule_data()
        
        if not self._schedule_data:
            _LOGGER.warning("No schedule data available for grid generation")
            return {
                "mode": mode,
                "entity_id": entity_id,
                "grid": {},
                "resolution_minutes": 30,
                "error": "No schedule data available"
            }
        
        # Check if entity is tracked
        if entity_id not in self._schedule_data.entities_tracked:
            _LOGGER.warning("Entity %s is not tracked in schedules", entity_id)
            return {
                "mode": mode,
                "entity_id": entity_id,
                "grid": {},
                "resolution_minutes": self._schedule_data.ui.get("resolution_minutes", 30),
                "error": f"Entity {entity_id} is not tracked"
            }
        
        mode_schedules = self._schedule_data.schedules.get(mode, {})
        resolution_minutes = self._schedule_data.ui.get("resolution_minutes", 30)
        
        # Convert to grid format with enhanced metadata
        grid = {}
        for day in WEEKDAYS:
            day_slots = mode_schedules.get(day, [])
            
            # Sort slots by start time for consistent ordering
            sorted_slots = sorted(day_slots, key=lambda s: s.start_time)
            
            grid[day] = []
            for slot in sorted_slots:
                slot_dict = slot.to_dict()
                # Add additional metadata for frontend
                slot_dict["day"] = day
                slot_dict["duration_minutes"] = self._calculate_slot_duration(slot.start_time, slot.end_time)
                grid[day].append(slot_dict)
        
        # Get current slot for highlighting
        current_slot = await self.evaluate_current_slot(entity_id, mode)
        current_slot_info = None
        if current_slot:
            current_slot_info = {
                "day": current_slot.day,
                "start": current_slot.start_time,
                "end": current_slot.end_time,
                "target_value": current_slot.target_value
            }
        
        return {
            "mode": mode,
            "entity_id": entity_id,
            "grid": grid,
            "resolution_minutes": resolution_minutes,
            "current_slot": current_slot_info,
            "total_slots": sum(len(day_slots) for day_slots in grid.values()),
            "coverage_analysis": self._analyze_schedule_coverage(mode_schedules)
        }
    
    async def apply_slot_service(self, call: ServiceCall) -> None:
        """
        Handle the apply_slot service call with comprehensive parameter validation.
        
        Implements requirements 6.3, 6.4, 6.5:
        - 6.3: Service call parameter parsing and validation
        - 6.4: Apply specific schedule slots with buffer override support
        - 6.5: Comprehensive error handling for invalid service parameters
        """
        try:
            # Extract and validate parameters (Requirement 6.3)
            entity_id = call.data.get("entity_id")
            day = call.data.get("day")
            time_slot = call.data.get("time")
            force = call.data.get("force", False)
            buffer_override = call.data.get("buffer_override", {})
            
            # Comprehensive parameter validation (Requirement 6.5)
            validation_errors = []
            
            if not entity_id:
                validation_errors.append("entity_id is required")
            elif not isinstance(entity_id, str):
                validation_errors.append("entity_id must be a string")
            
            if not day:
                validation_errors.append("day is required")
            elif not isinstance(day, str):
                validation_errors.append("day must be a string")
            elif day.lower() not in [d.lower() for d in WEEKDAYS]:
                validation_errors.append(f"day must be one of: {', '.join(WEEKDAYS)}")
            
            if not time_slot:
                validation_errors.append("time is required")
            elif not isinstance(time_slot, str):
                validation_errors.append("time must be a string")
            
            if not isinstance(force, bool):
                validation_errors.append("force must be a boolean")
            
            if not isinstance(buffer_override, dict):
                validation_errors.append("buffer_override must be a dictionary")
            
            if validation_errors:
                error_msg = f"apply_slot service validation errors: {'; '.join(validation_errors)}"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            _LOGGER.info("Apply slot service called: entity=%s, day=%s, time=%s, force=%s", 
                        entity_id, day, time_slot, force)
            
            # Load schedule data if needed
            if not self._schedule_data:
                await self._load_schedule_data()
            
            if not self._schedule_data:
                error_msg = "No schedule data available for apply_slot service"
                _LOGGER.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Validate entity exists in Home Assistant
            entity_state = self.hass.states.get(entity_id)
            if not entity_state:
                error_msg = f"Entity {entity_id} not found in Home Assistant"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            # Validate entity is tracked
            if entity_id not in self._schedule_data.entities_tracked:
                error_msg = f"Entity {entity_id} is not tracked in schedules"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            # Parse and validate time slot format
            try:
                start_time, end_time = time_slot.split('-')
                start_time = start_time.strip()
                end_time = end_time.strip()
                
                # Validate time format (HH:MM)
                from datetime import time
                start_time_obj = time.fromisoformat(start_time)
                end_time_obj = time.fromisoformat(end_time)
                
                # Validate time range is logical
                if start_time == end_time:
                    raise ValueError("Start and end times cannot be the same")
                
            except ValueError as e:
                error_msg = f"Invalid time slot format '{time_slot}': {e}"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            # Validate buffer override parameters (Requirement 6.4)
            if buffer_override:
                buffer_errors = self._validate_buffer_override(buffer_override)
                if buffer_errors:
                    error_msg = f"Invalid buffer override: {'; '.join(buffer_errors)}"
                    _LOGGER.error(error_msg)
                    raise ValueError(error_msg)
            
            # Get current mode and find the slot
            current_mode = await self.presence_manager.get_current_mode()
            mode_schedules = self._schedule_data.schedules.get(current_mode, {})
            day_schedules = mode_schedules.get(day.lower(), [])
            
            target_slot = None
            for slot in day_schedules:
                if slot.start_time == start_time and slot.end_time == end_time:
                    target_slot = slot
                    break
            
            if not target_slot:
                error_msg = f"No slot found for {entity_id} on {day} at {time_slot} in {current_mode} mode"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            # Apply buffer override if provided (Requirement 6.4)
            if buffer_override:
                # Create a copy of the slot with buffer override
                from .models import BufferConfig
                try:
                    buffer_config = BufferConfig.from_dict(buffer_override)
                    target_slot.buffer_override = buffer_config
                    _LOGGER.debug("Applied buffer override: %s", buffer_override)
                except Exception as e:
                    error_msg = f"Failed to apply buffer override: {e}"
                    _LOGGER.error(error_msg)
                    raise ValueError(error_msg)
            
            # Apply the slot value
            success = await self._apply_entity_value(entity_id, target_slot.target_value, target_slot, force)
            
            if success:
                self.buffer_manager.update_scheduled_change(entity_id, target_slot.target_value)
                _LOGGER.info("Successfully applied slot %s for %s: %.1f°C", 
                           time_slot, entity_id, target_slot.target_value)
            else:
                error_msg = f"Failed to apply slot {time_slot} for {entity_id}"
                _LOGGER.error(error_msg)
                raise RuntimeError(error_msg)
                
        except Exception as e:
            _LOGGER.error("Error in apply_slot service: %s", e)
            raise
    
    async def apply_grid_now_service(self, call: ServiceCall) -> None:
        """
        Handle the apply_grid_now service call with comprehensive parameter validation.
        
        Implements requirements 6.1, 6.2, 6.5:
        - 6.1: Immediate full schedule application service
        - 6.2: Evaluate current time and presence, then apply appropriate schedule
        - 6.5: Comprehensive error handling for invalid service parameters
        """
        try:
            # Extract and validate parameters (Requirement 6.5)
            entity_id = call.data.get("entity_id")
            force = call.data.get("force", False)
            
            # Comprehensive parameter validation
            validation_errors = []
            
            if not entity_id:
                validation_errors.append("entity_id is required")
            elif not isinstance(entity_id, str):
                validation_errors.append("entity_id must be a string")
            
            if not isinstance(force, bool):
                validation_errors.append("force must be a boolean")
            
            if validation_errors:
                error_msg = f"apply_grid_now service validation errors: {'; '.join(validation_errors)}"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            _LOGGER.info("Apply grid now service called: entity=%s, force=%s", entity_id, force)
            
            # Validate entity exists in Home Assistant
            entity_state = self.hass.states.get(entity_id)
            if not entity_state:
                error_msg = f"Entity {entity_id} not found in Home Assistant"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            # Check if entity is available
            if entity_state.state in ["unavailable", "unknown"]:
                error_msg = f"Entity {entity_id} is {entity_state.state} and cannot be controlled"
                _LOGGER.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Load schedule data if needed
            if not self._schedule_data:
                await self._load_schedule_data()
            
            if not self._schedule_data:
                error_msg = "No schedule data available for apply_grid_now service"
                _LOGGER.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Validate entity is tracked
            if entity_id not in self._schedule_data.entities_tracked:
                error_msg = f"Entity {entity_id} is not tracked in schedules"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            # Apply current schedule (Requirement 6.2)
            success = await self.apply_schedule(entity_id, force)
            
            if success:
                _LOGGER.info("Successfully applied current schedule for %s", entity_id)
            else:
                error_msg = f"Failed to apply current schedule for {entity_id}"
                _LOGGER.error(error_msg)
                raise RuntimeError(error_msg)
                
        except Exception as e:
            _LOGGER.error("Error in apply_grid_now service: %s", e)
            raise
    
    async def migrate_resolution_service(self, call: ServiceCall) -> None:
        """
        Handle the migrate_resolution service call for changing time resolution.
        
        Implements requirement 1.4: Schedule resolution migration with preview and confirmation.
        """
        try:
            # Extract and validate parameters
            new_resolution = call.data.get("resolution_minutes")
            preview_only = call.data.get("preview", True)
            
            # Parameter validation
            validation_errors = []
            
            if new_resolution is None:
                validation_errors.append("resolution_minutes is required")
            elif not isinstance(new_resolution, int):
                validation_errors.append("resolution_minutes must be an integer")
            elif new_resolution not in [15, 30, 60]:
                validation_errors.append("resolution_minutes must be 15, 30, or 60")
            
            if not isinstance(preview_only, bool):
                validation_errors.append("preview must be a boolean")
            
            if validation_errors:
                error_msg = f"migrate_resolution service validation errors: {'; '.join(validation_errors)}"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            _LOGGER.info("Migrate resolution service called: resolution=%d, preview=%s", 
                        new_resolution, preview_only)
            
            # Perform migration
            result = await self.migrate_resolution(new_resolution, preview_only)
            
            # Emit event with results
            from .const import DOMAIN
            self.hass.bus.async_fire(f"{DOMAIN}_migration_result", {
                "service": "migrate_resolution",
                "result": result
            })
            
            _LOGGER.info("Resolution migration service completed: %s", result["status"])
            
        except Exception as e:
            _LOGGER.error("Error in migrate_resolution service: %s", e)
            raise
    
    def _validate_buffer_override(self, buffer_override: Dict[str, Any]) -> List[str]:
        """
        Validate buffer override parameters.
        
        Args:
            buffer_override: Dictionary containing buffer override parameters
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Validate time_minutes
        if "time_minutes" in buffer_override:
            time_minutes = buffer_override["time_minutes"]
            if not isinstance(time_minutes, (int, float)):
                errors.append("time_minutes must be a number")
            elif time_minutes < 0:
                errors.append("time_minutes must be non-negative")
            elif time_minutes > 1440:  # 24 hours
                errors.append("time_minutes cannot exceed 1440 (24 hours)")
        
        # Validate value_delta
        if "value_delta" in buffer_override:
            value_delta = buffer_override["value_delta"]
            if not isinstance(value_delta, (int, float)):
                errors.append("value_delta must be a number")
            elif value_delta < 0:
                errors.append("value_delta must be non-negative")
            elif value_delta > 50:  # Reasonable upper limit
                errors.append("value_delta cannot exceed 50 degrees")
        
        # Validate enabled
        if "enabled" in buffer_override:
            enabled = buffer_override["enabled"]
            if not isinstance(enabled, bool):
                errors.append("enabled must be a boolean")
        
        # Check for unknown parameters
        valid_params = {"time_minutes", "value_delta", "enabled"}
        unknown_params = set(buffer_override.keys()) - valid_params
        if unknown_params:
            errors.append(f"Unknown buffer override parameters: {', '.join(unknown_params)}")
        
        return errors
    
    def _time_in_slot(self, current_time: time, start_str: str, end_str: str) -> bool:
        """Check if current time falls within a schedule slot."""
        try:
            start_time = time.fromisoformat(start_str)
            end_time = time.fromisoformat(end_str)
            
            # Handle slots that cross midnight
            if start_time <= end_time:
                return start_time <= current_time <= end_time
            else:
                return current_time >= start_time or current_time <= end_time
        except ValueError as e:
            _LOGGER.error("Invalid time format in slot: start=%s, end=%s, error=%s", 
                         start_str, end_str, e)
            return False
    
    async def _load_schedule_data(self) -> None:
        """Load schedule data from storage."""
        try:
            data = await self.storage_service.load_schedules()
            if data:
                self._schedule_data = ScheduleData.from_dict(data)
                _LOGGER.debug("Loaded schedule data for %d entities", 
                             len(self._schedule_data.entities_tracked))
            else:
                _LOGGER.info("No schedule data found in storage")
        except Exception as e:
            _LOGGER.error("Failed to load schedule data: %s", e)
            self._schedule_data = None
    
    async def migrate_resolution(self, new_resolution_minutes: int, preview: bool = True) -> Dict[str, Any]:
        """
        Migrate schedule resolution with preview and user confirmation.
        
        Implements requirement 1.4: Handle changing time resolution with preview system.
        
        Args:
            new_resolution_minutes: New time resolution (15, 30, or 60 minutes)
            preview: If True, return preview without applying changes
            
        Returns:
            Dictionary containing migration preview or results
        """
        if not self._schedule_data:
            await self._load_schedule_data()
        
        if not self._schedule_data:
            raise ValueError("No schedule data available for migration")
        
        # Validate new resolution
        valid_resolutions = [15, 30, 60]
        if new_resolution_minutes not in valid_resolutions:
            raise ValueError(f"Resolution must be one of {valid_resolutions}, got {new_resolution_minutes}")
        
        current_resolution = self._schedule_data.ui.get("resolution_minutes", 30)
        
        if current_resolution == new_resolution_minutes:
            return {
                "status": "no_change",
                "message": f"Resolution is already {new_resolution_minutes} minutes",
                "current_resolution": current_resolution,
                "new_resolution": new_resolution_minutes
            }
        
        _LOGGER.info("Starting resolution migration from %d to %d minutes (preview=%s)", 
                    current_resolution, new_resolution_minutes, preview)
        
        # Create migration preview
        migration_preview = {
            "status": "preview" if preview else "applied",
            "current_resolution": current_resolution,
            "new_resolution": new_resolution_minutes,
            "changes": {},
            "warnings": [],
            "total_slots_before": 0,
            "total_slots_after": 0
        }
        
        # Process each mode and day
        migrated_schedules = {}
        for mode, mode_schedules in self._schedule_data.schedules.items():
            migrated_schedules[mode] = {}
            migration_preview["changes"][mode] = {}
            
            for day, slots in mode_schedules.items():
                migration_preview["total_slots_before"] += len(slots)
                
                # Migrate slots for this day
                migrated_slots, day_changes = self._migrate_day_slots(
                    slots, current_resolution, new_resolution_minutes
                )
                
                migrated_schedules[mode][day] = migrated_slots
                migration_preview["changes"][mode][day] = day_changes
                migration_preview["total_slots_after"] += len(migrated_slots)
                
                # Check for potential issues
                warnings = self._validate_migrated_slots(migrated_slots, day, mode)
                migration_preview["warnings"].extend(warnings)
        
        # Add summary statistics
        migration_preview["summary"] = {
            "slots_changed": migration_preview["total_slots_after"] - migration_preview["total_slots_before"],
            "resolution_factor": new_resolution_minutes / current_resolution,
            "data_loss_risk": current_resolution < new_resolution_minutes,
            "precision_gain": current_resolution > new_resolution_minutes
        }
        
        # If not preview, apply the migration
        if not preview:
            try:
                # Update schedule data
                self._schedule_data.schedules = migrated_schedules
                self._schedule_data.ui["resolution_minutes"] = new_resolution_minutes
                self._schedule_data.metadata["last_modified"] = datetime.now().isoformat()
                self._schedule_data.metadata["last_migration"] = {
                    "from_resolution": current_resolution,
                    "to_resolution": new_resolution_minutes,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Save updated data
                await self.storage_service.save_schedules(self._schedule_data.to_dict())
                
                # Emit event for real-time updates
                from .const import DOMAIN
                self.hass.bus.async_fire(f"{DOMAIN}_resolution_migrated", {
                    "from_resolution": current_resolution,
                    "to_resolution": new_resolution_minutes,
                    "total_changes": migration_preview["total_slots_after"] - migration_preview["total_slots_before"]
                })
                
                _LOGGER.info("Resolution migration completed: %d -> %d minutes", 
                           current_resolution, new_resolution_minutes)
                
            except Exception as e:
                _LOGGER.error("Error applying resolution migration: %s", e)
                migration_preview["status"] = "error"
                migration_preview["error"] = str(e)
        
        return migration_preview
    
    def _migrate_day_slots(self, slots: List[ScheduleSlot], current_res: int, new_res: int) -> tuple[List[ScheduleSlot], Dict[str, Any]]:
        """
        Migrate slots for a single day to new resolution.
        
        Args:
            slots: List of current schedule slots
            current_res: Current resolution in minutes
            new_res: New resolution in minutes
            
        Returns:
            Tuple of (migrated_slots, change_summary)
        """
        if not slots:
            return [], {"original_count": 0, "new_count": 0, "changes": []}
        
        migrated_slots = []
        changes = []
        
        # Sort slots by start time
        sorted_slots = sorted(slots, key=lambda s: s.start_time)
        
        for slot in sorted_slots:
            # Convert times to minutes since midnight
            start_minutes = self._time_to_minutes(slot.start_time)
            end_minutes = self._time_to_minutes(slot.end_time)
            
            # Align to new resolution boundaries
            new_start_minutes = self._align_to_resolution(start_minutes, new_res)
            new_end_minutes = self._align_to_resolution(end_minutes, new_res, align_up=True)
            
            # Ensure minimum slot duration (at least one resolution unit)
            if new_end_minutes <= new_start_minutes:
                new_end_minutes = new_start_minutes + new_res
            
            # Convert back to time strings
            new_start_time = self._minutes_to_time(new_start_minutes)
            new_end_time = self._minutes_to_time(new_end_minutes)
            
            # Create migrated slot
            migrated_slot = ScheduleSlot(
                day=slot.day,
                start_time=new_start_time,
                end_time=new_end_time,
                target_value=slot.target_value,
                entity_domain=slot.entity_domain,
                buffer_override=slot.buffer_override
            )
            
            # Track changes
            if (slot.start_time != new_start_time or slot.end_time != new_end_time):
                changes.append({
                    "original": {"start": slot.start_time, "end": slot.end_time},
                    "migrated": {"start": new_start_time, "end": new_end_time},
                    "target_value": slot.target_value
                })
            
            migrated_slots.append(migrated_slot)
        
        # Merge overlapping slots with same target value
        merged_slots = self._merge_overlapping_slots(migrated_slots)
        
        return merged_slots, {
            "original_count": len(slots),
            "new_count": len(merged_slots),
            "changes": changes,
            "merged": len(migrated_slots) != len(merged_slots)
        }
    
    def _align_to_resolution(self, minutes: int, resolution: int, align_up: bool = False) -> int:
        """Align time in minutes to resolution boundary."""
        if align_up:
            return ((minutes + resolution - 1) // resolution) * resolution
        else:
            return (minutes // resolution) * resolution
    
    def _time_to_minutes(self, time_str: str) -> int:
        """Convert time string to minutes since midnight."""
        try:
            hour, minute = map(int, time_str.split(':'))
            return hour * 60 + minute
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid time format: {time_str}")
    
    def _minutes_to_time(self, minutes: int) -> str:
        """Convert minutes since midnight to time string."""
        # Handle special case for exactly 1440 minutes (24:00) - convert to 23:59
        if minutes >= 24 * 60:
            return "23:59"
        
        hour = minutes // 60
        minute = minutes % 60
        
        return f"{hour:02d}:{minute:02d}"
    
    def _merge_overlapping_slots(self, slots: List[ScheduleSlot]) -> List[ScheduleSlot]:
        """Merge overlapping slots with the same target value."""
        if not slots:
            return []
        
        # Sort by start time
        sorted_slots = sorted(slots, key=lambda s: s.start_time)
        merged = [sorted_slots[0]]
        
        for current in sorted_slots[1:]:
            last_merged = merged[-1]
            
            # Check if slots can be merged (adjacent or overlapping with same target)
            if (self._time_to_minutes(current.start_time) <= self._time_to_minutes(last_merged.end_time) and
                abs(current.target_value - last_merged.target_value) < 0.1 and
                current.entity_domain == last_merged.entity_domain):
                
                # Extend the last merged slot
                if self._time_to_minutes(current.end_time) > self._time_to_minutes(last_merged.end_time):
                    last_merged.end_time = current.end_time
            else:
                merged.append(current)
        
        return merged
    
    def _validate_migrated_slots(self, slots: List[ScheduleSlot], day: str, mode: str) -> List[str]:
        """Validate migrated slots and return warnings."""
        warnings = []
        
        if not slots:
            warnings.append(f"No slots after migration for {mode} mode on {day}")
            return warnings
        
        # Check for overlaps
        sorted_slots = sorted(slots, key=lambda s: s.start_time)
        for i in range(len(sorted_slots) - 1):
            if sorted_slots[i].overlaps_with(sorted_slots[i + 1]):
                warnings.append(
                    f"Overlapping slots after migration in {mode}/{day}: "
                    f"{sorted_slots[i].start_time}-{sorted_slots[i].end_time} and "
                    f"{sorted_slots[i + 1].start_time}-{sorted_slots[i + 1].end_time}"
                )
        
        # Check for gaps
        for i in range(len(sorted_slots) - 1):
            if sorted_slots[i].end_time != sorted_slots[i + 1].start_time:
                warnings.append(
                    f"Gap after migration in {mode}/{day}: "
                    f"{sorted_slots[i].end_time} to {sorted_slots[i + 1].start_time}"
                )
        
        return warnings

    def _calculate_slot_duration(self, start_time: str, end_time: str) -> int:
        """Calculate the duration of a schedule slot in minutes."""
        try:
            start = time.fromisoformat(start_time)
            end = time.fromisoformat(end_time)
            
            # Convert to minutes since midnight
            start_minutes = start.hour * 60 + start.minute
            end_minutes = end.hour * 60 + end.minute
            
            # Handle slots that cross midnight
            if end_minutes <= start_minutes:
                end_minutes += 24 * 60  # Add 24 hours
            
            return end_minutes - start_minutes
        except ValueError as e:
            _LOGGER.error("Invalid time format in slot duration calculation: start=%s, end=%s, error=%s", 
                         start_time, end_time, e)
            return 0
    
    def _analyze_schedule_coverage(self, mode_schedules: Dict[str, List[ScheduleSlot]]) -> Dict[str, Any]:
        """
        Analyze schedule coverage for a mode to identify gaps and overlaps.
        
        Returns:
            Dictionary with coverage analysis including gaps and total coverage percentage
        """
        analysis = {
            "total_coverage_percent": 0.0,
            "gaps": [],
            "overlaps": [],
            "days_with_schedules": 0,
            "days_with_full_coverage": 0
        }
        
        total_minutes_possible = len(WEEKDAYS) * 24 * 60  # 7 days * 24 hours * 60 minutes
        total_minutes_covered = 0
        
        for day in WEEKDAYS:
            day_slots = mode_schedules.get(day, [])
            if not day_slots:
                analysis["gaps"].append({
                    "day": day,
                    "start": "00:00",
                    "end": "23:59",
                    "duration_minutes": 24 * 60
                })
                continue
            
            analysis["days_with_schedules"] += 1
            
            # Sort slots by start time
            sorted_slots = sorted(day_slots, key=lambda s: s.start_time)
            
            day_coverage = 0
            last_end_minutes = 0
            
            for i, slot in enumerate(sorted_slots):
                start_minutes = self._time_to_minutes(slot.start_time)
                end_minutes = self._time_to_minutes(slot.end_time)
                
                # Check for gap before this slot
                if start_minutes > last_end_minutes:
                    gap_duration = start_minutes - last_end_minutes
                    analysis["gaps"].append({
                        "day": day,
                        "start": self._minutes_to_time(last_end_minutes),
                        "end": slot.start_time,
                        "duration_minutes": gap_duration
                    })
                
                # Check for overlap with previous slot
                if i > 0 and start_minutes < last_end_minutes:
                    overlap_duration = last_end_minutes - start_minutes
                    analysis["overlaps"].append({
                        "day": day,
                        "slot1_end": self._minutes_to_time(last_end_minutes),
                        "slot2_start": slot.start_time,
                        "duration_minutes": overlap_duration
                    })
                
                # Add this slot's coverage
                slot_duration = end_minutes - start_minutes
                if slot_duration > 0:
                    day_coverage += slot_duration
                    last_end_minutes = max(last_end_minutes, end_minutes)
            
            # Check for gap at end of day
            if last_end_minutes < 24 * 60:
                gap_duration = (24 * 60) - last_end_minutes
                analysis["gaps"].append({
                    "day": day,
                    "start": self._minutes_to_time(last_end_minutes),
                    "end": "23:59",
                    "duration_minutes": gap_duration
                })
            
            total_minutes_covered += day_coverage
            
            # Check if day has full coverage
            if day_coverage >= (24 * 60 - 1):  # Allow 1 minute tolerance
                analysis["days_with_full_coverage"] += 1
        
        analysis["total_coverage_percent"] = (total_minutes_covered / total_minutes_possible) * 100
        
        return analysis
    
    def _time_to_minutes(self, time_str: str) -> int:
        """Convert time string (HH:MM) to minutes since midnight."""
        try:
            time_obj = time.fromisoformat(time_str)
            return time_obj.hour * 60 + time_obj.minute
        except ValueError:
            _LOGGER.error("Invalid time format: %s", time_str)
            return 0
    
    def _minutes_to_time(self, minutes: int) -> str:
        """Convert minutes since midnight to time string (HH:MM)."""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"
    
    async def get_all_schedule_grids(self, entity_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get schedule grids for all modes (home and away).
        
        Returns:
            Dictionary with 'home' and 'away' keys containing their respective grids
        """
        grids = {}
        for mode in [MODE_HOME, MODE_AWAY]:
            grids[mode] = await self.get_schedule_grid(entity_id, mode)
        
        return grids
    
    async def get_schedule_summary(self, entity_id: str) -> Dict[str, Any]:
        """
        Get a summary of schedules for an entity across all modes.
        
        Returns:
            Dictionary with schedule statistics and current status
        """
        if not self._schedule_data:
            await self._load_schedule_data()
        
        if not self._schedule_data or entity_id not in self._schedule_data.entities_tracked:
            return {
                "entity_id": entity_id,
                "is_tracked": False,
                "error": "Entity not tracked or no schedule data"
            }
        
        current_mode = await self.presence_manager.get_current_mode()
        current_slot = await self.evaluate_current_slot(entity_id, current_mode)
        
        # Count slots per mode
        home_slots = sum(len(day_slots) for day_slots in self._schedule_data.schedules.get(MODE_HOME, {}).values())
        away_slots = sum(len(day_slots) for day_slots in self._schedule_data.schedules.get(MODE_AWAY, {}).values())
        
        return {
            "entity_id": entity_id,
            "is_tracked": True,
            "current_mode": current_mode,
            "current_slot": {
                "active": current_slot is not None,
                "start": current_slot.start_time if current_slot else None,
                "end": current_slot.end_time if current_slot else None,
                "target_value": current_slot.target_value if current_slot else None,
                "day": current_slot.day if current_slot else None
            },
            "schedule_counts": {
                "home_slots": home_slots,
                "away_slots": away_slots,
                "total_slots": home_slots + away_slots
            },
            "resolution_minutes": self._schedule_data.ui.get("resolution_minutes", 30),
            "last_updated": datetime.now().isoformat()
        }
    
    async def _apply_entity_value(self, entity_id: str, target_value: float, 
                                 slot: ScheduleSlot, force: bool = False) -> bool:
        """
        Apply a target value to an entity with proper error handling.
        
        Implements requirement 1.4: Apply schedule values with proper error handling
        for unavailable entities and service failures.
        
        Args:
            entity_id: The entity to update
            target_value: The target value to set
            slot: The schedule slot being applied
            force: Whether to force application bypassing buffer logic
            
        Returns:
            True if value was applied successfully, False otherwise
        """
        try:
            # Get entity state and validate availability
            entity_state = self.hass.states.get(entity_id)
            if not entity_state:
                _LOGGER.error("Entity %s not found", entity_id)
                return False
            
            if entity_state.state in ["unavailable", "unknown"]:
                _LOGGER.warning("Entity %s is %s, cannot apply value", entity_id, entity_state.state)
                return False
            
            # Determine the appropriate service call based on entity domain
            domain = entity_id.split('.')[0]
            
            if domain == "climate":
                return await self._apply_climate_value(entity_id, target_value)
            elif domain == "input_number":
                return await self._apply_input_number_value(entity_id, target_value)
            elif domain == "number":
                return await self._apply_number_value(entity_id, target_value)
            else:
                _LOGGER.error("Unsupported entity domain for %s: %s", entity_id, domain)
                return False
                
        except Exception as e:
            _LOGGER.error("Error applying value %.1f to %s: %s", target_value, entity_id, e)
            return False
    
    async def _apply_climate_value(self, entity_id: str, temperature: float) -> bool:
        """Apply temperature value to a climate entity."""
        try:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": entity_id,
                    "temperature": temperature
                }
            )
            _LOGGER.debug("Set temperature for %s to %.1f°C", entity_id, temperature)
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to set temperature for %s: %s", entity_id, e)
            return False
    
    async def _apply_input_number_value(self, entity_id: str, value: float) -> bool:
        """Apply value to an input_number entity."""
        try:
            await self.hass.services.async_call(
                "input_number",
                "set_value",
                {
                    "entity_id": entity_id,
                    "value": value
                }
            )
            _LOGGER.debug("Set input_number %s to %.1f", entity_id, value)
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to set input_number %s: %s", entity_id, e)
            return False
    
    async def _apply_number_value(self, entity_id: str, value: float) -> bool:
        """Apply value to a number entity."""
        try:
            await self.hass.services.async_call(
                "number",
                "set_value",
                {
                    "entity_id": entity_id,
                    "value": value
                }
            )
            _LOGGER.debug("Set number %s to %.1f", entity_id, value)
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to set number %s: %s", entity_id, e)
            return False
    
    async def apply_all_tracked_entities(self, force: bool = False) -> Dict[str, bool]:
        """
        Apply current schedules to all tracked entities.
        
        Returns:
            Dictionary mapping entity_id to success status
        """
        if not self._schedule_data:
            await self._load_schedule_data()
        
        if not self._schedule_data:
            _LOGGER.error("No schedule data available for bulk application")
            return {}
        
        results = {}
        
        for entity_id in self._schedule_data.entities_tracked:
            try:
                success = await self.apply_schedule(entity_id, force)
                results[entity_id] = success
                
                if success:
                    _LOGGER.debug("Successfully applied schedule for %s", entity_id)
                else:
                    _LOGGER.warning("Failed to apply schedule for %s", entity_id)
                    
            except Exception as e:
                _LOGGER.error("Error applying schedule for %s: %s", entity_id, e)
                results[entity_id] = False
        
        successful_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        _LOGGER.info("Applied schedules to %d/%d entities (force=%s)", 
                    successful_count, total_count, force)
        
        return results
    
    async def validate_entity_compatibility(self, entity_id: str) -> Dict[str, Any]:
        """
        Validate that an entity is compatible with the scheduler.
        
        Returns:
            Dictionary with compatibility information
        """
        entity_state = self.hass.states.get(entity_id)
        
        if not entity_state:
            return {
                "compatible": False,
                "reason": "Entity not found",
                "entity_id": entity_id
            }
        
        domain = entity_id.split('.')[0]
        
        # Check supported domains
        if domain not in ["climate", "input_number", "number"]:
            return {
                "compatible": False,
                "reason": f"Unsupported domain: {domain}",
                "entity_id": entity_id,
                "domain": domain
            }
        
        # Check entity availability
        if entity_state.state in ["unavailable", "unknown"]:
            return {
                "compatible": False,
                "reason": f"Entity is {entity_state.state}",
                "entity_id": entity_id,
                "domain": domain,
                "state": entity_state.state
            }
        
        # Domain-specific validation
        validation_info = {
            "compatible": True,
            "entity_id": entity_id,
            "domain": domain,
            "state": entity_state.state
        }
        
        if domain == "climate":
            # Check if climate entity supports temperature setting
            supported_features = entity_state.attributes.get("supported_features", 0)
            # SUPPORT_TARGET_TEMPERATURE = 1
            if not (supported_features & 1):
                validation_info["compatible"] = False
                validation_info["reason"] = "Climate entity does not support target temperature"
            else:
                validation_info["current_temperature"] = entity_state.attributes.get("temperature")
                validation_info["min_temp"] = entity_state.attributes.get("min_temp")
                validation_info["max_temp"] = entity_state.attributes.get("max_temp")
        
        elif domain in ["input_number", "number"]:
            # Check min/max values
            validation_info["min_value"] = entity_state.attributes.get("min")
            validation_info["max_value"] = entity_state.attributes.get("max")
            validation_info["step"] = entity_state.attributes.get("step")
            
            try:
                validation_info["current_value"] = float(entity_state.state)
            except (ValueError, TypeError):
                validation_info["compatible"] = False
                validation_info["reason"] = f"Cannot parse current value: {entity_state.state}"
        
        return validation_info
    
    async def migrate_resolution(self, new_resolution_minutes: int, preview: bool = True) -> Dict[str, Any]:
        """
        Migrate schedule resolution with preview and user confirmation.
        
        Implements requirement 1.4: Handle changing time resolution with preview system.
        
        Args:
            new_resolution_minutes: New time resolution (15, 30, or 60 minutes)
            preview: If True, return preview without applying changes
            
        Returns:
            Dictionary containing migration preview or results
        """
        if not self._schedule_data:
            await self._load_schedule_data()
        
        if not self._schedule_data:
            raise ValueError("No schedule data available for migration")
        
        # Validate new resolution
        valid_resolutions = [15, 30, 60]
        if new_resolution_minutes not in valid_resolutions:
            raise ValueError(f"Resolution must be one of {valid_resolutions}, got {new_resolution_minutes}")
        
        current_resolution = self._schedule_data.ui.get("resolution_minutes", 30)
        
        if current_resolution == new_resolution_minutes:
            return {
                "status": "no_change",
                "message": f"Resolution is already {new_resolution_minutes} minutes",
                "current_resolution": current_resolution,
                "new_resolution": new_resolution_minutes
            }
        
        _LOGGER.info("Starting resolution migration from %d to %d minutes (preview=%s)", 
                    current_resolution, new_resolution_minutes, preview)
        
        # Create migration preview
        migration_preview = {
            "status": "preview" if preview else "applied",
            "current_resolution": current_resolution,
            "new_resolution": new_resolution_minutes,
            "changes": {},
            "warnings": [],
            "total_slots_before": 0,
            "total_slots_after": 0
        }
        
        # Process each mode and day
        migrated_schedules = {}
        for mode, mode_schedules in self._schedule_data.schedules.items():
            migrated_schedules[mode] = {}
            migration_preview["changes"][mode] = {}
            
            for day, slots in mode_schedules.items():
                migration_preview["total_slots_before"] += len(slots)
                
                # Migrate slots for this day
                migrated_slots, day_changes = self._migrate_day_slots(
                    slots, current_resolution, new_resolution_minutes
                )
                
                migrated_schedules[mode][day] = migrated_slots
                migration_preview["changes"][mode][day] = day_changes
                migration_preview["total_slots_after"] += len(migrated_slots)
                
                # Check for potential issues
                warnings = self._validate_migrated_slots(migrated_slots, day, mode)
                migration_preview["warnings"].extend(warnings)
        
        # Add summary statistics
        migration_preview["summary"] = {
            "slots_changed": migration_preview["total_slots_after"] - migration_preview["total_slots_before"],
            "resolution_factor": new_resolution_minutes / current_resolution,
            "data_loss_risk": current_resolution < new_resolution_minutes,
            "precision_gain": current_resolution > new_resolution_minutes
        }
        
        # If not preview, apply the migration
        if not preview:
            try:
                # Update schedule data
                self._schedule_data.schedules = migrated_schedules
                self._schedule_data.ui["resolution_minutes"] = new_resolution_minutes
                self._schedule_data.metadata["last_modified"] = datetime.now().isoformat()
                self._schedule_data.metadata["last_migration"] = {
                    "from_resolution": current_resolution,
                    "to_resolution": new_resolution_minutes,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Save updated data
                await self.storage_service.save_schedules(self._schedule_data.to_dict())
                
                # Emit event for real-time updates
                from .const import DOMAIN
                self.hass.bus.async_fire(f"{DOMAIN}_resolution_migrated", {
                    "from_resolution": current_resolution,
                    "to_resolution": new_resolution_minutes,
                    "total_changes": migration_preview["total_slots_after"] - migration_preview["total_slots_before"]
                })
                
                _LOGGER.info("Resolution migration completed: %d -> %d minutes", 
                           current_resolution, new_resolution_minutes)
                
            except Exception as e:
                _LOGGER.error("Error applying resolution migration: %s", e)
                migration_preview["status"] = "error"
                migration_preview["error"] = str(e)
        
        return migration_preview
    
    def _migrate_day_slots(self, slots: List[ScheduleSlot], current_res: int, new_res: int) -> tuple[List[ScheduleSlot], Dict[str, Any]]:
        """
        Migrate slots for a single day to new resolution.
        
        Args:
            slots: List of current schedule slots
            current_res: Current resolution in minutes
            new_res: New resolution in minutes
            
        Returns:
            Tuple of (migrated_slots, change_summary)
        """
        if not slots:
            return [], {"original_count": 0, "new_count": 0, "changes": []}
        
        migrated_slots = []
        changes = []
        
        # Sort slots by start time
        sorted_slots = sorted(slots, key=lambda s: s.start_time)
        
        for slot in sorted_slots:
            # Convert times to minutes since midnight
            start_minutes = self._time_to_minutes(slot.start_time)
            end_minutes = self._time_to_minutes(slot.end_time)
            
            # Align to new resolution boundaries
            new_start_minutes = self._align_to_resolution(start_minutes, new_res)
            new_end_minutes = self._align_to_resolution(end_minutes, new_res, align_up=True)
            
            # Ensure minimum slot duration (at least one resolution unit)
            if new_end_minutes <= new_start_minutes:
                new_end_minutes = new_start_minutes + new_res
            
            # Convert back to time strings
            new_start_time = self._minutes_to_time(new_start_minutes)
            new_end_time = self._minutes_to_time(new_end_minutes)
            
            # Create migrated slot
            migrated_slot = ScheduleSlot(
                day=slot.day,
                start_time=new_start_time,
                end_time=new_end_time,
                target_value=slot.target_value,
                entity_domain=slot.entity_domain,
                buffer_override=slot.buffer_override
            )
            
            # Track changes
            if (slot.start_time != new_start_time or slot.end_time != new_end_time):
                changes.append({
                    "original": {"start": slot.start_time, "end": slot.end_time},
                    "migrated": {"start": new_start_time, "end": new_end_time},
                    "target_value": slot.target_value
                })
            
            migrated_slots.append(migrated_slot)
        
        # Merge overlapping slots with same target value
        merged_slots = self._merge_overlapping_slots(migrated_slots)
        
        return merged_slots, {
            "original_count": len(slots),
            "new_count": len(merged_slots),
            "changes": changes,
            "merged": len(migrated_slots) != len(merged_slots)
        }
    
    def _align_to_resolution(self, minutes: int, resolution: int, align_up: bool = False) -> int:
        """Align time in minutes to resolution boundary."""
        if align_up:
            return ((minutes + resolution - 1) // resolution) * resolution
        else:
            return (minutes // resolution) * resolution
    
    def _time_to_minutes(self, time_str: str) -> int:
        """Convert time string to minutes since midnight."""
        try:
            hour, minute = map(int, time_str.split(':'))
            return hour * 60 + minute
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid time format: {time_str}")
    
    def _minutes_to_time(self, minutes: int) -> str:
        """Convert minutes since midnight to time string."""
        # Handle special case for exactly 1440 minutes (24:00) - convert to 23:59
        if minutes >= 24 * 60:
            return "23:59"
        
        hour = minutes // 60
        minute = minutes % 60
        
        return f"{hour:02d}:{minute:02d}"
    
    def _merge_overlapping_slots(self, slots: List[ScheduleSlot]) -> List[ScheduleSlot]:
        """Merge overlapping slots with the same target value."""
        if not slots:
            return []
        
        # Sort by start time
        sorted_slots = sorted(slots, key=lambda s: s.start_time)
        merged = [sorted_slots[0]]
        
        for current in sorted_slots[1:]:
            last_merged = merged[-1]
            
            # Check if slots can be merged (adjacent or overlapping with same target)
            if (self._time_to_minutes(current.start_time) <= self._time_to_minutes(last_merged.end_time) and
                abs(current.target_value - last_merged.target_value) < 0.1 and
                current.entity_domain == last_merged.entity_domain):
                
                # Extend the last merged slot
                if self._time_to_minutes(current.end_time) > self._time_to_minutes(last_merged.end_time):
                    last_merged.end_time = current.end_time
            else:
                merged.append(current)
        
        return merged
    
    def _validate_migrated_slots(self, slots: List[ScheduleSlot], day: str, mode: str) -> List[str]:
        """Validate migrated slots and return warnings."""
        warnings = []
        
        if not slots:
            warnings.append(f"No slots after migration for {mode} mode on {day}")
            return warnings
        
        # Check for overlaps
        sorted_slots = sorted(slots, key=lambda s: s.start_time)
        for i in range(len(sorted_slots) - 1):
            if sorted_slots[i].overlaps_with(sorted_slots[i + 1]):
                warnings.append(
                    f"Overlapping slots after migration in {mode}/{day}: "
                    f"{sorted_slots[i].start_time}-{sorted_slots[i].end_time} and "
                    f"{sorted_slots[i + 1].start_time}-{sorted_slots[i + 1].end_time}"
                )
        
        # Check for gaps
        for i in range(len(sorted_slots) - 1):
            if sorted_slots[i].end_time != sorted_slots[i + 1].start_time:
                warnings.append(
                    f"Gap after migration in {mode}/{day}: "
                    f"{sorted_slots[i].end_time} to {sorted_slots[i + 1].start_time}"
                )
        
        return warnings

    async def migrate_resolution_service(self, call: ServiceCall) -> None:
        """
        Handle the migrate_resolution service call for changing time resolution.
        
        Implements requirement 1.4: Schedule resolution migration with preview and confirmation.
        """
        try:
            # Extract and validate parameters
            new_resolution = call.data.get("resolution_minutes")
            preview_only = call.data.get("preview", True)
            
            # Parameter validation
            validation_errors = []
            
            if new_resolution is None:
                validation_errors.append("resolution_minutes is required")
            elif not isinstance(new_resolution, int):
                validation_errors.append("resolution_minutes must be an integer")
            elif new_resolution not in [15, 30, 60]:
                validation_errors.append("resolution_minutes must be 15, 30, or 60")
            
            if not isinstance(preview_only, bool):
                validation_errors.append("preview must be a boolean")
            
            if validation_errors:
                error_msg = f"migrate_resolution service validation errors: {'; '.join(validation_errors)}"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)
            
            _LOGGER.info("Migrate resolution service called: resolution=%d, preview=%s", 
                        new_resolution, preview_only)
            
            # Perform migration
            result = await self.migrate_resolution(new_resolution, preview_only)
            
            # Emit event with results
            from .const import DOMAIN
            self.hass.bus.async_fire(f"{DOMAIN}_migration_result", {
                "service": "migrate_resolution",
                "result": result
            })
            
            _LOGGER.info("Resolution migration service completed: %s", result["status"])
            
        except Exception as e:
            _LOGGER.error("Error in migrate_resolution service: %s", e)
            raise