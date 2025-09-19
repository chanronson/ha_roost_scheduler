"""Tests for configuration validation and consistency checks."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.config_validator import ConfigurationValidator
from custom_components.roost_scheduler.models import (
    PresenceConfig, BufferConfig, GlobalBufferConfig, EntityState
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.states = Mock()
    hass.services = Mock()
    hass.bus = Mock()
    return hass


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service."""
    storage = Mock()
    storage.load_schedules = AsyncMock(return_value=None)
    storage.save_schedules = AsyncMock()
    return storage


@pytest.fixture
def presence_manager(mock_hass, mock_storage_service):
    """Create a PresenceManager instance for testing."""
    manager = PresenceManager(mock_hass, mock_storage_service)
    manager._presence_entities = ["device_tracker.phone", "person.user"]
    manager._presence_rule = "anyone_home"
    manager._timeout_seconds = 600
    manager._override_entities = {
        "force_home": "input_boolean.roost_force_home",
        "force_away": "input_boolean.roost_force_away"
    }
    manager._template_entities = []
    manager._custom_template = None
    return manager


@pytest.fixture
def buffer_manager(mock_hass, mock_storage_service):
    """Create a BufferManager instance for testing."""
    manager = BufferManager(mock_hass, mock_storage_service)
    manager._global_buffer_config = GlobalBufferConfig(
        time_minutes=15,
        value_delta=2.0,
        enabled=True,
        apply_to="climate"
    )
    return manager


class TestPresenceManagerValidation:
    """Test presence manager configuration validation."""
    
    def test_validate_configuration_valid(self, presence_manager, mock_hass):
        """Test validation with valid configuration."""
        # Mock entity states to exist
        mock_hass.states.get.side_effect = lambda entity_id: Mock(state="home") if entity_id else None
        
        is_valid, errors = presence_manager.validate_configuration()
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_configuration_invalid_entities(self, presence_manager, mock_hass):
        """Test validation with invalid presence entities."""
        # Set invalid entities
        presence_manager._presence_entities = ["invalid_entity", "domain.entity"]
        
        # Mock states - first entity doesn't exist, second does
        def mock_get_state(entity_id):
            if entity_id == "invalid_entity":
                return None
            elif entity_id == "domain.entity":
                return Mock(state="home")
            return None
        
        mock_hass.states.get.side_effect = mock_get_state
        
        is_valid, errors = presence_manager.validate_configuration()
        
        assert not is_valid
        assert any("entity_id must be in format 'domain.entity'" in error for error in errors)
        assert any("not found in Home Assistant" in error for error in errors)
    
    def test_validate_configuration_invalid_rule(self, presence_manager, mock_hass):
        """Test validation with invalid presence rule."""
        presence_manager._presence_rule = "invalid_rule"
        mock_hass.states.get.return_value = Mock(state="home")
        
        is_valid, errors = presence_manager.validate_configuration()
        
        assert not is_valid
        assert any("presence_rule must be one of" in error for error in errors)
    
    def test_validate_configuration_invalid_timeout(self, presence_manager, mock_hass):
        """Test validation with invalid timeout."""
        presence_manager._timeout_seconds = -100
        mock_hass.states.get.return_value = Mock(state="home")
        
        is_valid, errors = presence_manager.validate_configuration()
        
        assert not is_valid
        assert any("timeout_seconds must be a non-negative integer" in error for error in errors)
    
    def test_validate_configuration_excessive_timeout(self, presence_manager, mock_hass):
        """Test validation with excessive timeout."""
        presence_manager._timeout_seconds = 100000  # More than 24 hours
        mock_hass.states.get.return_value = Mock(state="home")
        
        is_valid, errors = presence_manager.validate_configuration()
        
        assert not is_valid
        assert any("cannot exceed 86400" in error for error in errors)
    
    def test_validate_configuration_custom_rule_without_template(self, presence_manager, mock_hass):
        """Test validation with custom rule but no template."""
        presence_manager._presence_rule = "custom"
        presence_manager._custom_template = None
        mock_hass.states.get.return_value = Mock(state="home")
        
        is_valid, errors = presence_manager.validate_configuration()
        
        assert not is_valid
        assert any("Custom presence rule specified but no custom template" in error for error in errors)
    
    def test_repair_configuration_invalid_entities(self, presence_manager, mock_hass):
        """Test repairing configuration with invalid entities."""
        presence_manager._presence_entities = ["invalid_entity", "device_tracker.phone", ""]
        
        # Mock states - only device_tracker.phone exists
        def mock_get_state(entity_id):
            if entity_id == "device_tracker.phone":
                return Mock(state="home")
            return None
        
        mock_hass.states.get.side_effect = mock_get_state
        
        was_repaired, repairs = presence_manager.repair_configuration()
        
        assert was_repaired
        assert len(repairs) >= 2  # Should remove invalid entities
        assert presence_manager._presence_entities == ["device_tracker.phone"]
    
    def test_repair_configuration_invalid_rule(self, presence_manager, mock_hass):
        """Test repairing configuration with invalid rule."""
        presence_manager._presence_rule = "invalid_rule"
        mock_hass.states.get.return_value = Mock(state="home")
        
        was_repaired, repairs = presence_manager.repair_configuration()
        
        assert was_repaired
        assert any("Fixed invalid presence rule" in repair for repair in repairs)
        assert presence_manager._presence_rule == "anyone_home"
    
    def test_repair_configuration_invalid_timeout(self, presence_manager, mock_hass):
        """Test repairing configuration with invalid timeout."""
        presence_manager._timeout_seconds = -100
        mock_hass.states.get.return_value = Mock(state="home")
        
        was_repaired, repairs = presence_manager.repair_configuration()
        
        assert was_repaired
        assert any("Fixed invalid timeout" in repair for repair in repairs)
        assert presence_manager._timeout_seconds == 600


