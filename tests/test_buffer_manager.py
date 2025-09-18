"""Tests for the BufferManager class."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.models import BufferConfig, EntityState, GlobalBufferConfig, ScheduleData
from custom_components.roost_scheduler.const import DEFAULT_BUFFER_TIME_MINUTES, DEFAULT_BUFFER_VALUE_DELTA


@pytest.fixture
def hass():
    """Mock Home Assistant instance."""
    return Mock()


@pytest.fixture
def mock_storage_service():
    """Mock storage service for testing."""
    storage = Mock()
    storage.load_schedules = AsyncMock()
    storage.save_schedules = AsyncMock()
    return storage


@pytest.fixture
def buffer_manager(hass):
    """Create a BufferManager instance for testing."""
    return BufferManager(hass)


@pytest.fixture
def buffer_manager_with_storage(hass, mock_storage_service):
    """Create a BufferManager instance with storage service for testing."""
    return BufferManager(hass, mock_storage_service)


class TestBufferManager:
    """Test cases for BufferManager."""
    
    def test_init(self, buffer_manager):
        """Test BufferManager initialization."""
        assert buffer_manager.hass is not None
        assert buffer_manager._entity_states == {}
        assert buffer_manager._global_buffer.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager._global_buffer.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager._global_buffer.enabled is True
    
    def test_should_suppress_change_no_entity_state(self, buffer_manager):
        """Test suppression when no entity state exists."""
        result = buffer_manager.should_suppress_change("climate.test", 20.0, {})
        assert result is False
    
    def test_should_suppress_change_force_apply(self, buffer_manager):
        """Test force apply bypasses all buffer logic."""
        # Set up entity state
        buffer_manager.update_manual_change("climate.test", 18.0)
        
        # Force apply should bypass buffer logic
        result = buffer_manager.should_suppress_change("climate.test", 22.0, {}, force_apply=True)
        assert result is False
    
    def test_should_suppress_change_buffer_disabled(self, buffer_manager):
        """Test suppression when buffer is disabled."""
        slot_config = {
            "buffer_override": {
                "time_minutes": 15,
                "value_delta": 2.0,
                "enabled": False
            }
        }
        
        buffer_manager.update_manual_change("climate.test", 18.0)
        result = buffer_manager.should_suppress_change("climate.test", 22.0, slot_config)
        assert result is False
    
    def test_should_suppress_change_within_tolerance(self, buffer_manager):
        """Test suppression when current value is within tolerance of target."""
        # Set current value to 20.0
        buffer_manager.update_current_value("climate.test", 20.0)
        
        # Target 21.0 is within default tolerance of 2.0
        result = buffer_manager.should_suppress_change("climate.test", 21.0, {})
        assert result is True
        
        # Target 23.0 is outside tolerance
        result = buffer_manager.should_suppress_change("climate.test", 23.0, {})
        assert result is False
    
    def test_should_suppress_change_recent_manual_within_tolerance(self, buffer_manager):
        """Test suppression for recent manual change within tolerance."""
        # Manual change 5 minutes ago
        buffer_manager.update_manual_change("climate.test", 20.0)
        
        # Target 21.0 is within tolerance, should suppress
        result = buffer_manager.should_suppress_change("climate.test", 21.0, {})
        assert result is True
        
        # Target 23.0 is outside tolerance, should not suppress
        result = buffer_manager.should_suppress_change("climate.test", 23.0, {})
        assert result is False
    
    def test_should_suppress_change_old_manual_change(self, buffer_manager):
        """Test no suppression for old manual changes."""
        # Create entity state with old manual change
        old_time = datetime.now() - timedelta(minutes=30)
        entity_state = EntityState(
            entity_id="climate.test",
            current_value=20.0,
            last_manual_change=old_time,
            last_scheduled_change=None,
            buffer_config=buffer_manager._global_buffer
        )
        buffer_manager._entity_states["climate.test"] = entity_state
        
        # Even within tolerance, old manual change should not suppress
        result = buffer_manager.should_suppress_change("climate.test", 21.0, {})
        assert result is True  # Still suppressed due to tolerance check
        
        # Outside tolerance should not suppress
        result = buffer_manager.should_suppress_change("climate.test", 25.0, {})
        assert result is False


class TestBufferConfigOverrides:
    """Test buffer configuration overrides."""
    
    def test_get_buffer_config_global(self, buffer_manager):
        """Test getting global buffer config."""
        config = buffer_manager.get_buffer_config({})
        assert config == buffer_manager._global_buffer
    
    def test_get_buffer_config_slot_override_dict(self, buffer_manager):
        """Test slot-specific buffer override from dictionary."""
        slot_config = {
            "buffer_override": {
                "time_minutes": 10,
                "value_delta": 1.0,
                "enabled": True
            }
        }
        
        config = buffer_manager.get_buffer_config(slot_config)
        assert config.time_minutes == 10
        assert config.value_delta == 1.0
        assert config.enabled is True
    
    def test_get_buffer_config_slot_override_object(self, buffer_manager):
        """Test slot-specific buffer override from BufferConfig object."""
        override = BufferConfig(time_minutes=5, value_delta=0.5, enabled=False)
        slot_config = {"buffer_override": override}
        
        config = buffer_manager.get_buffer_config(slot_config)
        assert config == override
    
    def test_get_buffer_config_invalid_override(self, buffer_manager):
        """Test handling of invalid buffer override."""
        slot_config = {
            "buffer_override": {
                "time_minutes": -5,  # Invalid
                "value_delta": "invalid",  # Invalid
                "enabled": "not_bool"  # Invalid
            }
        }
        
        # Should fall back to global config
        config = buffer_manager.get_buffer_config(slot_config)
        assert config == buffer_manager._global_buffer
    
    def test_slot_override_suppression(self, buffer_manager):
        """Test suppression with slot-specific overrides."""
        # Set up entity with current value 20.0
        buffer_manager.update_current_value("climate.test", 20.0)
        
        # Slot config with tight tolerance
        slot_config = {
            "buffer_override": {
                "time_minutes": 15,
                "value_delta": 0.5,  # Very tight tolerance
                "enabled": True
            }
        }
        
        # Target 20.3 should be suppressed (within 0.5 tolerance)
        result = buffer_manager.should_suppress_change("climate.test", 20.3, slot_config)
        assert result is True
        
        # Target 21.0 should not be suppressed (outside 0.5 tolerance)
        result = buffer_manager.should_suppress_change("climate.test", 21.0, slot_config)
        assert result is False


class TestManualChangeTracking:
    """Test manual change tracking functionality."""
    
    def test_update_manual_change_new_entity(self, buffer_manager):
        """Test recording manual change for new entity."""
        buffer_manager.update_manual_change("climate.test", 22.0)
        
        entity_state = buffer_manager.get_entity_state("climate.test")
        assert entity_state is not None
        assert entity_state.current_value == 22.0
        assert entity_state.last_manual_change is not None
        assert entity_state.last_scheduled_change is None
    
    def test_update_manual_change_existing_entity(self, buffer_manager):
        """Test updating manual change for existing entity."""
        # Create initial state
        buffer_manager.update_current_value("climate.test", 20.0)
        
        # Update with manual change
        buffer_manager.update_manual_change("climate.test", 22.0)
        
        entity_state = buffer_manager.get_entity_state("climate.test")
        assert entity_state.current_value == 22.0
        assert entity_state.last_manual_change is not None
    
    def test_update_manual_change_invalid_value(self, buffer_manager):
        """Test handling invalid value types."""
        # Should not crash, but should log warning
        buffer_manager.update_manual_change("climate.test", "invalid")
        
        # Entity state should not be created
        entity_state = buffer_manager.get_entity_state("climate.test")
        assert entity_state is None
    
    def test_is_recent_manual_change(self, buffer_manager):
        """Test checking for recent manual changes."""
        # No entity state
        assert buffer_manager.is_recent_manual_change("climate.test") is False
        
        # Recent manual change
        buffer_manager.update_manual_change("climate.test", 20.0)
        assert buffer_manager.is_recent_manual_change("climate.test") is True
        
        # Custom threshold
        assert buffer_manager.is_recent_manual_change("climate.test", threshold_minutes=1) is True
        assert buffer_manager.is_recent_manual_change("climate.test", threshold_minutes=0) is False
    
    def test_get_time_since_last_manual_change(self, buffer_manager):
        """Test getting time since last manual change."""
        # No entity state
        assert buffer_manager.get_time_since_last_manual_change("climate.test") is None
        
        # No manual change
        buffer_manager.update_current_value("climate.test", 20.0)
        assert buffer_manager.get_time_since_last_manual_change("climate.test") is None
        
        # With manual change
        buffer_manager.update_manual_change("climate.test", 22.0)
        time_delta = buffer_manager.get_time_since_last_manual_change("climate.test")
        assert time_delta is not None
        assert time_delta.total_seconds() < 1  # Should be very recent


class TestScheduledChangeTracking:
    """Test scheduled change tracking functionality."""
    
    def test_update_scheduled_change_new_entity(self, buffer_manager):
        """Test recording scheduled change for new entity."""
        buffer_manager.update_scheduled_change("climate.test", 21.0)
        
        entity_state = buffer_manager.get_entity_state("climate.test")
        assert entity_state is not None
        assert entity_state.current_value == 21.0
        assert entity_state.last_manual_change is None
        assert entity_state.last_scheduled_change is not None
    
    def test_update_scheduled_change_existing_entity(self, buffer_manager):
        """Test updating scheduled change for existing entity."""
        # Create initial state
        buffer_manager.update_manual_change("climate.test", 20.0)
        
        # Update with scheduled change
        buffer_manager.update_scheduled_change("climate.test", 21.0)
        
        entity_state = buffer_manager.get_entity_state("climate.test")
        assert entity_state.current_value == 21.0
        assert entity_state.last_manual_change is not None  # Should preserve
        assert entity_state.last_scheduled_change is not None
    
    def test_update_scheduled_change_invalid_value(self, buffer_manager):
        """Test handling invalid value types for scheduled changes."""
        # Should not crash, but should log warning
        buffer_manager.update_scheduled_change("climate.test", None)
        
        # Entity state should not be created
        entity_state = buffer_manager.get_entity_state("climate.test")
        assert entity_state is None


class TestBufferConfigValidation:
    """Test buffer configuration validation."""
    
    def test_validate_buffer_config_valid(self, buffer_manager):
        """Test validation of valid buffer config."""
        config = {
            "time_minutes": 10,
            "value_delta": 1.5,
            "enabled": True
        }
        
        is_valid, error = buffer_manager.validate_buffer_config(config)
        assert is_valid is True
        assert error == ""
    
    def test_validate_buffer_config_invalid(self, buffer_manager):
        """Test validation of invalid buffer config."""
        config = {
            "time_minutes": -5,  # Invalid
            "value_delta": 1.5,
            "enabled": True
        }
        
        is_valid, error = buffer_manager.validate_buffer_config(config)
        assert is_valid is False
        assert "time_minutes" in error
    
    def test_create_default_buffer_config(self, buffer_manager):
        """Test creating default buffer configuration."""
        config = buffer_manager.create_default_buffer_config()
        assert config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert config.enabled is True
    
    def test_apply_buffer_defaults(self, buffer_manager):
        """Test applying defaults to partial config."""
        partial_config = {"time_minutes": 5}
        
        config = buffer_manager.apply_buffer_defaults(partial_config)
        assert config.time_minutes == 5  # From partial config
        assert config.value_delta == DEFAULT_BUFFER_VALUE_DELTA  # From defaults
        assert config.enabled is True  # From defaults
    
    def test_apply_buffer_defaults_invalid(self, buffer_manager):
        """Test applying defaults with invalid partial config."""
        invalid_config = {"time_minutes": -5}
        
        # Should return default config when invalid
        config = buffer_manager.apply_buffer_defaults(invalid_config)
        assert config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert config.enabled is True


class TestGlobalBufferManagement:
    """Test global buffer configuration management."""
    
    def test_update_global_buffer(self, buffer_manager):
        """Test updating global buffer configuration."""
        new_config = BufferConfig(time_minutes=30, value_delta=3.0, enabled=False)
        buffer_manager.update_global_buffer(new_config)
        
        assert buffer_manager._global_buffer == new_config
    
    def test_global_buffer_affects_new_entities(self, buffer_manager):
        """Test that global buffer config affects new entities."""
        # Update global config
        new_config = BufferConfig(time_minutes=30, value_delta=3.0, enabled=True)
        buffer_manager.update_global_buffer(new_config)
        
        # Create new entity
        buffer_manager.update_current_value("climate.test", 20.0)
        
        entity_state = buffer_manager.get_entity_state("climate.test")
        assert entity_state.buffer_config == new_config


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_update_current_value_invalid_type(self, buffer_manager):
        """Test updating current value with invalid type."""
        # Should not crash
        buffer_manager.update_current_value("climate.test", "invalid")
        
        # Entity should not be created
        assert buffer_manager.get_entity_state("climate.test") is None
    
    def test_suppression_with_zero_tolerance(self, buffer_manager):
        """Test suppression with zero tolerance."""
        slot_config = {
            "buffer_override": {
                "time_minutes": 15,
                "value_delta": 0.0,  # Zero tolerance
                "enabled": True
            }
        }
        
        buffer_manager.update_current_value("climate.test", 20.0)
        
        # Exact match should suppress
        result = buffer_manager.should_suppress_change("climate.test", 20.0, slot_config)
        assert result is True
        
        # Any difference should not suppress
        result = buffer_manager.should_suppress_change("climate.test", 20.1, slot_config)
        assert result is False
    
    def test_suppression_with_large_tolerance(self, buffer_manager):
        """Test suppression with very large tolerance."""
        slot_config = {
            "buffer_override": {
                "time_minutes": 15,
                "value_delta": 50.0,  # Very large tolerance
                "enabled": True
            }
        }
        
        buffer_manager.update_current_value("climate.test", 20.0)
        
        # Large difference should still suppress
        result = buffer_manager.should_suppress_change("climate.test", 60.0, slot_config)
        assert result is True
        
        # Extreme difference should not suppress
        result = buffer_manager.should_suppress_change("climate.test", 80.0, slot_config)
        assert result is False


class TestBufferManagerStorageIntegration:
    """Test BufferManager storage integration functionality."""
    
    def test_init_with_storage_service(self, hass, mock_storage_service):
        """Test BufferManager initialization with storage service."""
        buffer_manager = BufferManager(hass, mock_storage_service)
        
        assert buffer_manager.hass is hass
        assert buffer_manager.storage_service is mock_storage_service
        assert buffer_manager._entity_states == {}
        assert isinstance(buffer_manager._global_buffer_config, GlobalBufferConfig)
        assert isinstance(buffer_manager._global_buffer, BufferConfig)
    
    def test_init_without_storage_service(self, hass):
        """Test BufferManager initialization without storage service."""
        buffer_manager = BufferManager(hass)
        
        assert buffer_manager.hass is hass
        assert buffer_manager.storage_service is None
        assert buffer_manager._entity_states == {}
        assert isinstance(buffer_manager._global_buffer_config, GlobalBufferConfig)
        assert isinstance(buffer_manager._global_buffer, BufferConfig)
    
    @pytest.mark.asyncio
    async def test_load_configuration_no_storage(self, buffer_manager):
        """Test loading configuration when no storage service is available."""
        await buffer_manager.load_configuration()
        
        # Should use default configuration
        assert buffer_manager._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager._global_buffer_config.enabled is True
    
    @pytest.mark.asyncio
    async def test_load_configuration_with_stored_data(self, buffer_manager_with_storage, mock_storage_service):
        """Test loading configuration from storage."""
        # Mock stored data
        buffer_config = GlobalBufferConfig(
            time_minutes=30,
            value_delta=3.0,
            enabled=False,
            apply_to="climate"
        )
        schedule_data = Mock()
        schedule_data.buffer_config = buffer_config
        mock_storage_service.load_schedules.return_value = schedule_data
        
        await buffer_manager_with_storage.load_configuration()
        
        assert buffer_manager_with_storage._global_buffer_config == buffer_config
        assert buffer_manager_with_storage._global_buffer.time_minutes == 30
        assert buffer_manager_with_storage._global_buffer.value_delta == 3.0
        assert buffer_manager_with_storage._global_buffer.enabled is False
    
    @pytest.mark.asyncio
    async def test_load_configuration_no_stored_data(self, buffer_manager_with_storage, mock_storage_service):
        """Test loading configuration when no stored data exists."""
        mock_storage_service.load_schedules.return_value = None
        
        await buffer_manager_with_storage.load_configuration()
        
        # Should use default configuration
        assert buffer_manager_with_storage._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager_with_storage._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager_with_storage._global_buffer_config.enabled is True
    
    @pytest.mark.asyncio
    async def test_load_configuration_storage_error(self, buffer_manager_with_storage, mock_storage_service):
        """Test loading configuration when storage raises an error."""
        mock_storage_service.load_schedules.side_effect = Exception("Storage error")
        
        await buffer_manager_with_storage.load_configuration()
        
        # Should use default configuration
        assert buffer_manager_with_storage._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager_with_storage._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager_with_storage._global_buffer_config.enabled is True
    
    @pytest.mark.asyncio
    async def test_save_configuration_no_storage(self, buffer_manager):
        """Test saving configuration when no storage service is available."""
        # Should not raise an error
        await buffer_manager.save_configuration()
    
    @pytest.mark.asyncio
    async def test_save_configuration_success(self, buffer_manager_with_storage, mock_storage_service):
        """Test successful configuration saving."""
        # Mock existing schedule data
        schedule_data = Mock()
        mock_storage_service.load_schedules.return_value = schedule_data
        
        await buffer_manager_with_storage.save_configuration()
        
        mock_storage_service.load_schedules.assert_called_once()
        mock_storage_service.save_schedules.assert_called_once_with(schedule_data)
        assert schedule_data.buffer_config == buffer_manager_with_storage._global_buffer_config
    
    @pytest.mark.asyncio
    async def test_save_configuration_no_schedule_data(self, buffer_manager_with_storage, mock_storage_service):
        """Test saving configuration when no schedule data exists."""
        mock_storage_service.load_schedules.return_value = None
        
        await buffer_manager_with_storage.save_configuration()
        
        mock_storage_service.load_schedules.assert_called_once()
        mock_storage_service.save_schedules.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_update_global_buffer_config(self, buffer_manager_with_storage, mock_storage_service):
        """Test updating global buffer configuration."""
        # Mock existing schedule data
        schedule_data = Mock()
        mock_storage_service.load_schedules.return_value = schedule_data
        
        new_config = GlobalBufferConfig(
            time_minutes=45,
            value_delta=4.0,
            enabled=False,
            apply_to="climate"
        )
        
        await buffer_manager_with_storage.update_global_buffer_config(new_config)
        
        assert buffer_manager_with_storage._global_buffer_config == new_config
        assert buffer_manager_with_storage._global_buffer.time_minutes == 45
        assert buffer_manager_with_storage._global_buffer.value_delta == 4.0
        assert buffer_manager_with_storage._global_buffer.enabled is False
        mock_storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_global_buffer_config_invalid(self, buffer_manager_with_storage):
        """Test updating global buffer configuration with invalid data."""
        # Create a valid config first, then modify it to be invalid
        invalid_config = GlobalBufferConfig(
            time_minutes=15,
            value_delta=2.0,
            enabled=True
        )
        # Bypass validation by setting invalid value directly
        invalid_config.time_minutes = -5
        
        with pytest.raises(ValueError):
            await buffer_manager_with_storage.update_global_buffer_config(invalid_config)
    
    @pytest.mark.asyncio
    async def test_update_entity_buffer_config(self, buffer_manager_with_storage, mock_storage_service):
        """Test updating entity-specific buffer configuration."""
        # Mock existing schedule data
        schedule_data = Mock()
        mock_storage_service.load_schedules.return_value = schedule_data
        
        entity_config = BufferConfig(
            time_minutes=20,
            value_delta=1.5,
            enabled=True,
            apply_to="climate"
        )
        
        await buffer_manager_with_storage.update_entity_buffer_config("climate.test", entity_config)
        
        assert "climate.test" in buffer_manager_with_storage._global_buffer_config.entity_overrides
        assert buffer_manager_with_storage._global_buffer_config.entity_overrides["climate.test"] == entity_config
        mock_storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_entity_buffer_config_invalid_entity(self, buffer_manager_with_storage):
        """Test updating entity buffer configuration with invalid entity ID."""
        entity_config = BufferConfig(
            time_minutes=20,
            value_delta=1.5,
            enabled=True,
            apply_to="climate"
        )
        
        with pytest.raises(ValueError):
            await buffer_manager_with_storage.update_entity_buffer_config("invalid_entity", entity_config)
    
    @pytest.mark.asyncio
    async def test_remove_entity_buffer_config(self, buffer_manager_with_storage, mock_storage_service):
        """Test removing entity-specific buffer configuration."""
        # Mock existing schedule data
        schedule_data = Mock()
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Add entity override first
        entity_config = BufferConfig(
            time_minutes=20,
            value_delta=1.5,
            enabled=True,
            apply_to="climate"
        )
        buffer_manager_with_storage._global_buffer_config.set_entity_override("climate.test", entity_config)
        
        result = await buffer_manager_with_storage.remove_entity_buffer_config("climate.test")
        
        assert result is True
        assert "climate.test" not in buffer_manager_with_storage._global_buffer_config.entity_overrides
        mock_storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_entity_buffer_config_not_exists(self, buffer_manager_with_storage, mock_storage_service):
        """Test removing entity buffer configuration that doesn't exist."""
        # Mock existing schedule data
        schedule_data = Mock()
        mock_storage_service.load_schedules.return_value = schedule_data
        
        result = await buffer_manager_with_storage.remove_entity_buffer_config("climate.nonexistent")
        
        assert result is False
        mock_storage_service.save_schedules.assert_not_called()
    
    def test_get_configuration_summary(self, buffer_manager_with_storage):
        """Test getting configuration summary."""
        # Add some entity states
        buffer_manager_with_storage.update_current_value("climate.test1", 20.0)
        buffer_manager_with_storage.update_current_value("climate.test2", 22.0)
        
        summary = buffer_manager_with_storage.get_configuration_summary()
        
        assert "global_config" in summary
        assert "entity_count" in summary
        assert "entities_tracked" in summary
        assert "storage_available" in summary
        assert summary["entity_count"] == 2
        assert "climate.test1" in summary["entities_tracked"]
        assert "climate.test2" in summary["entities_tracked"]
        assert summary["storage_available"] is True
    
    def test_get_entity_buffer_config_global(self, buffer_manager_with_storage):
        """Test getting entity buffer configuration using global settings."""
        config = buffer_manager_with_storage.get_entity_buffer_config("climate.test")
        
        assert config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert config.enabled is True
    
    def test_get_entity_buffer_config_entity_specific(self, buffer_manager_with_storage):
        """Test getting entity buffer configuration with entity-specific override."""
        entity_config = BufferConfig(
            time_minutes=25,
            value_delta=1.8,
            enabled=False,
            apply_to="climate"
        )
        buffer_manager_with_storage._global_buffer_config.set_entity_override("climate.test", entity_config)
        
        config = buffer_manager_with_storage.get_entity_buffer_config("climate.test")
        
        assert config == entity_config
        assert config.time_minutes == 25
        assert config.value_delta == 1.8
        assert config.enabled is False
    
    def test_get_buffer_config_with_entity_id(self, buffer_manager_with_storage):
        """Test get_buffer_config method with entity ID for entity-specific configuration."""
        # Set up entity-specific override
        entity_config = BufferConfig(
            time_minutes=35,
            value_delta=2.5,
            enabled=True,
            apply_to="climate"
        )
        buffer_manager_with_storage._global_buffer_config.set_entity_override("climate.test", entity_config)
        
        # Test with entity ID
        config = buffer_manager_with_storage.get_buffer_config({}, "climate.test")
        assert config == entity_config
        
        # Test with different entity (should use global)
        config = buffer_manager_with_storage.get_buffer_config({}, "climate.other")
        assert config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
    
    def test_get_buffer_config_slot_override_priority(self, buffer_manager_with_storage):
        """Test that slot override takes priority over entity-specific configuration."""
        # Set up entity-specific override
        entity_config = BufferConfig(
            time_minutes=35,
            value_delta=2.5,
            enabled=True,
            apply_to="climate"
        )
        buffer_manager_with_storage._global_buffer_config.set_entity_override("climate.test", entity_config)
        
        # Set up slot override
        slot_config = {
            "buffer_override": {
                "time_minutes": 10,
                "value_delta": 1.0,
                "enabled": False,
                "apply_to": "climate"
            }
        }
        
        config = buffer_manager_with_storage.get_buffer_config(slot_config, "climate.test")
        
        # Should use slot override, not entity-specific
        assert config.time_minutes == 10
        assert config.value_delta == 1.0
        assert config.enabled is False
    
    def test_should_suppress_change_with_entity_config(self, buffer_manager_with_storage):
        """Test suppression logic with entity-specific buffer configuration."""
        # Set up tight entity-specific configuration
        entity_config = BufferConfig(
            time_minutes=15,
            value_delta=0.5,  # Very tight tolerance
            enabled=True,
            apply_to="climate"
        )
        buffer_manager_with_storage._global_buffer_config.set_entity_override("climate.test", entity_config)
        
        # Set current value
        buffer_manager_with_storage.update_current_value("climate.test", 20.0)
        
        # Target within entity-specific tolerance should be suppressed
        result = buffer_manager_with_storage.should_suppress_change("climate.test", 20.3, {})
        assert result is True
        
        # Target outside entity-specific tolerance should not be suppressed
        result = buffer_manager_with_storage.should_suppress_change("climate.test", 21.0, {})
        assert result is False
    
    @pytest.mark.asyncio
    async def test_initialize_default_configuration_with_storage(self, buffer_manager_with_storage, mock_storage_service):
        """Test initializing default configuration with storage available."""
        # Mock existing schedule data
        schedule_data = Mock()
        mock_storage_service.load_schedules.return_value = schedule_data
        
        await buffer_manager_with_storage._initialize_default_configuration()
        
        assert buffer_manager_with_storage._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager_with_storage._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager_with_storage._global_buffer_config.enabled is True
        mock_storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_default_configuration_storage_error(self, buffer_manager_with_storage, mock_storage_service):
        """Test initializing default configuration when storage save fails."""
        # Mock storage error
        mock_storage_service.load_schedules.return_value = Mock()
        mock_storage_service.save_schedules.side_effect = Exception("Storage error")
        
        # Should not raise an error
        await buffer_manager_with_storage._initialize_default_configuration()
        
        assert buffer_manager_with_storage._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager_with_storage._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager_with_storage._global_buffer_config.enabled is True


