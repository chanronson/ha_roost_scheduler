"""Schedule management for the Roost Scheduler integration."""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from .models import ScheduleSlot, ScheduleData
from .storage import StorageService
from .const import MODE_HOME, MODE_AWAY, WEEKDAYS

_LOGGER = logging.getLogger(__name__)


class ScheduleManager:
    """Manages schedule evaluation and execution."""
    
    def __init__(self, hass: HomeAssistant, storage_service: StorageService) -> None:
        """Initialize the schedule manager."""
        self.hass = hass
        self.storage_service = storage_service
        self._schedule_data: Optional[ScheduleData] = None
    
    async def evaluate_current_slot(self, entity_id: str, mode: str) -> Optional[ScheduleSlot]:
        """Evaluate the current schedule slot for an entity and mode."""
        if not self._schedule_data:
            await self._load_schedule_data()
        
        if not self._schedule_data:
            _LOGGER.warning("No schedule data available")
            return None
        
        now = datetime.now()
        current_day = WEEKDAYS[now.weekday()]
        current_time = now.time()
        
        # Get schedules for the current mode and day
        mode_schedules = self._schedule_data.schedules.get(mode, {})
        day_schedules = mode_schedules.get(current_day, [])
        
        # Find the slot that contains the current time
        for slot in day_schedules:
            if self._time_in_slot(current_time, slot.start_time, slot.end_time):
                return slot
        
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
        """Get the schedule grid for display in the frontend."""
        if not self._schedule_data:
            await self._load_schedule_data()
        
        if not self._schedule_data:
            return {}
        
        mode_schedules = self._schedule_data.schedules.get(mode, {})
        
        # Convert to grid format
        grid = {}
        for day in WEEKDAYS:
            day_slots = mode_schedules.get(day, [])
            grid[day] = [slot.to_dict() for slot in day_slots]
        
        return {
            "mode": mode,
            "entity_id": entity_id,
            "grid": grid,
            "resolution_minutes": self._schedule_data.ui.get("resolution_minutes", 30)
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
        data = await self.storage_service.load_schedules()
        if data:
            self._schedule_data = ScheduleData.from_dict(data)