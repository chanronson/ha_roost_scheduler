"""Tests for version migration fixes - specifically testing migration from 0.3.0 to 0.4.0."""
import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

from custom_components.roost_scheduler.migration import MigrationManager
from custom_components.roost_scheduler.version import VERSION, get_migration_path, is_version_supported


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


@pytest.fixture
def sample_0_3_0_data():
    """Sample data structure for version 0.3.0."""
    return {
        "version": "0.3.0",
        "entities_tracked": ["climate.living_room", "climate.bedroom"],
        "presence_entities": ["device_tracker.phone"],
        "presence_rule": "anyone_home",
        "presence_timeout_seconds": 600,
        "schedules": {
            "home": {
                "monday": [
                    {
                        "start": "06:00",
                        "end": "08:00",
                        "target": {"domain": "climate", "temperature": 20.0},
                        "buffer_override": None
                    }
                ],
                "tuesday": []
            },
            "away": {
                "monday": [
                    {
                        "start": "08:00",
                        "end": "18:00",
                        "target": {"domain": "climate", "temperature": 16.0},
                        "buffer_override": {"time_minutes": 10, "value_delta": 1.0}
                    }
                ],
                "tuesday": []
            }
        },
        "buffer": {
            "global": {
                "time_minutes": 15,
                "value_delta": 2.0
            }
        },
        "ui": {
            "resolution_minutes": 30
        },
        "metadata": {
            "created_at": "2024-01-01T00:00:00",
            "last_updated": "2024-01-15T12:00:00"
        }
    }


class TestVersionMigrationFrom030To040:
    """Test migration from version 0.3.0 to 0.4.0 with proper version persistence."""
    
    @pytest.mark.asyncio
    async def test_migration_0_3_0_to_0_4_0_version_persistence(self, migration_manager, sample_0_3_0_data):
        """Test migration from 0.3.0 to 0.4.0 properly updates and persists version.
        
        Requirements: 2.1 - WHEN migrating from version 0.3.0 to 0.4.0 THEN the system SHALL correctly update the stored version to 0.4.0
        """
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(sample_0_3_0_data)
        
        # Verify version is updated to current VERSION (0.4.0)
        assert result["version"] == VERSION
        assert result["version"] == "0.4.0"
        
        # Verify migration metadata is added
        assert "metadata" in result
        assert "migration_completed" in result["metadata"]
        
        migration_info = result["metadata"]["migration_completed"]
        assert migration_info["from_version"] == "0.3.0"
        assert migration_info["to_version"] == VERSION
        assert "timestamp" in migration_info
        assert "migration_path" in migration_info
    
    @pytest.mark.asyncio
    async def test_migration_validation_passes_with_correct_version(self, migration_manager, sample_0_3_0_data):
        """Test migration validation passes when version is correctly updated.
        
        Requirements: 2.2 - WHEN migration validation runs THEN it SHALL pass with the correct target version
        """
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(sample_0_3_0_data)
        
        # Verify validation passes with the migrated data
        validation_result = await migration_manager.validate_migrated_data(result)
        assert validation_result is True
        
        # Verify the version in the result matches expected version
        assert result["version"] == VERSION
    
    @pytest.mark.asyncio
    async def test_migration_without_specific_function_updates_version(self, migration_manager):
        """Test migration updates version metadata even when no specific migration function exists.
        
        Requirements: 2.3 - WHEN no migration function exists for a version THEN the system SHALL still update the version metadata correctly
        """
        # Create data that needs migration but has no specific migration function
        data_without_migration_function = {
            "version": "0.3.0",
            "entities_tracked": ["climate.test"],
            "schedules": {"home": {}, "away": {}}
        }
        
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            # Ensure no migration function exists for this path by mocking MIGRATIONS
            with patch('custom_components.roost_scheduler.migration.MIGRATIONS', {}):
                result = await migration_manager.migrate_if_needed(data_without_migration_function)
        
        # Verify version is still updated correctly
        assert result["version"] == VERSION
        
        # Verify migration metadata indicates version update only
        assert "metadata" in result
        assert "migration_completed" in result["metadata"]
        
        migration_info = result["metadata"]["migration_completed"]
        assert migration_info["from_version"] == "0.3.0"
        assert migration_info["to_version"] == VERSION
    
    @pytest.mark.asyncio
    async def test_migration_completion_version_matches_target(self, migration_manager, sample_0_3_0_data):
        """Test that stored data version matches expected target version after migration.
        
        Requirements: 2.4 - WHEN migration completes THEN the stored data version SHALL match the expected target version
        """
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(sample_0_3_0_data)
        
        # Verify the final version exactly matches the target VERSION
        assert result["version"] == VERSION
        
        # Verify no intermediate version remains
        assert result["version"] != "0.3.0"
        
        # Verify metadata confirms successful completion to target version
        migration_info = result["metadata"]["migration_completed"]
        assert migration_info["to_version"] == VERSION
        assert migration_info["to_version"] == result["version"]


