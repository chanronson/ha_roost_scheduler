"""
Roost Scheduler - A HACS-compatible Home Assistant custom integration.

Provides grid-based scheduling interface with intelligent buffering and presence-aware automation.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .schedule_manager import ScheduleManager
from .storage import StorageService

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Roost Scheduler integration."""
    _LOGGER.debug("Setting up Roost Scheduler integration")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roost Scheduler from a config entry."""
    _LOGGER.info("Setting up Roost Scheduler config entry: %s", entry.entry_id)
    
    # Initialize storage service
    storage_service = StorageService(hass, entry.entry_id)
    
    # Initialize schedule manager
    schedule_manager = ScheduleManager(hass, storage_service)
    
    # Store services in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "storage_service": storage_service,
        "schedule_manager": schedule_manager,
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
    """Register Roost Scheduler services."""
    async def apply_slot_service(call) -> None:
        """Handle apply_slot service call."""
        await schedule_manager.apply_slot_service(call)
    
    async def apply_grid_now_service(call) -> None:
        """Handle apply_grid_now service call."""
        await schedule_manager.apply_grid_now_service(call)
    
    hass.services.async_register(DOMAIN, "apply_slot", apply_slot_service)
    hass.services.async_register(DOMAIN, "apply_grid_now", apply_grid_now_service)
    
    _LOGGER.debug("Registered Roost Scheduler services")