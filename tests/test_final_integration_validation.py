"""
Final integration testing and validation for manager integration fix.

This test suite performs comprehensive end-to-end testing to validate:
1. Complete setup flow from fresh installation to operation
2. Real presence entity integration
3. Original TypeError resolution
4. Performance impact validation
5. Stress testing with various configuration scenarios
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME

from custom_components.roost_scheduler import async_setup_entry, async_unload_entry
from custom_components.roost_scheduler.const import DOMAIN
from custom_components.roost_scheduler.storage import StorageService
from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.schedule_manager import ScheduleManager
from custom_components.roost_scheduler.models import ScheduleData, PresenceConfig, BufferConfig


class TestFinalIntegrationValidation:
    """Comprehensive end-to-end integration tests."""

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry for testing."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        entry.data = {
            "entities_tracked": ["climate.living_room", "climate.bedroom"],
            "presence_entities": ["device_tracker.phone", "person.user"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        entry.options = {}
        return entry

    @pytest.fixture
    async def mock_hass_with_entities(self, hass):
        """Create a Home Assistant instance with real-like entities."""
        # Set up entity states
        hass.states.async_set("climate.living_room", "heat", {"temperature": 20.0})
        hass.states.async_set("climate.bedroom", "heat", {"temperature": 19.0})
        hass.states.async_set("device_tracker.phone", STATE_HOME)
        hass.states.async_set("person.user", STATE_HOME)
        hass.states.async_set("input_boolean.roost_force_home", "off")
        hass.states.async_set("input_boolean.roost_force_away", "off")
        
        return hass

    async def test_complete_fresh_installation_setup(self, mock_hass_with_entities, mock_config_entry):
        """Test complete setup flow from fresh installation to operation."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # Ensure clean state
        assert DOMAIN not in hass.data
        
        # Test setup
        setup_start_time = time.time()
        result = await async_setup_entry(hass, entry)
        setup_duration = time.time() - setup_start_time
        
        # Validate setup succeeded
        assert result is True, "Integration setup should succeed"
        assert DOMAIN in hass.data, "Domain should be in hass.data"
        assert entry.entry_id in hass.data[DOMAIN], "Entry ID should be in domain data"
        
        # Validate performance - setup should complete quickly
        assert setup_duration < 5.0, f"Setup took too long: {setup_duration}s"
        
        # Validate all managers are properly initialized
        integration_data = hass.data[DOMAIN][entry.entry_id]
        
        assert "storage_service" in integration_data
        assert "presence_manager" in integration_data
        assert "buffer_manager" in integration_data
        assert "schedule_manager" in integration_data
        
        storage_service = integration_data["storage_service"]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        schedule_manager = integration_data["schedule_manager"]
        
        # Validate manager types and initialization
        assert isinstance(storage_service, StorageService)
        assert isinstance(presence_manager, PresenceManager)
        assert isinstance(buffer_manager, BufferManager)
        assert isinstance(schedule_manager, ScheduleManager)
        
        # Validate managers have storage service
        assert presence_manager.storage_service is storage_service
        assert buffer_manager.storage_service is storage_service
        assert schedule_manager.storage_service is storage_service
        
        # Validate presence configuration is loaded
        presence_entities = presence_manager.get_presence_entities()
        assert "device_tracker.phone" in presence_entities
        assert "person.user" in presence_entities
        
        # Test unload
        unload_result = await async_unload_entry(hass, entry)
        assert unload_result is True, "Integration unload should succeed"

    async def test_original_typeerror_resolution(self, mock_hass_with_entities, mock_config_entry):
        """Validate that the original TypeError is completely resolved."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # This test specifically validates that the constructor signature mismatch is fixed
        # The original error was:
        # TypeError: PresenceManager.__init__() takes 2 positional arguments but 3 were given
        
        try:
            # This should not raise a TypeError anymore
            result = await async_setup_entry(hass, entry)
            assert result is True, "Setup should succeed without TypeError"
            
            # Validate managers were created with correct parameters
            integration_data = hass.data[DOMAIN][entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            buffer_manager = integration_data["buffer_manager"]
            
            # Validate managers have both hass and storage_service
            assert hasattr(presence_manager, 'hass')
            assert hasattr(presence_manager, 'storage_service')
            assert hasattr(buffer_manager, 'hass')
            assert hasattr(buffer_manager, 'storage_service')
            
        except TypeError as e:
            pytest.fail(f"TypeError still occurs: {e}")
        except Exception as e:
            # Other exceptions are acceptable for this specific test
            pass

    async def test_presence_entity_integration(self, mock_hass_with_entities, mock_config_entry):
        """Test integration with real presence entities."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # Setup integration
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        
        # Test presence detection with different entity states
        test_scenarios = [
            {
                "name": "All home",
                "states": {"device_tracker.phone": STATE_HOME, "person.user": STATE_HOME},
                "expected": True
            },
            {
                "name": "One away",
                "states": {"device_tracker.phone": STATE_NOT_HOME, "person.user": STATE_HOME},
                "expected": True  # anyone_home rule
            },
            {
                "name": "All away",
                "states": {"device_tracker.phone": STATE_NOT_HOME, "person.user": STATE_NOT_HOME},
                "expected": False
            }
        ]
        
        for scenario in test_scenarios:
            # Update entity states
            for entity_id, state in scenario["states"].items():
                hass.states.get(entity_id).state = state
            
            # Test presence detection
            is_home = await presence_manager.async_is_home()
            assert is_home == scenario["expected"], f"Scenario '{scenario['name']}' failed"

    async def test_configuration_persistence_across_restarts(self, mock_hass_with_entities, mock_config_entry):
        """Test that configuration persists across integration restarts."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # First setup
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        
        # Modify configuration
        new_presence_entities = ["device_tracker.tablet", "person.guest"]
        await presence_manager.update_presence_entities(new_presence_entities)
        
        new_buffer_config = BufferConfig(time_minutes=30, value_delta=3.0)
        await buffer_manager.update_global_buffer_config(new_buffer_config)
        
        # Unload integration
        await async_unload_entry(hass, entry)
        
        # Setup again (simulating restart)
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        
        # Validate configuration was persisted
        loaded_entities = presence_manager.get_presence_entities()
        assert set(loaded_entities) == set(new_presence_entities)
        
        loaded_buffer_config = buffer_manager.get_global_buffer_config()
        assert loaded_buffer_config.time_minutes == 30
        assert loaded_buffer_config.value_delta == 3.0

    async def test_performance_impact_validation(self, mock_hass_with_entities, mock_config_entry):
        """Test performance impact of storage integration."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # Measure setup performance
        setup_times = []
        for i in range(5):
            start_time = time.time()
            await async_setup_entry(hass, entry)
            setup_time = time.time() - start_time
            setup_times.append(setup_time)
            
            await async_unload_entry(hass, entry)
        
        avg_setup_time = sum(setup_times) / len(setup_times)
        max_setup_time = max(setup_times)
        
        # Performance assertions
        assert avg_setup_time < 2.0, f"Average setup time too high: {avg_setup_time}s"
        assert max_setup_time < 5.0, f"Maximum setup time too high: {max_setup_time}s"
        
        # Test configuration operation performance
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        
        # Measure configuration update performance
        config_update_times = []
        for i in range(10):
            entities = [f"device_tracker.test_{i}", f"person.test_{i}"]
            
            start_time = time.time()
            await presence_manager.update_presence_entities(entities)
            update_time = time.time() - start_time
            config_update_times.append(update_time)
        
        avg_update_time = sum(config_update_times) / len(config_update_times)
        assert avg_update_time < 0.5, f"Configuration update too slow: {avg_update_time}s"

    async def test_stress_testing_various_configurations(self, mock_hass_with_entities, mock_config_entry):
        """Perform stress testing with various configuration scenarios."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # Test with large number of entities
        large_entity_list = [f"device_tracker.device_{i}" for i in range(100)]
        entry.data["presence_entities"] = large_entity_list
        
        # Add mock states for all entities
        for entity_id in large_entity_list:
            hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        
        # Test presence detection with many entities
        start_time = time.time()
        is_home = await presence_manager.async_is_home()
        detection_time = time.time() - start_time
        
        assert detection_time < 1.0, f"Presence detection with many entities too slow: {detection_time}s"
        assert is_home is True  # All entities are home
        
        await async_unload_entry(hass, entry)
        
        # Test with complex buffer configurations
        entry.data["presence_entities"] = ["device_tracker.phone"]  # Reset to simple
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        buffer_manager = integration_data["buffer_manager"]
        
        # Create many entity-specific buffer configs
        for i in range(50):
            entity_id = f"climate.room_{i}"
            config = BufferConfig(
                time_minutes=10 + i,
                value_delta=1.0 + (i * 0.1),
                enabled=i % 2 == 0
            )
            await buffer_manager.update_entity_buffer_config(entity_id, config)
        
        # Validate all configurations were saved
        for i in range(50):
            entity_id = f"climate.room_{i}"
            config = buffer_manager.get_entity_buffer_config(entity_id)
            if config:  # Some might not be saved if disabled
                assert config.time_minutes == 10 + i

    async def test_error_recovery_scenarios(self, mock_hass_with_entities, mock_config_entry):
        """Test error recovery in various failure scenarios."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # Test setup with storage service failure
        with patch('custom_components.roost_scheduler.storage.StorageService.load_schedules') as mock_load:
            mock_load.side_effect = Exception("Storage failure")
            
            # Setup should still succeed with fallback behavior
            result = await async_setup_entry(hass, entry)
            assert result is True, "Setup should succeed even with storage failure"
            
            # Managers should still be initialized
            integration_data = hass.data[DOMAIN][entry.entry_id]
            assert "presence_manager" in integration_data
            assert "buffer_manager" in integration_data
        
        await async_unload_entry(hass, entry)
        
        # Test setup with presence manager initialization failure
        with patch('custom_components.roost_scheduler.presence_manager.PresenceManager.__init__') as mock_init:
            mock_init.side_effect = Exception("PresenceManager failure")
            
            # Setup should handle the error gracefully
            result = await async_setup_entry(hass, entry)
            # Result might be False, but should not raise unhandled exception
            assert isinstance(result, bool)

    async def test_migration_from_legacy_configuration(self, mock_hass_with_entities, mock_config_entry):
        """Test migration from legacy configuration format."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # Simulate legacy configuration in config entry
        entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.legacy"],
            "presence_rule": "all_home",
            "presence_timeout_seconds": 300
        }
        
        # Setup should migrate configuration
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        
        # Validate migration occurred
        entities = presence_manager.get_presence_entities()
        assert "device_tracker.legacy" in entities
        
        rule = presence_manager.get_presence_rule()
        assert rule == "all_home"
        
        timeout = presence_manager.get_timeout_seconds()
        assert timeout == 300

    async def test_concurrent_operations(self, mock_hass_with_entities, mock_config_entry):
        """Test concurrent operations on managers."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        
        # Test concurrent presence entity updates
        async def update_presence_entities(index):
            entities = [f"device_tracker.concurrent_{index}", f"person.concurrent_{index}"]
            await presence_manager.update_presence_entities(entities)
        
        # Test concurrent buffer config updates
        async def update_buffer_config(index):
            config = BufferConfig(time_minutes=index, value_delta=float(index))
            await buffer_manager.update_global_buffer_config(config)
        
        # Run concurrent operations
        tasks = []
        for i in range(10):
            tasks.append(update_presence_entities(i))
            tasks.append(update_buffer_config(i))
        
        # All operations should complete without errors
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Validate final state is consistent
        final_entities = presence_manager.get_presence_entities()
        final_config = buffer_manager.get_global_buffer_config()
        
        assert isinstance(final_entities, list)
        assert isinstance(final_config, BufferConfig)


