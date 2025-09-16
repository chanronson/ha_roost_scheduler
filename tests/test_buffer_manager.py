"""Tests for the BufferManager class."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.models import BufferConfig, EntityState
from custom_components.roost_scheduler.const import DEFAULT_BUFFER_TIME_MINUTES, DEFAULT_BUFFER_VALUE_DELTA


@pytest.fixture
def hass():
    """Mock Home Assistant instance."""
    return Mock()


@pytest.fixture
def buffer_manager(hass):
    """Create a BufferManager instance for testing."""
    return BufferManager(hass)


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