class TestGlobalBufferConfig:
    """Test GlobalBufferConfig functionality."""
    
    def test_global_buffer_config_creation(self):
        """Test creating GlobalBufferConfig."""
        config = GlobalBufferConfig(
            time_minutes=20,
            value_delta=1.5,
            enabled=True,
            apply_to="climate"
        )
        
        assert config.time_minutes == 20
        assert config.value_delta == 1.5
        assert config.enabled is True
        assert config.apply_to == "climate"
        assert config.entity_overrides == {}
    
    def test_global_buffer_config_validation(self):
        """Test GlobalBufferConfig validation."""
        # Valid config should not raise
        config = GlobalBufferConfig(
            time_minutes=15,
            value_delta=2.0,
            enabled=True,
            apply_to="climate"
        )
        config.validate()
        
        # Invalid time_minutes should raise
        with pytest.raises(ValueError, match="time_minutes must be a non-negative integer"):
            GlobalBufferConfig(time_minutes=-5, value_delta=2.0, enabled=True, apply_to="climate")
        
        # Invalid value_delta should raise
        with pytest.raises(ValueError, match="value_delta must be a non-negative number"):
            GlobalBufferConfig(time_minutes=15, value_delta=-1.0, enabled=True, apply_to="climate")
        
        # Invalid enabled should raise
        with pytest.raises(ValueError, match="enabled must be a boolean"):
            GlobalBufferConfig(time_minutes=15, value_delta=2.0, enabled="yes", apply_to="climate")
        
        # Invalid apply_to should raise
        with pytest.raises(ValueError, match="apply_to must be a non-empty string"):
            GlobalBufferConfig(time_minutes=15, value_delta=2.0, enabled=True, apply_to="")
    
    def test_get_effective_config_global(self):
        """Test getting effective config when no entity override exists."""
        config = GlobalBufferConfig(
            time_minutes=25,
            value_delta=3.0,
            enabled=False,
            apply_to="climate"
        )
        
        effective = config.get_effective_config("climate.test")
        
        assert effective.time_minutes == 25
        assert effective.value_delta == 3.0
        assert effective.enabled is False
        assert effective.apply_to == "climate"
    
    def test_get_effective_config_entity_override(self):
        """Test getting effective config with entity override."""
        global_config = GlobalBufferConfig(
            time_minutes=25,
            value_delta=3.0,
            enabled=False,
            apply_to="climate"
        )
        
        entity_config = BufferConfig(
            time_minutes=10,
            value_delta=1.0,
            enabled=True,
            apply_to="climate"
        )
        
        global_config.set_entity_override("climate.test", entity_config)
        effective = global_config.get_effective_config("climate.test")
        
        assert effective == entity_config
        assert effective.time_minutes == 10
        assert effective.value_delta == 1.0
        assert effective.enabled is True
    
    def test_set_entity_override(self):
        """Test setting entity-specific override."""
        config = GlobalBufferConfig()
        entity_config = BufferConfig(
            time_minutes=30,
            value_delta=2.5,
            enabled=True,
            apply_to="climate"
        )
        
        config.set_entity_override("climate.test", entity_config)
        
        assert "climate.test" in config.entity_overrides
        assert config.entity_overrides["climate.test"] == entity_config
    
    def test_set_entity_override_invalid_entity(self):
        """Test setting entity override with invalid entity ID."""
        config = GlobalBufferConfig()
        entity_config = BufferConfig(
            time_minutes=30,
            value_delta=2.5,
            enabled=True,
            apply_to="climate"
        )
        
        with pytest.raises(ValueError, match="Invalid entity_id"):
            config.set_entity_override("invalid_entity", entity_config)
    
    def test_set_entity_override_invalid_config(self):
        """Test setting entity override with invalid config."""
        config = GlobalBufferConfig()
        
        with pytest.raises(ValueError, match="config must be BufferConfig instance"):
            config.set_entity_override("climate.test", {"time_minutes": 30})
    
    def test_remove_entity_override(self):
        """Test removing entity-specific override."""
        config = GlobalBufferConfig()
        entity_config = BufferConfig(
            time_minutes=30,
            value_delta=2.5,
            enabled=True,
            apply_to="climate"
        )
        
        config.set_entity_override("climate.test", entity_config)
        assert "climate.test" in config.entity_overrides
        
        result = config.remove_entity_override("climate.test")
        assert result is True
        assert "climate.test" not in config.entity_overrides
        
        # Removing non-existent override should return False
        result = config.remove_entity_override("climate.nonexistent")
        assert result is False
    
    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        original = GlobalBufferConfig(
            time_minutes=40,
            value_delta=4.0,
            enabled=False,
            apply_to="climate"
        )
        
        entity_config = BufferConfig(
            time_minutes=20,
            value_delta=1.0,
            enabled=True,
            apply_to="climate"
        )
        original.set_entity_override("climate.test", entity_config)
        
        # Serialize
        data = original.to_dict()
        
        # Deserialize
        restored = GlobalBufferConfig.from_dict(data)
        
        assert restored.time_minutes == original.time_minutes
        assert restored.value_delta == original.value_delta
        assert restored.enabled == original.enabled
        assert restored.apply_to == original.apply_to
        assert len(restored.entity_overrides) == len(original.entity_overrides)
        assert "climate.test" in restored.entity_overrides
        assert restored.entity_overrides["climate.test"].time_minutes == entity_config.time_minutes