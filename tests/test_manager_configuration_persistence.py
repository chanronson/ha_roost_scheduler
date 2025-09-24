"""Tests for manager configuration persistence and event emission."""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, call

from homeassistant.core import HomeAssistant, State
from homeassistant.const import STATE_HOME, STATE_NOT_HOME

from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.models import (
    PresenceConfig, BufferConfig, GlobalBufferConfig, ScheduleData
)
from custom_components.roost_scheduler.const import (
    MODE_HOME, MODE_AWAY, DEFAULT_PRESENCE_TIMEOUT_SECONDS,
    DEFAULT_BUFFER_TIME_MINUTES, DEFAULT_BUFFER_VALUE_DELTA
)

# Mark all async tests in this module
pytestmark = pytest.mark.asyncio


@pytest.fixture
def hass():
    """Create a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.states = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    hass.bus = Mock()
    hass.bus.async_fire = AsyncMock(return_value=None)
    return hass


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service."""
    storage = Mock()
    storage.load_schedules = AsyncMock()
    storage.save_schedules = AsyncMock()
    return storage


@pytest.fixture
def presence_manager_with_storage(hass, mock_storage_service):
    """Create a PresenceManager with storage service."""
    return PresenceManager(hass, mock_storage_service)


@pytest.fixture
def buffer_manager_with_storage(hass, mock_storage_service):
    """Create a BufferManager with storage service."""
    return BufferManager(hass, mock_storage_service)


