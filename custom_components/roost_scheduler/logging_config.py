"""Logging configuration and debugging support for Roost Scheduler."""
from __future__ import annotations

import logging
import os
from typing import Dict, Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Default logging configuration
DEFAULT_LOG_CONFIG = {
    "level": "INFO",
    "debug_schedule_evaluation": False,
    "debug_buffer_decisions": False,
    "debug_service_calls": False,
    "debug_presence_evaluation": False,
    "debug_entity_states": False,
    "debug_buffer_logic": False,
    "debug_manual_changes": False,
    "debug_websocket_events": False,
    "debug_storage_operations": False,
    "debug_config_flow_registration": False,
    "debug_validation_checks": False,
    "debug_diagnostic_collection": False,
    "debug_integration_setup": False,
    "performance_monitoring": False,
    "log_to_file": False,
    "log_file_path": "/config/roost_scheduler.log",
    "max_log_file_size_mb": 10,
    "log_retention_days": 7,
    "config_flow_logging_enabled": True,
    "detailed_error_reporting": True
}


class LoggingManager:
    """Manages logging configuration and debugging features."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the logging manager."""
        self.hass = hass
        self._config = DEFAULT_LOG_CONFIG.copy()
        self._store = Store(hass, 1, f"{DOMAIN}_logging_config")
        self._file_handler: Optional[logging.FileHandler] = None
        
    async def async_setup(self) -> None:
        """Set up logging configuration."""
        # Load saved configuration
        saved_config = await self._store.async_load()
        if saved_config:
            self._config.update(saved_config)
        
        # Apply configuration
        await self._apply_config()
        
        _LOGGER.info("Logging manager initialized with level: %s", self._config["level"])
    
    async def _apply_config(self) -> None:
        """Apply the current logging configuration."""
        # Set logging level
        logger = logging.getLogger(f"custom_components.{DOMAIN}")
        level = getattr(logging, self._config["level"].upper(), logging.INFO)
        logger.setLevel(level)
        
        # Configure file logging if enabled
        if self._config["log_to_file"]:
            await self._setup_file_logging()
        else:
            await self._cleanup_file_logging()
        
        # Set debug flags in modules
        self._set_debug_flags()
        
        # Log configuration summary
        enabled_debug = [k for k, v in self._config.items() if k.startswith("debug_") and v]
        if enabled_debug:
            _LOGGER.info("Debug logging enabled for: %s", ", ".join(enabled_debug))
    
    def _set_debug_flags(self) -> None:
        """Set debug flags in relevant modules."""
        try:
            # Import modules and set debug flags
            from . import schedule_manager
            from . import presence_manager
            from . import buffer_manager
            from . import storage
            
            schedule_manager.DEBUG_SCHEDULE_EVALUATION = self._config["debug_schedule_evaluation"]
            schedule_manager.DEBUG_BUFFER_DECISIONS = self._config["debug_buffer_decisions"]
            schedule_manager.DEBUG_SERVICE_CALLS = self._config["debug_service_calls"]
            
            presence_manager.DEBUG_PRESENCE_EVALUATION = self._config["debug_presence_evaluation"]
            presence_manager.DEBUG_ENTITY_STATES = self._config["debug_entity_states"]
            
            buffer_manager.DEBUG_BUFFER_LOGIC = self._config["debug_buffer_logic"]
            buffer_manager.DEBUG_MANUAL_CHANGES = self._config["debug_manual_changes"]
            
            if hasattr(storage, 'DEBUG_STORAGE_OPERATIONS'):
                storage.DEBUG_STORAGE_OPERATIONS = self._config["debug_storage_operations"]
            
            # Set config flow debug flags
            try:
                from . import config_flow_validator
                from . import integration_diagnostics
                
                if hasattr(config_flow_validator, 'DEBUG_CONFIG_FLOW_REGISTRATION'):
                    config_flow_validator.DEBUG_CONFIG_FLOW_REGISTRATION = self._config["debug_config_flow_registration"]
                
                if hasattr(integration_diagnostics, 'DEBUG_DIAGNOSTIC_COLLECTION'):
                    integration_diagnostics.DEBUG_DIAGNOSTIC_COLLECTION = self._config["debug_diagnostic_collection"]
                    
            except ImportError:
                pass  # Config flow modules may not be available yet
                
        except ImportError as e:
            _LOGGER.warning("Could not set debug flags: %s", e)
    
    async def _setup_file_logging(self) -> None:
        """Set up file logging handler."""
        try:
            log_file = self._config["log_file_path"]
            max_size = self._config["max_log_file_size_mb"] * 1024 * 1024
            
            # Create rotating file handler
            from logging.handlers import RotatingFileHandler
            
            if self._file_handler:
                await self._cleanup_file_logging()
            
            self._file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=self._config["log_retention_days"]
            )
            
            # Set formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            self._file_handler.setFormatter(formatter)
            
            # Add to logger
            logger = logging.getLogger(f"custom_components.{DOMAIN}")
            logger.addHandler(self._file_handler)
            
            _LOGGER.info("File logging enabled: %s", log_file)
            
        except Exception as e:
            _LOGGER.error("Failed to set up file logging: %s", e)
    
    async def _cleanup_file_logging(self) -> None:
        """Clean up file logging handler."""
        if self._file_handler:
            logger = logging.getLogger(f"custom_components.{DOMAIN}")
            logger.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None
    
    async def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update logging configuration."""
        self._config.update(new_config)
        await self._store.async_save(self._config)
        await self._apply_config()
        
        _LOGGER.info("Logging configuration updated")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current logging configuration."""
        return self._config.copy()
    
    async def enable_debug_mode(self, duration_minutes: int = 30) -> None:
        """Enable comprehensive debug mode for a limited time."""
        debug_config = {
            "level": "DEBUG",
            "debug_schedule_evaluation": True,
            "debug_buffer_decisions": True,
            "debug_service_calls": True,
            "debug_presence_evaluation": True,
            "debug_entity_states": True,
            "debug_buffer_logic": True,
            "debug_manual_changes": True,
            "debug_websocket_events": True,
            "debug_storage_operations": True,
            "debug_config_flow_registration": True,
            "debug_validation_checks": True,
            "debug_diagnostic_collection": True,
            "debug_integration_setup": True,
            "performance_monitoring": True,
            "detailed_error_reporting": True
        }
        
        await self.update_config(debug_config)
        
        # Schedule automatic disable
        async def disable_debug():
            await self.disable_debug_mode()
        
        self.hass.loop.call_later(duration_minutes * 60, lambda: self.hass.async_create_task(disable_debug()))
        
        _LOGGER.warning("Debug mode enabled for %d minutes - this will generate extensive logs", duration_minutes)
    
    async def disable_debug_mode(self) -> None:
        """Disable debug mode and return to normal logging."""
        normal_config = {
            "level": "INFO",
            "debug_schedule_evaluation": False,
            "debug_buffer_decisions": False,
            "debug_service_calls": False,
            "debug_presence_evaluation": False,
            "debug_entity_states": False,
            "debug_buffer_logic": False,
            "debug_manual_changes": False,
            "debug_websocket_events": False,
            "debug_storage_operations": False,
            "debug_config_flow_registration": False,
            "debug_validation_checks": False,
            "debug_diagnostic_collection": False,
            "debug_integration_setup": False,
            "performance_monitoring": False,
            "detailed_error_reporting": True  # Keep this enabled for troubleshooting
        }
        
        await self.update_config(normal_config)
        _LOGGER.info("Debug mode disabled, returned to normal logging")
    
    def log_performance_metric(self, operation: str, duration_seconds: float, 
                             entity_id: Optional[str] = None, **kwargs) -> None:
        """Log performance metrics if monitoring is enabled."""
        if not self._config["performance_monitoring"]:
            return
        
        extra_info = ""
        if entity_id:
            extra_info += f" entity={entity_id}"
        
        for key, value in kwargs.items():
            extra_info += f" {key}={value}"
        
        _LOGGER.info("PERF: %s completed in %.3fs%s", operation, duration_seconds, extra_info)
    
    def get_debug_status(self) -> Dict[str, Any]:
        """Get current debug status for diagnostics."""
        return {
            "logging_level": self._config["level"],
            "debug_flags": {k: v for k, v in self._config.items() if k.startswith("debug_")},
            "file_logging": self._config["log_to_file"],
            "performance_monitoring": self._config["performance_monitoring"],
            "config_flow_logging_enabled": self._config["config_flow_logging_enabled"],
            "detailed_error_reporting": self._config["detailed_error_reporting"],
            "log_file_path": self._config["log_file_path"] if self._config["log_to_file"] else None
        }
    
    async def enable_config_flow_debug(self) -> None:
        """Enable detailed config flow debugging."""
        config_flow_debug = {
            "debug_config_flow_registration": True,
            "debug_validation_checks": True,
            "debug_diagnostic_collection": True,
            "debug_integration_setup": True,
            "detailed_error_reporting": True,
            "config_flow_logging_enabled": True
        }
        
        await self.update_config(config_flow_debug)
        _LOGGER.info("Config flow debug logging enabled")
    
    async def disable_config_flow_debug(self) -> None:
        """Disable config flow debugging."""
        config_flow_debug = {
            "debug_config_flow_registration": False,
            "debug_validation_checks": False,
            "debug_diagnostic_collection": False,
            "debug_integration_setup": False
        }
        
        await self.update_config(config_flow_debug)
        _LOGGER.info("Config flow debug logging disabled")
    
    def log_config_flow_event(self, event_type: str, message: str, **kwargs) -> None:
        """Log config flow events if debugging is enabled."""
        if not self._config.get("debug_config_flow_registration", False):
            return
        
        extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} ({extra_info})"
        
        _LOGGER.debug("CONFIG_FLOW[%s]: %s", event_type, message)
    
    def log_validation_event(self, validation_type: str, message: str, **kwargs) -> None:
        """Log validation events if debugging is enabled."""
        if not self._config.get("debug_validation_checks", False):
            return
        
        extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} ({extra_info})"
        
        _LOGGER.debug("VALIDATION[%s]: %s", validation_type, message)
    
    def log_diagnostic_event(self, diagnostic_type: str, message: str, **kwargs) -> None:
        """Log diagnostic events if debugging is enabled."""
        if not self._config.get("debug_diagnostic_collection", False):
            return
        
        extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} ({extra_info})"
        
        _LOGGER.debug("DIAGNOSTIC[%s]: %s", diagnostic_type, message)
    
    def log_setup_event(self, setup_phase: str, message: str, **kwargs) -> None:
        """Log integration setup events if debugging is enabled."""
        if not self._config.get("debug_integration_setup", False):
            return
        
        extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        if extra_info:
            message = f"{message} ({extra_info})"
        
        _LOGGER.debug("SETUP[%s]: %s", setup_phase, message)


