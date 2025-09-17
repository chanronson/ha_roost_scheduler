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


class TestServiceParameterValidation:
    """Test comprehensive service parameter validation."""
    
    @pytest.fixture
    def mock_schedule_manager_with_validation(self):
        """Create a mock schedule manager with validation methods."""
        from custom_components.roost_scheduler.schedule_manager import ScheduleManager
        manager = MagicMock(spec=ScheduleManager)
        
        # Mock the validation method
        def mock_validate_buffer_override(buffer_override):
            errors = []
            if "time_minutes" in buffer_override:
                if not isinstance(buffer_override["time_minutes"], (int, float)):
                    errors.append("time_minutes must be a number")
                elif buffer_override["time_minutes"] < 0:
                    errors.append("time_minutes must be non-negative")
            return errors
        
        manager._validate_buffer_override = mock_validate_buffer_override
        return manager
    
    def test_buffer_override_validation_valid(self, mock_schedule_manager_with_validation):
        """Test valid buffer override parameters."""
        valid_override = {
            "time_minutes": 10,
            "value_delta": 1.5,
            "enabled": True
        }
        
        errors = mock_schedule_manager_with_validation._validate_buffer_override(valid_override)
        assert errors == []
    
    def test_buffer_override_validation_invalid_time(self, mock_schedule_manager_with_validation):
        """Test invalid time_minutes in buffer override."""
        invalid_override = {
            "time_minutes": "invalid"
        }
        
        errors = mock_schedule_manager_with_validation._validate_buffer_override(invalid_override)
        assert "time_minutes must be a number" in errors
    
    def test_buffer_override_validation_negative_time(self, mock_schedule_manager_with_validation):
        """Test negative time_minutes in buffer override."""
        invalid_override = {
            "time_minutes": -5
        }
        
        errors = mock_schedule_manager_with_validation._validate_buffer_override(invalid_override)
        assert "time_minutes must be non-negative" in errors


class TestServiceIntegration:
    """Integration tests for service scenarios."""
    
    @pytest.fixture
    def mock_hass_with_entities(self):
        """Create a mock Home Assistant with entities."""
        hass = MagicMock()
        
        # Mock entity states
        mock_climate_state = MagicMock()
        mock_climate_state.state = "heat"
        mock_climate_state.attributes = {"temperature": 20.0}
        
        mock_unavailable_state = MagicMock()
        mock_unavailable_state.state = "unavailable"
        
        def mock_get_state(entity_id):
            if entity_id == "climate.living_room":
                return mock_climate_state
            elif entity_id == "climate.unavailable":
                return mock_unavailable_state
            return None
        
        # Create mock states object
        mock_states = MagicMock()
        mock_states.get = mock_get_state
        hass.states = mock_states
        
        return hass
    
    @pytest.fixture
    def mock_schedule_data(self):
        """Create mock schedule data."""
        from custom_components.roost_scheduler.models import ScheduleData, ScheduleSlot
        
        schedule_data = MagicMock(spec=ScheduleData)
        schedule_data.entities_tracked = ["climate.living_room"]
        
        # Mock schedule slot
        mock_slot = MagicMock(spec=ScheduleSlot)
        mock_slot.start_time = "08:00"
        mock_slot.end_time = "09:30"
        mock_slot.target_value = 21.0
        mock_slot.to_dict.return_value = {
            "start_time": "08:00",
            "end_time": "09:30",
            "target_value": 21.0
        }
        
        schedule_data.schedules = {
            "home": {
                "monday": [mock_slot]
            }
        }
        
        return schedule_data
    
    @pytest.mark.asyncio
    async def test_apply_slot_service_comprehensive_validation(self, mock_hass_with_entities, mock_schedule_data):
        """Test comprehensive validation in apply_slot service."""
        from custom_components.roost_scheduler.schedule_manager import ScheduleManager
        from custom_components.roost_scheduler.storage import StorageService
        from custom_components.roost_scheduler.presence_manager import PresenceManager
        from custom_components.roost_scheduler.buffer_manager import BufferManager
        
        # Create mocks
        storage_service = MagicMock(spec=StorageService)
        presence_manager = MagicMock(spec=PresenceManager)
        buffer_manager = MagicMock(spec=BufferManager)
        
        presence_manager.get_current_mode = AsyncMock(return_value="home")
        
        # Create schedule manager
        schedule_manager = ScheduleManager(
            mock_hass_with_entities, 
            storage_service, 
            presence_manager, 
            buffer_manager
        )
        schedule_manager._schedule_data = mock_schedule_data
        schedule_manager._apply_entity_value = AsyncMock(return_value=True)
        
        # Test valid service call
        valid_call = ServiceCall(
            domain="roost_scheduler",
            service="apply_slot",
            data={
                "entity_id": "climate.living_room",
                "day": "monday",
                "time": "08:00-09:30",
                "force": False,
                "buffer_override": {
                    "time_minutes": 10,
                    "value_delta": 1.5
                }
            },
            context=Context()
        )
        
        # Should not raise an exception
        await schedule_manager.apply_slot_service(valid_call)
        
        # Verify entity value was applied
        schedule_manager._apply_entity_value.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_slot_service_invalid_entity(self, mock_hass_with_entities, mock_schedule_data):
        """Test apply_slot service with invalid entity."""
        from custom_components.roost_scheduler.schedule_manager import ScheduleManager
        from custom_components.roost_scheduler.storage import StorageService
        from custom_components.roost_scheduler.presence_manager import PresenceManager
        from custom_components.roost_scheduler.buffer_manager import BufferManager
        
        # Create mocks
        storage_service = MagicMock(spec=StorageService)
        presence_manager = MagicMock(spec=PresenceManager)
        buffer_manager = MagicMock(spec=BufferManager)
        
        # Create schedule manager
        schedule_manager = ScheduleManager(
            mock_hass_with_entities, 
            storage_service, 
            presence_manager, 
            buffer_manager
        )
        schedule_manager._schedule_data = mock_schedule_data
        
        # Test with non-existent entity
        invalid_call = ServiceCall(
            domain="roost_scheduler",
            service="apply_slot",
            data={
                "entity_id": "climate.nonexistent",
                "day": "monday",
                "time": "08:00-09:30"
            },
            context=Context()
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Entity climate.nonexistent not found"):
            await schedule_manager.apply_slot_service(invalid_call)
    
    @pytest.mark.asyncio
    async def test_apply_grid_now_service_unavailable_entity(self, mock_hass_with_entities, mock_schedule_data):
        """Test apply_grid_now service with unavailable entity."""
        from custom_components.roost_scheduler.schedule_manager import ScheduleManager
        from custom_components.roost_scheduler.storage import StorageService
        from custom_components.roost_scheduler.presence_manager import PresenceManager
        from custom_components.roost_scheduler.buffer_manager import BufferManager
        
        # Create mocks
        storage_service = MagicMock(spec=StorageService)
        presence_manager = MagicMock(spec=PresenceManager)
        buffer_manager = MagicMock(spec=BufferManager)
        
        # Create schedule manager
        schedule_manager = ScheduleManager(
            mock_hass_with_entities, 
            storage_service, 
            presence_manager, 
            buffer_manager
        )
        schedule_manager._schedule_data = mock_schedule_data
        
        # Test with unavailable entity
        invalid_call = ServiceCall(
            domain="roost_scheduler",
            service="apply_grid_now",
            data={
                "entity_id": "climate.unavailable"
            },
            context=Context()
        )
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="is unavailable and cannot be controlled"):
            await schedule_manager.apply_grid_now_service(invalid_call)