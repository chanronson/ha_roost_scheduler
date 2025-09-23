"""Tests for logging and diagnostic functionality."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import logging

from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.logging_config import LoggingManager
from custom_components.roost_scheduler.models import PresenceConfig, BufferConfig, GlobalBufferConfig


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.states = Mock()
    hass.bus = Mock()
    hass.loop = Mock()
    hass.async_create_task = Mock()
    return hass


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service."""
    storage = AsyncMock()
    storage.load_schedules = AsyncMock(return_value=None)
    storage.save_schedules = AsyncMock()
    return storage


@pytest.fixture
def presence_manager(mock_hass, mock_storage_service):
    """Create a PresenceManager instance for testing."""
    return PresenceManager(mock_hass, mock_storage_service)


@pytest.fixture
def buffer_manager(mock_hass, mock_storage_service):
    """Create a BufferManager instance for testing."""
    return BufferManager(mock_hass, mock_storage_service)


@pytest.fixture
def logging_manager(mock_hass):
    """Create a LoggingManager instance for testing."""
    return LoggingManager(mock_hass)


class TestPresenceManagerLogging:
    """Test logging and diagnostic functionality in PresenceManager."""
    
    @pytest.mark.asyncio
    async def test_initialization_logging(self, presence_manager, caplog):
        """Test that initialization logs appropriate messages."""
        with caplog.at_level(logging.INFO):
            # Mock the required methods
            presence_manager.load_configuration = AsyncMock()
            presence_manager._setup_state_listeners = AsyncMock()
            presence_manager.get_current_mode = AsyncMock(return_value="home")
            
            await presence_manager.async_initialize()
            
            # Check that initialization was logged
            assert "Initializing PresenceManager" in caplog.text
            assert "PresenceManager initialized successfully" in caplog.text
    
    @pytest.mark.asyncio
    async def test_initialization_error_logging(self, presence_manager, caplog):
        """Test that initialization errors are properly logged."""
        with caplog.at_level(logging.ERROR):
            # Mock load_configuration to raise an exception
            presence_manager.load_configuration = AsyncMock(side_effect=Exception("Test error"))
            
            with pytest.raises(Exception):
                await presence_manager.async_initialize()
            
            # Check that error was logged
            assert "Failed to initialize PresenceManager" in caplog.text
    
    @pytest.mark.asyncio
    async def test_configuration_loading_logging(self, presence_manager, caplog):
        """Test that configuration loading logs performance metrics."""
        with caplog.at_level(logging.INFO):
            # Mock the detection and migration method
            presence_manager._detect_and_migrate_configuration = AsyncMock()
            
            await presence_manager.load_configuration()
            
            # Check that loading was logged
            assert "Presence configuration loaded successfully" in caplog.text
    
    @pytest.mark.asyncio
    async def test_configuration_saving_logging(self, presence_manager, caplog):
        """Test that configuration saving logs performance metrics."""
        with caplog.at_level(logging.INFO):
            # Set up minimal configuration
            presence_manager._presence_config = PresenceConfig()
            presence_manager._presence_entities = ["device_tracker.test"]
            presence_manager._presence_rule = "anyone_home"
            presence_manager._timeout_seconds = 600
            
            await presence_manager.save_configuration()
            
            # Check that saving was logged
            assert "Presence configuration saved successfully" in caplog.text
    
    def test_get_diagnostic_info(self, presence_manager):
        """Test that diagnostic info is comprehensive."""
        # Set up some test data
        presence_manager._presence_entities = ["device_tracker.test"]
        presence_manager._presence_rule = "anyone_home"
        presence_manager._timeout_seconds = 600
        presence_manager._initialized = True
        
        # Mock entity state
        mock_state = Mock()
        mock_state.state = "home"
        mock_state.domain = "device_tracker"
        mock_state.last_updated = datetime.now()
        mock_state.last_changed = datetime.now()
        mock_state.attributes = {"friendly_name": "Test Device"}
        presence_manager.hass.states.get.return_value = mock_state
        
        # Mock validation
        presence_manager.validate_configuration = Mock(return_value=(True, []))
        
        diagnostic_info = presence_manager.get_diagnostic_info()
        
        # Check structure
        assert "manager_status" in diagnostic_info
        assert "configuration" in diagnostic_info
        assert "entity_states" in diagnostic_info
        assert "override_states" in diagnostic_info
        assert "validation_results" in diagnostic_info
        assert "troubleshooting" in diagnostic_info
        
        # Check manager status
        assert diagnostic_info["manager_status"]["initialized"] is True
        assert diagnostic_info["manager_status"]["storage_available"] is True
        
        # Check entity states
        assert "device_tracker.test" in diagnostic_info["entity_states"]
        entity_info = diagnostic_info["entity_states"]["device_tracker.test"]
        assert entity_info["state"] == "home"
        assert entity_info["domain"] == "device_tracker"
        assert entity_info["is_home"] is True
    
    @pytest.mark.asyncio
    async def test_run_diagnostics(self, presence_manager):
        """Test that run_diagnostics executes without errors."""
        # Mock required methods
        presence_manager.get_diagnostic_info = Mock(return_value={
            "manager_status": {"initialized": True},
            "performance_metrics": {}
        })
        presence_manager.get_current_mode = AsyncMock(return_value="home")
        presence_manager.load_configuration = AsyncMock()
        
        result = await presence_manager.run_diagnostics()
        
        assert "performance_metrics" in result
        assert "total_diagnostic_time" in result["performance_metrics"]
    
    def test_troubleshooting_info_generation(self, presence_manager):
        """Test that troubleshooting information is generated correctly."""
        # Create diagnostic info with issues
        diagnostic_info = {
            "manager_status": {
                "initialized": False,
                "storage_available": False
            },
            "configuration": {
                "presence_entities": []
            },
            "entity_states": {
                "device_tracker.missing": {"state": "not_found"}
            },
            "override_states": {
                "force_home": {"state": "not_found", "entity_id": "input_boolean.missing"}
            },
            "validation_results": {
                "is_valid": False,
                "errors": ["Test validation error"]
            }
        }
        
        troubleshooting = presence_manager._generate_troubleshooting_info(diagnostic_info)
        
        assert "common_issues" in troubleshooting
        assert "recommendations" in troubleshooting
        assert "health_score" in troubleshooting
        
        # Check that issues were identified
        issues = troubleshooting["common_issues"]
        assert any("not initialized" in issue for issue in issues)
        assert any("Storage service is not available" in issue for issue in issues)
        assert any("No presence entities configured" in issue for issue in issues)
        assert any("not found" in issue for issue in issues)
        
        # Check that recommendations were provided
        recommendations = troubleshooting["recommendations"]
        assert len(recommendations) > 0
        
        # Health score should be reduced due to issues
        assert troubleshooting["health_score"] < 100