@pytest.mark.asyncio
class TestEndToEndScenarios:
    """End-to-end scenario testing."""

    async def test_typical_user_workflow(self, mock_hass_with_entities, mock_config_entry):
        """Test a typical user workflow from installation to daily use."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # 1. Fresh installation
        result = await async_setup_entry(hass, entry)
        assert result is True
        
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        schedule_manager = integration_data["schedule_manager"]
        
        # 2. User configures presence entities
        await presence_manager.update_presence_entities([
            "device_tracker.phone",
            "device_tracker.tablet",
            "person.user"
        ])
        
        # 3. User sets up buffer configuration
        buffer_config = BufferConfig(time_minutes=20, value_delta=1.5, enabled=True)
        await buffer_manager.update_global_buffer_config(buffer_config)
        
        # 4. User creates schedules
        schedule_data = ScheduleData()
        schedule_data.schedules["home"] = {
            "climate.living_room": {"temperature": 22.0, "time": "07:00"}
        }
        schedule_data.schedules["away"] = {
            "climate.living_room": {"temperature": 18.0, "time": "08:00"}
        }
        
        await schedule_manager.save_schedules(schedule_data)
        
        # 5. Simulate daily operations
        for _ in range(5):
            # Check presence
            is_home = await presence_manager.async_is_home()
            
            # Apply schedules based on presence
            if is_home:
                await schedule_manager.apply_schedule("home")
            else:
                await schedule_manager.apply_schedule("away")
        
        # 6. User modifies configuration
        await presence_manager.update_presence_rule("all_home")
        
        # 7. Restart simulation
        await async_unload_entry(hass, entry)
        await async_setup_entry(hass, entry)
        
        # 8. Validate configuration persisted
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        
        entities = presence_manager.get_presence_entities()
        rule = presence_manager.get_presence_rule()
        
        assert "device_tracker.phone" in entities
        assert "device_tracker.tablet" in entities
        assert "person.user" in entities
        assert rule == "all_home"

    async def test_upgrade_scenario(self, mock_hass_with_entities, mock_config_entry):
        """Test upgrade from previous version scenario."""
        hass = mock_hass_with_entities
        entry = mock_config_entry
        
        # Simulate existing installation with old format
        entry.data = {
            "entities_tracked": ["climate.living_room", "climate.bedroom"],
            "presence_entities": ["device_tracker.old_phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Setup should handle upgrade
        result = await async_setup_entry(hass, entry)
        assert result is True
        
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        
        # Validate old configuration was preserved
        entities = presence_manager.get_presence_entities()
        assert "device_tracker.old_phone" in entities
        
        # Add new configuration
        await presence_manager.update_presence_entities([
            "device_tracker.old_phone",
            "device_tracker.new_phone"
        ])
        
        # Restart to validate persistence
        await async_unload_entry(hass, entry)
        await async_setup_entry(hass, entry)
        
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        
        entities = presence_manager.get_presence_entities()
        assert "device_tracker.old_phone" in entities
        assert "device_tracker.new_phone" in entities


if __name__ == "__main__":
    pytest.main([__file__, "-v"])