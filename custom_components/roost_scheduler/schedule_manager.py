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
        """Apply the current schedule for an entity."""
        # This will be implemented in later tasks
        # For now, just log the action
        _LOGGER.info("Apply schedule called for %s (force=%s)", entity_id, force)
        return True
    
    async def update_slot(self, entity_id: str, day: str, time: str, target: Dict[str, Any]) -> None:
        """Update a specific schedule slot."""
        # This will be implemented in later tasks
        _LOGGER.info("Update slot called for %s on %s at %s", entity_id, day, time)
    
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
        """Handle the apply_slot service call."""
        entity_id = call.data.get("entity_id")
        day = call.data.get("day")
        time_slot = call.data.get("time")
        force = call.data.get("force", False)
        
        _LOGGER.info("Apply slot service called: entity=%s, day=%s, time=%s, force=%s", 
                    entity_id, day, time_slot, force)
        
        # Implementation will be added in later tasks
    
    async def apply_grid_now_service(self, call: ServiceCall) -> None:
        """Handle the apply_grid_now service call."""
        entity_id = call.data.get("entity_id")
        force = call.data.get("force", False)
        
        _LOGGER.info("Apply grid now service called: entity=%s, force=%s", entity_id, force)
        
        # Implementation will be added in later tasks
    
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