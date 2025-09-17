"""Tests for migration and upgrade handling."""
import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.roost_scheduler.migration import (
    MigrationManager,
    UninstallManager,
    migrate_to_0_2_0,
    migrate_to_0_3_0,
)
from custom_components.roost_scheduler.version import VERSION


@pytest.fixture
def hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.config_dir = "/config"
    return hass


@pytest.fixture
def migration_manager(hass):
    """Create migration manager instance."""
    return MigrationManager(hass, "test_entry")


class TestMigrationFunctions:
    """Test individual migration functions."""
    
    def test_migrate_to_0_2_0_adds_presence_config(self):
        """Test migration to 0.2.0 adds presence configuration."""
        old_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.living_room"],
            "schedules": {
                "monday": [{"start": "06:00", "end": "08:00", "target": 20.0}]
            }
        }
        
        migrated = migrate_to_0_2_0(old_data)
        
        assert migrated["presence_entities"] == []
        assert migrated["presence_rule"] == "anyone_home"
        assert migrated["presence_timeout_seconds"] == 600
        assert "home" in migrated["schedules"]
        assert "away" in migrated["schedules"]
        assert migrated["schedules"]["home"]["monday"][0]["target"] == 20.0
    
    def test_migrate_to_0_2_0_preserves_existing_presence(self):
        """Test migration to 0.2.0 preserves existing presence config."""
        old_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "schedules": {"home": {}, "away": {}}
        }
        
        migrated = migrate_to_0_2_0(old_data)
        
        assert migrated["presence_entities"] == ["device_tracker.phone"]
        assert "home" in migrated["schedules"]
        assert "away" in migrated["schedules"]
    
    def test_migrate_to_0_3_0_adds_buffer_config(self):
        """Test migration to 0.3.0 adds buffer configuration."""
        old_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "schedules": {
                "home": {
                    "monday": [{"start": "06:00", "end": "08:00", "target": 20.0}]
                },
                "away": {}
            }
        }
        
        migrated = migrate_to_0_3_0(old_data)
        
        assert "buffer" in migrated
        assert migrated["buffer"]["global"]["time_minutes"] == 15
        assert migrated["buffer"]["global"]["value_delta"] == 2.0
        assert "ui" in migrated
        assert migrated["ui"]["resolution_minutes"] == 30
        assert "metadata" in migrated
        
        # Check target structure migration
        slot = migrated["schedules"]["home"]["monday"][0]
        assert slot["target"]["domain"] == "climate"
        assert slot["target"]["temperature"] == 20.0
        assert slot["buffer_override"] is None
    
    def test_migrate_to_0_3_0_preserves_new_target_structure(self):
        """Test migration to 0.3.0 preserves new target structure."""
        old_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "schedules": {
                "home": {
                    "monday": [{
                        "start": "06:00", 
                        "end": "08:00", 
                        "target": {"domain": "climate", "temperature": 20.0}
                    }]
                },
                "away": {}
            }
        }
        
        migrated = migrate_to_0_3_0(old_data)
        
        slot = migrated["schedules"]["home"]["monday"][0]
        assert slot["target"]["domain"] == "climate"
        assert slot["target"]["temperature"] == 20.0