class TestMigrationValidationScenarios:
    """Test migration validation with various scenarios."""
    
    @pytest.mark.asyncio
    async def test_validation_with_valid_migrated_data(self, migration_manager):
        """Test validation passes with properly migrated data structure."""
        valid_migrated_data = {
            "version": VERSION,
            "entities_tracked": ["climate.living_room"],
            "schedules": {
                "home": {
                    "monday": [{
                        "start": "06:00",
                        "end": "08:00",
                        "target": {"domain": "climate", "temperature": 20.0},
                        "buffer_override": None
                    }]
                },
                "away": {}
            },
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "buffer": {
                "global": {"time_minutes": 15, "value_delta": 2.0}
            },
            "ui": {"resolution_minutes": 30},
            "metadata": {
                "migration_completed": {
                    "from_version": "0.3.0",
                    "to_version": VERSION,
                    "timestamp": datetime.now().isoformat()
                }
            }
        }
        
        result = await migration_manager.validate_migrated_data(valid_migrated_data)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validation_fails_with_wrong_version(self, migration_manager):
        """Test validation fails when version doesn't match expected."""
        invalid_version_data = {
            "version": "0.0.1",  # Truly unsupported old version
            "entities_tracked": ["climate.living_room"],
            "schedules": {"home": {}, "away": {}}
        }
        
        result = await migration_manager.validate_migrated_data(invalid_version_data)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validation_fails_with_missing_required_fields(self, migration_manager):
        """Test validation fails when required fields are missing."""
        incomplete_data = {
            "version": VERSION,
            # Missing entities_tracked and schedules
        }
        
        result = await migration_manager.validate_migrated_data(incomplete_data)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validation_handles_corrupted_data_gracefully(self, migration_manager):
        """Test validation handles corrupted or malformed data gracefully."""
        corrupted_data = {
            "version": VERSION,
            "entities_tracked": "not_a_list",  # Should be list
            "schedules": "not_a_dict"  # Should be dict
        }
        
        result = await migration_manager.validate_migrated_data(corrupted_data)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validation_with_partial_data_structure(self, migration_manager):
        """Test validation with minimal but valid data structure."""
        minimal_valid_data = {
            "version": VERSION,
            "entities_tracked": [],
            "schedules": {"home": {}, "away": {}}
        }
        
        result = await migration_manager.validate_migrated_data(minimal_valid_data)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validation_with_extra_fields(self, migration_manager):
        """Test validation passes with extra fields (forward compatibility)."""
        data_with_extra_fields = {
            "version": VERSION,
            "entities_tracked": ["climate.test"],
            "schedules": {"home": {}, "away": {}},
            "future_field": "some_value",  # Extra field
            "another_extra": {"nested": "data"}
        }
        
        result = await migration_manager.validate_migrated_data(data_with_extra_fields)
        assert result is True


class TestMigrationPathAndVersionHandling:
    """Test migration path calculation and version handling."""
    
    def test_migration_path_from_0_3_0_to_current(self):
        """Test migration path calculation from 0.3.0 to current version."""
        path = get_migration_path("0.3.0")
        
        # Should include 0.4.0 in the path
        assert "0.4.0" in path
        assert path[-1] == VERSION  # Last item should be current version
    
    def test_version_support_check(self):
        """Test version support validation."""
        # 0.3.0 should be supported
        assert is_version_supported("0.3.0") is True
        
        # Current version should be supported
        assert is_version_supported(VERSION) is True
        
        # Very old version should not be supported
        assert is_version_supported("0.0.1") is False
        
        # Future version should not be supported
        assert is_version_supported("1.0.0") is False
    
    def test_migration_path_empty_for_current_version(self):
        """Test migration path is empty when already at current version."""
        path = get_migration_path(VERSION)
        assert path == []
    
    def test_migration_path_empty_for_unsupported_version(self):
        """Test migration path is empty for unsupported versions."""
        path = get_migration_path("0.0.1")
        assert path == []


class TestMigrationErrorScenarios:
    """Test migration behavior in error scenarios."""
    
    @pytest.mark.asyncio
    async def test_migration_with_backup_failure(self, migration_manager, sample_0_3_0_data):
        """Test migration continues even if backup creation fails."""
        # Mock the backup method to not raise an exception but log the error
        async def mock_backup_with_error(data, version):
            # Simulate the actual behavior - log error but don't raise
            import logging
            logger = logging.getLogger(__name__)
            logger.error("Migration backup creation failed - continuing without backup")
        
        with patch.object(migration_manager, '_create_migration_backup', side_effect=mock_backup_with_error):
            # Migration should still proceed despite backup failure
            result = await migration_manager.migrate_if_needed(sample_0_3_0_data)
            
            # Verify migration completed successfully
            assert result["version"] == VERSION
            assert "metadata" in result
            assert "migration_completed" in result["metadata"]
    
    @pytest.mark.asyncio
    async def test_migration_with_validation_failure_after_migration(self, migration_manager, sample_0_3_0_data):
        """Test migration fails if validation fails after migration."""
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup, \
             patch.object(migration_manager, 'validate_migrated_data') as mock_validate:
            
            mock_backup.return_value = None
            mock_validate.return_value = False  # Force validation failure
            
            with pytest.raises(ValueError, match="Migration validation failed"):
                await migration_manager.migrate_if_needed(sample_0_3_0_data)
    
    @pytest.mark.asyncio
    async def test_migration_with_unsupported_source_version(self, migration_manager):
        """Test migration fails gracefully with unsupported source version."""
        unsupported_data = {
            "version": "0.0.1",  # Unsupported version
            "entities_tracked": ["climate.test"],
            "schedules": {"home": {}, "away": {}}
        }
        
        with pytest.raises(ValueError, match="Unsupported migration"):
            await migration_manager.migrate_if_needed(unsupported_data)


