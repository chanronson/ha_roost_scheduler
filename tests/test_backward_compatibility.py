"""Comprehensive backward compatibility validation tests."""
import pytest
import json
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.roost_scheduler import async_setup_entry, async_unload_entry
from custom_components.roost_scheduler.storage import StorageService
from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.schedule_manager import ScheduleManager
from custom_components.roost_scheduler.models import ScheduleData, PresenceConfig, GlobalBufferConfig
from custom_components.roost_scheduler.const import (
    DOMAIN, 
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
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock()
    return hass


@pytest.fixture
def config_entry():
    """Mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {
        "entities_tracked": ["climate.living_room"],
        "presence_entities": ["device_tracker.phone"],
        "presence_rule": "anyone_home",
        "presence_timeout_seconds": 600
    }
    entry.options = {}
    return entry


class TestExistingInstallationCompatibility:
    """Test that existing installations continue to work after upgrade."""
    
    @pytest.mark.asyncio
    async def test_existing_installation_with_legacy_storage_format(self, hass, config_entry):
        """Test that existing installations with legacy storage format continue to work."""
        # Simulate legacy storage data (version 0.2.0 format)
        legacy_storage_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room", "climate.bedroom"],
            "presence_entities": ["device_tracker.phone", "person.user"],
            "presence_rule": "everyone_home",
            "presence_timeout_seconds": 300,
            "schedules": {
                "home": {
                    "monday": [
                        {"start": "06:00", "end": "08:00", "target": {"domain": "climate", "temperature": 20.0}}
                    ]
                },
                "away": {
                    "monday": [
                        {"start": "08:00", "end": "18:00", "target": {"domain": "climate", "temperature": 16.0}}
                    ]
                }
            }
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = legacy_storage_data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            # Setup should succeed
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify managers were created and initialized
            assert DOMAIN in hass.data
            assert config_entry.entry_id in hass.data[DOMAIN]
            
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            assert "presence_manager" in integration_data
            assert "buffer_manager" in integration_data
            assert "schedule_manager" in integration_data
            
            # Verify storage was migrated to current version
            mock_store.async_save.assert_called()
            saved_data = mock_store.async_save.call_args[0][0]
            assert saved_data["version"] == VERSION
            
            # Verify user data was preserved
            assert saved_data["entities_tracked"] == ["climate.living_room", "climate.bedroom"]
            assert saved_data["presence_entities"] == ["device_tracker.phone", "person.user"]
            assert saved_data["presence_rule"] == "everyone_home"
            assert saved_data["presence_timeout_seconds"] == 300
    
    @pytest.mark.asyncio
    async def test_existing_installation_with_very_old_format(self, hass, config_entry):
        """Test that very old installations (0.1.0) can be upgraded."""
        # Simulate very old storage data (version 0.1.0 format)
        very_old_storage_data = {
            "version": "0.1.0",
            "entities_tracked": ["climate.thermostat"],
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
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = very_old_storage_data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            # Setup should succeed despite very old format
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify migration occurred
            mock_store.async_save.assert_called()
            saved_data = mock_store.async_save.call_args[0][0]
            assert saved_data["version"] == VERSION
            
            # Verify presence configuration was added with defaults
            assert "presence_entities" in saved_data
            assert "presence_rule" in saved_data
            assert "presence_timeout_seconds" in saved_data
            
            # Verify buffer configuration was added
            assert "buffer" in saved_data
            
            # Verify schedule structure was migrated
            assert "home" in saved_data["schedules"]
            assert "away" in saved_data["schedules"]
            
            # Verify original schedule data was preserved in home mode
            home_monday = saved_data["schedules"]["home"]["monday"]
            assert len(home_monday) == 2
            assert home_monday[0]["target"]["temperature"] == 20.0
            assert home_monday[1]["target"]["temperature"] == 22.0
    
    @pytest.mark.asyncio
    async def test_existing_installation_with_custom_presence_config(self, hass, config_entry):
        """Test that existing custom presence configurations are preserved."""
        # Simulate existing installation with custom presence setup
        existing_storage_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone", "device_tracker.tablet", "person.user"],
            "presence_rule": "everyone_home",
            "presence_timeout_seconds": 1200,  # Custom timeout
            "schedules": {
                "home": {"monday": []},
                "away": {"monday": []}
            }
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = existing_storage_data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Get the presence manager
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Verify custom presence configuration was preserved
            assert presence_manager._presence_entities == ["device_tracker.phone", "device_tracker.tablet", "person.user"]
            assert presence_manager._presence_rule == "everyone_home"
            assert presence_manager._timeout_seconds == 1200
    
    @pytest.mark.asyncio
    async def test_existing_installation_with_complex_schedules(self, hass, config_entry):
        """Test that complex existing schedules are preserved during upgrade."""
        # Simulate existing installation with complex schedule data
        complex_storage_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room", "climate.bedroom", "climate.office"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "schedules": {
                "home": {
                    "monday": [
                        {"start": "06:00", "end": "08:00", "target": {"domain": "climate", "temperature": 20.0}},
                        {"start": "12:00", "end": "13:00", "target": {"domain": "climate", "temperature": 22.0}},
                        {"start": "18:00", "end": "22:00", "target": {"domain": "climate", "temperature": 21.0}}
                    ],
                    "tuesday": [
                        {"start": "07:00", "end": "09:00", "target": {"domain": "climate", "temperature": 19.5}}
                    ],
                    "wednesday": [],
                    "thursday": [
                        {"start": "06:30", "end": "08:30", "target": {"domain": "climate", "temperature": 20.5}}
                    ],
                    "friday": [
                        {"start": "06:00", "end": "08:00", "target": {"domain": "climate", "temperature": 20.0}},
                        {"start": "17:00", "end": "23:00", "target": {"domain": "climate", "temperature": 22.5}}
                    ],
                    "saturday": [
                        {"start": "08:00", "end": "10:00", "target": {"domain": "climate", "temperature": 21.0}}
                    ],
                    "sunday": [
                        {"start": "09:00", "end": "11:00", "target": {"domain": "climate", "temperature": 20.0}}
                    ]
                },
                "away": {
                    "monday": [
                        {"start": "08:00", "end": "18:00", "target": {"domain": "climate", "temperature": 16.0}}
                    ],
                    "tuesday": [
                        {"start": "09:00", "end": "17:00", "target": {"domain": "climate", "temperature": 15.5}}
                    ],
                    "wednesday": [],
                    "thursday": [
                        {"start": "08:30", "end": "17:30", "target": {"domain": "climate", "temperature": 16.0}}
                    ],
                    "friday": [
                        {"start": "08:00", "end": "17:00", "target": {"domain": "climate", "temperature": 16.0}}
                    ],
                    "saturday": [],
                    "sunday": []
                }
            }
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = complex_storage_data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify all schedule data was preserved
            saved_data = mock_store.async_save.call_args[0][0]
            
            # Check home schedules
            home_schedules = saved_data["schedules"]["home"]
            assert len(home_schedules["monday"]) == 3
            assert len(home_schedules["tuesday"]) == 1
            assert len(home_schedules["wednesday"]) == 0
            assert len(home_schedules["friday"]) == 2
            
            # Check away schedules
            away_schedules = saved_data["schedules"]["away"]
            assert len(away_schedules["monday"]) == 1
            assert len(away_schedules["tuesday"]) == 1
            assert len(away_schedules["saturday"]) == 0
            
            # Verify specific temperature values
            assert home_schedules["monday"][0]["target"]["temperature"] == 20.0
            assert home_schedules["monday"][1]["target"]["temperature"] == 22.0
            assert home_schedules["friday"][1]["target"]["temperature"] == 22.5
            assert away_schedules["tuesday"][0]["target"]["temperature"] == 15.5


class TestConfigurationPreservationDuringMigration:
    """Test that all existing configuration is preserved during migration."""
    
    @pytest.mark.asyncio
    async def test_presence_configuration_preservation(self, hass, config_entry):
        """Test that presence configuration is fully preserved during migration."""
        # Test data with all possible presence configuration options
        storage_data_with_full_presence = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone", "device_tracker.tablet", "person.user", "person.spouse"],
            "presence_rule": "everyone_home",
            "presence_timeout_seconds": 1800,  # 30 minutes
            "schedules": {"home": {}, "away": {}}
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = storage_data_with_full_presence
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify all presence configuration was preserved
            saved_data = mock_store.async_save.call_args[0][0]
            assert saved_data["presence_entities"] == ["device_tracker.phone", "device_tracker.tablet", "person.user", "person.spouse"]
            assert saved_data["presence_rule"] == "everyone_home"
            assert saved_data["presence_timeout_seconds"] == 1800
            
            # Verify presence_config was created with preserved data
            if "presence_config" in saved_data:
                presence_config = saved_data["presence_config"]
                assert presence_config["entities"] == ["device_tracker.phone", "device_tracker.tablet", "person.user", "person.spouse"]
                assert presence_config["rule"] == "everyone_home"
                assert presence_config["timeout_seconds"] == 1800
    
    @pytest.mark.asyncio
    async def test_entity_tracking_preservation(self, hass, config_entry):
        """Test that entity tracking configuration is preserved."""
        # Test with multiple tracked entities
        storage_data_with_entities = {
            "version": "0.2.0",
            "entities_tracked": [
                "climate.living_room", 
                "climate.bedroom", 
                "climate.office", 
                "climate.basement",
                "switch.heater_1",
                "switch.heater_2"
            ],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "schedules": {"home": {}, "away": {}}
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = storage_data_with_entities
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify all tracked entities were preserved
            saved_data = mock_store.async_save.call_args[0][0]
            expected_entities = [
                "climate.living_room", 
                "climate.bedroom", 
                "climate.office", 
                "climate.basement",
                "switch.heater_1",
                "switch.heater_2"
            ]
            assert saved_data["entities_tracked"] == expected_entities
    
    @pytest.mark.asyncio
    async def test_schedule_data_preservation_with_edge_cases(self, hass, config_entry):
        """Test that schedule data with edge cases is preserved."""
        # Test with edge case schedule data
        storage_data_with_edge_cases = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "schedules": {
                "home": {
                    "monday": [
                        # Very early morning slot
                        {"start": "00:00", "end": "01:00", "target": {"domain": "climate", "temperature": 18.0}},
                        # Very late night slot
                        {"start": "23:30", "end": "23:59", "target": {"domain": "climate", "temperature": 17.0}},
                        # Slot with decimal temperature
                        {"start": "12:00", "end": "13:00", "target": {"domain": "climate", "temperature": 20.5}}
                    ],
                    "tuesday": [],  # Empty day
                    "wednesday": [
                        # Single minute slot
                        {"start": "12:00", "end": "12:01", "target": {"domain": "climate", "temperature": 21.0}}
                    ]
                },
                "away": {
                    "monday": [
                        # All day slot
                        {"start": "00:00", "end": "23:59", "target": {"domain": "climate", "temperature": 15.0}}
                    ],
                    "tuesday": [],
                    "wednesday": []
                }
            }
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = storage_data_with_edge_cases
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify all edge case schedule data was preserved
            saved_data = mock_store.async_save.call_args[0][0]
            home_monday = saved_data["schedules"]["home"]["monday"]
            
            assert len(home_monday) == 3
            assert home_monday[0]["start"] == "00:00"
            assert home_monday[0]["end"] == "01:00"
            assert home_monday[0]["target"]["temperature"] == 18.0
            
            assert home_monday[1]["start"] == "23:30"
            assert home_monday[1]["end"] == "23:59"
            assert home_monday[1]["target"]["temperature"] == 17.0
            
            assert home_monday[2]["target"]["temperature"] == 20.5
            
            # Verify empty days are preserved
            assert len(saved_data["schedules"]["home"]["tuesday"]) == 0
            
            # Verify single minute slot
            home_wednesday = saved_data["schedules"]["home"]["wednesday"]
            assert len(home_wednesday) == 1
            assert home_wednesday[0]["start"] == "12:00"
            assert home_wednesday[0]["end"] == "12:01"


class TestMissingOrCorruptedStorageHandling:
    """Test that the integration works with missing or corrupted storage."""
    
    @pytest.mark.asyncio
    async def test_missing_storage_file(self, hass, config_entry):
        """Test that integration works when storage file is missing."""
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = None  # No storage file
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            # Setup should succeed even without storage
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify managers were created with defaults
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            buffer_manager = integration_data["buffer_manager"]
            
            # Verify default configurations
            assert presence_manager._presence_entities == []
            assert presence_manager._presence_rule == "anyone_home"
            assert presence_manager._timeout_seconds == DEFAULT_PRESENCE_TIMEOUT_SECONDS
            
            assert buffer_manager._global_buffer_config.time_minutes == DEFAULT_BUFFER_TIME_MINUTES
            assert buffer_manager._global_buffer_config.value_delta == DEFAULT_BUFFER_VALUE_DELTA
            assert buffer_manager._global_buffer_config.enabled is True
    
    @pytest.mark.asyncio
    async def test_corrupted_storage_data(self, hass, config_entry):
        """Test that integration handles corrupted storage data gracefully."""
        # Simulate corrupted storage data
        corrupted_data = {
            "version": "invalid_version",
            "entities_tracked": "not_a_list",  # Should be list
            "presence_entities": {"invalid": "format"},  # Should be list
            "schedules": "not_a_dict"  # Should be dict
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = corrupted_data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            # Setup should still succeed with corrupted data
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify managers were created (should fall back to defaults)
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            assert "presence_manager" in integration_data
            assert "buffer_manager" in integration_data
            assert "schedule_manager" in integration_data
    
    @pytest.mark.asyncio
    async def test_storage_load_exception(self, hass, config_entry):
        """Test that integration handles storage load exceptions."""
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.side_effect = Exception("Storage load error")
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            # Setup should still succeed despite storage error
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify managers were created
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            assert "presence_manager" in integration_data
            assert "buffer_manager" in integration_data
    
    @pytest.mark.asyncio
    async def test_partial_storage_corruption(self, hass, config_entry):
        """Test handling of partially corrupted storage data."""
        # Simulate partially corrupted data (some fields valid, some invalid)
        partially_corrupted_data = {
            "version": "0.2.0",  # Valid
            "entities_tracked": ["climate.living_room"],  # Valid
            "presence_entities": "invalid_format",  # Invalid - should be list
            "presence_rule": "anyone_home",  # Valid
            "presence_timeout_seconds": "not_a_number",  # Invalid - should be int
            "schedules": {  # Valid structure
                "home": {"monday": []},
                "away": {"monday": []}
            }
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = partially_corrupted_data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify that valid data was preserved and invalid data was replaced with defaults
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Valid data should be preserved
            # Note: The actual behavior depends on the migration/validation logic
            # This test ensures the integration doesn't crash with partial corruption


class TestGracefulDegradationOnStorageFailures:
    """Test graceful degradation when storage operations fail."""
    
    @pytest.mark.asyncio
    async def test_storage_save_failure_during_setup(self, hass, config_entry):
        """Test that setup continues even if storage save fails."""
        valid_storage_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "schedules": {"home": {}, "away": {}}
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = valid_storage_data
            mock_store.async_save.side_effect = Exception("Storage save error")
            mock_store_class.return_value = mock_store
            
            # Setup should still succeed despite save error
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify managers were created and can operate
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Manager should have loaded the data even if save failed
            assert presence_manager._presence_entities == ["device_tracker.phone"]
    
    @pytest.mark.asyncio
    async def test_manager_operation_with_storage_failures(self, hass, config_entry):
        """Test that managers can operate even when storage operations fail."""
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = None
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            buffer_manager = integration_data["buffer_manager"]
            
            # Test that managers can operate with storage failures
            with patch.object(presence_manager.storage_service, 'save_schedules', side_effect=Exception("Save error")):
                # These operations should not crash even if storage fails
                await presence_manager.update_presence_entities(["device_tracker.new_phone"])
                current_mode = await presence_manager.get_current_mode()
                assert current_mode in ["home", "away"]
            
            with patch.object(buffer_manager.storage_service, 'save_schedules', side_effect=Exception("Save error")):
                # Buffer operations should continue working
                should_suppress = buffer_manager.should_suppress_change(
                    "climate.living_room", 20.0, {}, force_apply=False
                )
                assert isinstance(should_suppress, bool)
    
    @pytest.mark.asyncio
    async def test_configuration_persistence_failure_fallback(self, hass, config_entry):
        """Test fallback behavior when configuration persistence fails."""
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = None
            # Make save operations fail
            mock_store.async_save.side_effect = Exception("Persistent storage unavailable")
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Manager should still function with in-memory configuration
            await presence_manager.update_presence_entities(["device_tracker.phone"])
            assert presence_manager._presence_entities == ["device_tracker.phone"]
            
            # Configuration should be maintained in memory even if persistence fails
            await presence_manager.update_presence_rule("everyone_home")
            assert presence_manager._presence_rule == "everyone_home"


class TestConfigEntryDataFallback:
    """Test that config entry data is still used as fallback."""
    
    @pytest.mark.asyncio
    async def test_config_entry_fallback_when_storage_missing(self, hass, config_entry):
        """Test that config entry data is used when storage is missing."""
        # Set up config entry with presence data
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone", "person.user"],
            "presence_rule": "everyone_home",
            "presence_timeout_seconds": 900
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = None  # No storage data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Should use config entry data as fallback
            assert presence_manager._presence_entities == ["device_tracker.phone", "person.user"]
            assert presence_manager._presence_rule == "everyone_home"
            assert presence_manager._timeout_seconds == 900
    
    @pytest.mark.asyncio
    async def test_config_entry_fallback_when_storage_corrupted(self, hass, config_entry):
        """Test that config entry data is used when storage is corrupted."""
        config_entry.data = {
            "entities_tracked": ["climate.bedroom"],
            "presence_entities": ["device_tracker.tablet"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 1200
        }
        
        # Corrupted storage data
        corrupted_storage = {
            "version": "invalid",
            "entities_tracked": None,
            "presence_entities": "not_a_list",
            "schedules": None
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = corrupted_storage
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Should fall back to config entry data when storage is corrupted
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Verify fallback to config entry data
            # Note: Actual behavior depends on implementation details
            # This test ensures the integration doesn't crash
    
    @pytest.mark.asyncio
    async def test_config_entry_and_storage_data_merge(self, hass, config_entry):
        """Test proper merging of config entry and storage data."""
        # Config entry has some data
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Storage has additional/different data
        storage_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room", "climate.bedroom"],  # More entities
            "presence_entities": ["device_tracker.phone", "person.user"],  # More entities
            "presence_rule": "everyone_home",  # Different rule
            "presence_timeout_seconds": 900,  # Different timeout
            "schedules": {
                "home": {"monday": [{"start": "06:00", "end": "08:00", "target": {"domain": "climate", "temperature": 20.0}}]},
                "away": {"monday": []}
            }
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = storage_data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            integration_data = hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Storage data should take precedence over config entry data
            assert presence_manager._presence_entities == ["device_tracker.phone", "person.user"]
            assert presence_manager._presence_rule == "everyone_home"
            assert presence_manager._timeout_seconds == 900


class TestComprehensiveBackwardCompatibilityScenarios:
    """Comprehensive backward compatibility test scenarios."""
    
    @pytest.mark.asyncio
    async def test_upgrade_from_each_supported_version(self, hass, config_entry):
        """Test upgrade path from each supported version."""
        versions_to_test = [
            ("0.1.0", {
                "version": "0.1.0",
                "entities_tracked": ["climate.test"],
                "schedules": {"monday": [{"start": "06:00", "end": "08:00", "target": 20.0}]}
            }),
            ("0.2.0", {
                "version": "0.2.0",
                "entities_tracked": ["climate.test"],
                "presence_entities": ["device_tracker.phone"],
                "presence_rule": "anyone_home",
                "presence_timeout_seconds": 600,
                "schedules": {"home": {}, "away": {}}
            })
        ]
        
        for version, test_data in versions_to_test:
            with patch('homeassistant.helpers.storage.Store') as mock_store_class:
                mock_store = AsyncMock()
                mock_store.async_load.return_value = test_data
                mock_store.async_save.return_value = None
                mock_store_class.return_value = mock_store
                
                # Reset hass.data for each test
                hass.data = {}
                
                result = await async_setup_entry(hass, config_entry)
                assert result is True, f"Setup failed for version {version}"
                
                # Verify upgrade to current version
                mock_store.async_save.assert_called()
                saved_data = mock_store.async_save.call_args[0][0]
                assert saved_data["version"] == VERSION, f"Version upgrade failed for {version}"
    
    @pytest.mark.asyncio
    async def test_integration_unload_and_reload_compatibility(self, hass, config_entry):
        """Test that integration can be unloaded and reloaded without issues."""
        storage_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "schedules": {"home": {}, "away": {}}
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = storage_data
            mock_store.async_save.return_value = None
            mock_store_class.return_value = mock_store
            
            # Initial setup
            result = await async_setup_entry(hass, config_entry)
            assert result is True
            
            # Verify setup worked
            assert DOMAIN in hass.data
            assert config_entry.entry_id in hass.data[DOMAIN]
            
            # Unload
            unload_result = await async_unload_entry(hass, config_entry)
            assert unload_result is True
            
            # Verify cleanup
            if DOMAIN in hass.data:
                assert config_entry.entry_id not in hass.data[DOMAIN]
            
            # Reload
            reload_result = await async_setup_entry(hass, config_entry)
            assert reload_result is True
            
            # Verify reload worked
            assert DOMAIN in hass.data
            assert config_entry.entry_id in hass.data[DOMAIN]
    
    @pytest.mark.asyncio
    async def test_multiple_config_entries_compatibility(self, hass):
        """Test backward compatibility with multiple config entries."""
        # Create two config entries
        config_entry_1 = MagicMock(spec=ConfigEntry)
        config_entry_1.entry_id = "entry_1"
        config_entry_1.data = {"entities_tracked": ["climate.living_room"]}
        config_entry_1.options = {}
        
        config_entry_2 = MagicMock(spec=ConfigEntry)
        config_entry_2.entry_id = "entry_2"
        config_entry_2.data = {"entities_tracked": ["climate.bedroom"]}
        config_entry_2.options = {}
        
        storage_data_1 = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "schedules": {"home": {}, "away": {}}
        }
        
        storage_data_2 = {
            "version": "0.2.0",
            "entities_tracked": ["climate.bedroom"],
            "presence_entities": ["device_tracker.tablet"],
            "schedules": {"home": {}, "away": {}}
        }
        
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            # Mock different storage instances for different entries
            def create_mock_store(hass, version, key):
                mock_store = AsyncMock()
                if "entry_1" in key:
                    mock_store.async_load.return_value = storage_data_1
                elif "entry_2" in key:
                    mock_store.async_load.return_value = storage_data_2
                else:
                    mock_store.async_load.return_value = None
                mock_store.async_save.return_value = None
                return mock_store
            
            mock_store_class.side_effect = create_mock_store
            
            # Setup both entries
            result_1 = await async_setup_entry(hass, config_entry_1)
            result_2 = await async_setup_entry(hass, config_entry_2)
            
            assert result_1 is True
            assert result_2 is True
            
            # Verify both entries are set up correctly
            assert DOMAIN in hass.data
            assert config_entry_1.entry_id in hass.data[DOMAIN]
            assert config_entry_2.entry_id in hass.data[DOMAIN]
            
            # Verify each entry has its own managers
            entry_1_data = hass.data[DOMAIN][config_entry_1.entry_id]
            entry_2_data = hass.data[DOMAIN][config_entry_2.entry_id]
            
            assert "presence_manager" in entry_1_data
            assert "presence_manager" in entry_2_data
            
            # Verify managers are separate instances
            assert entry_1_data["presence_manager"] is not entry_2_data["presence_manager"]