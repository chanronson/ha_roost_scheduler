"""Focused backward compatibility validation tests."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from custom_components.roost_scheduler.storage import StorageService
from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.models import ScheduleData, PresenceConfig, GlobalBufferConfig
from custom_components.roost_scheduler.const import (
    DEFAULT_PRESENCE_TIMEOUT_SECONDS, 
    DEFAULT_BUFFER_TIME_MINUTES, 
    DEFAULT_BUFFER_VALUE_DELTA
)
from custom_components.roost_scheduler.version import VERSION


@pytest.fixture
def hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.config_dir = "/config"
    hass.data = {}
    return hass


@pytest.fixture
def storage_service(hass):
    """Mock storage service."""
    storage_service = AsyncMock()
    storage_service.hass = hass
    storage_service.entry_id = "test_entry"
    storage_service.get_config_entry_data = MagicMock(return_value={})
    return storage_service


class TestExistingInstallationCompatibility:
    """Test that existing installations continue to work after upgrade."""
    
    @pytest.mark.asyncio
    async def test_presence_manager_with_legacy_config_entry_data(self, hass, storage_service):
        """Test PresenceManager works with legacy config entry data when storage is missing."""
        # Simulate config entry data (fallback scenario)
        config_entry_data = {
            'presence_entities': ['device_tracker.phone', 'person.user'],
            'presence_rule': 'everyone_home',
            'presence_timeout_seconds': 900
        }
        storage_service.get_config_entry_data.return_value = config_entry_data
        storage_service.load_schedules.return_value = None  # No storage data
        
        # Create presence manager
        presence_manager = PresenceManager(hass, storage_service)
        
        # Load configuration should fall back to config entry data
        await presence_manager.load_configuration()
        
        # Verify fallback worked
        assert presence_manager._presence_entities == ['device_tracker.phone', 'person.user']
        assert presence_manager._presence_rule == 'everyone_home'
        assert presence_manager._timeout_seconds == 900
    
    @pytest.mark.asyncio
    async def test_buffer_manager_with_legacy_config_entry_data(self, hass, storage_service):
        """Test BufferManager works with legacy config entry data when storage is missing."""
        # Simulate config entry data (fallback scenario)
        config_entry_data = {
            'buffer_time_minutes': 20,
            'buffer_value_delta': 3.0,
            'buffer_enabled': False
        }
        storage_service.get_config_entry_data.return_value = config_entry_data
        storage_service.load_schedules.return_value = None  # No storage data
        
        # Create buffer manager
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configuration should fall back to config entry data
        await buffer_manager.load_configuration()
        
        # Verify fallback worked
        assert buffer_manager._global_buffer_config.time_minutes == 20
        assert buffer_manager._global_buffer_config.value_delta == 3.0
        assert buffer_manager._global_buffer_config.enabled is False
    
    @pytest.mark.asyncio
    async def test_presence_manager_with_legacy_storage_format(self, hass, storage_service):
        """Test PresenceManager works with legacy storage format (0.2.0)."""
        # Simulate legacy storage data (version 0.2.0 format)
        legacy_schedule_data = ScheduleData(
            version="0.2.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone", "person.user"],
            presence_rule="everyone_home",
            presence_timeout_seconds=300,
            schedules={"home": {}, "away": {}},
            buffer={},
            ui={},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        # Create presence manager
        presence_manager = PresenceManager(hass, storage_service)
        
        # Load configuration should migrate from legacy fields
        await presence_manager.load_configuration()
        
        # Verify migration worked
        assert presence_manager._presence_entities == ["device_tracker.phone", "person.user"]
        assert presence_manager._presence_rule == "everyone_home"
        assert presence_manager._timeout_seconds == 300
        
        # Verify migration was saved
        storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_buffer_manager_with_legacy_storage_format(self, hass, storage_service):
        """Test BufferManager works with legacy storage format (0.2.0)."""
        from custom_components.roost_scheduler.models import BufferConfig
        
        # Simulate legacy storage data with buffer config
        legacy_buffer_config = BufferConfig(
            time_minutes=25,
            value_delta=1.5,
            enabled=False,
            apply_to="climate"
        )
        
        legacy_schedule_data = ScheduleData(
            version="0.2.0",
            entities_tracked=["climate.living_room"],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={"global": legacy_buffer_config},
            schedules={"home": {}, "away": {}},
            ui={},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        # Create buffer manager
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configuration should migrate from legacy fields
        await buffer_manager.load_configuration()
        
        # Verify migration worked
        assert buffer_manager._global_buffer_config.time_minutes == 25
        assert buffer_manager._global_buffer_config.value_delta == 1.5
        assert buffer_manager._global_buffer_config.enabled is False
        
        # Verify migration was saved
        storage_service.save_schedules.assert_called_once()


class TestMissingOrCorruptedStorageHandling:
    """Test that the integration works with missing or corrupted storage."""
    
    @pytest.mark.asyncio
    async def test_presence_manager_with_missing_storage(self, hass, storage_service):
        """Test PresenceManager handles missing storage gracefully."""
        storage_service.load_schedules.return_value = None
        storage_service.get_config_entry_data.return_value = {}
        
        # Create presence manager
        presence_manager = PresenceManager(hass, storage_service)
        
        # Load configuration should use defaults
        await presence_manager.load_configuration()
        
        # Verify defaults were used
        assert presence_manager._presence_entities == []
        assert presence_manager._presence_rule == "anyone_home"
        assert presence_manager._timeout_seconds == DEFAULT_PRESENCE_TIMEOUT_SECONDS
    
    @pytest.mark.asyncio
    async def test_buffer_manager_with_missing_storage(self, hass, storage_service):
        """Test BufferManager handles missing storage gracefully."""
        storage_service.load_schedules.return_value = None
        storage_service.get_config_entry_data.return_value = {}
        
        # Create buffer manager
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configuration should use defaults
        await buffer_manager.load_configuration()
        
        # Verify defaults were used
        assert buffer_manager._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager._global_buffer_config.enabled is True
    
    @pytest.mark.asyncio
    async def test_presence_manager_with_storage_load_error(self, hass, storage_service):
        """Test PresenceManager handles storage load errors gracefully."""
        storage_service.load_schedules.side_effect = Exception("Storage load error")
        storage_service.get_config_entry_data.return_value = {}
        
        # Create presence manager
        presence_manager = PresenceManager(hass, storage_service)
        
        # Load configuration should handle error and use defaults
        await presence_manager.load_configuration()
        
        # Verify defaults were used despite error
        assert presence_manager._presence_entities == []
        assert presence_manager._presence_rule == "anyone_home"
        assert presence_manager._timeout_seconds == DEFAULT_PRESENCE_TIMEOUT_SECONDS
    
    @pytest.mark.asyncio
    async def test_buffer_manager_with_storage_load_error(self, hass, storage_service):
        """Test BufferManager handles storage load errors gracefully."""
        storage_service.load_schedules.side_effect = Exception("Storage load error")
        storage_service.get_config_entry_data.return_value = {}
        
        # Create buffer manager
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configuration should handle error and use defaults
        await buffer_manager.load_configuration()
        
        # Verify defaults were used despite error
        assert buffer_manager._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager._global_buffer_config.enabled is True


class TestGracefulDegradationOnStorageFailures:
    """Test graceful degradation when storage operations fail."""
    
    @pytest.mark.asyncio
    async def test_presence_manager_operation_with_save_failures(self, hass, storage_service):
        """Test PresenceManager handles save failures gracefully during operations."""
        # Setup initial data - first load should succeed
        storage_service.load_schedules.return_value = None
        storage_service.get_config_entry_data.return_value = {
            'presence_entities': ['device_tracker.phone'],
            'presence_rule': 'anyone_home',
            'presence_timeout_seconds': 600
        }
        
        # Create presence manager
        presence_manager = PresenceManager(hass, storage_service)
        
        # Load configuration first (this should work)
        await presence_manager.load_configuration()
        
        # Verify initial configuration was loaded
        assert presence_manager._presence_entities == ['device_tracker.phone']
        
        # Now make save operations fail for subsequent operations
        storage_service.save_schedules.side_effect = Exception("Save error")
        
        # Operations should fail gracefully but revert changes to maintain consistency
        with pytest.raises(Exception, match="Save error"):
            await presence_manager.update_presence_entities(['device_tracker.new_phone'])
        
        # Configuration should be reverted to original state after failed save
        assert presence_manager._presence_entities == ['device_tracker.phone']
        
        # Same for rule updates
        with pytest.raises(Exception, match="Save error"):
            await presence_manager.update_presence_rule('everyone_home')
        
        # Rule should remain unchanged
        assert presence_manager._presence_rule == 'anyone_home'
    
    @pytest.mark.asyncio
    async def test_buffer_manager_operation_with_save_failures(self, hass, storage_service):
        """Test BufferManager continues to operate when save operations fail."""
        # Setup initial data
        storage_service.load_schedules.return_value = None
        storage_service.get_config_entry_data.return_value = {
            'buffer_time_minutes': 20,
            'buffer_value_delta': 2.5,
            'buffer_enabled': True
        }
        
        # Make save operations fail
        storage_service.save_schedules.side_effect = Exception("Save error")
        
        # Create buffer manager
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configuration should work despite save failures
        await buffer_manager.load_configuration()
        
        # Verify configuration was loaded
        assert buffer_manager._global_buffer_config.time_minutes == 20
        
        # Operations should continue working even if save fails
        new_config = GlobalBufferConfig(
            time_minutes=30,
            value_delta=3.0,
            enabled=False,
            apply_to="climate"
        )
        await buffer_manager.update_global_buffer_config(new_config)
        assert buffer_manager._global_buffer_config.time_minutes == 30
        assert buffer_manager._global_buffer_config.value_delta == 3.0
        assert buffer_manager._global_buffer_config.enabled is False


class TestConfigEntryDataFallback:
    """Test that config entry data is still used as fallback."""
    
    @pytest.mark.asyncio
    async def test_presence_manager_config_entry_fallback(self, hass, storage_service):
        """Test PresenceManager uses config entry data as fallback."""
        # No storage data
        storage_service.load_schedules.return_value = None
        
        # Config entry data available
        config_entry_data = {
            'presence_entities': ['device_tracker.phone', 'person.user'],
            'presence_rule': 'everyone_home',
            'presence_timeout_seconds': 1200
        }
        storage_service.get_config_entry_data.return_value = config_entry_data
        
        # Create presence manager
        presence_manager = PresenceManager(hass, storage_service)
        
        # Load configuration should use config entry data
        await presence_manager.load_configuration()
        
        # Verify config entry data was used
        assert presence_manager._presence_entities == ['device_tracker.phone', 'person.user']
        assert presence_manager._presence_rule == 'everyone_home'
        assert presence_manager._timeout_seconds == 1200
    
    @pytest.mark.asyncio
    async def test_buffer_manager_config_entry_fallback(self, hass, storage_service):
        """Test BufferManager uses config entry data as fallback."""
        # No storage data
        storage_service.load_schedules.return_value = None
        
        # Config entry data available
        config_entry_data = {
            'buffer_time_minutes': 25,
            'buffer_value_delta': 1.5,
            'buffer_enabled': False
        }
        storage_service.get_config_entry_data.return_value = config_entry_data
        
        # Create buffer manager
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configuration should use config entry data
        await buffer_manager.load_configuration()
        
        # Verify config entry data was used
        assert buffer_manager._global_buffer_config.time_minutes == 25
        assert buffer_manager._global_buffer_config.value_delta == 1.5
        assert buffer_manager._global_buffer_config.enabled is False
    
    @pytest.mark.asyncio
    async def test_storage_data_takes_precedence_over_config_entry(self, hass, storage_service):
        """Test that storage data takes precedence over config entry data."""
        # Both storage and config entry data available
        storage_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.tablet"],  # Different from config entry
            presence_rule="anyone_home",
            presence_timeout_seconds=900,  # Different from config entry
            schedules={"home": {}, "away": {}},
            buffer={},
            ui={},
            metadata={}
        )
        storage_service.load_schedules.return_value = storage_data
        
        config_entry_data = {
            'presence_entities': ['device_tracker.phone'],  # Different from storage
            'presence_rule': 'anyone_home',
            'presence_timeout_seconds': 600  # Different from storage
        }
        storage_service.get_config_entry_data.return_value = config_entry_data
        
        # Create presence manager
        presence_manager = PresenceManager(hass, storage_service)
        
        # Load configuration should prefer storage data
        await presence_manager.load_configuration()
        
        # Verify storage data was used (not config entry data)
        assert presence_manager._presence_entities == ["device_tracker.tablet"]
        assert presence_manager._timeout_seconds == 900


class TestConfigurationPreservationDuringMigration:
    """Test that all existing configuration is preserved during migration."""
    
    @pytest.mark.asyncio
    async def test_presence_configuration_preservation_during_migration(self, hass, storage_service):
        """Test that presence configuration is fully preserved during migration."""
        # Legacy storage data with full presence configuration
        legacy_schedule_data = ScheduleData(
            version="0.2.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone", "device_tracker.tablet", "person.user"],
            presence_rule="everyone_home",
            presence_timeout_seconds=1800,  # Custom timeout
            schedules={"home": {}, "away": {}},
            buffer={},
            ui={},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        # Create presence manager
        presence_manager = PresenceManager(hass, storage_service)
        
        # Load configuration should preserve all data during migration
        await presence_manager.load_configuration()
        
        # Verify all presence configuration was preserved
        assert presence_manager._presence_entities == ["device_tracker.phone", "device_tracker.tablet", "person.user"]
        assert presence_manager._presence_rule == "everyone_home"
        assert presence_manager._timeout_seconds == 1800
        
        # Verify migration was triggered (save was called)
        storage_service.save_schedules.assert_called_once()
        
        # Verify the saved data has modern format
        saved_schedule_data = storage_service.save_schedules.call_args[0][0]
        assert saved_schedule_data.presence_config is not None
        assert saved_schedule_data.presence_config.entities == ["device_tracker.phone", "device_tracker.tablet", "person.user"]
        assert saved_schedule_data.presence_config.rule == "everyone_home"
        assert saved_schedule_data.presence_config.timeout_seconds == 1800
    
    @pytest.mark.asyncio
    async def test_buffer_configuration_preservation_during_migration(self, hass, storage_service):
        """Test that buffer configuration is fully preserved during migration."""
        from custom_components.roost_scheduler.models import BufferConfig
        
        # Legacy storage data with buffer configuration
        legacy_buffer_config = BufferConfig(
            time_minutes=30,
            value_delta=2.5,
            enabled=False,
            apply_to="climate"
        )
        
        legacy_schedule_data = ScheduleData(
            version="0.2.0",
            entities_tracked=["climate.living_room"],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={"global": legacy_buffer_config},
            schedules={"home": {}, "away": {}},
            ui={},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        # Create buffer manager
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configuration should preserve all data during migration
        await buffer_manager.load_configuration()
        
        # Verify all buffer configuration was preserved
        assert buffer_manager._global_buffer_config.time_minutes == 30
        assert buffer_manager._global_buffer_config.value_delta == 2.5
        assert buffer_manager._global_buffer_config.enabled is False
        
        # Verify migration was triggered (save was called)
        storage_service.save_schedules.assert_called_once()
        
        # Verify the saved data has modern format
        saved_schedule_data = storage_service.save_schedules.call_args[0][0]
        assert saved_schedule_data.buffer_config is not None
        assert saved_schedule_data.buffer_config.time_minutes == 30
        assert saved_schedule_data.buffer_config.value_delta == 2.5
        assert saved_schedule_data.buffer_config.enabled is False


class TestManagerInitializationCompatibility:
    """Test that managers can be initialized with storage service parameter."""
    
    def test_presence_manager_constructor_accepts_storage_service(self, hass, storage_service):
        """Test that PresenceManager constructor accepts storage_service parameter."""
        # This should not raise any errors
        presence_manager = PresenceManager(hass, storage_service)
        
        # Verify the manager was created with correct attributes
        assert presence_manager.hass is hass
        assert presence_manager.storage_service is storage_service
        assert hasattr(presence_manager, '_presence_entities')
        assert hasattr(presence_manager, '_presence_rule')
        assert hasattr(presence_manager, '_timeout_seconds')
    
    def test_buffer_manager_constructor_accepts_storage_service(self, hass, storage_service):
        """Test that BufferManager constructor accepts storage_service parameter."""
        # This should not raise any errors
        buffer_manager = BufferManager(hass, storage_service)
        
        # Verify the manager was created with correct attributes
        assert buffer_manager.hass is hass
        assert buffer_manager.storage_service is storage_service
        assert hasattr(buffer_manager, '_global_buffer_config')
        assert hasattr(buffer_manager, '_entity_states')
    
    def test_managers_have_required_methods(self, hass, storage_service):
        """Test that managers have all required methods for storage integration."""
        presence_manager = PresenceManager(hass, storage_service)
        buffer_manager = BufferManager(hass, storage_service)
        
        # Verify presence manager has required methods
        assert hasattr(presence_manager, 'load_configuration')
        assert hasattr(presence_manager, 'save_configuration')
        assert hasattr(presence_manager, 'update_presence_entities')
        assert hasattr(presence_manager, 'update_presence_rule')
        assert hasattr(presence_manager, 'get_configuration_summary')
        
        # Verify buffer manager has required methods
        assert hasattr(buffer_manager, 'load_configuration')
        assert hasattr(buffer_manager, 'save_configuration')
        assert hasattr(buffer_manager, 'update_global_buffer_config')
        assert hasattr(buffer_manager, 'get_configuration_summary')


class TestVersionCompatibilityScenarios:
    """Test version compatibility scenarios."""
    
    @pytest.mark.asyncio
    async def test_upgrade_from_version_0_1_0_equivalent(self, hass, storage_service):
        """Test upgrade scenario equivalent to version 0.1.0 (no presence/buffer config)."""
        # Simulate very old data (equivalent to 0.1.0 - no presence or buffer config)
        old_schedule_data = ScheduleData(
            version="0.1.0",
            entities_tracked=["climate.thermostat"],
            presence_entities=[],  # Empty in old version
            presence_rule="anyone_home",  # Default
            presence_timeout_seconds=DEFAULT_PRESENCE_TIMEOUT_SECONDS,  # Default
            schedules={"home": {}, "away": {}},
            buffer={},  # Empty in old version
            ui={},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = old_schedule_data
        
        # Create managers
        presence_manager = PresenceManager(hass, storage_service)
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configurations should handle old format
        await presence_manager.load_configuration()
        await buffer_manager.load_configuration()
        
        # Verify managers work with old data
        assert presence_manager._presence_entities == []
        assert presence_manager._presence_rule == "anyone_home"
        assert presence_manager._timeout_seconds == DEFAULT_PRESENCE_TIMEOUT_SECONDS
        
        assert buffer_manager._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager._global_buffer_config.enabled is True
    
    @pytest.mark.asyncio
    async def test_modern_configuration_no_migration_needed(self, hass, storage_service):
        """Test that modern configuration doesn't trigger unnecessary migration."""
        # Modern storage data with presence_config and buffer_config
        modern_presence_config = PresenceConfig(
            entities=["device_tracker.phone"],
            rule="anyone_home",
            timeout_seconds=600
        )
        
        modern_buffer_config = GlobalBufferConfig(
            time_minutes=15,
            value_delta=2.0,
            enabled=True,
            apply_to="climate"
        )
        
        modern_schedule_data = ScheduleData(
            version=VERSION,
            entities_tracked=["climate.living_room"],
            presence_entities=[],  # Legacy field (should be ignored)
            presence_rule="anyone_home",  # Legacy field (should be ignored)
            presence_timeout_seconds=600,  # Legacy field (should be ignored)
            schedules={"home": {}, "away": {}},
            buffer={},  # Legacy field (should be ignored)
            ui={},
            metadata={},
            presence_config=modern_presence_config,
            buffer_config=modern_buffer_config
        )
        
        storage_service.load_schedules.return_value = modern_schedule_data
        
        # Create managers
        presence_manager = PresenceManager(hass, storage_service)
        buffer_manager = BufferManager(hass, storage_service)
        
        # Load configurations should use modern config
        await presence_manager.load_configuration()
        await buffer_manager.load_configuration()
        
        # Verify modern configuration was used
        assert presence_manager._presence_entities == ["device_tracker.phone"]
        assert presence_manager._presence_rule == "anyone_home"
        assert presence_manager._timeout_seconds == 600
        
        assert buffer_manager._global_buffer_config.time_minutes == 15
        assert buffer_manager._global_buffer_config.value_delta == 2.0
        assert buffer_manager._global_buffer_config.enabled is True
        
        # Should not trigger migration (no save calls)
        storage_service.save_schedules.assert_not_called()