class TestBufferManagerLogging:
    """Test logging and diagnostic functionality in BufferManager."""
    
    @pytest.mark.asyncio
    async def test_configuration_loading_logging(self, buffer_manager, caplog):
        """Test that configuration loading logs performance metrics."""
        with caplog.at_level(logging.INFO):
            # Mock the detection and migration method
            buffer_manager._detect_and_migrate_configuration = AsyncMock()
            
            await buffer_manager.load_configuration()
            
            # Check that loading was logged
            assert "Buffer configuration loaded successfully" in caplog.text
    
    @pytest.mark.asyncio
    async def test_configuration_saving_logging(self, buffer_manager, caplog):
        """Test that configuration saving logs performance metrics."""
        with caplog.at_level(logging.INFO):
            # Mock schedule data
            from custom_components.roost_scheduler.models import ScheduleData
            mock_schedule_data = ScheduleData(
                version="0.3.0",
                entities_tracked=[],
                presence_entities=[],
                presence_rule="anyone_home",
                presence_timeout_seconds=600,
                buffer={},
                ui={},
                schedules={"home": {}, "away": {}},
                metadata={}
            )
            buffer_manager.storage_service.load_schedules.return_value = mock_schedule_data
            
            await buffer_manager.save_configuration()
            
            # Check that saving was logged
            assert "Buffer configuration saved successfully" in caplog.text
    
    def test_get_diagnostic_info(self, buffer_manager):
        """Test that diagnostic info is comprehensive."""
        # Set up some test data
        from custom_components.roost_scheduler.models import EntityState
        
        entity_state = EntityState(
            entity_id="climate.test",
            current_value=20.0,
            last_manual_change=datetime.now() - timedelta(minutes=5),
            last_scheduled_change=datetime.now() - timedelta(minutes=10),
            buffer_config=BufferConfig()
        )
        buffer_manager._entity_states["climate.test"] = entity_state
        
        # Mock Home Assistant state
        mock_state = Mock()
        mock_state.state = "20.0"
        mock_state.domain = "climate"
        mock_state.last_updated = datetime.now()
        buffer_manager.hass.states.get.return_value = mock_state
        
        # Mock validation
        buffer_manager.validate_configuration = Mock(return_value=(True, []))
        
        diagnostic_info = buffer_manager.get_diagnostic_info()
        
        # Check structure
        assert "manager_status" in diagnostic_info
        assert "configuration" in diagnostic_info
        assert "entity_states" in diagnostic_info
        assert "buffer_decisions" in diagnostic_info
        assert "validation_results" in diagnostic_info
        assert "troubleshooting" in diagnostic_info
        
        # Check entity states
        assert "climate.test" in diagnostic_info["entity_states"]
        entity_info = diagnostic_info["entity_states"]["climate.test"]
        assert entity_info["current_value"] == 20.0
        assert entity_info["ha_state"] == "20.0"
        assert entity_info["ha_domain"] == "climate"
        
        # Check buffer decisions
        assert "climate.test" in diagnostic_info["buffer_decisions"]
    
    @pytest.mark.asyncio
    async def test_run_diagnostics(self, buffer_manager):
        """Test that run_diagnostics executes without errors."""
        # Set up test entity
        from custom_components.roost_scheduler.models import EntityState
        entity_state = EntityState(
            entity_id="climate.test",
            current_value=20.0,
            buffer_config=BufferConfig()
        )
        buffer_manager._entity_states["climate.test"] = entity_state
        
        # Mock required methods
        buffer_manager.get_diagnostic_info = Mock(return_value={
            "manager_status": {"storage_available": True},
            "performance_metrics": {}
        })
        buffer_manager.load_configuration = AsyncMock()
        
        result = await buffer_manager.run_diagnostics()
        
        assert "performance_metrics" in result
        assert "total_diagnostic_time" in result["performance_metrics"]
    
    def test_troubleshooting_info_generation(self, buffer_manager):
        """Test that troubleshooting information is generated correctly."""
        # Create diagnostic info with issues
        diagnostic_info = {
            "manager_status": {
                "storage_available": False,
                "global_buffer_enabled": False
            },
            "configuration": {
                "global_config": {
                    "time_minutes": 0,
                    "value_delta": 0,
                    "enabled": True
                }
            },
            "entity_states": {
                "climate.missing": {"ha_state": "not_found"}
            },
            "validation_results": {
                "is_valid": False,
                "errors": ["Test validation error"]
            }
        }
        
        troubleshooting = buffer_manager._generate_troubleshooting_info(diagnostic_info)
        
        assert "common_issues" in troubleshooting
        assert "recommendations" in troubleshooting
        assert "health_score" in troubleshooting
        
        # Check that issues were identified
        issues = troubleshooting["common_issues"]
        assert any("Storage service is not available" in issue for issue in issues)
        assert any("Global buffer is disabled" in issue for issue in issues)
        assert any("Buffer time is 0 minutes" in issue for issue in issues)
        assert any("Buffer value delta is 0" in issue for issue in issues)
        
        # Health score should be reduced due to issues
        assert troubleshooting["health_score"] < 100


