"""Tests for integration setup error handling and recovery."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler import async_setup_entry
from custom_components.roost_scheduler.const import DOMAIN


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.options = {}
    return entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {}
    hass.services = Mock()
    hass.services.has_service = Mock(return_value=True)
    hass.services.async_register = Mock()
    hass.bus = Mock()
    hass.bus.async_fire = Mock()
    hass.components = Mock()
    hass.components.websocket_api = Mock()
    hass.components.websocket_api.async_register_command = Mock()
    hass.config = Mock()
    hass.config.components = ["frontend", "websocket_api"]
    hass.config.as_dict = Mock(return_value={"version": "2024.1.0"})
    return hass


class TestIntegrationSetupErrorHandling:
    """Test integration setup error handling and recovery."""

    @pytest.mark.asyncio
    async def test_successful_setup(self, mock_hass, mock_config_entry):
        """Test successful setup with all components working."""
        with patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws:
            
            # Setup mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance
            
            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance
            
            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            
            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            
            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance
            
            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)
            
            # Verify success
            assert result is True
            
            # Verify data was stored
            assert DOMAIN in mock_hass.data
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            assert "storage_service" in entry_data
            assert "schedule_manager" in entry_data
            assert "presence_manager" in entry_data
            assert "buffer_manager" in entry_data
            assert "setup_diagnostics" in entry_data

    @pytest.mark.asyncio
    async def test_logging_manager_failure_continues_setup(self, mock_hass, mock_config_entry):
        """Test that logging manager failure doesn't prevent setup."""
        with patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws:
            
            # Make logging manager fail
            mock_logging_mgr.side_effect = Exception("Logging setup failed")
            
            # Setup other mocks
            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance
            
            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            
            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            
            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance
            
            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)
            
            # Verify setup continues and succeeds
            assert result is True
            
            # Verify logging manager is None in stored data
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            assert entry_data["logging_manager"] is None
            
            # Verify diagnostics recorded the failure
            diagnostics = entry_data["setup_diagnostics"]
            assert any(comp["component"] == "logging_manager" for comp in diagnostics["components_failed"])
            assert "Logging manager initialization failed" in diagnostics["warnings"]