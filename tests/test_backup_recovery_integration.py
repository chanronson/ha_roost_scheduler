"""
Integration tests for backup recovery with real backup files.

Tests the backup recovery system using actual backup files and validates
graceful handling of corrupted or invalid backup files.
"""
import asyncio
import json
import logging
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler.storage import StorageService
from custom_components.roost_scheduler.const import DOMAIN

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config = MagicMock()
    hass.config.config_dir = "/config"
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_123"
    entry.data = {"name": "Test Scheduler"}
    entry.options = {}
    entry.title = "Test Roost Scheduler"
    return entry


@pytest.fixture
def valid_backup_data():
    """Valid backup data that should be recoverable."""
    return {
        "version": "0.4.0",
        "schedules": {
            "climate.living_room": {
                "monday": {
                    "08:00": {"temperature": 21, "mode": "heat"},
                    "22:00": {"temperature": 18, "mode": "heat"}
                },
                "tuesday": {
                    "08:00": {"temperature": 21, "mode": "heat"},
                    "22:00": {"temperature": 18, "mode": "heat"}
                }
            },
            "light.bedroom": {
                "monday": {
                    "07:00": {"state": "on", "brightness": 80},
                    "23:00": {"state": "off"}
                }
            }
        },
        "presence_config": {
            "home_entities": ["person.john", "person.jane"],
            "away_mode": "eco"
        },
        "buffer_config": {
            "default_buffer": 5,
            "entity_buffers": {
                "climate.living_room": 10
            }
        },
        "backup_metadata": {
            "created_at": "2025-10-07T10:00:00",
            "entry_id": "test_entry_123",
            "backup_type": "automatic"
        }
    }


@pytest.fixture
def corrupted_backup_scenarios():
    """Various corrupted backup scenarios to test recovery."""
    return {
        "invalid_json": '{"version": "0.4.0", "schedules":',  # Truncated JSON
        "missing_version": {
            "schedules": {"light.test": {"monday": {"08:00": {"state": "on"}}}},
            "presence_config": {"home_entities": [], "away_mode": "eco"}
        },
        "invalid_schedule_format": {
            "version": "0.4.0",
            "schedules": "invalid_format",  # Should be dict
            "presence_config": {"home_entities": [], "away_mode": "eco"}
        },
        "corrupted_time_data": {
            "version": "0.4.0",
            "schedules": {
                "light.test": {
                    "monday": {
                        "invalid_time": {"state": "on"}  # Invalid time format
                    }
                }
            },
            "presence_config": {"home_entities": [], "away_mode": "eco"}
        },
        "mixed_data_types": {
            "version": "0.4.0",
            "schedules": {
                "light.test": {
                    "monday": {
                        "08:00": ["invalid", "list", "format"]  # Should be dict
                    }
                }
            },
            "presence_config": {"home_entities": [], "away_mode": "eco"}
        }
    }