class TestMigrationMetadataHandling:
    """Test migration metadata creation and handling."""
    
    @pytest.mark.asyncio
    async def test_migration_metadata_creation(self, migration_manager, sample_0_3_0_data):
        """Test that migration creates comprehensive metadata."""
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(sample_0_3_0_data)
        
        # Verify metadata structure
        assert "metadata" in result
        metadata = result["metadata"]
        
        # Check migration completion metadata
        assert "migration_completed" in metadata
        migration_info = metadata["migration_completed"]
        
        assert migration_info["from_version"] == "0.3.0"
        assert migration_info["to_version"] == VERSION
        assert "timestamp" in migration_info
        assert "migration_path" in migration_info
        
        # Verify timestamp is valid ISO format
        timestamp = migration_info["timestamp"]
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))  # Should not raise
    
    @pytest.mark.asyncio
    async def test_migration_preserves_existing_metadata(self, migration_manager):
        """Test that migration preserves existing metadata while adding migration info."""
        data_with_metadata = {
            "version": "0.3.0",
            "entities_tracked": ["climate.test"],
            "schedules": {"home": {}, "away": {}},
            "metadata": {
                "created_at": "2024-01-01T00:00:00",
                "custom_field": "preserved_value"
            }
        }
        
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(data_with_metadata)
        
        # Verify existing metadata is preserved
        metadata = result["metadata"]
        assert metadata["created_at"] == "2024-01-01T00:00:00"
        assert metadata["custom_field"] == "preserved_value"
        
        # Verify migration metadata is added
        assert "migration_completed" in metadata
        assert metadata["migration_completed"]["from_version"] == "0.3.0"
        assert metadata["migration_completed"]["to_version"] == VERSION


class TestMigrationDataIntegrity:
    """Test that migration preserves data integrity."""
    
    @pytest.mark.asyncio
    async def test_migration_preserves_schedule_data(self, migration_manager, sample_0_3_0_data):
        """Test that migration preserves all schedule data correctly."""
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(sample_0_3_0_data)
        
        # Verify schedule structure is preserved
        assert "schedules" in result
        schedules = result["schedules"]
        
        # Check home schedule
        assert "home" in schedules
        assert "monday" in schedules["home"]
        monday_home = schedules["home"]["monday"]
        assert len(monday_home) == 1
        assert monday_home[0]["start"] == "06:00"
        assert monday_home[0]["end"] == "08:00"
        assert monday_home[0]["target"]["temperature"] == 20.0
        
        # Check away schedule
        assert "away" in schedules
        assert "monday" in schedules["away"]
        monday_away = schedules["away"]["monday"]
        assert len(monday_away) == 1
        assert monday_away[0]["start"] == "08:00"
        assert monday_away[0]["end"] == "18:00"
        assert monday_away[0]["target"]["temperature"] == 16.0
    
    @pytest.mark.asyncio
    async def test_migration_preserves_entity_configuration(self, migration_manager, sample_0_3_0_data):
        """Test that migration preserves entity configuration."""
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(sample_0_3_0_data)
        
        # Verify entities are preserved
        assert result["entities_tracked"] == ["climate.living_room", "climate.bedroom"]
        assert result["presence_entities"] == ["device_tracker.phone"]
        assert result["presence_rule"] == "anyone_home"
        assert result["presence_timeout_seconds"] == 600
    
    @pytest.mark.asyncio
    async def test_migration_preserves_buffer_configuration(self, migration_manager, sample_0_3_0_data):
        """Test that migration preserves buffer configuration."""
        with patch.object(migration_manager, '_create_migration_backup') as mock_backup:
            mock_backup.return_value = None
            
            result = await migration_manager.migrate_if_needed(sample_0_3_0_data)
        
        # Verify buffer configuration is preserved
        assert "buffer" in result
        buffer_config = result["buffer"]
        assert "global" in buffer_config
        assert buffer_config["global"]["time_minutes"] == 15
        assert buffer_config["global"]["value_delta"] == 2.0
        
        # Verify UI configuration is preserved
        assert "ui" in result
        assert result["ui"]["resolution_minutes"] == 30