class TestBufferManagerValidation:
    """Test buffer manager configuration validation."""
    
    def test_validate_configuration_valid(self, buffer_manager, mock_hass):
        """Test validation with valid configuration."""
        is_valid, errors = buffer_manager.validate_configuration()
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_configuration_invalid_global_config(self, buffer_manager, mock_hass):
        """Test validation with invalid global configuration."""
        buffer_manager._global_buffer_config.time_minutes = -10
        buffer_manager._global_buffer_config.value_delta = -5.0
        
        is_valid, errors = buffer_manager.validate_configuration()
        
        assert not is_valid
        assert any("Global buffer configuration error" in error for error in errors)
    
    def test_validate_configuration_invalid_entity_override(self, buffer_manager, mock_hass):
        """Test validation with invalid entity override."""
        # Add invalid entity override by bypassing validation
        invalid_config = BufferConfig.__new__(BufferConfig)
        invalid_config.time_minutes = -5
        invalid_config.value_delta = 2.0
        invalid_config.enabled = True
        invalid_config.apply_to = "climate"
        buffer_manager._global_buffer_config.entity_overrides["climate.invalid"] = invalid_config
        
        # Mock entity doesn't exist
        mock_hass.states.get.return_value = None
        
        is_valid, errors = buffer_manager.validate_configuration()
        
        assert not is_valid
        assert any("not found in Home Assistant" in error for error in errors)
    
    def test_validate_configuration_zero_buffer_values(self, buffer_manager, mock_hass):
        """Test validation with zero buffer values."""
        buffer_manager._global_buffer_config.time_minutes = 0
        buffer_manager._global_buffer_config.value_delta = 0
        
        is_valid, errors = buffer_manager.validate_configuration()
        
        assert not is_valid
        assert any("Buffer time is 0 minutes" in error for error in errors)
        assert any("Buffer value delta is 0" in error for error in errors)
    
    def test_repair_configuration_negative_values(self, buffer_manager, mock_hass):
        """Test repairing configuration with negative values."""
        buffer_manager._global_buffer_config.time_minutes = -10
        buffer_manager._global_buffer_config.value_delta = -5.0
        
        was_repaired, repairs = buffer_manager.repair_configuration()
        
        assert was_repaired
        assert any("Fixed negative buffer time" in repair for repair in repairs)
        assert any("Fixed negative buffer delta" in repair for repair in repairs)
        assert buffer_manager._global_buffer_config.time_minutes == 15
        assert buffer_manager._global_buffer_config.value_delta == 2.0
    
    def test_repair_configuration_excessive_values(self, buffer_manager, mock_hass):
        """Test repairing configuration with excessive values."""
        buffer_manager._global_buffer_config.time_minutes = 2000  # More than 24 hours
        buffer_manager._global_buffer_config.value_delta = 100.0  # Excessive delta
        
        was_repaired, repairs = buffer_manager.repair_configuration()
        
        assert was_repaired
        assert any("Fixed excessive buffer time" in repair for repair in repairs)
        assert any("Fixed excessive buffer delta" in repair for repair in repairs)
        assert buffer_manager._global_buffer_config.time_minutes == 1440
        assert buffer_manager._global_buffer_config.value_delta == 50.0
    
    def test_repair_configuration_invalid_entity_overrides(self, buffer_manager, mock_hass):
        """Test repairing configuration with invalid entity overrides."""
        # Add invalid entity override
        buffer_manager._global_buffer_config.entity_overrides["invalid_entity"] = BufferConfig(
            time_minutes=15, value_delta=2.0
        )
        
        # Mock entity doesn't exist
        mock_hass.states.get.return_value = None
        
        was_repaired, repairs = buffer_manager.repair_configuration()
        
        assert was_repaired
        assert any("Removed invalid buffer override" in repair for repair in repairs)
        assert "invalid_entity" not in buffer_manager._global_buffer_config.entity_overrides