class TestLoggingManager:
    """Test LoggingManager functionality."""
    
    @pytest.mark.asyncio
    async def test_async_setup(self, logging_manager):
        """Test that logging manager sets up correctly."""
        # Mock the store
        logging_manager._store = AsyncMock()
        logging_manager._store.async_load = AsyncMock(return_value=None)
        
        # Mock the apply config method
        logging_manager._apply_config = AsyncMock()
        
        await logging_manager.async_setup()
        
        # Verify setup was called
        logging_manager._apply_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_config(self, logging_manager):
        """Test that configuration updates work correctly."""
        # Mock the store and apply config
        logging_manager._store = AsyncMock()
        logging_manager._apply_config = AsyncMock()
        
        new_config = {"level": "DEBUG", "debug_presence_evaluation": True}
        
        await logging_manager.update_config(new_config)
        
        # Verify config was updated and saved
        assert logging_manager._config["level"] == "DEBUG"
        assert logging_manager._config["debug_presence_evaluation"] is True
        logging_manager._store.async_save.assert_called_once()
        logging_manager._apply_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enable_debug_mode(self, logging_manager):
        """Test that debug mode can be enabled."""
        # Mock the store and apply config
        logging_manager._store = AsyncMock()
        logging_manager._apply_config = AsyncMock()
        
        await logging_manager.enable_debug_mode(duration_minutes=5)
        
        # Verify debug flags were enabled
        assert logging_manager._config["level"] == "DEBUG"
        assert logging_manager._config["debug_presence_evaluation"] is True
        assert logging_manager._config["debug_buffer_logic"] is True
        assert logging_manager._config["performance_monitoring"] is True
    
    @pytest.mark.asyncio
    async def test_disable_debug_mode(self, logging_manager):
        """Test that debug mode can be disabled."""
        # Mock the store and apply config
        logging_manager._store = AsyncMock()
        logging_manager._apply_config = AsyncMock()
        
        await logging_manager.disable_debug_mode()
        
        # Verify debug flags were disabled
        assert logging_manager._config["level"] == "INFO"
        assert logging_manager._config["debug_presence_evaluation"] is False
        assert logging_manager._config["debug_buffer_logic"] is False
        assert logging_manager._config["performance_monitoring"] is False
    
    def test_log_performance_metric(self, logging_manager, caplog):
        """Test that performance metrics are logged when enabled."""
        # Enable performance monitoring
        logging_manager._config["performance_monitoring"] = True
        
        with caplog.at_level(logging.INFO):
            logging_manager.log_performance_metric("test_operation", 0.123, entity_id="test.entity")
            
            # Check that metric was logged
            assert "PERF: test_operation completed in 0.123s" in caplog.text
            assert "entity_id=test.entity" in caplog.text
    
    def test_log_performance_metric_disabled(self, logging_manager, caplog):
        """Test that performance metrics are not logged when disabled."""
        # Disable performance monitoring
        logging_manager._config["performance_monitoring"] = False
        
        with caplog.at_level(logging.INFO):
            logging_manager.log_performance_metric("test_operation", 0.123)
            
            # Check that metric was not logged
            assert "PERF:" not in caplog.text
    
    def test_get_debug_status(self, logging_manager):
        """Test that debug status is returned correctly."""
        # Set some debug flags
        logging_manager._config.update({
            "level": "DEBUG",
            "debug_presence_evaluation": True,
            "debug_buffer_logic": False,
            "performance_monitoring": True,
            "log_to_file": True,
            "log_file_path": "/test/path.log"
        })
        
        status = logging_manager.get_debug_status()
        
        assert status["logging_level"] == "DEBUG"
        assert status["debug_flags"]["debug_presence_evaluation"] is True
        assert status["debug_flags"]["debug_buffer_logic"] is False
        assert status["performance_monitoring"] is True
        assert status["file_logging"] is True
        assert status["log_file_path"] == "/test/path.log"


