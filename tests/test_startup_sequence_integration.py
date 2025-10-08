"""
Integration tests for complete startup sequence without blocking warnings.

Tests the entire integration startup process to ensure no blocking I/O operations
occur that would generate Home Assistant warnings.
"""
import asyncio
import logging
import pytest

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_OFF

from custom_components.roost_scheduler import async_setup, async_setup_entry
from custom_components.roost_scheduler.const import DOMAIN
from custom_components.roost_scheduler.storage import StorageService
from custom_components.roost_scheduler.schedule_manager import ScheduleManager
from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager


class BlockingCallDetector:
    """Detector for blocking I/O operations during startup."""
    
    def __init__(self):
        self.blocking_calls = []
        self.monitored_functions = [
            'builtins.open',
            'os.path.exists',
            'os.makedirs',
            'shutil.copy',
            'json.load',
            'json.dump'
        ]
    
    def detect_blocking_call(self, func_name: str, *args, **kwargs):
        """Record a blocking call for analysis."""
        self.blocking_calls.append({
            'function': func_name,
            'args': args,
            'kwargs': kwargs,
            'timestamp': datetime.now()
        })
    
    def get_blocking_calls(self) -> list:
        """Get all detected blocking calls."""
        return self.blocking_calls
    
    def has_blocking_calls(self) -> bool:
        """Check if any blocking calls were detected."""
        return len(self.blocking_calls) > 0


@pytest.fixture
def blocking_detector():
    """Fixture providing blocking call detection."""
    return BlockingCallDetector()


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.config = MagicMock()
    hass.config.config_dir = "/config"
    hass.async_add_executor_job = AsyncMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = AsyncMock()
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.http = MagicMock()
    hass.http.register_static_path = MagicMock()
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


