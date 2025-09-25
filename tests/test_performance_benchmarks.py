"""
Performance benchmarking tests for manager integration fix.

This module provides detailed performance testing to validate that the storage
integration doesn't negatively impact system performance.
"""

import pytest
import time
import asyncio
import statistics
from unittest.mock import AsyncMock, MagicMock
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler import async_setup_entry, async_unload_entry
from custom_components.roost_scheduler.const import DOMAIN
from custom_components.roost_scheduler.models import BufferConfig


class TestPerformanceBenchmarks:
    """Performance benchmarking test suite."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {}
        hass.states.get = MagicMock(return_value=MagicMock(state="home"))
        hass.states.async_set = AsyncMock()
        hass.services.async_register = AsyncMock()
        hass.services.async_call = AsyncMock()
        hass.bus.async_listen = MagicMock()
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "benchmark_test"
        entry.data = {
            "entities_tracked": ["climate.test"],
            "presence_entities": ["device_tracker.test"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        entry.options = {}
        return entry

    async def benchmark_operation(self, operation_func, iterations=10):
        """Benchmark an async operation."""
        times = []
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            await operation_func()
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        
        return {
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'min': min(times),
            'max': max(times),
            'stdev': statistics.stdev(times) if len(times) > 1 else 0
        }

    async def test_setup_performance_benchmark(self, mock_hass, mock_config_entry):
        """Benchmark integration setup performance."""
        hass = mock_hass
        entry = mock_config_entry
        
        async def setup_operation():
            await async_setup_entry(hass, entry)
            await async_unload_entry(hass, entry)
        
        # Benchmark setup/teardown cycle
        stats = await self.benchmark_operation(setup_operation, iterations=5)
        
        # Performance assertions
        assert stats['mean'] < 2.0, f"Average setup time too high: {stats['mean']:.3f}s"
        assert stats['max'] < 5.0, f"Maximum setup time too high: {stats['max']:.3f}s"
        
        print(f"Setup Performance Stats:")
        print(f"  Mean: {stats['mean']:.3f}s")
        print(f"  Median: {stats['median']:.3f}s")
        print(f"  Min: {stats['min']:.3f}s")
        print(f"  Max: {stats['max']:.3f}s")
        print(f"  StdDev: {stats['stdev']:.3f}s")

    async def test_configuration_update_performance(self, mock_hass, mock_config_entry):
        """Benchmark configuration update performance."""
        hass = mock_hass
        entry = mock_config_entry
        
        # Setup integration
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        
        # Benchmark presence entity updates
        async def update_presence():
            entities = ["device_tracker.test1", "device_tracker.test2"]
            await presence_manager.update_presence_entities(entities)
        
        presence_stats = await self.benchmark_operation(update_presence, iterations=20)
        
        # Benchmark buffer config updates
        async def update_buffer():
            config = BufferConfig(time_minutes=15, value_delta=2.0)
            await buffer_manager.update_global_buffer_config(config)
        
        buffer_stats = await self.benchmark_operation(update_buffer, iterations=20)
        
        # Performance assertions
        assert presence_stats['mean'] < 0.1, f"Presence update too slow: {presence_stats['mean']:.3f}s"
        assert buffer_stats['mean'] < 0.1, f"Buffer update too slow: {buffer_stats['mean']:.3f}s"
        
        print(f"Presence Update Performance:")
        print(f"  Mean: {presence_stats['mean']:.3f}s")
        print(f"  Max: {presence_stats['max']:.3f}s")
        
        print(f"Buffer Update Performance:")
        print(f"  Mean: {buffer_stats['mean']:.3f}s")
        print(f"  Max: {buffer_stats['max']:.3f}s")

    async def test_concurrent_operations_performance(self, mock_hass, mock_config_entry):
        """Benchmark concurrent operations performance."""
        hass = mock_hass
        entry = mock_config_entry
        
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        presence_manager = integration_data["presence_manager"]
        buffer_manager = integration_data["buffer_manager"]
        
        async def concurrent_operations():
            tasks = []
            
            # Multiple presence updates
            for i in range(5):
                entities = [f"device_tracker.concurrent_{i}"]
                tasks.append(presence_manager.update_presence_entities(entities))
            
            # Multiple buffer updates
            for i in range(5):
                config = BufferConfig(time_minutes=10 + i, value_delta=1.0 + i)
                tasks.append(buffer_manager.update_global_buffer_config(config))
            
            await asyncio.gather(*tasks)
        
        stats = await self.benchmark_operation(concurrent_operations, iterations=5)
        
        # Concurrent operations should not be significantly slower than sequential
        assert stats['mean'] < 1.0, f"Concurrent operations too slow: {stats['mean']:.3f}s"
        
        print(f"Concurrent Operations Performance:")
        print(f"  Mean: {stats['mean']:.3f}s")
        print(f"  Max: {stats['max']:.3f}s")

    async def test_memory_usage_stability(self, mock_hass, mock_config_entry):
        """Test memory usage stability during operations."""
        import gc
        import sys
        
        hass = mock_hass
        entry = mock_config_entry
        
        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Perform multiple setup/teardown cycles
        for i in range(10):
            await async_setup_entry(hass, entry)
            
            # Perform some operations
            integration_data = hass.data[DOMAIN][entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            entities = [f"device_tracker.memory_test_{i}"]
            await presence_manager.update_presence_entities(entities)
            
            await async_unload_entry(hass, entry)
        
        # Check final memory usage
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Memory usage should not grow significantly
        object_growth = final_objects - initial_objects
        growth_percentage = (object_growth / initial_objects) * 100
        
        print(f"Memory Usage:")
        print(f"  Initial objects: {initial_objects}")
        print(f"  Final objects: {final_objects}")
        print(f"  Growth: {object_growth} objects ({growth_percentage:.1f}%)")
        
        # Allow some growth but not excessive
        assert growth_percentage < 50, f"Memory usage grew too much: {growth_percentage:.1f}%"

    async def test_large_configuration_performance(self, mock_hass, mock_config_entry):
        """Test performance with large configurations."""
        hass = mock_hass
        entry = mock_config_entry
        
        # Create large configuration
        large_entity_list = [f"device_tracker.large_test_{i}" for i in range(100)]
        entry.data["presence_entities"] = large_entity_list
        
        # Mock states for all entities
        def mock_get_state(entity_id):
            return MagicMock(state="home")
        hass.states.get = mock_get_state
        
        # Benchmark setup with large configuration
        async def large_setup():
            await async_setup_entry(hass, entry)
            integration_data = hass.data[DOMAIN][entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Test presence detection with many entities
            await presence_manager.async_is_home()
            
            await async_unload_entry(hass, entry)
        
        stats = await self.benchmark_operation(large_setup, iterations=3)
        
        # Should handle large configurations reasonably well
        assert stats['mean'] < 10.0, f"Large config setup too slow: {stats['mean']:.3f}s"
        
        print(f"Large Configuration Performance (100 entities):")
        print(f"  Mean: {stats['mean']:.3f}s")
        print(f"  Max: {stats['max']:.3f}s")

    async def test_storage_operation_performance(self, mock_hass, mock_config_entry):
        """Test storage operation performance specifically."""
        hass = mock_hass
        entry = mock_config_entry
        
        await async_setup_entry(hass, entry)
        integration_data = hass.data[DOMAIN][entry.entry_id]
        storage_service = integration_data["storage_service"]
        
        # Benchmark storage load operations
        async def load_operation():
            await storage_service.load_schedules()
        
        load_stats = await self.benchmark_operation(load_operation, iterations=50)
        
        # Benchmark storage save operations
        from custom_components.roost_scheduler.models import ScheduleData
        
        async def save_operation():
            schedule_data = ScheduleData()
            schedule_data.schedules["test"] = {"climate.test": {"temperature": 20.0}}
            await storage_service.save_schedules(schedule_data)
        
        save_stats = await self.benchmark_operation(save_operation, iterations=50)
        
        # Storage operations should be fast
        assert load_stats['mean'] < 0.05, f"Storage load too slow: {load_stats['mean']:.3f}s"
        assert save_stats['mean'] < 0.05, f"Storage save too slow: {save_stats['mean']:.3f}s"
        
        print(f"Storage Load Performance:")
        print(f"  Mean: {load_stats['mean']:.4f}s")
        print(f"  Max: {load_stats['max']:.4f}s")
        
        print(f"Storage Save Performance:")
        print(f"  Mean: {save_stats['mean']:.4f}s")
        print(f"  Max: {save_stats['max']:.4f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to show print output