class TestConfigurationValidator:
    """Test cross-manager configuration validation."""
    
    def test_validate_all_configurations_valid(self, presence_manager, buffer_manager, mock_hass):
        """Test validation with all valid configurations."""
        mock_hass.states.get.return_value = Mock(state="home")
        
        validator = ConfigurationValidator(presence_manager, buffer_manager)
        all_valid, errors = validator.validate_all_configurations()
        
        assert all_valid
        assert len(errors) == 0
    
    def test_validate_all_configurations_with_errors(self, presence_manager, buffer_manager, mock_hass):
        """Test validation with configuration errors."""
        # Make presence manager invalid
        presence_manager._presence_rule = "invalid_rule"
        
        # Make buffer manager invalid
        buffer_manager._global_buffer_config.time_minutes = -10
        
        mock_hass.states.get.return_value = Mock(state="home")
        
        validator = ConfigurationValidator(presence_manager, buffer_manager)
        all_valid, errors = validator.validate_all_configurations()
        
        assert not all_valid
        assert "presence_manager" in errors
        assert "buffer_manager" in errors
    
    def test_check_cross_manager_consistency_presence_in_buffer(self, presence_manager, buffer_manager, mock_hass):
        """Test cross-manager consistency check for presence entities in buffer."""
        # Add presence entity to buffer tracking
        presence_entity = "device_tracker.phone"
        buffer_manager._entity_states[presence_entity] = EntityState(
            entity_id=presence_entity,
            current_value=1.0,
            last_manual_change=None,
            last_scheduled_change=None,
            buffer_config=BufferConfig(time_minutes=15, value_delta=2.0)
        )
        
        validator = ConfigurationValidator(presence_manager, buffer_manager)
        consistency_errors = validator._check_cross_manager_consistency()
        
        assert len(consistency_errors) > 0
        assert any("Presence entities are being tracked by buffer manager" in error for error in consistency_errors)
    
    def test_repair_cross_manager_consistency(self, presence_manager, buffer_manager, mock_hass):
        """Test repairing cross-manager consistency issues."""
        # Add presence entity to buffer tracking
        presence_entity = "device_tracker.phone"
        buffer_manager._entity_states[presence_entity] = EntityState(
            entity_id=presence_entity,
            current_value=1.0,
            last_manual_change=None,
            last_scheduled_change=None,
            buffer_config=BufferConfig(time_minutes=15, value_delta=2.0)
        )
        
        validator = ConfigurationValidator(presence_manager, buffer_manager)
        repairs = validator._repair_cross_manager_consistency()
        
        assert len(repairs) > 0
        assert any("Removed buffer tracking for presence entity" in repair for repair in repairs)
        assert presence_entity not in buffer_manager._entity_states
    
    def test_repair_all_configurations(self, presence_manager, buffer_manager, mock_hass):
        """Test repairing all configurations."""
        # Make both managers invalid
        presence_manager._presence_rule = "invalid_rule"
        buffer_manager._global_buffer_config.time_minutes = -10
        
        # Add cross-manager conflict
        presence_entity = "device_tracker.phone"
        buffer_manager._entity_states[presence_entity] = EntityState(
            entity_id=presence_entity,
            current_value=1.0,
            last_manual_change=None,
            last_scheduled_change=None,
            buffer_config=BufferConfig(time_minutes=15, value_delta=2.0)
        )
        
        mock_hass.states.get.return_value = Mock(state="home")
        
        validator = ConfigurationValidator(presence_manager, buffer_manager)
        any_repairs, all_repairs = validator.repair_all_configurations()
        
        assert any_repairs
        assert "presence_manager" in all_repairs
        assert "buffer_manager" in all_repairs
        assert "cross_manager_consistency" in all_repairs
    
    def test_get_validation_report(self, presence_manager, buffer_manager, mock_hass):
        """Test getting comprehensive validation report."""
        mock_hass.states.get.return_value = Mock(state="home")
        
        validator = ConfigurationValidator(presence_manager, buffer_manager)
        report = validator.get_validation_report()
        
        assert "timestamp" in report
        assert "overall_status" in report
        assert "managers" in report
        assert "cross_manager_issues" in report
        assert "recommendations" in report
        
        assert report["overall_status"] == "valid"
        assert "presence" in report["managers"]
        assert "buffer" in report["managers"]
    
    def test_get_validation_report_with_issues(self, presence_manager, buffer_manager, mock_hass):
        """Test getting validation report with configuration issues."""
        # Make configurations invalid
        presence_manager._presence_rule = "invalid_rule"
        buffer_manager._global_buffer_config.time_minutes = -10
        
        mock_hass.states.get.return_value = Mock(state="home")
        
        validator = ConfigurationValidator(presence_manager, buffer_manager)
        report = validator.get_validation_report()
        
        assert report["overall_status"] == "invalid"
        assert len(report["managers"]["presence"]["errors"]) > 0
        assert len(report["managers"]["buffer"]["errors"]) > 0
        assert len(report["recommendations"]) > 0