class TestMigrationManager:
    """Test migration manager functionality."""
    
    @pytest.mark.asyncio
    async def test_migrate_if_needed_no_migration(self, migration_manager):
        """Test no migration needed for current version."""
        data = {"version": VERSION, "entities_tracked": []}
        
        result = await migration_manager.migrate_if_needed(data)
        
        assert result == data
    
    @pytest.mark.asyncio
    async def test_migrate_if_needed_empty_data(self, migration_manager):
        """Test migration with empty data."""
        result = await migration_manager.migrate_if_needed({})
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_migrate_if_needed_unsupported_version(self, migration_manager):
        """Test migration fails for unsupported version."""
        data = {"version": "0.0.1", "entities_tracked": []}
        
        with pytest.raises(ValueError, match="Unsupported migration"):
            await migration_manager.migrate_if_needed(data)
    
    @pytest.mark.asyncio
    async def test_migrate_if_needed_full_migration(self, migration_manager):
        """Test full migration from 0.1.0 to current."""
        data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.living_room"],
            "schedules": {
                "monday": [{"start": "06:00", "end": "08:00", "target": 20.0}]
            }
        }
        
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(data)
        
        assert result["version"] == VERSION
        assert "presence_entities" in result
        assert "buffer" in result
        assert "metadata" in result
        assert "last_migration" in result["metadata"]
    
    @pytest.mark.asyncio
    async def test_validate_migrated_data_valid(self, migration_manager):
        """Test validation of valid migrated data."""
        data = {
            "version": VERSION,
            "entities_tracked": ["climate.living_room"],
            "schedules": {
                "home": {
                    "monday": [{
                        "start": "06:00",
                        "end": "08:00", 
                        "target": {"domain": "climate", "temperature": 20.0}
                    }]
                },
                "away": {}
            }
        }
        
        result = await migration_manager.validate_migrated_data(data)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_migrated_data_invalid(self, migration_manager):
        """Test validation of invalid migrated data."""
        data = {
            "version": VERSION,
            # Missing required keys
        }
        
        result = await migration_manager.validate_migrated_data(data)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_migrated_data_wrong_version(self, migration_manager):
        """Test validation fails for wrong version."""
        data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.living_room"],
            "schedules": {"home": {}, "away": {}}
        }
        
        result = await migration_manager.validate_migrated_data(data)
        
        assert result is False