class TestStartupSequenceIntegration:
    """Test complete startup sequence without blocking warnings."""
    
    @pytest.mark.asyncio
    async def test_async_setup_no_blocking_calls(self, mock_hass, blocking_detector):
        """Test that async_setup doesn't make blocking calls."""
        
        # Patch potentially blocking functions to detect calls
        with patch('builtins.open', side_effect=lambda *args, **kwargs: blocking_detector.detect_blocking_call('builtins.open', *args, **kwargs)):
            with patch('custom_components.roost_scheduler.validate_manifest_version', return_value=True):
                with patch('custom_components.roost_scheduler._validate_ha_version', return_value=True):
                    with patch('custom_components.roost_scheduler._validate_dependencies', return_value=True):
                        
                        # Run async_setup
                        result = await async_setup(mock_hass, {})
                        
                        # Verify setup succeeded
                        assert result is True
                        
                        # Verify no blocking calls were made
                        assert not blocking_detector.has_blocking_calls(), \
                            f"Blocking calls detected: {blocking_detector.get_blocking_calls()}"
    
    @pytest.mark.asyncio
    async def test_async_setup_entry_no_blocking_calls(self, mock_hass, mock_config_entry, blocking_detector):
        """Test that async_setup_entry doesn't make blocking calls."""
        
        # Mock all async file operations
        mock_aiofiles_open = AsyncMock()
        mock_file_context = AsyncMock()
        mock_file_context.__aenter__ = AsyncMock(return_value=mock_file_context)
        mock_file_context.__aexit__ = AsyncMock(return_value=None)
        mock_file_context.read = AsyncMock(return_value='{"version": "0.4.0", "schedules": {}}')
        mock_file_context.write = AsyncMock()
        mock_aiofiles_open.return_value = mock_file_context
        
        # Mock validation systems
        mock_validation_result = MagicMock()
        mock_validation_result.success = True
        mock_validation_result.issues = []
        mock_validation_result.warnings = []
        mock_validation_result.diagnostic_data = {}
        mock_validation_result.startup_diagnostics = {}
        
        mock_comprehensive_result = MagicMock()
        mock_comprehensive_result.valid = True
        mock_comprehensive_result.overall_status = "valid"
        mock_comprehensive_result.manifest_result = MagicMock()
        mock_comprehensive_result.manifest_result.valid = True
        mock_comprehensive_result.dependency_result = MagicMock()
        mock_comprehensive_result.dependency_result.valid = True
        mock_comprehensive_result.version_result = MagicMock()
        mock_comprehensive_result.version_result.compatible = True
        
        # Patch potentially blocking functions
        patches = [
            patch('builtins.open', side_effect=lambda *args, **kwargs: blocking_detector.detect_blocking_call('builtins.open', *args, **kwargs)),
            patch('aiofiles.open', return_value=mock_aiofiles_open),
            patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem'),
            patch('custom_components.roost_scheduler.comprehensive_validator.ComprehensiveValidator'),
            patch('custom_components.roost_scheduler.storage.StorageService'),
            patch('custom_components.roost_scheduler.presence_manager.PresenceManager'),
            patch('custom_components.roost_scheduler.buffer_manager.BufferManager'),
            patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager'),
            patch('custom_components.roost_scheduler.logging_config.LoggingManager'),
            patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager'),
            patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService'),
        ]
        
        with patch.multiple('custom_components.roost_scheduler', *patches):
            # Mock validation system responses
            with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_startup_validator:
                mock_startup_validator.return_value.run_validation_orchestration = AsyncMock(return_value=mock_validation_result)
                
                with patch('custom_components.roost_scheduler.comprehensive_validator.ComprehensiveValidator') as mock_comprehensive_validator:
                    mock_comprehensive_validator.return_value.validate_all = AsyncMock(return_value=mock_comprehensive_result)
                    
                    # Mock storage service
                    with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage:
                        mock_storage_instance = AsyncMock()
                        mock_storage_instance.load_schedules = AsyncMock()
                        mock_storage.return_value = mock_storage_instance
                        
                        # Mock managers
                        with patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence:
                            mock_presence_instance = AsyncMock()
                            mock_presence_instance.load_configuration = AsyncMock()
                            mock_presence.return_value = mock_presence_instance
                            
                            with patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer:
                                mock_buffer_instance = AsyncMock()
                                mock_buffer_instance.load_configuration = AsyncMock()
                                mock_buffer.return_value = mock_buffer_instance
                                
                                with patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule:
                                    mock_schedule_instance = AsyncMock()
                                    mock_schedule.return_value = mock_schedule_instance
                                    
                                    # Mock frontend and dashboard services
                                    with patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend:
                                        mock_frontend_instance = AsyncMock()
                                        mock_frontend_instance.register_frontend_resources = AsyncMock(return_value={
                                            "success": True,
                                            "resources_registered": [],
                                            "resources_failed": [],
                                            "warnings": []
                                        })
                                        mock_frontend.return_value = mock_frontend_instance
                                        
                                        with patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard:
                                            mock_dashboard_instance = AsyncMock()
                                            mock_dashboard.return_value = mock_dashboard_instance
                                            
                                            # Run async_setup_entry
                                            result = await async_setup_entry(mock_hass, mock_config_entry)
                                            
                                            # Verify setup succeeded
                                            assert result is True
                                            
                                            # Verify no blocking calls were made
                                            assert not blocking_detector.has_blocking_calls(), \
                                                f"Blocking calls detected: {blocking_detector.get_blocking_calls()}"
    
    @pytest.mark.asyncio
    async def test_startup_with_various_data_states(self, mock_hass, mock_config_entry):
        """Test startup with various data states (empty, corrupted, missing)."""
        
        test_scenarios = [
            {
                "name": "empty_data",
                "storage_data": '{"version": "0.4.0", "schedules": {}}',
                "expected_success": True
            },
            {
                "name": "missing_version",
                "storage_data": '{"schedules": {"test": "data"}}',
                "expected_success": True  # Should handle missing version gracefully
            },
            {
                "name": "corrupted_json",
                "storage_data": '{"version": "0.4.0", "schedules":',  # Invalid JSON
                "expected_success": True  # Should fall back to defaults
            },
            {
                "name": "old_version",
                "storage_data": '{"version": "0.3.0", "schedules": {"old": "format"}}',
                "expected_success": True  # Should trigger migration
            }
        ]
        
        for scenario in test_scenarios:
            # Mock file operations for this scenario
            mock_aiofiles_open = AsyncMock()
            mock_file_context = AsyncMock()
            mock_file_context.__aenter__ = AsyncMock(return_value=mock_file_context)
            mock_file_context.__aexit__ = AsyncMock(return_value=None)
            
            if scenario["name"] == "corrupted_json":
                mock_file_context.read = AsyncMock(side_effect=Exception("Invalid JSON"))
            else:
                mock_file_context.read = AsyncMock(return_value=scenario["storage_data"])
            
            mock_file_context.write = AsyncMock()
            mock_aiofiles_open.return_value = mock_file_context
            
            # Mock validation systems to pass
            mock_validation_result = MagicMock()
            mock_validation_result.success = True
            mock_validation_result.issues = []
            mock_validation_result.warnings = []
            mock_validation_result.diagnostic_data = {}
            mock_validation_result.startup_diagnostics = {}
            
            mock_comprehensive_result = MagicMock()
            mock_comprehensive_result.valid = True
            mock_comprehensive_result.overall_status = "valid"
            mock_comprehensive_result.manifest_result = MagicMock()
            mock_comprehensive_result.manifest_result.valid = True
            mock_comprehensive_result.dependency_result = MagicMock()
            mock_comprehensive_result.dependency_result.valid = True
            mock_comprehensive_result.version_result = MagicMock()
            mock_comprehensive_result.version_result.compatible = True
            
            with patch('aiofiles.open', return_value=mock_aiofiles_open):
                with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_startup_validator:
                    mock_startup_validator.return_value.run_validation_orchestration = AsyncMock(return_value=mock_validation_result)
                    
                    with patch('custom_components.roost_scheduler.comprehensive_validator.ComprehensiveValidator') as mock_comprehensive_validator:
                        mock_comprehensive_validator.return_value.validate_all = AsyncMock(return_value=mock_comprehensive_result)
                        
                        # Mock all required services
                        with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage:
                            mock_storage_instance = AsyncMock()
                            if scenario["name"] == "corrupted_json":
                                mock_storage_instance.load_schedules = AsyncMock(side_effect=Exception("Corrupted data"))
                            else:
                                mock_storage_instance.load_schedules = AsyncMock()
                            mock_storage.return_value = mock_storage_instance
                            
                            with patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence:
                                mock_presence_instance = AsyncMock()
                                mock_presence_instance.load_configuration = AsyncMock()
                                mock_presence.return_value = mock_presence_instance
                                
                                with patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer:
                                    mock_buffer_instance = AsyncMock()
                                    mock_buffer_instance.load_configuration = AsyncMock()
                                    mock_buffer.return_value = mock_buffer_instance
                                    
                                    with patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule:
                                        mock_schedule_instance = AsyncMock()
                                        mock_schedule.return_value = mock_schedule_instance
                                        
                                        with patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend:
                                            mock_frontend_instance = AsyncMock()
                                            mock_frontend_instance.register_frontend_resources = AsyncMock(return_value={
                                                "success": True,
                                                "resources_registered": [],
                                                "resources_failed": [],
                                                "warnings": []
                                            })
                                            mock_frontend.return_value = mock_frontend_instance
                                            
                                            with patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard:
                                                mock_dashboard_instance = AsyncMock()
                                                mock_dashboard.return_value = mock_dashboard_instance
                                                
                                                # Run the test
                                                result = await async_setup_entry(mock_hass, mock_config_entry)
                                                
                                                # Verify expected outcome
                                                assert result == scenario["expected_success"], \
                                                    f"Scenario '{scenario['name']}' failed: expected {scenario['expected_success']}, got {result}"
    
    @pytest.mark.asyncio
    async def test_startup_performance_metrics(self, mock_hass, mock_config_entry):
        """Test that startup completes within reasonable time limits."""
        
        # Mock all services for fast startup
        mock_validation_result = MagicMock()
        mock_validation_result.success = True
        mock_validation_result.issues = []
        mock_validation_result.warnings = []
        mock_validation_result.diagnostic_data = {}
        mock_validation_result.startup_diagnostics = {}
        
        mock_comprehensive_result = MagicMock()
        mock_comprehensive_result.valid = True
        mock_comprehensive_result.overall_status = "valid"
        mock_comprehensive_result.manifest_result = MagicMock()
        mock_comprehensive_result.manifest_result.valid = True
        mock_comprehensive_result.dependency_result = MagicMock()
        mock_comprehensive_result.dependency_result.valid = True
        mock_comprehensive_result.version_result = MagicMock()
        mock_comprehensive_result.version_result.compatible = True
        
        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_startup_validator:
            mock_startup_validator.return_value.run_validation_orchestration = AsyncMock(return_value=mock_validation_result)
            
            with patch('custom_components.roost_scheduler.comprehensive_validator.ComprehensiveValidator') as mock_comprehensive_validator:
                mock_comprehensive_validator.return_value.validate_all = AsyncMock(return_value=mock_comprehensive_result)
                
                with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage:
                    mock_storage_instance = AsyncMock()
                    mock_storage_instance.load_schedules = AsyncMock()
                    mock_storage.return_value = mock_storage_instance
                    
                    with patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence:
                        mock_presence_instance = AsyncMock()
                        mock_presence_instance.load_configuration = AsyncMock()
                        mock_presence.return_value = mock_presence_instance
                        
                        with patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer:
                            mock_buffer_instance = AsyncMock()
                            mock_buffer_instance.load_configuration = AsyncMock()
                            mock_buffer.return_value = mock_buffer_instance
                            
                            with patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule:
                                mock_schedule_instance = AsyncMock()
                                mock_schedule.return_value = mock_schedule_instance
                                
                                with patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend:
                                    mock_frontend_instance = AsyncMock()
                                    mock_frontend_instance.register_frontend_resources = AsyncMock(return_value={
                                        "success": True,
                                        "resources_registered": [],
                                        "resources_failed": [],
                                        "warnings": []
                                    })
                                    mock_frontend.return_value = mock_frontend_instance
                                    
                                    with patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard:
                                        mock_dashboard_instance = AsyncMock()
                                        mock_dashboard.return_value = mock_dashboard_instance
                                        
                                        # Measure startup time
                                        start_time = datetime.now()
                                        result = await async_setup_entry(mock_hass, mock_config_entry)
                                        end_time = datetime.now()
                                        
                                        startup_duration = (end_time - start_time).total_seconds()
                                        
                                        # Verify setup succeeded
                                        assert result is True
                                        
                                        # Verify startup completed within reasonable time (5 seconds)
                                        assert startup_duration < 5.0, \
                                            f"Startup took too long: {startup_duration:.2f} seconds"
    
    @pytest.mark.asyncio
    async def test_concurrent_startup_safety(self, mock_hass):
        """Test that multiple concurrent startups don't cause issues."""
        
        # Create multiple config entries
        entries = []
        for i in range(3):
            entry = MagicMock(spec=ConfigEntry)
            entry.entry_id = f"test_entry_{i}"
            entry.data = {"name": f"Test Scheduler {i}"}
            entry.options = {}
            entry.title = f"Test Roost Scheduler {i}"
            entries.append(entry)
        
        # Mock validation systems
        mock_validation_result = MagicMock()
        mock_validation_result.success = True
        mock_validation_result.issues = []
        mock_validation_result.warnings = []
        mock_validation_result.diagnostic_data = {}
        mock_validation_result.startup_diagnostics = {}
        
        mock_comprehensive_result = MagicMock()
        mock_comprehensive_result.valid = True
        mock_comprehensive_result.overall_status = "valid"
        mock_comprehensive_result.manifest_result = MagicMock()
        mock_comprehensive_result.manifest_result.valid = True
        mock_comprehensive_result.dependency_result = MagicMock()
        mock_comprehensive_result.dependency_result.valid = True
        mock_comprehensive_result.version_result = MagicMock()
        mock_comprehensive_result.version_result.compatible = True
        
        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_startup_validator:
            mock_startup_validator.return_value.run_validation_orchestration = AsyncMock(return_value=mock_validation_result)
            
            with patch('custom_components.roost_scheduler.comprehensive_validator.ComprehensiveValidator') as mock_comprehensive_validator:
                mock_comprehensive_validator.return_value.validate_all = AsyncMock(return_value=mock_comprehensive_result)
                
                with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage:
                    mock_storage_instance = AsyncMock()
                    mock_storage_instance.load_schedules = AsyncMock()
                    mock_storage.return_value = mock_storage_instance
                    
                    with patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence:
                        mock_presence_instance = AsyncMock()
                        mock_presence_instance.load_configuration = AsyncMock()
                        mock_presence.return_value = mock_presence_instance
                        
                        with patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer:
                            mock_buffer_instance = AsyncMock()
                            mock_buffer_instance.load_configuration = AsyncMock()
                            mock_buffer.return_value = mock_buffer_instance
                            
                            with patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule:
                                mock_schedule_instance = AsyncMock()
                                mock_schedule.return_value = mock_schedule_instance
                                
                                with patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend:
                                    mock_frontend_instance = AsyncMock()
                                    mock_frontend_instance.register_frontend_resources = AsyncMock(return_value={
                                        "success": True,
                                        "resources_registered": [],
                                        "resources_failed": [],
                                        "warnings": []
                                    })
                                    mock_frontend.return_value = mock_frontend_instance
                                    
                                    with patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard:
                                        mock_dashboard_instance = AsyncMock()
                                        mock_dashboard.return_value = mock_dashboard_instance
                                        
                                        # Run concurrent setups
                                        tasks = [async_setup_entry(mock_hass, entry) for entry in entries]
                                        results = await asyncio.gather(*tasks, return_exceptions=True)
                                        
                                        # Verify all setups succeeded
                                        for i, result in enumerate(results):
                                            if isinstance(result, Exception):
                                                pytest.fail(f"Entry {i} setup failed with exception: {result}")
                                            assert result is True, f"Entry {i} setup returned False"


if __name__ == "__main__":
    pytest.main([__file__])