class TestPresenceManagerConfigurationPersistence:
    """Test PresenceManager configuration persistence and event emission."""
    
    async def test_configure_presence_saves_to_storage(self, presence_manager_with_storage, mock_storage_service, hass):
        """Test that configure_presence saves configuration to storage."""
        # Mock entity states
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_HOME
        hass.states.get.return_value = phone_state
        
        # Mock storage service
        mock_storage_service.load_schedules.return_value = None
        
        # Configure presence
        await presence_manager_with_storage.configure_presence(
            entities=["device_tracker.phone"],
            rule="anyone_home",
            timeout_seconds=900
        )
        
        # Verify save_configuration was called
        mock_storage_service.save_schedules.assert_called_once()
        
        # Verify configuration was updated
        assert presence_manager_with_storage._presence_entities == ["device_tracker.phone"]
        assert presence_manager_with_storage._presence_rule == "anyone_home"
        assert presence_manager_with_storage._timeout_seconds == 900
    
    async def test_configure_presence_emits_event(self, presence_manager_with_storage, mock_storage_service, hass):
        """Test that configure_presence emits configuration change event."""
        # Mock entity states
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_HOME
        hass.states.get.return_value = phone_state
        
        # Mock storage service
        mock_storage_service.load_schedules.return_value = None
        
        # Configure presence
        await presence_manager_with_storage.configure_presence(
            entities=["device_tracker.phone"],
            rule="anyone_home",
            timeout_seconds=900
        )
        
        # Verify event was emitted
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        
        assert call_args[0][0] == "roost_scheduler_config_changed"
        event_data = call_args[0][1]
        assert event_data["manager"] == "presence"
        assert event_data["operation"] == "configure_presence"
        assert "timestamp" in event_data
        assert "old_config" in event_data
        assert "new_config" in event_data
        assert "changes" in event_data
    
    async def test_configure_presence_validation_error_reverts(self, presence_manager_with_storage, mock_storage_service, hass):
        """Test that configuration errors revert changes."""
        # Set initial configuration
        presence_manager_with_storage._presence_entities = ["device_tracker.existing"]
        presence_manager_with_storage._presence_rule = "everyone_home"
        
        # Mock storage service to raise error
        mock_storage_service.save_schedules.side_effect = Exception("Storage error")
        
        # Try to configure with invalid data - should raise exception
        with pytest.raises(Exception):
            await presence_manager_with_storage.configure_presence(
                entities=["device_tracker.phone"],
                rule="anyone_home",
                timeout_seconds=900
            )
        
        # Verify configuration was reverted
        assert presence_manager_with_storage._presence_entities == ["device_tracker.existing"]
        assert presence_manager_with_storage._presence_rule == "everyone_home"
    
    async def test_update_presence_entities_saves_to_storage(self, presence_manager_with_storage, mock_storage_service, hass):
        """Test that update_presence_entities saves to storage."""
        # Mock entity states
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_HOME
        hass.states.get.return_value = phone_state
        
        # Mock storage service
        mock_storage_service.load_schedules.return_value = None
        
        # Update entities
        await presence_manager_with_storage.update_presence_entities(["device_tracker.phone1", "device_tracker.phone2"])
        
        # Verify save_configuration was called
        mock_storage_service.save_schedules.assert_called_once()
        
        # Verify configuration was updated
        assert presence_manager_with_storage._presence_entities == ["device_tracker.phone1", "device_tracker.phone2"]
    
    async def test_update_presence_entities_emits_event(self, presence_manager_with_storage, mock_storage_service, hass):
        """Test that update_presence_entities emits configuration change event."""
        # Mock entity states
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_HOME
        hass.states.get.return_value = phone_state
        
        # Mock storage service
        mock_storage_service.load_schedules.return_value = None
        
        # Update entities
        await presence_manager_with_storage.update_presence_entities(["device_tracker.phone"])
        
        # Verify event was emitted
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        
        assert call_args[0][0] == "roost_scheduler_config_changed"
        event_data = call_args[0][1]
        assert event_data["manager"] == "presence"
        assert event_data["operation"] == "update_presence_entities"
    
    async def test_update_presence_entities_validation_error_reverts(self, presence_manager_with_storage, mock_storage_service):
        """Test that validation errors revert entity changes."""
        # Set initial configuration
        presence_manager_with_storage._presence_entities = ["device_tracker.existing"]
        
        # Try to update with invalid entity ID
        with pytest.raises(ValueError):
            await presence_manager_with_storage.update_presence_entities(["invalid_entity"])
        
        # Verify configuration was reverted
        assert presence_manager_with_storage._presence_entities == ["device_tracker.existing"]
    
    async def test_update_presence_rule_saves_to_storage(self, presence_manager_with_storage, mock_storage_service):
        """Test that update_presence_rule saves to storage."""
        # Mock storage service
        mock_storage_service.load_schedules.return_value = None
        
        # Update rule
        await presence_manager_with_storage.update_presence_rule("everyone_home")
        
        # Verify save_configuration was called
        mock_storage_service.save_schedules.assert_called_once()
        
        # Verify configuration was updated
        assert presence_manager_with_storage._presence_rule == "everyone_home"
    
    async def test_update_presence_rule_emits_event(self, presence_manager_with_storage, mock_storage_service, hass):
        """Test that update_presence_rule emits configuration change event."""
        # Mock storage service
        mock_storage_service.load_schedules.return_value = None
        
        # Update rule
        await presence_manager_with_storage.update_presence_rule("everyone_home")
        
        # Verify event was emitted
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        
        assert call_args[0][0] == "roost_scheduler_config_changed"
        event_data = call_args[0][1]
        assert event_data["manager"] == "presence"
        assert event_data["operation"] == "update_presence_rule"
    
    async def test_update_presence_rule_validation_error_reverts(self, presence_manager_with_storage, mock_storage_service):
        """Test that validation errors revert rule changes."""
        # Set initial configuration
        presence_manager_with_storage._presence_rule = "anyone_home"
        
        # Try to update with invalid rule
        with pytest.raises(ValueError):
            await presence_manager_with_storage.update_presence_rule("invalid_rule")
        
        # Verify configuration was reverted
        assert presence_manager_with_storage._presence_rule == "anyone_home"


