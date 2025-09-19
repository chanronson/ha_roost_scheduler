"""Tests for manager configuration migration system."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from custom_components.roost_scheduler.migration import ConfigurationMigrationManager
from custom_components.roost_scheduler.models import ScheduleData, PresenceConfig, GlobalBufferConfig
from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.const import DEFAULT_PRESENCE_TIMEOUT_SECONDS, DEFAULT_BUFFER_TIME_MINUTES, DEFAULT_BUFFER_VALUE_DELTA


@pytest.fixture
def hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.config_dir = "/config"
    return hass


@pytest.fixture
def storage_service():
    """Mock storage service."""
    storage_service = AsyncMock()
    storage_service.get_config_entry_data = MagicMock()
    return storage_service


@pytest.fixture
def migration_manager(hass, storage_service):
    """Create configuration migration manager instance."""
    return ConfigurationMigrationManager(hass, storage_service)


class TestPresenceConfigurationMigration:
    """Test presence configuration migration scenarios."""
    
    @pytest.mark.asyncio
    async def test_migrate_presence_from_legacy_schedule_data(self, migration_manager, storage_service):
        """Test migrating presence configuration from legacy schedule data fields."""
        # Setup legacy schedule data
        legacy_schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone", "person.user"],
            presence_rule="everyone_home",
            presence_timeout_seconds=300,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        result = await migration_manager.migrate_presence_configuration()
        
        assert result is True
        storage_service.save_schedules.assert_called_once()
        
        # Verify the saved schedule data has presence_config
        saved_data = storage_service.save_schedules.call_args[0][0]
        assert saved_data.presence_config is not None
        assert saved_data.presence_config.entities == ["device_tracker.phone", "person.user"]
        assert saved_data.presence_config.rule == "everyone_home"
        assert saved_data.presence_config.timeout_seconds == 300
    
    @pytest.mark.asyncio
    async def test_migrate_presence_from_config_entry(self, migration_manager, storage_service):
        """Test migrating presence configuration from config entry data."""
        # No existing schedule data
        storage_service.load_schedules.return_value = None
        
        # Config entry data
        config_entry_data = {
            'presence_entities': ['device_tracker.phone'],
            'presence_rule': 'anyone_home',
            'presence_timeout_seconds': 600
        }
        storage_service.get_config_entry_data.return_value = config_entry_data
        
        result = await migration_manager.migrate_presence_configuration()
        
        assert result is True
        storage_service.save_schedules.assert_called_once()
        
        # Verify the saved schedule data
        saved_data = storage_service.save_schedules.call_args[0][0]
        assert saved_data.presence_config is not None
        assert saved_data.presence_config.entities == ['device_tracker.phone']
        assert saved_data.presence_config.rule == 'anyone_home'
        assert saved_data.presence_config.timeout_seconds == 600
    
    @pytest.mark.asyncio
    async def test_migrate_presence_already_modern(self, migration_manager, storage_service):
        """Test that migration skips when modern configuration already exists."""
        # Modern schedule data with presence_config
        modern_schedule_data = ScheduleData(
            version="0.3.1",
            entities_tracked=["climate.living_room"],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            presence_config=PresenceConfig(
                entities=["device_tracker.phone"],
                rule="anyone_home",
                timeout_seconds=600
            )
        )
        
        storage_service.load_schedules.return_value = modern_schedule_data
        
        result = await migration_manager.migrate_presence_configuration()
        
        assert result is True
        # Should not save since modern config already exists
        storage_service.save_schedules.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_migrate_presence_no_data_found(self, migration_manager, storage_service):
        """Test migration when no presence data is found."""
        # No schedule data
        storage_service.load_schedules.return_value = None
        # No config entry data
        storage_service.get_config_entry_data.return_value = {}
        
        result = await migration_manager.migrate_presence_configuration()
        
        assert result is True
        # Should not save since no data to migrate
        storage_service.save_schedules.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_migrate_presence_error_handling(self, migration_manager, storage_service):
        """Test error handling during presence migration."""
        storage_service.load_schedules.side_effect = Exception("Storage error")
        
        result = await migration_manager.migrate_presence_configuration()
        
        assert result is False


class TestBufferConfigurationMigration:
    """Test buffer configuration migration scenarios."""
    
    @pytest.mark.asyncio
    async def test_migrate_buffer_from_legacy_schedule_data(self, migration_manager, storage_service):
        """Test migrating buffer configuration from legacy schedule data fields."""
        # Setup legacy schedule data with buffer config
        from custom_components.roost_scheduler.models import BufferConfig
        
        legacy_buffer_config = BufferConfig(
            time_minutes=20,
            value_delta=3.0,
            enabled=True,
            apply_to="climate"
        )
        
        legacy_schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={"global": legacy_buffer_config},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        result = await migration_manager.migrate_buffer_configuration()
        
        assert result is True
        storage_service.save_schedules.assert_called_once()
        
        # Verify the saved schedule data has buffer_config
        saved_data = storage_service.save_schedules.call_args[0][0]
        assert saved_data.buffer_config is not None
        assert saved_data.buffer_config.time_minutes == 20
        assert saved_data.buffer_config.value_delta == 3.0
        assert saved_data.buffer_config.enabled is True
        assert saved_data.buffer_config.apply_to == "climate"
    
    @pytest.mark.asyncio
    async def test_migrate_buffer_from_config_entry(self, migration_manager, storage_service):
        """Test migrating buffer configuration from config entry data."""
        # No existing schedule data
        storage_service.load_schedules.return_value = None
        
        # Config entry data
        config_entry_data = {
            'buffer_time_minutes': 25,
            'buffer_value_delta': 1.5,
            'buffer_enabled': False
        }
        storage_service.get_config_entry_data.return_value = config_entry_data
        
        result = await migration_manager.migrate_buffer_configuration()
        
        assert result is True
        storage_service.save_schedules.assert_called_once()
        
        # Verify the saved schedule data
        saved_data = storage_service.save_schedules.call_args[0][0]
        assert saved_data.buffer_config is not None
        assert saved_data.buffer_config.time_minutes == 25
        assert saved_data.buffer_config.value_delta == 1.5
        assert saved_data.buffer_config.enabled is False
    
    @pytest.mark.asyncio
    async def test_migrate_buffer_already_modern(self, migration_manager, storage_service):
        """Test that migration skips when modern buffer configuration already exists."""
        # Modern schedule data with buffer_config
        modern_schedule_data = ScheduleData(
            version="0.3.1",
            entities_tracked=["climate.living_room"],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            buffer_config=GlobalBufferConfig(
                time_minutes=15,
                value_delta=2.0,
                enabled=True,
                apply_to="climate"
            )
        )
        
        storage_service.load_schedules.return_value = modern_schedule_data
        
        result = await migration_manager.migrate_buffer_configuration()
        
        assert result is True
        # Should not save since modern config already exists
        storage_service.save_schedules.assert_not_called()


class TestPresenceManagerMigration:
    """Test PresenceManager configuration migration."""
    
    @pytest.fixture
    def presence_manager(self, hass, storage_service):
        """Create PresenceManager instance."""
        return PresenceManager(hass, storage_service)
    
    @pytest.mark.asyncio
    async def test_presence_manager_detect_and_migrate_modern_config(self, presence_manager, storage_service):
        """Test PresenceManager detects and loads modern configuration."""
        # Modern schedule data
        modern_config = PresenceConfig(
            entities=["device_tracker.phone"],
            rule="anyone_home",
            timeout_seconds=600
        )
        
        schedule_data = ScheduleData(
            version="0.3.1",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            presence_config=modern_config
        )
        
        storage_service.load_schedules.return_value = schedule_data
        
        await presence_manager._detect_and_migrate_configuration()
        
        assert presence_manager._presence_config == modern_config
        assert presence_manager._presence_entities == ["device_tracker.phone"]
        assert presence_manager._presence_rule == "anyone_home"
        assert presence_manager._timeout_seconds == 600
    
    @pytest.mark.asyncio
    async def test_presence_manager_migrate_from_legacy_fields(self, presence_manager, storage_service):
        """Test PresenceManager migrates from legacy fields."""
        # Legacy schedule data
        legacy_schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=["device_tracker.phone", "person.user"],
            presence_rule="everyone_home",
            presence_timeout_seconds=300,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        await presence_manager._detect_and_migrate_configuration()
        
        assert presence_manager._presence_entities == ["device_tracker.phone", "person.user"]
        assert presence_manager._presence_rule == "everyone_home"
        assert presence_manager._timeout_seconds == 300
        
        # Should have saved the migrated configuration
        storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_presence_manager_migrate_from_config_entry(self, presence_manager, storage_service):
        """Test PresenceManager migrates from config entry data."""
        # No schedule data
        storage_service.load_schedules.return_value = None
        
        # Config entry data
        config_entry_data = {
            'presence_entities': ['device_tracker.phone'],
            'presence_rule': 'anyone_home',
            'presence_timeout_seconds': 600
        }
        storage_service.get_config_entry_data.return_value = config_entry_data
        
        await presence_manager._detect_and_migrate_configuration()
        
        assert presence_manager._presence_entities == ['device_tracker.phone']
        assert presence_manager._presence_rule == 'anyone_home'
        assert presence_manager._timeout_seconds == 600
        
        # Should have saved the migrated configuration
        storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_presence_manager_initialize_defaults_no_data(self, presence_manager, storage_service):
        """Test PresenceManager initializes defaults when no data found."""
        # No schedule data
        storage_service.load_schedules.return_value = None
        # No config entry data
        storage_service.get_config_entry_data.return_value = {}
        
        await presence_manager._detect_and_migrate_configuration()
        
        assert presence_manager._presence_entities == []
        assert presence_manager._presence_rule == "anyone_home"
        assert presence_manager._timeout_seconds == DEFAULT_PRESENCE_TIMEOUT_SECONDS


class TestBufferManagerMigration:
    """Test BufferManager configuration migration."""
    
    @pytest.fixture
    def buffer_manager(self, hass, storage_service):
        """Create BufferManager instance."""
        return BufferManager(hass, storage_service)
    
    @pytest.mark.asyncio
    async def test_buffer_manager_detect_and_migrate_modern_config(self, buffer_manager, storage_service):
        """Test BufferManager detects and loads modern configuration."""
        # Modern buffer config
        modern_config = GlobalBufferConfig(
            time_minutes=20,
            value_delta=3.0,
            enabled=True,
            apply_to="climate"
        )
        
        schedule_data = ScheduleData(
            version="0.3.1",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            buffer_config=modern_config
        )
        
        storage_service.load_schedules.return_value = schedule_data
        
        await buffer_manager._detect_and_migrate_configuration()
        
        assert buffer_manager._global_buffer_config == modern_config
        assert buffer_manager._global_buffer_config.time_minutes == 20
        assert buffer_manager._global_buffer_config.value_delta == 3.0
    
    @pytest.mark.asyncio
    async def test_buffer_manager_migrate_from_legacy_fields(self, buffer_manager, storage_service):
        """Test BufferManager migrates from legacy buffer fields."""
        # Legacy schedule data with buffer config
        from custom_components.roost_scheduler.models import BufferConfig
        
        legacy_buffer_config = BufferConfig(
            time_minutes=25,
            value_delta=1.5,
            enabled=False,
            apply_to="climate"
        )
        
        legacy_schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={"global": legacy_buffer_config},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        await buffer_manager._detect_and_migrate_configuration()
        
        assert buffer_manager._global_buffer_config.time_minutes == 25
        assert buffer_manager._global_buffer_config.value_delta == 1.5
        assert buffer_manager._global_buffer_config.enabled is False
        
        # Should have saved the migrated configuration
        storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_buffer_manager_initialize_defaults_no_data(self, buffer_manager, storage_service):
        """Test BufferManager initializes defaults when no data found."""
        # No schedule data
        storage_service.load_schedules.return_value = None
        # No config entry data
        storage_service.get_config_entry_data.return_value = {}
        
        await buffer_manager._detect_and_migrate_configuration()
        
        assert buffer_manager._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
        assert buffer_manager._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
        assert buffer_manager._global_buffer_config.enabled is True


class TestIntegrationMigrationScenarios:
    """Test complete integration migration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_migration_from_legacy_to_modern(self, migration_manager, storage_service):
        """Test complete migration from legacy configuration to modern format."""
        # Legacy schedule data with both presence and buffer config
        from custom_components.roost_scheduler.models import BufferConfig
        
        legacy_buffer_config = BufferConfig(
            time_minutes=20,
            value_delta=2.5,
            enabled=True,
            apply_to="climate"
        )
        
        legacy_schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone", "person.user"],
            presence_rule="everyone_home",
            presence_timeout_seconds=300,
            buffer={"global": legacy_buffer_config},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        result = await migration_manager.migrate_all_configurations()
        
        assert result is True
        
        # Should have been called twice (once for presence, once for buffer)
        assert storage_service.save_schedules.call_count == 2
        
        # Verify both configurations were migrated
        saved_calls = storage_service.save_schedules.call_args_list
        
        # Check that at least one call has presence_config
        presence_migrated = any(
            call[0][0].presence_config is not None 
            for call in saved_calls
        )
        assert presence_migrated
        
        # Check that at least one call has buffer_config
        buffer_migrated = any(
            call[0][0].buffer_config is not None 
            for call in saved_calls
        )
        assert buffer_migrated
    
    @pytest.mark.asyncio
    async def test_migration_error_handling(self, migration_manager, storage_service):
        """Test error handling during migration."""
        # Simulate storage error
        storage_service.load_schedules.side_effect = Exception("Storage error")
        
        result = await migration_manager.migrate_all_configurations()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_partial_migration_failure(self, migration_manager, storage_service):
        """Test handling of partial migration failures."""
        # Setup so presence migration succeeds but buffer fails
        from custom_components.roost_scheduler.models import BufferConfig
        
        legacy_buffer_config = BufferConfig(
            time_minutes=20,
            value_delta=2.5,
            enabled=True,
            apply_to="climate"
        )
        
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=["device_tracker.phone"],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={"global": legacy_buffer_config},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = schedule_data
        
        # Make buffer migration fail by causing an error during save
        def side_effect(*args, **kwargs):
            saved_data = args[0]
            if hasattr(saved_data, 'buffer_config') and saved_data.buffer_config:
                raise Exception("Buffer save error")
            return None
        
        storage_service.save_schedules.side_effect = side_effect
        
        result = await migration_manager.migrate_all_configurations()
        
        # Should return False due to buffer migration failure
        assert result is False


class TestMigrationLogging:
    """Test migration logging and error reporting."""
    
    @pytest.mark.asyncio
    async def test_migration_logging_success(self, migration_manager, storage_service, caplog):
        """Test that successful migrations are properly logged."""
        # Setup for successful migration
        legacy_schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=[],
            presence_entities=["device_tracker.phone"],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        storage_service.load_schedules.return_value = legacy_schedule_data
        
        await migration_manager.migrate_presence_configuration()
        
        # Check that success is logged
        assert "Successfully migrated presence configuration from legacy fields" in caplog.text
    
    @pytest.mark.asyncio
    async def test_migration_logging_errors(self, migration_manager, storage_service, caplog):
        """Test that migration errors are properly logged."""
        # Setup for migration error
        storage_service.load_schedules.side_effect = Exception("Test error")
        
        await migration_manager.migrate_presence_configuration()
        
        # Check that error is logged
        assert "Failed to migrate presence configuration" in caplog.text
        assert "Test error" in caplog.text