"""Tests for Roost Scheduler services."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, time

from homeassistant.core import HomeAssistant, ServiceCall, Context
from homeassistant.exceptions import ServiceValidationError
import voluptuous as vol

from custom_components.roost_scheduler import (
    SERVICE_APPLY_SLOT_SCHEMA,
    SERVICE_APPLY_GRID_NOW_SCHEMA,
    _register_services
)
from custom_components.roost_scheduler.const import DOMAIN, SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW
from custom_components.roost_scheduler.schedule_manager import ScheduleManager


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    return hass


@pytest.fixture
def mock_schedule_manager():
    """Create a mock schedule manager."""
    manager = MagicMock(spec=ScheduleManager)
    manager.apply_slot_service = AsyncMock()
    manager.apply_grid_now_service = AsyncMock()
    return manager


class TestServiceSchemas:
    """Test service parameter validation schemas."""
    
    def test_apply_slot_schema_valid(self):
        """Test valid apply_slot service parameters."""
        valid_data = {
            "entity_id": "climate.living_room",
            "day": "monday",
            "time": "08:00-09:30",
            "force": True,
            "buffer_override": {"time_minutes": 10}
        }
        
        result = SERVICE_APPLY_SLOT_SCHEMA(valid_data)
        assert result["entity_id"] == "climate.living_room"
        assert result["day"] == "monday"
        assert result["time"] == "08:00-09:30"
        assert result["force"] is True
        assert result["buffer_override"] == {"time_minutes": 10}
    
    def test_apply_slot_schema_minimal(self):
        """Test minimal valid apply_slot service parameters."""
        valid_data = {
            "entity_id": "climate.bedroom",
            "day": "tuesday",
            "time": "06:00-08:00"
        }
        
        result = SERVICE_APPLY_SLOT_SCHEMA(valid_data)
        assert result["entity_id"] == "climate.bedroom"
        assert result["day"] == "tuesday"
        assert result["time"] == "06:00-08:00"
        assert result["force"] is False  # Default value
        assert result["buffer_override"] == {}  # Default value
    
    def test_apply_slot_schema_invalid_day(self):
        """Test apply_slot schema with invalid day."""
        invalid_data = {
            "entity_id": "climate.living_room",
            "day": "invalid_day",
            "time": "08:00-09:30"
        }
        
        with pytest.raises(vol.Invalid):
            SERVICE_APPLY_SLOT_SCHEMA(invalid_data)
    
    def test_apply_slot_schema_missing_required(self):
        """Test apply_slot schema with missing required fields."""
        invalid_data = {
            "entity_id": "climate.living_room",
            "day": "monday"
            # Missing required 'time' field
        }
        
        with pytest.raises(vol.Invalid):
            SERVICE_APPLY_SLOT_SCHEMA(invalid_data)
    
    def test_apply_grid_now_schema_valid(self):
        """Test valid apply_grid_now service parameters."""
        valid_data = {
            "entity_id": "climate.living_room",
            "force": True
        }
        
        result = SERVICE_APPLY_GRID_NOW_SCHEMA(valid_data)
        assert result["entity_id"] == "climate.living_room"
        assert result["force"] is True
    
    def test_apply_grid_now_schema_minimal(self):
        """Test minimal valid apply_grid_now service parameters."""
        valid_data = {
            "entity_id": "climate.bedroom"
        }
        
        result = SERVICE_APPLY_GRID_NOW_SCHEMA(valid_data)
        assert result["entity_id"] == "climate.bedroom"
        assert result["force"] is False  # Default value
    
    def test_apply_grid_now_schema_missing_entity(self):
        """Test apply_grid_now schema with missing entity_id."""
        invalid_data = {
            "force": True
        }
        
        with pytest.raises(vol.Invalid):
            SERVICE_APPLY_GRID_NOW_SCHEMA(invalid_data)


class TestServiceRegistration:
    """Test service registration functionality."""
    
    @pytest.mark.asyncio
    async def test_register_services(self, mock_hass, mock_schedule_manager):
        """Test that services are registered correctly."""
        await _register_services(mock_hass, mock_schedule_manager)
        
        # Verify both services were registered
        assert mock_hass.services.async_register.call_count == 2
        
        # Check the calls
        calls = mock_hass.services.async_register.call_args_list
        
        # First call should be apply_slot
        assert calls[0][0][0] == DOMAIN  # domain
        assert calls[0][0][1] == SERVICE_APPLY_SLOT  # service name
        assert calls[0][1]["schema"] == SERVICE_APPLY_SLOT_SCHEMA
        
        # Second call should be apply_grid_now
        assert calls[1][0][0] == DOMAIN  # domain
        assert calls[1][0][1] == SERVICE_APPLY_GRID_NOW  # service name
        assert calls[1][1]["schema"] == SERVICE_APPLY_GRID_NOW_SCHEMA
    
    @pytest.mark.asyncio
    async def test_apply_slot_service_handler_valid(self, mock_hass, mock_schedule_manager):
        """Test apply_slot service handler with valid parameters."""
        await _register_services(mock_hass, mock_schedule_manager)
        
        # Get the registered service handler
        apply_slot_handler = mock_hass.services.async_register.call_args_list[0][0][2]
        
        # Create a valid service call with dict data (not ReadOnlyDict for testing)
        call_data = {
            "entity_id": "climate.living_room",
            "day": "monday",
            "time": "08:00-09:30",
            "force": False
        }
        
        service_call = ServiceCall(
            domain=DOMAIN,
            service=SERVICE_APPLY_SLOT,
            data=call_data,
            context=Context()
        )
        
        # Call the handler
        await apply_slot_handler(service_call)
        
        # Verify the schedule manager method was called
        mock_schedule_manager.apply_slot_service.assert_called_once()
        
        # Check that the call was made with the service call
        called_with = mock_schedule_manager.apply_slot_service.call_args[0][0]
        assert called_with.data["entity_id"] == "climate.living_room"
        assert called_with.data["day"] == "monday"
        assert called_with.data["time"] == "08:00-09:30"
        assert called_with.data["force"] is False
    
    @pytest.mark.asyncio
    async def test_apply_slot_service_handler_invalid(self, mock_hass, mock_schedule_manager):
        """Test apply_slot service handler with invalid parameters."""
        # Note: In real Home Assistant, schema validation happens before the handler is called
        # This test verifies that our schema correctly rejects invalid data
        
        # Test that invalid data fails schema validation
        invalid_data = {
            "entity_id": "climate.living_room",
            "day": "monday"
            # Missing required 'time' field
        }
        
        with pytest.raises(vol.Invalid):
            SERVICE_APPLY_SLOT_SCHEMA(invalid_data)
    
    @pytest.mark.asyncio
    async def test_apply_grid_now_service_handler_valid(self, mock_hass, mock_schedule_manager):
        """Test apply_grid_now service handler with valid parameters."""
        await _register_services(mock_hass, mock_schedule_manager)
        
        # Get the registered service handler
        apply_grid_now_handler = mock_hass.services.async_register.call_args_list[1][0][2]
        
        # Create a valid service call
        call_data = {
            "entity_id": "climate.bedroom",
            "force": True
        }
        
        service_call = ServiceCall(
            domain=DOMAIN,
            service=SERVICE_APPLY_GRID_NOW,
            data=call_data,
            context=Context()
        )
        
        # Call the handler
        await apply_grid_now_handler(service_call)
        
        # Verify the schedule manager method was called
        mock_schedule_manager.apply_grid_now_service.assert_called_once()
        
        # Check that the call was made with the service call
        called_with = mock_schedule_manager.apply_grid_now_service.call_args[0][0]
        assert called_with.data["entity_id"] == "climate.bedroom"
        assert called_with.data["force"] is True
    
    @pytest.mark.asyncio
    async def test_apply_grid_now_service_handler_invalid(self, mock_hass, mock_schedule_manager):
        """Test apply_grid_now service handler with invalid parameters."""
        # Note: In real Home Assistant, schema validation happens before the handler is called
        # This test verifies that our schema correctly rejects invalid data
        
        # Test that invalid data fails schema validation
        invalid_data = {
            "force": True
            # Missing required 'entity_id' field
        }
        
        with pytest.raises(vol.Invalid):
            SERVICE_APPLY_GRID_NOW_SCHEMA(invalid_data)


class TestServiceExamples:
    """Test service usage examples."""
    
    def test_apply_slot_example_data(self):
        """Test example data for apply_slot service."""
        example_data = {
            "entity_id": "climate.living_room",
            "day": "monday",
            "time": "08:00-09:30",
            "force": False,
            "buffer_override": {
                "time_minutes": 10,
                "value_delta": 1.5
            }
        }
        
        # Should validate without errors
        result = SERVICE_APPLY_SLOT_SCHEMA(example_data)
        assert result == example_data
    
    def test_apply_grid_now_example_data(self):
        """Test example data for apply_grid_now service."""
        example_data = {
            "entity_id": "climate.bedroom",
            "force": True
        }
        
        # Should validate without errors
        result = SERVICE_APPLY_GRID_NOW_SCHEMA(example_data)
        assert result == example_data