class TestBufferManagerConfigurationPersistence:
    """Test BufferManager configuration persistence and event emission."""
    
    async def test_update_global_buffer_saves_to_storage(self, buffer_manager_with_storage, mock_storage_service):
        """Test that update_global_buffer saves configuration to storage."""
        # Mock storage service
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Create new buffer config
        new_config = BufferConfig(
            time_minutes=20,
            value_delta=3.0,
            enabled=True,
            apply_to="climate"
        )
        
        # Update global buffer
        await buffer_manager_with_storage.update_global_buffer(new_config)
        
        # Verify save_configuration was called
        mock_storage_service.save_schedules.assert_called_once()
        
        # Verify configuration was updated
        assert buffer_manager_with_storage._global_buffer.time_minutes == 20
        assert buffer_manager_with_storage._global_buffer.value_delta == 3.0
    
    async def test_update_global_buffer_emits_event(self, buffer_manager_with_storage, mock_storage_service, hass):
        """Test that update_global_buffer emits configuration change event."""
        # Mock storage service
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Create new buffer config
        new_config = BufferConfig(
            time_minutes=20,
            value_delta=3.0,
            enabled=True,
            apply_to="climate"
        )
        
        # Update global buffer
        await buffer_manager_with_storage.update_global_buffer(new_config)
        
        # Verify event was emitted
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        
        assert call_args[0][0] == "roost_scheduler_config_changed"
        event_data = call_args[0][1]
        assert event_data["manager"] == "buffer"
        assert event_data["operation"] == "update_global_buffer"
        assert "timestamp" in event_data
        assert "old_config" in event_data
        assert "new_config" in event_data
        assert "changes" in event_data
    
    async def test_update_global_buffer_validation_error_reverts(self, buffer_manager_with_storage, mock_storage_service):
        """Test that validation errors revert buffer changes."""
        # Set initial configuration
        old_config = BufferConfig(
            time_minutes=15,
            value_delta=2.0,
            enabled=True,
            apply_to="climate"
        )
        buffer_manager_with_storage._global_buffer = old_config
        
        # Create invalid buffer config
        invalid_config = BufferConfig(
            time_minutes=-5,  # Invalid negative value
            value_delta=2.0,
            enabled=True,
            apply_to="climate"
        )
        
        # Try to update with invalid config - should raise exception
        with pytest.raises(ValueError):
            await buffer_manager_with_storage.update_global_buffer(invalid_config)
        
        # Verify configuration was reverted
        assert buffer_manager_with_storage._global_buffer.time_minutes == 15
        assert buffer_manager_with_storage._global_buffer.value_delta == 2.0
    
    async def test_update_global_buffer_config_saves_to_storage(self, buffer_manager_with_storage, mock_storage_service):
        """Test that update_global_buffer_config saves to storage."""
        # Mock storage service
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Create new global buffer config
        new_config = GlobalBufferConfig(
            time_minutes=25,
            value_delta=4.0,
            enabled=True,
            apply_to="climate"
        )
        
        # Update global buffer config
        await buffer_manager_with_storage.update_global_buffer_config(new_config)
        
        # Verify save_configuration was called
        mock_storage_service.save_schedules.assert_called_once()
        
        # Verify configuration was updated
        assert buffer_manager_with_storage._global_buffer_config.time_minutes == 25
        assert buffer_manager_with_storage._global_buffer_config.value_delta == 4.0
    
    async def test_update_global_buffer_config_emits_event(self, buffer_manager_with_storage, mock_storage_service, hass):
        """Test that update_global_buffer_config emits configuration change event."""
        # Mock storage service
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Create new global buffer config
        new_config = GlobalBufferConfig(
            time_minutes=25,
            value_delta=4.0,
            enabled=True,
            apply_to="climate"
        )
        
        # Update global buffer config
        await buffer_manager_with_storage.update_global_buffer_config(new_config)
        
        # Verify event was emitted
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        
        assert call_args[0][0] == "roost_scheduler_config_changed"
        event_data = call_args[0][1]
        assert event_data["manager"] == "buffer"
        assert event_data["operation"] == "update_global_buffer_config"
    
    async def test_update_entity_buffer_config_saves_to_storage(self, buffer_manager_with_storage, mock_storage_service, hass):
        """Test that update_entity_buffer_config saves to storage."""
        # Mock entity state
        climate_state = Mock(spec=State)
        climate_state.domain = "climate"
        climate_state.state = "heat"
        hass.states.get.return_value = climate_state
        
        # Mock storage service
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Create entity-specific buffer config
        entity_config = BufferConfig(
            time_minutes=30,
            value_delta=1.5,
            enabled=True,
            apply_to="climate"
        )
        
        # Update entity buffer config
        await buffer_manager_with_storage.update_entity_buffer_config("climate.living_room", entity_config)
        
        # Verify save_configuration was called
        mock_storage_service.save_schedules.assert_called_once()
        
        # Verify configuration was updated
        assert "climate.living_room" in buffer_manager_with_storage._global_buffer_config.entity_overrides
        override_config = buffer_manager_with_storage._global_buffer_config.entity_overrides["climate.living_room"]
        assert override_config.time_minutes == 30
        assert override_config.value_delta == 1.5
    
    async def test_update_entity_buffer_config_emits_event(self, buffer_manager_with_storage, mock_storage_service, hass):
        """Test that update_entity_buffer_config emits configuration change event."""
        # Mock entity state
        climate_state = Mock(spec=State)
        climate_state.domain = "climate"
        climate_state.state = "heat"
        hass.states.get.return_value = climate_state
        
        # Mock storage service
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Create entity-specific buffer config
        entity_config = BufferConfig(
            time_minutes=30,
            value_delta=1.5,
            enabled=True,
            apply_to="climate"
        )
        
        # Update entity buffer config
        await buffer_manager_with_storage.update_entity_buffer_config("climate.living_room", entity_config)
        
        # Verify event was emitted
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        
        assert call_args[0][0] == "roost_scheduler_config_changed"
        event_data = call_args[0][1]
        assert event_data["manager"] == "buffer"
        assert event_data["operation"] == "update_entity_buffer_config"
        assert event_data["entity_id"] == "climate.living_room"
    
    async def test_update_entity_buffer_config_validation_error_reverts(self, buffer_manager_with_storage, mock_storage_service, hass):
        """Test that validation errors revert entity buffer changes."""
        # Mock entity state
        climate_state = Mock(spec=State)
        climate_state.domain = "climate"
        climate_state.state = "heat"
        hass.states.get.return_value = climate_state
        
        # Set initial configuration
        initial_config = BufferConfig(
            time_minutes=15,
            value_delta=2.0,
            enabled=True,
            apply_to="climate"
        )
        buffer_manager_with_storage._global_buffer_config.set_entity_override("climate.living_room", initial_config)
        
        # Create invalid buffer config
        invalid_config = BufferConfig(
            time_minutes=2000,  # Invalid - exceeds maximum
            value_delta=1.5,
            enabled=True,
            apply_to="climate"
        )
        
        # Try to update with invalid config - should raise exception
        with pytest.raises(ValueError):
            await buffer_manager_with_storage.update_entity_buffer_config("climate.living_room", invalid_config)
        
        # Verify configuration was reverted
        override_config = buffer_manager_with_storage._global_buffer_config.entity_overrides["climate.living_room"]
        assert override_config.time_minutes == 15
        assert override_config.value_delta == 2.0


