"""Tests for the storage service."""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.roost_scheduler.models import BufferConfig, ScheduleData, ScheduleSlot
from custom_components.roost_scheduler.storage import CorruptedDataError, StorageError, StorageService


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config = MagicMock()
    hass.config.config_dir = "/config"
    return hass


@pytest.fixture
def sample_schedule_data():
    """Create sample schedule data for testing."""
    buffer_config = BufferConfig(time_minutes=15, value_delta=2.0, enabled=True)
    
    schedule_slot = ScheduleSlot(
        day="monday",
        start_time="06:00",
        end_time="08:00",
        target_value=20.0,
        entity_domain="climate"
    )
    
    return ScheduleData(
        version="0.3.0",
        entities_tracked=["climate.living_room"],
        presence_entities=["device_tracker.phone"],
        presence_rule="anyone_home",
        presence_timeout_seconds=600,
        buffer={"global": buffer_config},
        ui={"resolution_minutes": 30},
        schedules={"home": {"monday": [schedule_slot]}},
        metadata={"created_at": "2025-09-16T12:00:00Z"}
    )


@pytest.fixture
def storage_service(mock_hass):
    """Create a storage service instance."""
    with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
        mock_store = AsyncMock(spec=Store)
        mock_store_class.return_value = mock_store
        
        service = StorageService(mock_hass, "test_entry")
        service._store = mock_store
        return service


class TestStorageService:
    """Test the StorageService class."""
    
    @pytest.mark.asyncio
    async def test_load_schedules_success(self, storage_service, sample_schedule_data):
        """Test successful loading of schedule data."""
        # Setup mock to return valid data
        storage_service._store.async_load.return_value = sample_schedule_data.to_dict()
        
        # Load schedules
        result = await storage_service.load_schedules()
        
        # Verify result
        assert result is not None
        assert isinstance(result, ScheduleData)
        assert result.version == "0.3.0"
        assert len(result.entities_tracked) == 1
        assert "climate.living_room" in result.entities_tracked
        
        # Verify store was called
        storage_service._store.async_load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_schedules_no_data(self, storage_service):
        """Test loading when no data exists."""
        # Setup mock to return None
        storage_service._store.async_load.return_value = None
        
        # Load schedules
        result = await storage_service.load_schedules()
        
        # Verify result
        assert result is None
        storage_service._store.async_load.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_schedules_corrupted_data(self, storage_service):
        """Test loading corrupted data triggers recovery."""
        # Setup mock to return invalid data
        invalid_data = {"invalid": "data"}
        storage_service._store.async_load.return_value = invalid_data
        
        # Mock recovery attempt
        with patch.object(storage_service, '_attempt_recovery', return_value=None) as mock_recovery:
            # Load schedules
            result = await storage_service.load_schedules()
            
            # Verify recovery was attempted
            mock_recovery.assert_called_once()
            assert result is None
    
    @pytest.mark.asyncio
    async def test_save_schedules_success(self, storage_service, sample_schedule_data):
        """Test successful saving of schedule data."""
        # Save schedules
        await storage_service.save_schedules(sample_schedule_data)
        
        # Verify store was called with correct data
        storage_service._store.async_save.assert_called_once()
        saved_data = storage_service._store.async_save.call_args[0][0]
        
        # Verify metadata was updated
        assert "last_modified" in saved_data["metadata"]
        assert saved_data["version"] == "0.3.0"
    
    @pytest.mark.asyncio
    async def test_save_schedules_invalid_data(self, storage_service):
        """Test saving invalid data raises error."""
        # Create invalid schedule data
        invalid_data = ScheduleData(
            version="",  # Invalid empty version
            entities_tracked=[],
            presence_entities=[],
            presence_rule="invalid_rule",  # Invalid rule
            presence_timeout_seconds=-1,  # Invalid timeout
            buffer={},
            ui={},
            schedules={},
            metadata={}
        )
        
        # Attempt to save invalid data
        with pytest.raises(StorageError):
            await storage_service.save_schedules(invalid_data)
    
    @pytest.mark.asyncio
    async def test_export_backup_success(self, storage_service, sample_schedule_data):
        """Test successful backup export."""
        storage_service._schedule_data = sample_schedule_data
        
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            # Export backup
            backup_path = await storage_service.export_backup()
            
            # Verify file was created
            assert os.path.exists(backup_path)
            
            # Verify file contents
            with open(backup_path, 'r') as f:
                data = json.load(f)
            
            assert data["version"] == "0.3.0"
            assert "climate.living_room" in data["entities_tracked"]
    
    @pytest.mark.asyncio
    async def test_export_backup_no_data(self, storage_service):
        """Test export backup with no data raises error."""
        storage_service._schedule_data = None
        
        # Mock load_schedules to return None
        with patch.object(storage_service, 'load_schedules', return_value=None):
            with pytest.raises(StorageError, match="No schedule data to export"):
                await storage_service.export_backup()
    
    @pytest.mark.asyncio
    async def test_import_backup_success(self, storage_service, sample_schedule_data):
        """Test successful backup import."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            # Write sample data to temp file
            temp_file.write(sample_schedule_data.to_json())
            temp_file.flush()
            
            # Mock save_schedules
            with patch.object(storage_service, 'save_schedules') as mock_save:
                # Import backup
                result = await storage_service.import_backup(temp_file.name)
                
                # Verify success
                assert result is True
                mock_save.assert_called_once()
            
            # Clean up
            os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_import_backup_file_not_found(self, storage_service):
        """Test import backup with non-existent file."""
        result = await storage_service.import_backup("/non/existent/file.json")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_import_backup_invalid_json(self, storage_service):
        """Test import backup with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            # Write invalid JSON
            temp_file.write("invalid json content")
            temp_file.flush()
            
            # Import backup
            result = await storage_service.import_backup(temp_file.name)
            
            # Verify failure
            assert result is False
            
            # Clean up
            os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_create_nightly_backup(self, storage_service, sample_schedule_data):
        """Test nightly backup creation."""
        storage_service._schedule_data = sample_schedule_data
        
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            # Create nightly backup
            backup_path = await storage_service.create_nightly_backup()
            
            # Verify backup was created
            assert backup_path is not None
            assert os.path.exists(backup_path)
            assert "nightly_backup" in backup_path
    
    @pytest.mark.asyncio
    async def test_create_nightly_backup_no_data(self, storage_service):
        """Test nightly backup with no data."""
        storage_service._schedule_data = None
        
        # Mock load_schedules to return None
        with patch.object(storage_service, 'load_schedules', return_value=None):
            result = await storage_service.create_nightly_backup()
            assert result is None
    
    @pytest.mark.asyncio
    async def test_attempt_recovery_success(self, storage_service, sample_schedule_data):
        """Test successful recovery from backup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            # Create a backup file
            backup_file = Path(temp_dir) / f"backup_test_entry_20250916.json"
            with open(backup_file, 'w') as f:
                f.write(sample_schedule_data.to_json())
            
            # Mock import_backup to succeed
            with patch.object(storage_service, 'import_backup', return_value=True):
                storage_service._schedule_data = sample_schedule_data
                
                # Attempt recovery
                result = await storage_service._attempt_recovery()
                
                # Verify success
                assert result is not None
                assert isinstance(result, ScheduleData)
    
    @pytest.mark.asyncio
    async def test_attempt_recovery_no_backups(self, storage_service):
        """Test recovery attempt with no backup files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            # Attempt recovery
            result = await storage_service._attempt_recovery()
            
            # Verify failure
            assert result is None
    
    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, storage_service):
        """Test cleanup of old backup files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            # Create 10 old backup files
            for i in range(10):
                backup_file = Path(temp_dir) / f"nightly_backup_test_entry_2025091{i:02d}.json"
                backup_file.write_text('{"test": "data"}')
                
                # Set different modification times
                timestamp = 1694000000 + (i * 86400)  # Different days
                os.utime(backup_file, (timestamp, timestamp))
            
            # Run cleanup
            await storage_service._cleanup_old_backups()
            
            # Verify only 7 files remain
            remaining_files = list(Path(temp_dir).glob("nightly_backup_test_entry_*.json"))
            assert len(remaining_files) == 7

    @pytest.mark.asyncio
    async def test_configure_nightly_backup(self, storage_service):
        """Test configuring nightly backup settings."""
        # Test enabling backup
        storage_service.configure_nightly_backup(True, "03:30")
        assert storage_service.is_nightly_backup_enabled() is True
        assert storage_service.get_nightly_backup_time() == "03:30"
        
        # Test disabling backup
        storage_service.configure_nightly_backup(False)
        assert storage_service.is_nightly_backup_enabled() is False
    
    @pytest.mark.asyncio
    async def test_get_backup_info(self, storage_service):
        """Test getting backup information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            # Create some test backup files
            backup1 = Path(temp_dir) / f"manual_backup_test_entry_20250916.json"
            backup2 = Path(temp_dir) / f"nightly_backup_test_entry_20250917.json"
            
            backup1.write_text('{"test": "data1"}')
            backup2.write_text('{"test": "data2"}')
            
            # Get backup info
            info = await storage_service.get_backup_info()
            
            # Verify results
            assert len(info["backups"]) == 2
            assert info["total_size"] > 0
            assert any(b["type"] == "manual" for b in info["backups"])
            assert any(b["type"] == "nightly" for b in info["backups"])
    
    @pytest.mark.asyncio
    async def test_get_backup_info_no_backups(self, storage_service):
        """Test getting backup info when no backups exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            info = await storage_service.get_backup_info()
            
            assert info["backups"] == []
            assert info["total_size"] == 0
    
    @pytest.mark.asyncio
    async def test_delete_backup_success(self, storage_service):
        """Test successful backup deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            # Create a test backup file
            filename = f"manual_backup_test_entry_20250916.json"
            backup_file = Path(temp_dir) / filename
            backup_file.write_text('{"test": "data"}')
            
            # Delete the backup
            result = await storage_service.delete_backup(filename)
            
            # Verify deletion
            assert result is True
            assert not backup_file.exists()
    
    @pytest.mark.asyncio
    async def test_delete_backup_not_found(self, storage_service):
        """Test deleting non-existent backup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            result = await storage_service.delete_backup("nonexistent_file.json")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_backup_security_check(self, storage_service):
        """Test security checks in backup deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            
            # Test invalid filename (no entry_id)
            result = await storage_service.delete_backup("invalid_backup.json")
            assert result is False
            
            # Test invalid extension
            result = await storage_service.delete_backup(f"backup_test_entry_20250916.txt")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_migration_functionality(self, storage_service, sample_schedule_data):
        """Test data migration during import."""
        # Create old version data
        old_data = sample_schedule_data
        old_data.version = "0.2.0"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_file.write(old_data.to_json())
            temp_file.flush()
            
            # Mock save_schedules to capture migrated data
            migrated_data = None
            async def mock_save(data):
                nonlocal migrated_data
                migrated_data = data
            
            with patch.object(storage_service, 'save_schedules', side_effect=mock_save):
                result = await storage_service.import_backup(temp_file.name)
                
                # Verify migration occurred
                assert result is True
                assert migrated_data is not None
                assert migrated_data.version == "0.3.0"
            
            os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_backup_restore_roundtrip(self, storage_service, sample_schedule_data):
        """Test complete backup and restore cycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            storage_service._schedule_data = sample_schedule_data
            
            # Export backup
            backup_path = await storage_service.export_backup()
            assert os.path.exists(backup_path)
            
            # Clear current data
            storage_service._schedule_data = None
            
            # Import backup
            with patch.object(storage_service, 'save_schedules') as mock_save:
                result = await storage_service.import_backup(backup_path)
                assert result is True
                
                # Verify imported data matches original
                imported_data = mock_save.call_args[0][0]
                assert imported_data.version == sample_schedule_data.version
                assert imported_data.entities_tracked == sample_schedule_data.entities_tracked
                assert len(imported_data.schedules) == len(sample_schedule_data.schedules)


class TestStorageIntegration:
    """Integration tests for storage service."""
    
    @pytest.mark.asyncio
    async def test_storage_error_handling(self):
        """Test storage service error handling."""
        # Test with invalid hass object
        mock_hass = MagicMock()
        mock_hass.config = MagicMock()
        mock_hass.config.config_dir = "/invalid/path"
        
        service = StorageService(mock_hass, "test_entry")
        
        # Test export with invalid directory should handle gracefully
        with patch.object(service, '_schedule_data', None):
            with patch.object(service, 'load_schedules', return_value=None):
                with pytest.raises(StorageError):
                    await service.export_backup()
    
    @pytest.mark.asyncio
    async def test_concurrent_backup_operations(self, storage_service, sample_schedule_data):
        """Test concurrent backup operations."""
        import asyncio
        
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_service._backup_dir = Path(temp_dir)
            storage_service._schedule_data = sample_schedule_data
            
            # Run multiple backup operations concurrently
            tasks = [
                storage_service.export_backup(),
                storage_service.export_backup(),
                storage_service.create_nightly_backup()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # At least some should succeed
            successful_backups = [r for r in results if isinstance(r, str)]
            assert len(successful_backups) >= 1
            
            # Verify files were created
            backup_files = list(Path(temp_dir).glob("*.json"))
            assert len(backup_files) >= 1


if __name__ == "__main__":
    pytest.main([__file__])