def setup_environment_debug() -> None:
    """Set up debug logging based on environment variables."""
    # Check for environment variables to enable debug logging
    debug_vars = {
        "ROOST_DEBUG_SCHEDULE": "debug_schedule_evaluation",
        "ROOST_DEBUG_BUFFER": "debug_buffer_decisions", 
        "ROOST_DEBUG_PRESENCE": "debug_presence_evaluation",
        "ROOST_DEBUG_CONFIG_FLOW": "debug_config_flow_registration",
        "ROOST_DEBUG_VALIDATION": "debug_validation_checks",
        "ROOST_DEBUG_DIAGNOSTICS": "debug_diagnostic_collection",
        "ROOST_DEBUG_SETUP": "debug_integration_setup",
        "ROOST_DEBUG_ALL": "all"
    }
    
    for env_var, debug_flag in debug_vars.items():
        if os.getenv(env_var):
            _LOGGER.warning("Environment debug enabled: %s", debug_flag)
            
            if debug_flag == "all":
                # Enable all debug flags
                from . import schedule_manager, presence_manager, buffer_manager
                schedule_manager.DEBUG_SCHEDULE_EVALUATION = True
                schedule_manager.DEBUG_BUFFER_DECISIONS = True
                schedule_manager.DEBUG_SERVICE_CALLS = True
                presence_manager.DEBUG_PRESENCE_EVALUATION = True
                presence_manager.DEBUG_ENTITY_STATES = True
                buffer_manager.DEBUG_BUFFER_LOGIC = True
                buffer_manager.DEBUG_MANUAL_CHANGES = True
                
                # Enable config flow debug flags
                try:
                    from . import config_flow_validator, integration_diagnostics
                    if hasattr(config_flow_validator, 'DEBUG_CONFIG_FLOW_REGISTRATION'):
                        config_flow_validator.DEBUG_CONFIG_FLOW_REGISTRATION = True
                    if hasattr(integration_diagnostics, 'DEBUG_DIAGNOSTIC_COLLECTION'):
                        integration_diagnostics.DEBUG_DIAGNOSTIC_COLLECTION = True
                except ImportError:
                    pass
            else:
                # Enable specific debug flag
                try:
                    if "schedule" in debug_flag:
                        from . import schedule_manager
                        setattr(schedule_manager, debug_flag.upper(), True)
                    elif "buffer" in debug_flag:
                        from . import buffer_manager
                        setattr(buffer_manager, debug_flag.upper(), True)
                    elif "presence" in debug_flag:
                        from . import presence_manager
                        setattr(presence_manager, debug_flag.upper(), True)
                    elif "config_flow" in debug_flag:
                        from . import config_flow_validator
                        setattr(config_flow_validator, debug_flag.upper(), True)
                    elif "diagnostic" in debug_flag:
                        from . import integration_diagnostics
                        setattr(integration_diagnostics, debug_flag.upper(), True)
                except ImportError:
                    pass


# Initialize environment debug on module load
setup_environment_debug()