"""Tests for upgrade manager functionality."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.roost_scheduler.upgrade_manager import UpgradeManager
from custom_components.roost_scheduler.version import VERSION


@pytest.fixture
def hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.config_dir = "/config"
    return hass


@pytest.fixture
def upgrade_manager(hass):
    """Create upgrade manager instance."""
    return UpgradeManager(hass)


class TestUpgradeManager:
    """Test upgrade manager functionality."""
    
    @pytest.mark.asyncio
    async def test_check_upgrade_compatibility_fresh_install(self, upgrade_manager):
        """Test compatibility check for fresh install."""
        with patch('homeassistant.helpers.storage.Store') as mock_store:
            mock_store_instance = AsyncMock()
            mock_store_instance.async_load.return_value = None
            mock_store.return_value = mock_store_instance
            
            result = await upgrade_manager.check_upgrade_compatibility("test_entry")
        
        assert result["compatible"] is True
        assert result["upgrade_type"] == "fresh_install"
        assert result["migration_required"] is False
        assert result["backup_recommended"] is False
    
    @pytest.mark.asyncio
    async def test_check_upgrade_compatibility_minor_upgrade(self, upgrade_manager):
        """Test compatibility check for minor version upgrade."""
        existing_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"]
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store:
            mock_store_instance = AsyncMock()
            mock_store_instance.async_load.return_value = existing_data
            mock_store.return_value = mock_store_instance
            
            result = await upgrade_manager.check_upgrade_compatibility("test_entry")
        
        assert result["compatible"] is True
        assert result["upgrade_type"] == "minor"
        assert result["current_version"] == "0.2.0"
        assert result["target_version"] == VERSION
        assert result["migration_required"] is True
        assert result["backup_recommended"] is True
        assert len(result["breaking_changes"]) > 0
        assert len(result["new_features"]) > 0
    
    @pytest.mark.asyncio
    async def test_check_upgrade_compatibility_unsupported_version(self, upgrade_manager):
        """Test compatibility check for unsupported version."""
        existing_data = {
            "version": "1.0.0",  # Future version
            "entities_tracked": ["climate.living_room"]
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store:
            mock_store_instance = AsyncMock()
            mock_store_instance.async_load.return_value = existing_data
            mock_store.return_value = mock_store_instance
            
            result = await upgrade_manager.check_upgrade_compatibility("test_entry")
        
        assert result["compatible"] is False
        assert result["upgrade_type"] == "unsupported"
        assert "error" in result
    
    def test_determine_upgrade_type(self, upgrade_manager):
        """Test upgrade type determination."""
        assert upgrade_manager._determine_upgrade_type("0.1.0") == "minor"
        assert upgrade_manager._determine_upgrade_type("0.2.0") == "minor"
        assert upgrade_manager._determine_upgrade_type("0.3.0") == "none"
        assert upgrade_manager._determine_upgrade_type("1.0.0") == "none"  # Future version
    
    def test_get_breaking_changes(self, upgrade_manager):
        """Test breaking changes detection."""
        changes_from_0_1_0 = upgrade_manager._get_breaking_changes("0.1.0")
        assert len(changes_from_0_1_0) > 0
        assert any("Home/Away modes" in change for change in changes_from_0_1_0)
        
        changes_from_0_2_0 = upgrade_manager._get_breaking_changes("0.2.0")
        assert len(changes_from_0_2_0) > 0
        assert any("Target value structure" in change for change in changes_from_0_2_0)
        
        changes_from_current = upgrade_manager._get_breaking_changes(VERSION)
        assert len(changes_from_current) == 0
    
    def test_get_new_features(self, upgrade_manager):
        """Test new features detection."""
        features_from_0_1_0 = upgrade_manager._get_new_features("0.1.0")
        assert len(features_from_0_1_0) > 0
        assert any("presence-based scheduling" in feature for feature in features_from_0_1_0)
        
        features_from_0_2_0 = upgrade_manager._get_new_features("0.2.0")
        assert len(features_from_0_2_0) > 0
        assert any("buffering system" in feature for feature in features_from_0_2_0)
        
        features_from_current = upgrade_manager._get_new_features(VERSION)
        assert len(features_from_current) == 0
    
    @pytest.mark.asyncio
    async def test_perform_upgrade_success(self, upgrade_manager):
        """Test successful upgrade process."""
        existing_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.living_room"],
            "schedules": {"monday": []}
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store, \
             patch.object(upgrade_manager, '_record_upgrade_completion') as mock_record:
            
            mock_store_instance = AsyncMock()
            mock_store_instance.async_load.return_value = existing_data
            mock_store_instance.async_save.return_value = None
            mock_store.return_value = mock_store_instance
            mock_record.return_value = None
            
            result = await upgrade_manager.perform_upgrade("test_entry", create_backup=False)
        
        assert result["success"] is True
        assert result["migration_applied"] is True
        assert result["validation_passed"] is True
        assert len(result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_perform_upgrade_with_backup(self, upgrade_manager):
        """Test upgrade process with backup creation."""
        existing_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"]
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store, \
             patch('custom_components.roost_scheduler.migration.UninstallManager') as mock_uninstall_mgr, \
             patch.object(upgrade_manager, '_record_upgrade_completion') as mock_record:
            
            mock_store_instance = AsyncMock()
            mock_store_instance.async_load.return_value = existing_data
            mock_store_instance.async_save.return_value = None
            mock_store.return_value = mock_store_instance
            
            mock_uninstall_instance = AsyncMock()
            mock_uninstall_instance._create_final_backup.return_value = ["/config/backup.json"]
            mock_uninstall_mgr.return_value = mock_uninstall_instance
            mock_record.return_value = None
            
            result = await upgrade_manager.perform_upgrade("test_entry", create_backup=True)
        
        assert result["success"] is True
        assert result["backup_created"] is True
        assert result["backup_locations"] == ["/config/backup.json"]
    
    @pytest.mark.asyncio
    async def test_perform_upgrade_incompatible_version(self, upgrade_manager):
        """Test upgrade process with incompatible version."""
        with patch.object(upgrade_manager, 'check_upgrade_compatibility') as mock_check:
            mock_check.return_value = {
                "compatible": False,
                "error": "Unsupported version"
            }
            
            result = await upgrade_manager.perform_upgrade("test_entry")
        
        assert result["success"] is False
        assert "Unsupported version" in result["errors"]
    
    @pytest.mark.asyncio
    async def test_get_upgrade_history(self, upgrade_manager):
        """Test upgrade history retrieval."""
        mock_history = [
            {
                "timestamp": "2025-01-01T12:00:00Z",
                "from_version": "0.1.0",
                "to_version": "0.2.0"
            }
        ]
        
        with patch('homeassistant.helpers.storage.Store') as mock_store:
            mock_store_instance = AsyncMock()
            mock_store_instance.async_load.return_value = mock_history
            mock_store.return_value = mock_store_instance
            
            result = await upgrade_manager.get_upgrade_history()
        
        assert result == mock_history
    
    @pytest.mark.asyncio
    async def test_record_upgrade_completion(self, upgrade_manager):
        """Test upgrade completion recording."""
        compatibility_info = {
            "current_version": "0.1.0",
            "upgrade_type": "minor",
            "breaking_changes": ["Some change"],
            "new_features": ["Some feature"]
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store:
            mock_store_instance = AsyncMock()
            mock_store_instance.async_load.return_value = []
            mock_store_instance.async_save.return_value = None
            mock_store.return_value = mock_store_instance
            
            await upgrade_manager._record_upgrade_completion("test_entry", compatibility_info)
        
        # Verify save was called with upgrade record
        mock_store_instance.async_save.assert_called_once()
        saved_data = mock_store_instance.async_save.call_args[0][0]
        assert len(saved_data) == 1
        assert saved_data[0]["from_version"] == "0.1.0"
        assert saved_data[0]["to_version"] == VERSION
    
    def test_get_version_info(self, upgrade_manager):
        """Test version info retrieval."""
        result = upgrade_manager.get_version_info()
        
        assert "current" in result
        assert "manifest" in result
        assert "supported_min" in result
        assert "history" in result
        assert result["current"] == VERSION


class TestUpgradeIntegration:
    """Test upgrade manager integration with other components."""
    
    @pytest.mark.asyncio
    async def test_upgrade_manager_in_init(self, hass):
        """Test upgrade manager integration in component initialization."""
        from custom_components.roost_scheduler import async_setup_entry
        from homeassistant.config_entries import ConfigEntry
        
        # Mock config entry
        mock_entry = MagicMock(spec=ConfigEntry)
        mock_entry.entry_id = "test_entry"
        mock_entry.options = {}
        
        # Mock all required dependencies
        with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_websocket:
            
            # Mock storage service
            mock_storage_instance = AsyncMock()
            mock_storage_instance.load_schedules.return_value = None
            mock_storage.return_value = mock_storage_instance
            
            # Mock other managers
            mock_presence.return_value = MagicMock()
            mock_buffer.return_value = MagicMock()
            mock_schedule.return_value = MagicMock()
            
            # Mock service registration
            mock_services.return_value = None
            mock_websocket.return_value = None
            
            result = await async_setup_entry(hass, mock_entry)
        
        assert result is True
        mock_storage_instance.load_schedules.assert_called_once()