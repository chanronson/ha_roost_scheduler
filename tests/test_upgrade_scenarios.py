"""Tests for upgrade scenarios and version compatibility."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.roost_scheduler.storage import StorageService
from custom_components.roost_scheduler.migration import MigrationManager
from custom_components.roost_scheduler.version import VERSION


@pytest.fixture
def hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.config_dir = "/config"
    return hass


@pytest.fixture
def storage_service(hass):
    """Create storage service instance."""
    return StorageService(hass, "test_entry")


class TestUpgradeScenarios:
    """Test various upgrade scenarios."""
    
    @pytest.mark.asyncio
    async def test_fresh_install_no_migration(self, storage_service):
        """Test fresh install with no existing data."""
        with patch.object(storage_service._store, 'async_load') as mock_load:
            mock_load.return_value = None
            
            result = await storage_service.load_schedules()
        
        assert result is None
        mock_load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upgrade_from_0_1_0_with_simple_schedule(self, storage_service):
        """Test upgrade from 0.1.0 with simple schedule data."""
        old_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.thermostat"],
            "schedules": {
                "monday": [
                    {"start": "06:00", "end": "08:00", "target": 20.0}
                ]
            }
        }
        
        with patch.object(storage_service._store, 'async_load') as mock_load, \
             patch.object(storage_service._store, 'async_save') as mock_save, \
             patch('custom_components.roost_scheduler.models.ScheduleData.from_dict') as mock_from_dict:
            
            mock_load.return_value = old_data
            mock_save.return_value = None
            
            # Mock ScheduleData creation
            mock_schedule_data = MagicMock()
            mock_from_dict.return_value = mock_schedule_data
            
            result = await storage_service.load_schedules()
        
        # Verify migration was triggered
        mock_save.assert_called_once()
        
        # Verify the saved data has current version
        saved_data = mock_save.call_args[0][0]
        assert saved_data["version"] == VERSION
        assert "presence_entities" in saved_data
        assert "buffer" in saved_data
    
    @pytest.mark.asyncio
    async def test_upgrade_from_0_2_0_preserves_presence_config(self, storage_service):
        """Test upgrade from 0.2.0 preserves presence configuration."""
        old_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "everyone_home",
            "presence_timeout_seconds": 300,
            "schedules": {
                "home": {"monday": []},
                "away": {"monday": []}
            }
        }
        
        with patch.object(storage_service._store, 'async_load') as mock_load, \
             patch.object(storage_service._store, 'async_save') as mock_save, \
             patch('custom_components.roost_scheduler.models.ScheduleData.from_dict') as mock_from_dict:
            
            mock_load.return_value = old_data
            mock_save.return_value = None
            mock_from_dict.return_value = MagicMock()
            
            await storage_service.load_schedules()
        
        saved_data = mock_save.call_args[0][0]
        assert saved_data["version"] == VERSION
        assert saved_data["presence_entities"] == ["device_tracker.phone"]
        assert saved_data["presence_rule"] == "everyone_home"
        assert saved_data["presence_timeout_seconds"] == 300
        assert "buffer" in saved_data  # New in 0.3.0
    
    @pytest.mark.asyncio
    async def test_upgrade_handles_corrupted_data_with_recovery(self, storage_service):
        """Test upgrade handles corrupted data and attempts recovery."""
        corrupted_data = {
            "version": "0.2.0",
            "entities_tracked": "invalid_format",  # Should be list
            "schedules": "also_invalid"  # Should be dict
        }
        
        recovery_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.living_room"],
            "schedules": {"monday": []}
        }
        
        with patch.object(storage_service._store, 'async_load') as mock_load, \
             patch.object(storage_service, '_attempt_recovery') as mock_recovery, \
             patch('custom_components.roost_scheduler.models.ScheduleData.from_dict') as mock_from_dict:
            
            mock_load.return_value = corrupted_data
            mock_recovery.return_value = MagicMock()
            mock_from_dict.side_effect = [ValueError("Invalid data"), MagicMock()]
            
            result = await storage_service.load_schedules()
        
        # Should attempt recovery when validation fails
        mock_recovery.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_backup_import_with_migration(self, storage_service):
        """Test importing backup file that needs migration."""
        backup_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.bedroom"],
            "schedules": {
                "tuesday": [
                    {"start": "07:00", "end": "09:00", "target": 19.5}
                ]
            }
        }
        
        with patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open, \
             patch.object(storage_service, 'save_schedules') as mock_save:
            
            mock_exists.return_value = True
            mock_open.return_value.__enter__.return_value.read.return_value = "json_data"
            
            # Mock json.load to return our test data
            with patch('json.load') as mock_json_load:
                mock_json_load.return_value = backup_data
                mock_save.return_value = None
                
                result = await storage_service.import_backup("/config/backup.json")
        
        assert result is True
        mock_save.assert_called_once()
        
        # Verify the data passed to save_schedules was migrated
        saved_schedule_data = mock_save.call_args[0][0]
        # The ScheduleData object should have been created from migrated data
        assert saved_schedule_data is not None
    
    @pytest.mark.asyncio
    async def test_multiple_version_jumps(self, storage_service):
        """Test migration across multiple versions."""
        # Simulate data that has been through partial migrations
        partially_migrated_data = {
            "version": "0.1.0",  # Old version
            "entities_tracked": ["climate.main"],
            "schedules": {
                "wednesday": [
                    {"start": "06:30", "end": "08:30", "target": 21.0}
                ]
            },
            # Some 0.2.0 features already present (partial migration scenario)
            "presence_entities": ["device_tracker.tablet"]
        }
        
        with patch.object(storage_service._store, 'async_load') as mock_load, \
             patch.object(storage_service._store, 'async_save') as mock_save, \
             patch('custom_components.roost_scheduler.models.ScheduleData.from_dict') as mock_from_dict:
            
            mock_load.return_value = partially_migrated_data
            mock_save.return_value = None
            mock_from_dict.return_value = MagicMock()
            
            await storage_service.load_schedules()
        
        saved_data = mock_save.call_args[0][0]
        
        # Should reach current version
        assert saved_data["version"] == VERSION
        
        # Should preserve existing presence config
        assert saved_data["presence_entities"] == ["device_tracker.tablet"]
        
        # Should add missing 0.2.0 features
        assert "presence_rule" in saved_data
        assert "presence_timeout_seconds" in saved_data
        
        # Should add 0.3.0 features
        assert "buffer" in saved_data
        assert "ui" in saved_data
        
        # Should migrate schedule structure
        assert "home" in saved_data["schedules"]
        assert "away" in saved_data["schedules"]
    
    @pytest.mark.asyncio
    async def test_downgrade_prevention(self, storage_service):
        """Test that downgrade attempts are handled gracefully."""
        future_data = {
            "version": "1.0.0",  # Future version
            "entities_tracked": ["climate.future"],
            "schedules": {"home": {}, "away": {}}
        }
        
        with patch.object(storage_service._store, 'async_load') as mock_load, \
             patch('custom_components.roost_scheduler.version.is_version_supported') as mock_supported:
            
            mock_load.return_value = future_data
            mock_supported.return_value = False  # Future version not supported
            
            # Should raise error for unsupported version
            with pytest.raises(Exception):
                await storage_service.load_schedules()
    
    @pytest.mark.asyncio
    async def test_migration_backup_creation(self, storage_service):
        """Test that migration creates backup before proceeding."""
        old_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.test"],
            "schedules": {"monday": []}
        }
        
        with patch.object(storage_service._store, 'async_load') as mock_load, \
             patch.object(storage_service._store, 'async_save') as mock_save, \
             patch.object(storage_service._migration_manager, '_create_migration_backup') as mock_backup, \
             patch('custom_components.roost_scheduler.models.ScheduleData.from_dict') as mock_from_dict:
            
            mock_load.return_value = old_data
            mock_save.return_value = None
            mock_backup.return_value = None
            mock_from_dict.return_value = MagicMock()
            
            await storage_service.load_schedules()
        
        # Should create backup before migration
        mock_backup.assert_called_once_with(old_data, "0.1.0")
    
    @pytest.mark.asyncio
    async def test_validation_after_migration(self, storage_service):
        """Test that data is validated after migration."""
        old_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.test"],
            "schedules": {"monday": []}
        }
        
        with patch.object(storage_service._store, 'async_load') as mock_load, \
             patch.object(storage_service._migration_manager, 'validate_migrated_data') as mock_validate:
            
            mock_load.return_value = old_data
            mock_validate.return_value = False  # Validation fails
            
            # Should raise error if validation fails
            with pytest.raises(Exception):
                await storage_service.load_schedules()
        
        mock_validate.assert_called_once()


class TestVersionCompatibility:
    """Test version compatibility checks."""
    
    def test_version_validation_in_init(self):
        """Test version validation during integration initialization."""
        from custom_components.roost_scheduler.version import validate_manifest_version
        
        with patch('custom_components.roost_scheduler.version.get_manifest_version') as mock_get_version:
            mock_get_version.return_value = VERSION
            
            result = validate_manifest_version()
            assert result is True
            
            mock_get_version.return_value = "0.1.0"
            result = validate_manifest_version()
            assert result is False
    
    def test_ha_version_validation(self):
        """Test Home Assistant version validation."""
        from custom_components.roost_scheduler import _validate_ha_version
        
        mock_hass = MagicMock()
        
        with patch('homeassistant.const.__version__', "2024.1.0"):
            result = _validate_ha_version(mock_hass)
            assert result is True
        
        with patch('homeassistant.const.__version__', "2022.12.0"):
            result = _validate_ha_version(mock_hass)
            assert result is False
    
    def test_dependency_validation(self):
        """Test dependency validation."""
        from custom_components.roost_scheduler import _validate_dependencies
        
        mock_hass = MagicMock()
        mock_hass.config.components = {"frontend", "websocket_api", "device_tracker"}
        
        result = _validate_dependencies(mock_hass)
        assert result is True
        
        # Missing required dependency
        mock_hass.config.components = {"device_tracker"}
        result = _validate_dependencies(mock_hass)
        assert result is False