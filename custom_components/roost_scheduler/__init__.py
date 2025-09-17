"""
Roost Scheduler - A HACS-compatible Home Assistant custom integration.

Provides grid-based scheduling interface with intelligent buffering and presence-aware automation.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv
from homeassistant.components import websocket_api

from .const import DOMAIN, SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW, SERVICE_MIGRATE_RESOLUTION, WEEKDAYS
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

SERVICE_MIGRATE_RESOLUTION_SCHEMA = vol.Schema({
    vol.Required("resolution_minutes"): vol.In([15, 30, 60]),
    vol.Optional("preview", default=True): cv.boolean,
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
    
    # Register WebSocket API handlers
    _register_websocket_handlers(hass)
    
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
    
    async def migrate_resolution_service(call: ServiceCall) -> None:
        """Handle migrate_resolution service call with validation."""
        try:
            # The schema validation is handled by Home Assistant when we register with schema
            await schedule_manager.migrate_resolution_service(call)
            
        except Exception as e:
            _LOGGER.error("Error in migrate_resolution service: %s", e)
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
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_MIGRATE_RESOLUTION, 
        migrate_resolution_service,
        schema=SERVICE_MIGRATE_RESOLUTION_SCHEMA
    )
    
    _LOGGER.info("Registered Roost Scheduler services: %s, %s, %s", 
                SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW, SERVICE_MIGRATE_RESOLUTION)


def _register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register WebSocket API handlers for real-time communication."""
    
    @websocket_api.websocket_command({
        vol.Required("type"): "roost_scheduler/get_schedule_grid",
        vol.Required("entity_id"): cv.entity_id,
    })
    @websocket_api.async_response
    async def handle_get_schedule_grid(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
        """Handle get_schedule_grid WebSocket command."""
        try:
            entity_id = msg["entity_id"]
            
            # Find the schedule manager for this entity
            schedule_manager = None
            for entry_id, data in hass.data.get(DOMAIN, {}).items():
                if isinstance(data, dict) and "schedule_manager" in data:
                    schedule_manager = data["schedule_manager"]
                    break
            
            if not schedule_manager:
                connection.send_error(msg["id"], "no_schedule_manager", "No schedule manager found")
                return
            
            # Get schedule grid for both modes
            home_grid = await schedule_manager.get_schedule_grid(entity_id, "home")
            away_grid = await schedule_manager.get_schedule_grid(entity_id, "away")
            
            # Get current presence mode
            current_mode = await schedule_manager.presence_manager.get_current_mode()
            
            connection.send_result(msg["id"], {
                "schedules": {
                    "home": home_grid,
                    "away": away_grid
                },
                "current_mode": current_mode,
                "entity_id": entity_id
            })
            
        except Exception as e:
            _LOGGER.error("Error handling get_schedule_grid: %s", e)
            connection.send_error(msg["id"], "get_schedule_error", str(e))
    
    @websocket_api.websocket_command({
        vol.Required("type"): "roost_scheduler/update_schedule",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("mode"): vol.In(["home", "away"]),
        vol.Required("changes"): [dict],
        vol.Optional("update_id"): str,
        vol.Optional("conflict_resolution"): dict,
    })
    @websocket_api.async_response
    async def handle_update_schedule(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
        """Handle update_schedule WebSocket command."""
        try:
            entity_id = msg["entity_id"]
            mode = msg["mode"]
            changes = msg["changes"]
            update_id = msg.get("update_id")
            conflict_resolution = msg.get("conflict_resolution", {"strategy": "server_wins"})
            
            # Find the schedule manager for this entity
            schedule_manager = None
            for entry_id, data in hass.data.get(DOMAIN, {}).items():
                if isinstance(data, dict) and "schedule_manager" in data:
                    schedule_manager = data["schedule_manager"]
                    break
            
            if not schedule_manager:
                connection.send_error(msg["id"], "no_schedule_manager", "No schedule manager found")
                return
            
            # Check for conflicts if update_id is provided
            conflicts = []
            if update_id:
                conflicts = await _check_for_conflicts(schedule_manager, entity_id, mode, changes, update_id)
            
            # Handle conflicts based on resolution strategy
            if conflicts and conflict_resolution["strategy"] != "client_wins":
                if conflict_resolution["strategy"] == "server_wins":
                    # Don't apply changes, return current server state
                    current_grid = await schedule_manager.get_schedule_grid(entity_id, mode)
                    connection.send_result(msg["id"], {
                        "success": False,
                        "conflict": True,
                        "server_state": current_grid,
                        "conflicts": conflicts
                    })
                    return
                elif conflict_resolution["strategy"] == "prompt_user":
                    # Return conflict information for user resolution
                    connection.send_result(msg["id"], {
                        "success": False,
                        "conflict": True,
                        "conflicts": conflicts,
                        "requires_resolution": True
                    })
                    return
            
            # Apply each change
            successful_changes = []
            failed_changes = []
            
            for change in changes:
                try:
                    success = await schedule_manager.update_slot(
                        entity_id=entity_id,
                        mode=mode,
                        day=change["day"],
                        time=change["time"],
                        target={"temperature": change["value"]}
                    )
                    if success:
                        successful_changes.append(change)
                    else:
                        failed_changes.append(change)
                except Exception as e:
                    _LOGGER.error("Failed to apply change %s: %s", change, e)
                    failed_changes.append(change)
            
            # Broadcast the update to all connected clients (excluding the sender)
            hass.bus.async_fire(f"{DOMAIN}_schedule_updated", {
                "entity_id": entity_id,
                "mode": mode,
                "changes": successful_changes,
                "update_id": update_id,
                "timestamp": datetime.now().isoformat(),
                "sender_connection_id": connection.id if hasattr(connection, 'id') else None
            })
            
            connection.send_result(msg["id"], {
                "success": len(failed_changes) == 0,
                "successful_changes": successful_changes,
                "failed_changes": failed_changes,
                "update_id": update_id
            })
            
        except Exception as e:
            _LOGGER.error("Error handling update_schedule: %s", e)
            connection.send_error(msg["id"], "update_schedule_error", str(e))
    
    @websocket_api.websocket_command({
        vol.Required("type"): "roost_scheduler/subscribe_updates",
        vol.Required("entity_id"): cv.entity_id,
    })
    @websocket_api.require_admin  # Require admin for subscriptions
    async def handle_subscribe_updates(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
        """Handle subscribe_updates WebSocket command for real-time updates."""
        entity_id = msg["entity_id"]
        
        def forward_schedule_update(event):
            """Forward schedule update events to WebSocket client."""
            if event.data.get("entity_id") == entity_id:
                connection.send_message({
                    "id": msg["id"],
                    "type": "event",
                    "event": {
                        "type": "schedule_updated",
                        "data": event.data
                    }
                })
        
        def forward_presence_update(event):
            """Forward presence mode changes to WebSocket client."""
            connection.send_message({
                "id": msg["id"],
                "type": "event", 
                "event": {
                    "type": "presence_changed",
                    "data": event.data
                }
            })
        
        # Subscribe to relevant events
        remove_schedule_listener = hass.bus.async_listen(
            f"{DOMAIN}_schedule_updated", forward_schedule_update
        )
        remove_presence_listener = hass.bus.async_listen(
            f"{DOMAIN}_presence_changed", forward_presence_update
        )
        
        # Store cleanup function for when connection closes
        def cleanup():
            remove_schedule_listener()
            remove_presence_listener()
        
        connection.subscriptions[msg["id"]] = cleanup
        
        connection.send_result(msg["id"], {"subscribed": True})
    
    # Register all handlers
    hass.components.websocket_api.async_register_command(handle_get_schedule_grid)
    hass.components.websocket_api.async_register_command(handle_update_schedule)
    hass.components.websocket_api.async_register_command(handle_subscribe_updates)
    
    _LOGGER.info("Registered Roost Scheduler WebSocket handlers")


async def _check_for_conflicts(schedule_manager, entity_id: str, mode: str, changes: list, update_id: str) -> list:
    """Check for conflicts between proposed changes and current server state."""
    conflicts = []
    
    try:
        # Get current schedule grid
        current_grid = await schedule_manager.get_schedule_grid(entity_id, mode)
        
        # Check each proposed change against current state
        for change in changes:
            day = change["day"]
            time = change["time"]
            proposed_value = change["value"]
            
            # Find current value for this slot
            current_value = None
            if day in current_grid:
                for slot in current_grid[day]:
                    if slot.get("start_time") <= time <= slot.get("end_time", time):
                        current_value = slot.get("target_value")
                        break
            
            # Simple conflict detection: if values differ significantly
            if current_value is not None and abs(current_value - proposed_value) > 0.1:
                conflicts.append({
                    "day": day,
                    "time": time,
                    "proposed_value": proposed_value,
                    "current_value": current_value,
                    "update_id": update_id
                })
    
    except Exception as e:
        _LOGGER.error("Error checking for conflicts: %s", e)
    
    return conflicts