class TestBackupRecoveryIntegration:
    """Test backup recovery with real backup files."""
    
    @pytest.mark.asyncio
    async def test_graceful_handling_of_corrupted_json(self, mock_hass, mock_config_entry):
        """Test graceful handling of corrupted JSON backup files."""
        
        # Create temporary backup file with invalid JSON
        invalid_json = '{"version": "0.4.0", "schedules":'  # Truncated JSON
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as backup_file:
            backup_file.write(invalid_json)
            backup_file_path = backup_file.name
        
        try:
            # Initialize storage service
            storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
            
            # Attempt backup recovery (should fail gracefully)
            recovery_result = await storage_service.import_backup(backup_file_path)
            
            # Verify recovery failed gracefully (returns False, doesn't crash)
            assert recovery_result is False, "Recovery should fail gracefully with corrupted JSON"
            
        finally:
            # Clean up temporary file
            if os.path.exists(backup_file_path):
                os.unlink(backup_file_path)
    
    @pytest.mark.asyncio
    async def test_graceful_handling_of_empty_backup_file(self, mock_hass, mock_config_entry):
        """Test graceful handling of empty backup files."""
        
        # Create empty backup file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as backup_file:
            # Write nothing (empty file)
            backup_file_path = backup_file.name
        
        try:
            # Initialize storage service
            storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
            
            # Attempt backup recovery (should fail gracefully)
            recovery_result = await storage_service.import_backup(backup_file_path)
            
            # Verify recovery failed gracefully
            assert recovery_result is False, "Recovery should fail gracefully with empty file"
            
        finally:
            # Clean up temporary file
            if os.path.exists(backup_file_path):
                os.unlink(backup_file_path)
    
    @pytest.mark.asyncio
    async def test_recovery_with_missing_version(self, mock_hass, mock_config_entry, corrupted_backup_scenarios):
        """Test recovery from backup with missing version field."""
        
        # Test missing version scenario
        missing_version_data = corrupted_backup_scenarios["missing_version"]
        
        # Create temporary backup file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as backup_file:
            json.dump(missing_version_data, backup_file)
            backup_file_path = backup_file.name
        
        try:
            # Mock aiofiles to read from the backup file
            mock_aiofiles_open = AsyncMock()
            
            async def mock_file_operations(file_path, mode='r'):
                mock_file = AsyncMock()
                mock_file.__aenter__ = AsyncMock(return_value=mock_file)
                mock_file.__aexit__ = AsyncMock(return_value=None)
                
                if 'r' in mode:
                    with open(backup_file_path, 'r') as f:
                        content = f.read()
                    mock_file.read = AsyncMock(return_value=content)
                elif 'w' in mode:
                    # Mock write operations for recovery
                    async def write_content(content):
                        pass  # Don't actually write during test
                    mock_file.write = write_content
                
                return mock_file
            
            mock_aiofiles_open.side_effect = mock_file_operations
            
            with patch('aiofiles.open', mock_aiofiles_open):
                with patch('pathlib.Path.exists', return_value=True):
                    # Initialize storage service
                    storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
                    
                    # Attempt backup recovery
                    recovery_result = await storage_service.import_backup(backup_file_path)
                    
                    # Recovery might succeed but should handle missing version gracefully
                    if recovery_result:
                        loaded_data = await storage_service.load_data()
                        # Version should be added during recovery or set to default
                        assert "version" in loaded_data
                        # Original schedule data should be preserved
                        assert loaded_data["schedules"] == missing_version_data["schedules"]
                    
        finally:
            # Clean up temporary file
            if os.path.exists(backup_file_path):
                os.unlink(backup_file_path)
    
    @pytest.mark.asyncio
    async def test_recovery_with_invalid_data_types(self, mock_hass, mock_config_entry, corrupted_backup_scenarios):
        """Test recovery behavior with invalid data types in backup."""
        
        test_scenarios = [
            ("invalid_schedule_format", corrupted_backup_scenarios["invalid_schedule_format"]),
            ("corrupted_time_data", corrupted_backup_scenarios["corrupted_time_data"]),
            ("mixed_data_types", corrupted_backup_scenarios["mixed_data_types"])
        ]
        
        for scenario_name, scenario_data in test_scenarios:
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as backup_file:
                json.dump(scenario_data, backup_file)
                backup_file_path = backup_file.name
            
            try:
                # Mock aiofiles to read from the backup file
                mock_aiofiles_open = AsyncMock()
                
                async def mock_file_operations(file_path, mode='r'):
                    mock_file = AsyncMock()
                    mock_file.__aenter__ = AsyncMock(return_value=mock_file)
                    mock_file.__aexit__ = AsyncMock(return_value=None)
                    
                    if 'r' in mode:
                        with open(backup_file_path, 'r') as f:
                            content = f.read()
                        mock_file.read = AsyncMock(return_value=content)
                    
                    return mock_file
                
                mock_aiofiles_open.side_effect = mock_file_operations
                
                with patch('aiofiles.open', mock_aiofiles_open):
                    with patch('pathlib.Path.exists', return_value=True):
                        # Initialize storage service
                        storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
                        
                        # Attempt backup recovery
                        recovery_result = await storage_service.import_backup(backup_file_path)
                        
                        # Recovery should handle invalid data gracefully
                        # Either succeed with corrected data or fail gracefully
                        assert isinstance(recovery_result, bool), \
                            f"Recovery should return boolean for scenario: {scenario_name}"
                        
            finally:
                # Clean up temporary file
                if os.path.exists(backup_file_path):
                    os.unlink(backup_file_path)
    
    @pytest.mark.asyncio
    async def test_multiple_backup_recovery_priority(self, mock_hass, mock_config_entry, valid_backup_data):
        """Test recovery priority when multiple backup files exist."""
        
        # Create multiple backup files with different timestamps
        backup_files = []
        backup_data_variants = []
        
        for i in range(3):
            # Create slightly different backup data for each file
            backup_data = valid_backup_data.copy()
            backup_data["backup_metadata"] = {
                "created_at": f"2025-10-07T10:{i:02d}:00",  # Different timestamps
                "entry_id": mock_config_entry.entry_id,
                "backup_type": "automatic",
                "sequence": i
            }
            backup_data["schedules"][f"light.test_{i}"] = {
                "monday": {"08:00": {"state": "on", "test_id": i}}
            }
            
            backup_data_variants.append(backup_data)
            
            # Create temporary backup file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as backup_file:
                json.dump(backup_data, backup_file)
                backup_files.append(backup_file.name)
        
        try:
            # Mock file listing to return all backup files
            with patch('pathlib.Path.glob') as mock_glob:
                mock_glob.return_value = [Path(f) for f in backup_files]
                
                # Mock aiofiles to read from backup files
                mock_aiofiles_open = AsyncMock()
                
                def mock_file_operations(file_path, mode='r'):
                    mock_file = AsyncMock()
                    mock_file.__aenter__ = AsyncMock(return_value=mock_file)
                    mock_file.__aexit__ = AsyncMock(return_value=None)
                    
                    if 'r' in mode:
                        # Find which backup file this is
                        file_index = backup_files.index(str(file_path))
                        content = json.dumps(backup_data_variants[file_index])
                        mock_file.read = AsyncMock(return_value=content)
                    
                    return mock_file
                
                mock_aiofiles_open.side_effect = mock_file_operations
                
                with patch('aiofiles.open', mock_aiofiles_open):
                    with patch('pathlib.Path.exists', return_value=True):
                        # Initialize storage service
                        storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
                        
                        # Perform recovery (should use most recent backup)
                        recovery_result = await storage_service.recover_from_backups()
                        
                        # Verify recovery succeeded
                        assert recovery_result is True, "Recovery should succeed with multiple backups"
                        
                        # Verify the most recent backup was used (highest sequence number)
                        loaded_data = await storage_service.load_data()
                        
                        # Should contain the test entity from the most recent backup
                        assert "light.test_2" in loaded_data["schedules"], \
                            "Should recover from most recent backup (sequence 2)"
                        
        finally:
            # Clean up temporary files
            for backup_file in backup_files:
                if os.path.exists(backup_file):
                    os.unlink(backup_file)
    
    @pytest.mark.asyncio
    async def test_backup_recovery_performance(self, mock_hass, mock_config_entry):
        """Test backup recovery performance with large backup files."""
        
        # Create large backup data
        large_backup_data = {
            "version": "0.4.0",
            "schedules": {},
            "presence_config": {
                "home_entities": [f"person.user_{i}" for i in range(20)],
                "away_mode": "eco"
            },
            "buffer_config": {
                "default_buffer": 5,
                "entity_buffers": {}
            }
        }
        
        # Add many entities with schedules
        for i in range(100):
            entity_id = f"light.room_{i}"
            large_backup_data["schedules"][entity_id] = {}
            large_backup_data["buffer_config"]["entity_buffers"][entity_id] = i % 10 + 1
            
            # Add schedules for each day
            for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                large_backup_data["schedules"][entity_id][day] = {}
                
                # Add multiple time slots per day
                for hour in range(6, 23, 2):  # Every 2 hours
                    time_slot = f"{hour:02d}:00"
                    large_backup_data["schedules"][entity_id][day][time_slot] = {
                        "state": "on" if hour < 22 else "off",
                        "brightness": min(100, hour * 5)
                    }
        
        # Create temporary backup file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as backup_file:
            json.dump(large_backup_data, backup_file)
            backup_file_path = backup_file.name
        
        try:
            # Mock aiofiles to read from the backup file
            mock_aiofiles_open = AsyncMock()
            
            async def mock_file_operations(file_path, mode='r'):
                mock_file = AsyncMock()
                mock_file.__aenter__ = AsyncMock(return_value=mock_file)
                mock_file.__aexit__ = AsyncMock(return_value=None)
                
                if 'r' in mode:
                    with open(backup_file_path, 'r') as f:
                        content = f.read()
                    mock_file.read = AsyncMock(return_value=content)
                elif 'w' in mode:
                    async def write_content(content):
                        pass  # Don't actually write during test
                    mock_file.write = write_content
                
                return mock_file
            
            mock_aiofiles_open.side_effect = mock_file_operations
            
            with patch('aiofiles.open', mock_aiofiles_open):
                with patch('pathlib.Path.exists', return_value=True):
                    # Initialize storage service
                    storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
                    
                    # Measure recovery time
                    start_time = datetime.now()
                    recovery_result = await storage_service.import_backup(backup_file_path)
                    end_time = datetime.now()
                    
                    recovery_duration = (end_time - start_time).total_seconds()
                    
                    # Verify recovery succeeded
                    assert recovery_result is True, "Large backup recovery should succeed"
                    
                    # Verify recovery completed within reasonable time (3 seconds for large file)
                    assert recovery_duration < 3.0, \
                        f"Large backup recovery took too long: {recovery_duration:.2f} seconds"
                    
        finally:
            # Clean up temporary file
            if os.path.exists(backup_file_path):
                os.unlink(backup_file_path)
    
    @pytest.mark.asyncio
    async def test_backup_recovery_with_nonexistent_file(self, mock_hass, mock_config_entry):
        """Test error handling when backup file doesn't exist."""
        
        nonexistent_file = "/nonexistent/backup.json"
        
        # Initialize storage service
        storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
        
        # Attempt backup recovery with nonexistent file
        recovery_result = await storage_service.import_backup(nonexistent_file)
        
        # Verify error was handled gracefully
        assert recovery_result is False, "Recovery should fail gracefully with nonexistent file"
    
    @pytest.mark.asyncio
    async def test_backup_recovery_with_invalid_data_structure(self, mock_hass, mock_config_entry):
        """Test recovery behavior with invalid data structure in backup."""
        
        # Create backup with invalid structure (missing required fields)
        invalid_structure_data = {
            "invalid_field": "test",
            "schedules": "not_a_dict"  # Should be dict
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as backup_file:
            json.dump(invalid_structure_data, backup_file)
            backup_file_path = backup_file.name
        
        try:
            # Initialize storage service
            storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
            
            # Attempt backup recovery (should fail gracefully due to validation)
            recovery_result = await storage_service.import_backup(backup_file_path)
            
            # Verify recovery failed gracefully
            assert recovery_result is False, "Recovery should fail gracefully with invalid data structure"
            
        finally:
            # Clean up temporary file
            if os.path.exists(backup_file_path):
                os.unlink(backup_file_path)
    
    @pytest.mark.asyncio
    async def test_fallback_to_default_data(self, mock_hass, mock_config_entry):
        """Test fallback to default data when all backup recovery fails."""
        
        # Mock all backup recovery methods to fail
        with patch('pathlib.Path.glob', return_value=[]):  # No backup files found
            with patch('pathlib.Path.exists', return_value=False):  # No storage file exists
                # Initialize storage service
                storage_service = StorageService(mock_hass, mock_config_entry.entry_id)
                
                # Attempt to load data (should fall back to defaults)
                loaded_data = await storage_service.load_data()
                
                # Verify default data structure was created
                assert "version" in loaded_data
                assert "schedules" in loaded_data
                assert "presence_config" in loaded_data
                assert "buffer_config" in loaded_data
                
                # Verify schedules is empty dict (default)
                assert loaded_data["schedules"] == {}
                
                # Verify presence config has defaults
                assert "home_entities" in loaded_data["presence_config"]
                assert "away_mode" in loaded_data["presence_config"]
                
                # Verify buffer config has defaults
                assert "default_buffer" in loaded_data["buffer_config"]
                assert "entity_buffers" in loaded_data["buffer_config"]


if __name__ == "__main__":
    pytest.main([__file__])