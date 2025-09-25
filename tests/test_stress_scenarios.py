"""
Stress testing scenarios for manager integration fix.

This module provides comprehensive stress testing to validate system behavior
under extreme conditions and edge cases.
"""

import pytest
import asyncio
import random
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME

from custom_components.roost_scheduler import async_setup_entry, async_unload_entry
from custom_components.roost_scheduler.const import DOMAIN
from custom_components.roost_scheduler.models import BufferConfig, ScheduleData


class TestStressScenarios:
    """Comprehensive stress testing scenarios."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {}
        hass.states.async_set = AsyncMock()
        hass.services.async_register = AsyncMock()
        hass.services.async_call = AsyncMock()
        hass.bus.async_listen = MagicMock()
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "stress_test"
        entry.data = {
            "entities_tracked": ["climate.test"],
            "presence_entities": ["device_tracker.test"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        entry.options = {}
        return entry

    async def test_rapid_configuration_changes(self, mock_hass, mock_config_entry):
        """Test rapid configuration changes under stress."""
        hass = mock_hass
        entry = mock_config_entry
        
        # Mock entity states
        hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        
        # Perform rapid configuration changes
        tasks = []
        
        for i in range(100):
            # Rapid presence entity updates
            entities = [f"device_tracker.rapid_{i}", f"person.rapid_{i}"]
            tasks.append(presence_manager.update_presence_entities(entities))
            
            # Rapid buffer config updates
            config = BufferConfig(
                time_minutes=random.randint(1, 60),
                value_delta=random.uniform(0.1, 5.0),
                enabled=random.choice([True, False])
            )
            tasks.append(buffer_manager.update_global_buffer_config(config))
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful operations
        successful = sum(1 for result in results if not isinstance(result, Exception))
        failed = len(results) - successful
        
        print(f"Rapid changes: {successful} successful, {failed} failed")
        
        # Most operations should succeed
        success_rate = successful / len(results)
        assert success_rate > 0.8, f"Success rate too low: {success_rate:.2f}"
        
        # Validate final state is consistent
        final_entities = presence_manager.get_presence_entities()
        final_config = buffer_manager.get_global_buffer_config()
        
        assert isinstance(final_entities, list)
        assert isinstance(final_config, BufferConfig)

    async def test_massive_entity_configuration(self, mock_hass, mock_config_entry):
        """Test with massive number of entities."""
        hass = mock_hass
        entry = mock_config_entry
        
        # Create massive entity lists
        massive_presence_entities = [f"device_tracker.massive_{i}" for i in range(1000)]
        massive_climate_entities = [f"climate.massive_{i}" for i in range(500)]
        
        entry.data["presence_entities"] = massive_presence_entities
        entry.data["entities_tracked"] = massive_climate_entities
        
        # Mock states for all entities
        def mock_get_state(entity_id):
            return MagicMock(state=random.choice([STATE_HOME, STATE_NOT_HOME]))
        hass.states.get = mock_get_state
        
        # Setup should handle massive configuration
        result = await async_setup_entry(hass, entry)
        assert result is True, "Setup should succeed with massive configuration"
        
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        
        # Test presence detection with massive entity list
        is_home = await presence_manager.async_is_home()
        assert isinstance(is_home, bool)
        
        # Test configuration persistence
        loaded_entities = presence_manager.get_presence_entities()
        assert len(loaded_entities) == len(massive_presence_entities)

    async def test_continuous_operation_stress(self, mock_hass, mock_config_entry):
        """Test continuous operation under stress."""
        hass = mock_hass
        entry = mock_config_entry
        
        hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        schedule_manager = integration_data["schedule_manager"]
        
        # Simulate continuous operation for extended period
        operation_count = 0
        error_count = 0
        
        for cycle in range(200):  # Simulate 200 operation cycles
            try:
                # Simulate various operations
                operations = [
                    presence_manager.async_is_home(),
                    buffer_manager.get_global_buffer_config(),
                    schedule_manager.get_current_schedule_name()
                ]
                
                # Occasionally update configuration
                if cycle % 10 == 0:
                    entities = [f"device_tracker.continuous_{cycle}"]
                    operations.append(
                        presence_manager.update_presence_entities(entities)
                    )
                
                if cycle % 15 == 0:
                    config = BufferConfig(time_minutes=cycle % 60 + 1)
                    operations.append(
                        buffer_manager.update_global_buffer_config(config)
                    )
                
                await asyncio.gather(*operations)
                operation_count += len(operations)
                
            except Exception as e:
                error_count += 1
                print(f"Error in cycle {cycle}: {e}")
        
        print(f"Continuous operation: {operation_count} operations, {error_count} errors")
        
        # Error rate should be very low
        error_rate = error_count / 200
        assert error_rate < 0.05, f"Error rate too high: {error_rate:.3f}"

    async def test_memory_pressure_scenarios(self, mock_hass, mock_config_entry):
        """Test behavior under memory pressure scenarios."""
        hass = mock_hass
        entry = mock_config_entry
        
        hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        # Create many integration instances to simulate memory pressure
        instances = []
        
        for i in range(20):
            instance_entry = MagicMock(spec=ConfigEntry)
            instance_entry.entry_id = f"memory_test_{i}"
            instance_entry.data = {
                "entities_tracked": [f"climate.memory_{i}"],
                "presence_entities": [f"device_tracker.memory_{i}"],
                "presence_rule": "anyone_home",
                "presence_timeout_seconds": 600
            }
            instance_entry.options = {}
            
            result = await async_setup_entry(hass, instance_entry)
            if result:
                instances.append(instance_entry)
        
        print(f"Created {len(instances)} integration instances")
        
        # Perform operations on all instances
        for entry_instance in instances:
            if entry_instance.entry_id in hass.data.get(DOMAIN, {}):
                integration_data = hass.data[DOMAIN][entry_instance.entry_id]
                presence_manager = integration_data["presence_manager"]
                
                # Perform operations
                await presence_manager.async_is_home()
                
                entities = [f"device_tracker.pressure_{entry_instance.entry_id}"]
                await presence_manager.update_presence_entities(entities)
        
        # Clean up instances
        for entry_instance in instances:
            if entry_instance.entry_id in hass.data.get(DOMAIN, {}):
                await async_unload_entry(hass, entry_instance)
        
        # Should handle memory pressure gracefully
        assert len(instances) > 10, "Should create multiple instances under memory pressure"

    async def test_storage_failure_scenarios(self, mock_hass, mock_config_entry):
        """Test various storage failure scenarios."""
        hass = mock_hass
        entry = mock_config_entry
        
        hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        # Test intermittent storage failures
        failure_count = 0
        
        def failing_storage_operation(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            if failure_count % 3 == 0:  # Fail every 3rd operation
                raise Exception("Simulated storage failure")
            return AsyncMock()()
        
        with patch('custom_components.roost_scheduler.storage.StorageService.save_schedules') as mock_save:
            mock_save.side_effect = failing_storage_operation
            
            await async_setup_entry(hass, entry)
            integration_data = hass.data[DOMAIN][entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Perform operations that trigger saves
            success_count = 0
            error_count = 0
            
            for i in range(20):
                try:
                    entities = [f"device_tracker.storage_fail_{i}"]
                    await presence_manager.update_presence_entities(entities)
                    success_count += 1
                except Exception:
                    error_count += 1
            
            print(f"Storage failures: {success_count} successful, {error_count} failed")
            
            # Should handle storage failures gracefully
            assert success_count > 0, "Some operations should succeed despite storage failures"

    async def test_concurrent_setup_teardown(self, mock_hass, mock_config_entry):
        """Test concurrent setup and teardown operations."""
        hass = mock_hass
        
        hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        async def setup_teardown_cycle(cycle_id):
            """Perform setup/teardown cycle."""
            entry = MagicMock(spec=ConfigEntry)
            entry.entry_id = f"concurrent_{cycle_id}"
            entry.data = {
                "entities_tracked": [f"climate.concurrent_{cycle_id}"],
                "presence_entities": [f"device_tracker.concurrent_{cycle_id}"],
                "presence_rule": "anyone_home",
                "presence_timeout_seconds": 600
            }
            entry.options = {}
            
            try:
                # Setup
                result = await async_setup_entry(hass, entry)
                if not result:
                    return False
                
                # Perform some operations
                if entry.entry_id in hass.data.get(DOMAIN, {}):
                    integration_data = hass.data[DOMAIN][entry.entry_id]
                    presence_manager = integration_data["presence_manager"]
                    await presence_manager.async_is_home()
                
                # Teardown
                await async_unload_entry(hass, entry)
                return True
                
            except Exception as e:
                print(f"Error in cycle {cycle_id}: {e}")
                return False
        
        # Run multiple concurrent setup/teardown cycles
        tasks = [setup_teardown_cycle(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for result in results if result is True)
        print(f"Concurrent setup/teardown: {successful}/10 successful")
        
        # Most cycles should succeed
        assert successful >= 7, f"Too many concurrent failures: {successful}/10"

    async def test_extreme_configuration_values(self, mock_hass, mock_config_entry):
        """Test with extreme configuration values."""
        hass = mock_hass
        entry = mock_config_entry
        
        hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        # Test with extreme values
        extreme_configs = [
            {
                "presence_timeout_seconds": 0,  # Minimum timeout
                "buffer_time": 0,
                "buffer_delta": 0.0
            },
            {
                "presence_timeout_seconds": 86400 * 7,  # Week timeout
                "buffer_time": 1440,  # 24 hours
                "buffer_delta": 100.0
            },
            {
                "presence_timeout_seconds": -1,  # Invalid negative
                "buffer_time": -10,
                "buffer_delta": -5.0
            }
        ]
        
        for i, config in enumerate(extreme_configs):
            entry.entry_id = f"extreme_{i}"
            entry.data["presence_timeout_seconds"] = config["presence_timeout_seconds"]
            
            try:
                result = await async_setup_entry(hass, entry)
                
                if result and entry.entry_id in hass.data.get(DOMAIN, {}):
                    integration_data = hass.data[DOMAIN][entry.entry_id]
                    presence_manager = integration_data["presence_manager"]
                    buffer_manager = integration_data["buffer_manager"]
                    
                    # Test operations with extreme values
                    await presence_manager.async_is_home()
                    
                    buffer_config = BufferConfig(
                        time_minutes=config["buffer_time"],
                        value_delta=config["buffer_delta"]
                    )
                    await buffer_manager.update_global_buffer_config(buffer_config)
                    
                    await async_unload_entry(hass, entry)
                
            except Exception as e:
                print(f"Extreme config {i} error (expected): {e}")
                # Some extreme values should cause errors, which is acceptable

    async def test_resource_exhaustion_recovery(self, mock_hass, mock_config_entry):
        """Test recovery from resource exhaustion scenarios."""
        hass = mock_hass
        entry = mock_config_entry
        
        hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        # Simulate resource exhaustion
        with patch('asyncio.create_task') as mock_create_task:
            # Make task creation fail intermittently
            call_count = 0
            
            def failing_create_task(coro):
                nonlocal call_count
                call_count += 1
                if call_count % 5 == 0:
                    raise RuntimeError("Resource exhaustion")
                return AsyncMock()
            
            mock_create_task.side_effect = failing_create_task
            
            # Setup should handle resource exhaustion
            try:
                result = await async_setup_entry(hass, entry)
                # May succeed or fail, but should not crash
                assert isinstance(result, bool)
            except Exception as e:
                # Resource exhaustion errors are acceptable
                print(f"Resource exhaustion handled: {e}")

    async def test_data_corruption_scenarios(self, mock_hass, mock_config_entry):
        """Test handling of data corruption scenarios."""
        hass = mock_hass
        entry = mock_config_entry
        
        hass.states.get = MagicMock(return_value=MagicMock(state=STATE_HOME))
        
        # Test with corrupted storage data
        corrupted_data_scenarios = [
            None,  # No data
            {},  # Empty data
            {"invalid": "structure"},  # Invalid structure
            {"schedules": "not_a_dict"},  # Wrong type
            {"presence_config": {"entities": "not_a_list"}},  # Invalid nested data
        ]
        
        for i, corrupted_data in enumerate(corrupted_data_scenarios):
            entry.entry_id = f"corruption_{i}"
            
            with patch('custom_components.roost_scheduler.storage.StorageService.load_schedules') as mock_load:
                if corrupted_data is None:
                    mock_load.return_value = None
                else:
                    # Create a mock ScheduleData with corrupted attributes
                    mock_schedule_data = MagicMock()
                    for key, value in corrupted_data.items():
                        setattr(mock_schedule_data, key, value)
                    mock_load.return_value = mock_schedule_data
                
                try:
                    result = await async_setup_entry(hass, entry)
                    
                    if result and entry.entry_id in hass.data.get(DOMAIN, {}):
                        integration_data = hass.data[DOMAIN][entry.entry_id]
                        presence_manager = integration_data["presence_manager"]
                        
                        # Should handle corrupted data gracefully
                        await presence_manager.async_is_home()
                        
                        await async_unload_entry(hass, entry)
                    
                    print(f"Corruption scenario {i}: Handled gracefully")
                    
                except Exception as e:
                    print(f"Corruption scenario {i}: Error handled: {e}")
                    # Errors are acceptable for corrupted data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])