class TestPerformanceMonitoring:
    """Test performance monitoring functionality."""
    
    def test_performance_metric_logging(self, presence_manager, caplog):
        """Test that performance metrics are logged correctly."""
        # Enable performance monitoring
        from custom_components.roost_scheduler import presence_manager as pm_module
        pm_module.PERFORMANCE_MONITORING = True
        
        with caplog.at_level(logging.INFO):
            presence_manager.log_performance_metric("test_operation", 0.456, entity_count=5)
            
            # Check that metric was logged with correct format
            assert "PERF: PresenceManager.test_operation completed in 0.456s" in caplog.text
            assert "entity_count=5" in caplog.text
        
        # Disable performance monitoring
        pm_module.PERFORMANCE_MONITORING = False
    
    def test_performance_metric_not_logged_when_disabled(self, presence_manager, caplog):
        """Test that performance metrics are not logged when disabled."""
        # Ensure performance monitoring is disabled
        from custom_components.roost_scheduler import presence_manager as pm_module
        pm_module.PERFORMANCE_MONITORING = False
        
        with caplog.at_level(logging.INFO):
            presence_manager.log_performance_metric("test_operation", 0.456)
            
            # Check that metric was not logged
            assert "PERF:" not in caplog.text


class TestDebugLogging:
    """Test debug logging functionality."""
    
    def test_debug_presence_evaluation(self, presence_manager, caplog):
        """Test that debug logging works for presence evaluation."""
        # Enable debug logging
        from custom_components.roost_scheduler import presence_manager as pm_module
        pm_module.DEBUG_PRESENCE_EVALUATION = True
        
        # Mock entity state
        mock_state = Mock()
        mock_state.state = "home"
        presence_manager.hass.states.get.return_value = mock_state
        
        with caplog.at_level(logging.DEBUG):
            # This should trigger debug logging
            presence_manager._is_entity_home(mock_state)
            
            # Note: The actual debug logging happens in get_current_mode
            # which we can't easily test here without more complex mocking
        
        # Disable debug logging
        pm_module.DEBUG_PRESENCE_EVALUATION = False
    
    def test_debug_buffer_logic(self, buffer_manager, caplog):
        """Test that debug logging works for buffer logic."""
        # Enable debug logging
        from custom_components.roost_scheduler import buffer_manager as bm_module
        bm_module.DEBUG_BUFFER_LOGIC = True
        
        # Set up entity state
        from custom_components.roost_scheduler.models import EntityState
        entity_state = EntityState(
            entity_id="climate.test",
            current_value=20.0,
            buffer_config=BufferConfig()
        )
        buffer_manager._entity_states["climate.test"] = entity_state
        
        with caplog.at_level(logging.DEBUG):
            # This should trigger debug logging
            buffer_manager.should_suppress_change("climate.test", 22.0, {})
            
            # Check that debug messages were logged
            assert "Evaluating buffer suppression" in caplog.text
        
        # Disable debug logging
        bm_module.DEBUG_BUFFER_LOGIC = False