class TestUninstallManager:
    """Test uninstall manager functionality."""
    
    @pytest.fixture
    def uninstall_manager(self, hass):
        """Create uninstall manager instance."""
        return UninstallManager(hass)
    
    @pytest.mark.asyncio
    async def test_prepare_uninstall_preserve_data(self, uninstall_manager):
        """Test uninstall preparation with data preservation."""
        with patch.object(uninstall_manager, '_create_final_backup') as mock_backup, \
             patch.object(uninstall_manager, '_create_uninstall_info') as mock_info:
            
            mock_backup.return_value = ["/config/backup1.json"]
            mock_info.return_value = None
            
            result = await uninstall_manager.prepare_uninstall(preserve_data=True)
        
        assert result["preserve_data"] is True
        assert result["backup_locations"] == ["/config/backup1.json"]
        assert "timestamp" in result
        mock_backup.assert_called_once()
        mock_info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prepare_uninstall_cleanup_data(self, uninstall_manager):
        """Test uninstall preparation with data cleanup."""
        with patch.object(uninstall_manager, '_cleanup_all_data') as mock_cleanup:
            mock_cleanup.return_value = ["Removed storage file: test.json"]
            
            result = await uninstall_manager.prepare_uninstall(preserve_data=False)
        
        assert result["preserve_data"] is False
        assert result["cleanup_actions"] == ["Removed storage file: test.json"]
        mock_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_final_backup(self, uninstall_manager):
        """Test final backup creation."""
        mock_storage_dir = MagicMock()
        mock_file = MagicMock()
        mock_file.is_file.return_value = True
        mock_file.name = "roost_scheduler_test.json"
        mock_storage_dir.glob.return_value = [mock_file]
        
        with patch('pathlib.Path') as mock_path, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_path.return_value.mkdir = MagicMock()
            mock_path.return_value.__truediv__ = lambda self, other: mock_path.return_value
            
            # Mock the storage directory path
            config_path = mock_path.return_value
            config_path.__truediv__.return_value = mock_storage_dir
            
            mock_file.open = MagicMock()
            mock_file.open.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_file.open.return_value.__exit__ = MagicMock(return_value=None)
            
            result = await uninstall_manager._create_final_backup()
        
        # Should attempt to create backups
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_restore_from_backup_success(self, uninstall_manager):
        """Test successful backup restoration."""
        backup_data = {
            "version": VERSION,
            "entities_tracked": ["climate.living_room"],
            "schedules": {"home": {}, "away": {}},
            "entry_id": "test_entry"
        }
        
        with patch('pathlib.Path') as mock_path, \
             patch('builtins.open', create=True) as mock_open, \
             patch('homeassistant.helpers.storage.Store') as mock_store:
            
            mock_path.return_value.exists.return_value = True
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(backup_data)
            
            mock_store_instance = AsyncMock()
            mock_store.return_value = mock_store_instance
            
            result = await uninstall_manager.restore_from_backup("/config/backup.json")
        
        assert result is True
        mock_store_instance.async_save.assert_called_once_with(backup_data)
    
    @pytest.mark.asyncio
    async def test_restore_from_backup_file_not_found(self, uninstall_manager):
        """Test backup restoration with missing file."""
        with patch('pathlib.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            
            result = await uninstall_manager.restore_from_backup("/config/missing.json")
        
        assert result is False


class TestUpgradeScenarios:
    """Test various upgrade scenarios."""
    
    @pytest.mark.asyncio
    async def test_upgrade_from_0_1_0_to_current(self, migration_manager):
        """Test complete upgrade path from 0.1.0."""
        old_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.living_room"],
            "schedules": {
                "monday": [
                    {"start": "06:00", "end": "08:00", "target": 20.0},
                    {"start": "18:00", "end": "22:00", "target": 22.0}
                ],
                "tuesday": [
                    {"start": "07:00", "end": "09:00", "target": 19.0}
                ]
            }
        }
        
        with patch.object(migration_manager, '_create_migration_backup'):
            result = await migration_manager.migrate_if_needed(old_data)
        
        # Verify final structure
        assert result["version"] == VERSION
        assert "presence_entities" in result
        assert "buffer" in result
        assert "ui" in result
        assert "metadata" in result
        
        # Verify schedule structure
        assert "home" in result["schedules"]
        assert "away" in result["schedules"]
        
        # Verify target structure conversion
        monday_slots = result["schedules"]["home"]["monday"]
        assert len(monday_slots) == 2
        assert monday_slots[0]["target"]["temperature"] == 20.0
        assert monday_slots[1]["target"]["temperature"] == 22.0
        
        tuesday_slots = result["schedules"]["home"]["tuesday"]
        assert len(tuesday_slots) == 1
        assert tuesday_slots[0]["target"]["temperature"] == 19.0
    
    @pytest.mark.asyncio
    async def test_upgrade_preserves_user_data(self, migration_manager):
        """Test that upgrade preserves user customizations."""
        old_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room", "climate.bedroom"],
            "presence_entities": ["device_tracker.phone", "person.user"],
            "presence_rule": "everyone_home",
            "presence_timeout_seconds": 300,
            "schedules": {
                "home": {
                    "monday": [{
                        "start": "06:00",
                        "end": "08:00", 
                        "target": {"domain": "climate", "temperature": 21.5}
                    }]
                },
                "away": {
                    "monday": [{
                        "start": "08:00",
                        "end": "18:00",
                        "target": {"domain": "climate", "temperature": 16.0}
                    }]
                }
            }
        }
        
        with patch.object(migration_manager, '_create_migration_backup'):
            result = await migration_manager.migrate_if_needed(old_data)
        
        # Verify user data is preserved
        assert result["entities_tracked"] == ["climate.living_room", "climate.bedroom"]
        assert result["presence_entities"] == ["device_tracker.phone", "person.user"]
        assert result["presence_rule"] == "everyone_home"
        assert result["presence_timeout_seconds"] == 300
        
        # Verify schedules are preserved
        home_slot = result["schedules"]["home"]["monday"][0]
        assert home_slot["target"]["temperature"] == 21.5
        
        away_slot = result["schedules"]["away"]["monday"][0]
        assert away_slot["target"]["temperature"] == 16.0