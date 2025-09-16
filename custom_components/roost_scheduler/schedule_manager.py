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
    
    async def update_slot(self, entity_id: str, day: str, time_slot: str, target: Dict[str, Any]) -> bool:
        """
        Update a specific schedule slot for individual schedule modifications.
        
        Implements requirement 1.4: Allow individual schedule slot modifications.
        
        Args:
            entity_id: The entity to update schedule for
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
            
            # Get current mode (default to home for slot updates)
            current_mode = await self.presence_manager.get_current_mode()
            
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
            if current_mode not in self._schedule_data.schedules:
                self._schedule_data.schedules[current_mode] = {}
            
            if day.lower() not in self._schedule_data.schedules[current_mode]:
                self._schedule_data.schedules[current_mode][day.lower()] = []
            
            day_slots = self._schedule_data.schedules[current_mode][day.lower()]
            
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
        Handle the apply_slot service call.
        
        Implements requirements 6.3, 6.4:
        - 6.3: Service call parameter parsing and validation
        - 6.4: Apply specific schedule slots with buffer override support
        """
        try:
            # Extract and validate parameters (Requirement 6.3)
            entity_id = call.data.get("entity_id")
            day = call.data.get("day")
            time_slot = call.data.get("time")
            force = call.data.get("force", False)
            buffer_override = call.data.get("buffer_override", {})
            
            if not entity_id:
                _LOGGER.error("apply_slot service: entity_id is required")
                return
            
            if not day:
                _LOGGER.error("apply_slot service: day is required")
                return
            
            if not time_slot:
                _LOGGER.error("apply_slot service: time is required")
                return
            
            _LOGGER.info("Apply slot service called: entity=%s, day=%s, time=%s, force=%s", 
                        entity_id, day, time_slot, force)
            
            # Load schedule data if needed
            if not self._schedule_data:
                await self._load_schedule_data()
            
            if not self._schedule_data:
                _LOGGER.error("No schedule data available for apply_slot service")
                return
            
            # Validate entity is tracked
            if entity_id not in self._schedule_data.entities_tracked:
                _LOGGER.error("Entity %s is not tracked in schedules", entity_id)
                return
            
            # Parse time slot
            try:
                start_time, end_time = time_slot.split('-')
                start_time = start_time.strip()
                end_time = end_time.strip()
            except ValueError:
                _LOGGER.error("Invalid time slot format: %s", time_slot)
                return
            
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
                _LOGGER.error("No slot found for %s on %s at %s in %s mode", 
                             entity_id, day, time_slot, current_mode)
                return
            
            # Apply buffer override if provided (Requirement 6.4)
            slot_config = target_slot.to_dict()
            if buffer_override:
                slot_config["buffer_override"] = buffer_override
                _LOGGER.debug("Applying buffer override: %s", buffer_override)
            
            # Apply the slot value
            success = await self._apply_entity_value(entity_id, target_slot.target_value, target_slot, force)
            
            if success:
                self.buffer_manager.update_scheduled_change(entity_id, target_slot.target_value)
                _LOGGER.info("Successfully applied slot %s for %s: %.1f°C", 
                           time_slot, entity_id, target_slot.target_value)
            else:
                _LOGGER.error("Failed to apply slot %s for %s", time_slot, entity_id)
                
        except Exception as e:
            _LOGGER.error("Error in apply_slot service: %s", e)
    
    async def apply_grid_now_service(self, call: ServiceCall) -> None:
        """
        Handle the apply_grid_now service call.
        
        Implements requirements 6.1, 6.2:
        - 6.1: Immediate full schedule application service
        - 6.2: Evaluate current time and presence, then apply appropriate schedule
        """
        try:
            # Extract and validate parameters
            entity_id = call.data.get("entity_id")
            force = call.data.get("force", False)
            
            if not entity_id:
                _LOGGER.error("apply_grid_now service: entity_id is required")
                return
            
            _LOGGER.info("Apply grid now service called: entity=%s, force=%s", entity_id, force)
            
            # Apply current schedule (Requirement 6.2)
            success = await self.apply_schedule(entity_id, force)
            
            if success:
                _LOGGER.info("Successfully applied current schedule for %s", entity_id)
            else:
                _LOGGER.warning("Failed to apply current schedule for %s", entity_id)
                
        except Exception as e:
            _LOGGER.error("Error in apply_grid_now service: %s", e)
    
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