class TestConfigurationChangeEvents:
    """Test configuration change event emission and data."""
    
    async def test_presence_config_change_event_data(self, presence_manager_with_storage, mock_storage_service, hass):
        """Test that presence configuration change events contain correct data."""
        # Mock entity states
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_HOME
        hass.states.get.return_value = phone_state
        
        # Mock storage service
        mock_storage_service.load_schedules.return_value = None
        
        # Set initial configuration
        presence_manager_with_storage._presence_entities = ["device_tracker.old"]
        presence_manager_with_storage._presence_rule = "everyone_home"
        
        # Update configuration
        await presence_manager_with_storage.update_presence_entities(["device_tracker.new"])
        
        # Verify event data
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        event_data = call_args[0][1]
        
        # Check event structure
        assert event_data["manager"] == "presence"
        assert event_data["operation"] == "update_presence_entities"
        assert "timestamp" in event_data
        assert "old_config" in event_data
        assert "new_config" in event_data
        assert "changes" in event_data
        
        # Check changes calculation
        changes = event_data["changes"]
        assert "presence_entities" in changes
        assert changes["presence_entities"]["old"] == ["device_tracker.old"]
        assert changes["presence_entities"]["new"] == ["device_tracker.new"]
    
    async def test_buffer_config_change_event_data(self, buffer_manager_with_storage, mock_storage_service, hass):
        """Test that buffer configuration change events contain correct data."""
        # Mock storage service
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Set initial configuration
        old_config = BufferConfig(
            time_minutes=15,
            value_delta=2.0,
            enabled=True,
            apply_to="climate"
        )
        buffer_manager_with_storage._global_buffer = old_config
        
        # Create new buffer config
        new_config = BufferConfig(
            time_minutes=20,
            value_delta=3.0,
            enabled=False,
            apply_to="climate"
        )
        
        # Update configuration
        await buffer_manager_with_storage.update_global_buffer(new_config)
        
        # Verify event data
        hass.bus.async_fire.assert_called_once()
        call_args = hass.bus.async_fire.call_args
        event_data = call_args[0][1]
        
        # Check event structure
        assert event_data["manager"] == "buffer"
        assert event_data["operation"] == "update_global_buffer"
        assert "timestamp" in event_data
        assert "old_config" in event_data
        assert "new_config" in event_data
        assert "changes" in event_data
        
        # Check that changes were detected
        changes = event_data["changes"]
        assert len(changes) > 0  # Should have detected changes