class TestConfigurationValidationIntegration:
    """Test configuration validation integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_validation_with_storage_integration(self, mock_hass, mock_storage_service):
        """Test validation with storage service integration."""
        # Create managers with storage
        presence_manager = PresenceManager(mock_hass, mock_storage_service)
        buffer_manager = BufferManager(mock_hass, mock_storage_service)
        
        # Mock successful configuration loading
        await presence_manager._initialize_default_configuration()
        await buffer_manager._initialize_default_configuration()
        
        mock_hass.states.get.return_value = Mock(state="home")
        
        validator = ConfigurationValidator(presence_manager, buffer_manager)
        all_valid, errors = validator.validate_all_configurations()
        
        # Default configurations should be mostly valid, but may have warnings
        # about no presence entities configured
        if not all_valid:
            # Check that the only error is about missing presence entities
            assert len(errors) <= 2  # May have presence and cross-manager errors
            if "presence_manager" in errors:
                assert any("No presence entities" in error for error in errors["presence_manager"])
    
    def test_validation_error_handling(self, presence_manager, buffer_manager, mock_hass):
        """Test validation error handling with exceptions."""
        # Mock an exception during validation
        with patch.object(presence_manager, 'validate_configuration', side_effect=Exception("Test error")):
            validator = ConfigurationValidator(presence_manager, buffer_manager)
            all_valid, errors = validator.validate_all_configurations()
            
            # Should handle the exception gracefully
            assert not all_valid
            assert "presence_manager" in errors
    
    def test_repair_error_handling(self, presence_manager, buffer_manager, mock_hass):
        """Test repair error handling with exceptions."""
        # Mock an exception during repair
        with patch.object(presence_manager, 'repair_configuration', side_effect=Exception("Test error")):
            validator = ConfigurationValidator(presence_manager, buffer_manager)
            any_repairs, repairs = validator.repair_all_configurations()
            
            # Should handle the exception gracefully
            # May or may not have repairs depending on other managers
            assert isinstance(repairs, dict)
    
    def test_validation_with_missing_managers(self):
        """Test validation with missing managers."""
        validator = ConfigurationValidator(None, None, None)
        all_valid, errors = validator.validate_all_configurations()
        
        # Should be valid if no managers to validate
        assert all_valid
        assert len(errors) == 0
    
    def test_validation_report_error_handling(self, mock_hass):
        """Test validation report generation with errors."""
        # Create validator with invalid managers
        presence_manager = Mock()
        presence_manager.validate_configuration.side_effect = Exception("Test error")
        
        validator = ConfigurationValidator(presence_manager, None)
        report = validator.get_validation_report()
        
        # Should handle errors gracefully
        assert "error" in report or "timestamp" in report