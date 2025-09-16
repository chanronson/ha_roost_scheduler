"""
Roost Scheduler - A HACS-compatible Home Assistant custom integration.

Provides grid-based scheduling interface with intelligent buffering and presence-aware automation.
"""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW, WEEKDAYS
from .schedule_manager import ScheduleManager
from .storage import StorageService

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []

# Service schemas for parameter validation
SERVICE_APPLY_SLOT_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("day"): vol.In(WEEKDAYS),
    vol.Required("time"): cv.string,
    vol.Optional("force", default=False): cv.boolean,
    vol.Optional("buffer_override", default={}): dict,
})

SERVICE_APPLY_GRID_NOW_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Optional("force", default=False): cv.boolean,
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Roost Scheduler integration."""
    _LOGGER.debug("Setting up Roost Scheduler integration")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roost Scheduler from a config entry."""
    _LOGGER.info("Setting up Roost Scheduler config entry: %s", entry.entry_id)
    
    # Initialize storage service
    storage_service = StorageService(hass, entry.entry_id)
    
    # Initialize presence manager and buffer manager
    from .presence_manager import PresenceManager
    from .buffer_manager import BufferManager
    
    presence_manager = PresenceManager(hass, storage_service)
    buffer_manager = BufferManager(hass, storage_service)
    
    # Initialize schedule manager with all dependencies
    schedule_manager = ScheduleManager(hass, storage_service, presence_manager, buffer_manager)
    
    # Store services in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "storage_service": storage_service,
        "schedule_manager": schedule_manager,
        "presence_manager": presence_manager,
        "buffer_manager": buffer_manager,
    }
    
    # Load existing schedules
    await storage_service.load_schedules()
    
    # Register services
    await _register_services(hass, schedule_manager)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Roost Scheduler config entry: %s", entry.entry_id)
    
    # Clean up data
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return True


async def _register_services(hass: HomeAssistant, schedule_manager: ScheduleManager) -> None:
    """Register Roost Scheduler services with parameter validation."""
    
    async def apply_slot_service(call: ServiceCall) -> None:
        """Handle apply_slot service call with validation."""
        try:
            # The schema validation is handled by Home Assistant when we register with schema
            await schedule_manager.apply_slot_service(call)
            
        except Exception as e:
            _LOGGER.error("Error in apply_slot service: %s", e)
            raise
    
    async def apply_grid_now_service(call: ServiceCall) -> None:
        """Handle apply_grid_now service call with validation."""
        try:
            # The schema validation is handled by Home Assistant when we register with schema
            await schedule_manager.apply_grid_now_service(call)
            
        except Exception as e:
            _LOGGER.error("Error in apply_grid_now service: %s", e)
            raise
    
    # Register services with schemas
    hass.services.async_register(
        DOMAIN, 
        SERVICE_APPLY_SLOT, 
        apply_slot_service,
        schema=SERVICE_APPLY_SLOT_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_APPLY_GRID_NOW, 
        apply_grid_now_service,
        schema=SERVICE_APPLY_GRID_NOW_SCHEMA
    )
    
    _LOGGER.info("Registered Roost Scheduler services: %s, %s", 
                SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW)