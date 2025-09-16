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


if __name__ == "__main__":
    pytest.main([__file__])