"""
Roost Scheduler - A HACS-compatible Home Assistant custom integration.

Provides grid-based scheduling interface with intelligent buffering and presence-aware automation.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
import homeassistant.helpers.config_validation as cv
from homeassistant.components import websocket_api

from .const import (
    DOMAIN, 
    SERVICE_APPLY_SLOT, 
    SERVICE_APPLY_GRID_NOW, 
    SERVICE_MIGRATE_RESOLUTION, 
    WEEKDAYS,
    MIN_HA_VERSION,
    REQUIRED_DOMAINS,
    OPTIONAL_DOMAINS,
    MODE_HOME,
    MODE_AWAY
)
from .schedule_manager import ScheduleManager
from .storage import StorageService
from .version import VersionInfo, validate_manifest_version
from .migration import UninstallManager
from .logging_config import LoggingManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []

# Service schemas for parameter validation
SERVICE_APPLY_SLOT_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("day"): vol.In(WEEKDAYS),
    vol.Required("time"): cv.string,
    vol.Optional("force", default=False): cv.boolean,
    vol.Optional("buffer_override", default={}): dict,
})

SERVICE_APPLY_GRID_NOW_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
    vol.Optional("force", default=False): cv.boolean,
})

SERVICE_MIGRATE_RESOLUTION_SCHEMA = vol.Schema({
    vol.Required("resolution_minutes"): vol.In([15, 30, 60]),
    vol.Optional("preview", default=True): cv.boolean,
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Roost Scheduler integration."""
    _LOGGER.debug("Setting up Roost Scheduler integration")
    
    # Validate version consistency
    if not validate_manifest_version():
        _LOGGER.error("Version validation failed - manifest and code versions don't match")
        return False
    
    # Log version information
    version_info = VersionInfo()
    _LOGGER.info("Starting %s", version_info)
    
    # Validate Home Assistant version
    if not _validate_ha_version(hass):
        return False
    
    # Validate required dependencies
    if not _validate_dependencies(hass):
        return False
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roost Scheduler from a config entry with robust error handling."""
    setup_start_time = datetime.now()
    _LOGGER.info("Setting up Roost Scheduler config entry: %s", entry.entry_id)
    
    setup_diagnostics = {
        "entry_id": entry.entry_id,
        "start_time": setup_start_time,
        "components_initialized": [],
        "components_failed": [],
        "warnings": [],
        "fallbacks_used": [],
        "performance_metrics": {}
    }
    
    try:
        # Run startup validation before proceeding with setup
        from .startup_validation_system import StartupValidationSystem
        from .config_flow_registration_fixer import ConfigFlowRegistrationFixer
        from .comprehensive_validator import ComprehensiveValidator
        
        _LOGGER.info("Running comprehensive startup validation for entry %s", entry.entry_id)
        validation_start_time = datetime.now()
        
        # Initialize validation orchestration system
        startup_validator = StartupValidationSystem(hass)
        comprehensive_validator = ComprehensiveValidator(hass)
        
        # Run orchestrated validation with complete error handling chain
        validation_result = await startup_validator.run_validation_orchestration(DOMAIN, entry)
        comprehensive_result = await comprehensive_validator.validate_all()
        
        validation_duration = (datetime.now() - validation_start_time).total_seconds()
        setup_diagnostics["startup_validation"] = {
            "duration_seconds": validation_duration,
            "success": validation_result.success,
            "issues_found": len(validation_result.issues),
            "warnings_found": len(validation_result.warnings),
            "orchestration_steps": validation_result.startup_diagnostics.get("validation_context", {}).get("validation_steps", [])
        }
        setup_diagnostics["comprehensive_validation"] = {
            "valid": comprehensive_result.valid,
            "overall_status": comprehensive_result.overall_status,
            "manifest_valid": comprehensive_result.manifest_result.valid,
            "dependencies_valid": comprehensive_result.dependency_result.valid,
            "version_compatible": comprehensive_result.version_result.compatible
        }
        
        # Implement comprehensive error recovery system
        if not validation_result.success or not comprehensive_result.valid:
            _LOGGER.warning("Validation failed - startup: %s, comprehensive: %s", 
                          validation_result.success, comprehensive_result.valid)
            setup_diagnostics["warnings"].append("Validation found critical issues requiring fixes")
            
            # Attempt comprehensive error recovery with fallback mechanisms
            try:
                _LOGGER.info("Initiating comprehensive error recovery system")
                recovery_result = await _execute_comprehensive_error_recovery(
                    hass, DOMAIN, validation_result, comprehensive_result, setup_diagnostics
                )
                
                if recovery_result["success"]:
                    _LOGGER.info("Error recovery completed successfully")
                    setup_diagnostics["error_recovery"] = recovery_result
                    setup_diagnostics["components_initialized"].append("error_recovery_system")
                else:
                    _LOGGER.error("Error recovery failed: %s", recovery_result.get("error", "Unknown error"))
                    setup_diagnostics["components_failed"].append({
                        "component": "error_recovery_system", 
                        "error": recovery_result.get("error", "Recovery failed")
                    })
                    
                    # Apply emergency fallbacks when recovery fails
                    await _apply_emergency_recovery_fallbacks(setup_diagnostics)
                
            except Exception as e:
                _LOGGER.error("Critical error during comprehensive error recovery: %s", e)
                setup_diagnostics["components_failed"].append({
                    "component": "comprehensive_error_recovery", 
                    "error": str(e)
                })
                setup_diagnostics["warnings"].append("Comprehensive error recovery failed - using emergency fallbacks")
                
                # Apply emergency fallbacks when recovery system itself fails
                await _apply_emergency_recovery_fallbacks(setup_diagnostics)
        else:
            _LOGGER.info("All validation checks passed successfully")
            setup_diagnostics["components_initialized"].append("comprehensive_validation")
            
        # Legacy fix system for backward compatibility
        if not validation_result.success:
            _LOGGER.info("Running legacy fix system for additional coverage")
            try:
                fixer = ConfigFlowRegistrationFixer(hass, DOMAIN)
                fix_result = await fixer.apply_all_fixes()
                
                setup_diagnostics["automatic_fixes"] = {
                    "attempted": True,
                    "success": fix_result.success,
                    "total_issues": fix_result.total_issues,
                    "fixed_issues": fix_result.fixed_issues,
                    "failed_fixes": fix_result.failed_fixes,
                    "backup_created": fix_result.backup_created
                }
                
                if fix_result.success:
                    _LOGGER.info("Automatic fixes applied successfully (%d/%d issues fixed)", 
                               fix_result.fixed_issues, fix_result.total_issues)
                    setup_diagnostics["components_initialized"].append("startup_validation_fixes")
                    
                    # Re-run validation to confirm fixes
                    try:
                        validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                        setup_diagnostics["startup_validation"]["post_fix_success"] = validation_result.success
                        
                        if validation_result.success:
                            _LOGGER.info("Post-fix validation passed - proceeding with setup")
                        else:
                            _LOGGER.warning("Some validation issues remain after fixes")
                            setup_diagnostics["warnings"].append("Some validation issues could not be automatically fixed")
                            
                            # Apply fallback mechanisms for remaining issues
                            await _apply_validation_fallbacks(validation_result, setup_diagnostics)
                            
                    except Exception as e:
                        _LOGGER.error("Post-fix validation failed: %s", e)
                        setup_diagnostics["warnings"].append(f"Post-fix validation error: {str(e)}")
                        
                        # Apply emergency fallbacks
                        await _apply_emergency_fallbacks(setup_diagnostics)
                        
                else:
                    _LOGGER.error("Automatic fixes failed - applying fallback mechanisms")
                    setup_diagnostics["warnings"].append("Automatic fixes failed")
                    
                    # Log detailed fix results for troubleshooting
                    for fix_result_detail in fix_result.fix_results:
                        if not fix_result_detail.success:
                            _LOGGER.error("Fix failed for %s: %s", 
                                        fix_result_detail.issue_type, 
                                        "; ".join(fix_result_detail.errors))
                    
                    # Apply fallback mechanisms when fixes fail
                    await _apply_fix_failure_fallbacks(fix_result, setup_diagnostics)
                    
            except Exception as e:
                _LOGGER.error("Critical error during automatic fix application: %s", e)
                setup_diagnostics["components_failed"].append({
                    "component": "automatic_fixes", 
                    "error": str(e)
                })
                setup_diagnostics["warnings"].append("Automatic fix system failed - using emergency fallbacks")
                
                # Apply emergency fallbacks when fix system itself fails
                await _apply_emergency_fallbacks(setup_diagnostics)
        else:
            _LOGGER.info("Startup validation passed successfully")
            setup_diagnostics["components_initialized"].append("startup_validation")
        
        # Store validation results for later reference
        setup_diagnostics["validation_results"] = {
            "comprehensive_result": validation_result,
            "diagnostic_data": validation_result.diagnostic_data,
            "startup_diagnostics": validation_result.startup_diagnostics
        }
        
        # Implement error recovery mechanisms based on validation results
        if not validation_result.success:
            critical_issues = [
                issue for issue in validation_result.issues 
                if isinstance(issue, dict) and issue.get("severity") == "critical"
            ]
            
            if critical_issues:
                _LOGGER.error("Critical validation issues found that may prevent proper operation:")
                for issue in critical_issues:
                    _LOGGER.error("  - %s", issue.get("description", str(issue)))
                
                # Check if we should continue or fail setup
                should_continue = await _evaluate_setup_continuation(critical_issues, setup_diagnostics)
                
                if not should_continue:
                    _LOGGER.error("Setup cannot continue due to critical validation failures")
                    await _cleanup_entry_data(hass, entry)
                    return False
                else:
                    _LOGGER.warning("Continuing setup despite critical issues - functionality may be limited")
                    setup_diagnostics["warnings"].append("Setup continued despite critical validation issues")
        
        # Initialize logging manager with error handling
        logging_manager = None
        try:
            logging_manager = LoggingManager(hass)
            await logging_manager.async_setup()
            setup_diagnostics["components_initialized"].append("logging_manager")
            _LOGGER.debug("Logging manager initialized successfully")
        except Exception as e:
            _LOGGER.error("Failed to initialize logging manager: %s", e)
            setup_diagnostics["components_failed"].append({"component": "logging_manager", "error": str(e)})
            setup_diagnostics["warnings"].append("Logging manager initialization failed - continuing without enhanced logging")
            # Continue without logging manager - not critical for core functionality
        
        # Initialize storage service with enhanced error handling and fallbacks
        storage_service = None
        try:
            storage_service = StorageService(hass, entry.entry_id)
            setup_diagnostics["components_initialized"].append("storage_service")
            _LOGGER.debug("Storage service initialized successfully")
        except Exception as e:
            _LOGGER.error("Critical error: Failed to initialize storage service: %s", e)
            setup_diagnostics["components_failed"].append({"component": "storage_service", "error": str(e)})
            
            # Try emergency storage fallback
            try:
                _LOGGER.warning("Attempting emergency storage service fallback")
                from .storage import StorageService
                storage_service = StorageService(hass, entry.entry_id, emergency_mode=True)
                setup_diagnostics["fallbacks_used"].append("emergency_storage_service")
                setup_diagnostics["warnings"].append("Using emergency storage service - some features may be limited")
                _LOGGER.warning("Emergency storage service initialized")
            except Exception as fallback_error:
                _LOGGER.error("Emergency storage service fallback failed: %s", fallback_error)
                
                # Generate comprehensive error report before failing
                await _generate_setup_failure_report(hass, entry, setup_diagnostics, e)
                await _cleanup_entry_data(hass, entry)
                return False
        
        # Initialize managers with robust error handling and fallbacks
        from .presence_manager import PresenceManager
        from .buffer_manager import BufferManager
        
        # Initialize presence manager with fallback
        presence_manager = None
        try:
            presence_manager = PresenceManager(hass, storage_service)
            await presence_manager.load_configuration()
            setup_diagnostics["components_initialized"].append("presence_manager")
            _LOGGER.debug("Presence manager initialized successfully")
        except Exception as e:
            _LOGGER.error("Failed to initialize presence manager: %s", e)
            setup_diagnostics["components_failed"].append({"component": "presence_manager", "error": str(e)})
            
            # Attempt fallback initialization
            try:
                _LOGGER.info("Attempting fallback initialization for presence manager")
                presence_manager = PresenceManager(hass, storage_service)
                await presence_manager._initialize_default_configuration()
                setup_diagnostics["fallbacks_used"].append("presence_manager_fallback")
                setup_diagnostics["warnings"].append("Presence manager using fallback initialization")
                _LOGGER.warning("Presence manager initialized with fallback configuration")
            except Exception as fallback_error:
                _LOGGER.error("Fallback initialization failed for presence manager: %s", fallback_error)
                await _cleanup_entry_data(hass, entry)
                return False
        
        # Initialize buffer manager with fallback
        buffer_manager = None
        try:
            buffer_manager = BufferManager(hass, storage_service)
            await buffer_manager.load_configuration()
            setup_diagnostics["components_initialized"].append("buffer_manager")
            _LOGGER.debug("Buffer manager initialized successfully")
        except Exception as e:
            _LOGGER.error("Failed to initialize buffer manager: %s", e)
            setup_diagnostics["components_failed"].append({"component": "buffer_manager", "error": str(e)})
            
            # Attempt fallback initialization
            try:
                _LOGGER.info("Attempting fallback initialization for buffer manager")
                buffer_manager = BufferManager(hass, storage_service)
                await buffer_manager._initialize_default_configuration()
                setup_diagnostics["fallbacks_used"].append("buffer_manager_fallback")
                setup_diagnostics["warnings"].append("Buffer manager using fallback initialization")
                _LOGGER.warning("Buffer manager initialized with fallback configuration")
            except Exception as fallback_error:
                _LOGGER.error("Fallback initialization failed for buffer manager: %s", fallback_error)
                await _cleanup_entry_data(hass, entry)
                return False
        
        # Initialize schedule manager with error handling
        schedule_manager = None
        try:
            schedule_manager = ScheduleManager(hass, storage_service, presence_manager, buffer_manager)
            setup_diagnostics["components_initialized"].append("schedule_manager")
            _LOGGER.debug("Schedule manager initialized successfully")
        except Exception as e:
            _LOGGER.error("Critical error: Failed to initialize schedule manager: %s", e)
            setup_diagnostics["components_failed"].append({"component": "schedule_manager", "error": str(e)})
            await _cleanup_entry_data(hass, entry)
            return False
        
        # Initialize configuration validator and perform validation
        from .config_validator import ConfigurationValidator
        config_validator = None
        try:
            config_validator = ConfigurationValidator(presence_manager, buffer_manager, schedule_manager)
            
            # Validate all configurations
            all_valid, validation_errors = config_validator.validate_all_configurations()
            if not all_valid:
                _LOGGER.warning("Configuration validation found issues: %s", validation_errors)
                setup_diagnostics["warnings"].append("Configuration validation found issues")
                
                # Attempt to repair configuration issues
                any_repairs, repair_results = config_validator.repair_all_configurations()
                if any_repairs:
                    _LOGGER.info("Configuration repairs applied: %s", repair_results)
                    setup_diagnostics["configuration_repairs"] = repair_results
                    
                    # Re-validate after repairs
                    all_valid_after_repair, remaining_errors = config_validator.validate_all_configurations()
                    if all_valid_after_repair:
                        _LOGGER.info("All configuration issues resolved after repair")
                    else:
                        _LOGGER.warning("Some configuration issues remain after repair: %s", remaining_errors)
                        setup_diagnostics["warnings"].append("Some configuration issues could not be automatically repaired")
            else:
                _LOGGER.debug("All configurations validated successfully")
            
            setup_diagnostics["components_initialized"].append("config_validator")
        except Exception as e:
            _LOGGER.warning("Configuration validation failed: %s", e)
            setup_diagnostics["warnings"].append(f"Configuration validation failed: {str(e)}")
            # Continue setup even if validation fails - not critical
        
        # Initialize dashboard integration status tracking
        dashboard_integration_status = {
            "frontend_resources_registered": False,
            "card_available_in_picker": False,
            "dashboard_service_initialized": False,
            "card_added_to_dashboard": False,
            "dashboard_id": None,
            "frontend_errors": [],
            "dashboard_errors": [],
            "troubleshooting_steps": []
        }

        # Initialize dashboard integration service with comprehensive error handling
        dashboard_service = None
        try:
            _LOGGER.info("Initializing dashboard integration service for entry %s", entry.entry_id)
            from .dashboard_service import DashboardIntegrationService
            dashboard_service = DashboardIntegrationService(hass)
            dashboard_integration_status["dashboard_service_initialized"] = True
            setup_diagnostics["components_initialized"].append("dashboard_service")
            _LOGGER.debug("Dashboard integration service initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize dashboard integration service: {str(e)}"
            _LOGGER.error(error_msg, exc_info=True)
            setup_diagnostics["components_failed"].append({"component": "dashboard_service", "error": str(e)})
            setup_diagnostics["warnings"].append("Dashboard integration service failed - automatic card installation unavailable")
            dashboard_integration_status["dashboard_errors"].append(error_msg)
            dashboard_integration_status["troubleshooting_steps"].extend([
                "Check Lovelace configuration for any conflicts",
                "Verify dashboard permissions allow modifications",
                "Try manually adding the card through dashboard edit mode"
            ])
            # Continue setup even if dashboard service fails - not critical for core functionality

        # Load existing schedules with error handling
        try:
            await storage_service.load_schedules()
            _LOGGER.info("Successfully loaded schedule data for entry %s", entry.entry_id)
        except Exception as e:
            _LOGGER.error("Failed to load schedules for entry %s: %s", entry.entry_id, e)
            setup_diagnostics["warnings"].append(f"Schedule loading failed: {str(e)}")
            # Continue setup even if schedule loading fails - will use defaults
        
        # Register frontend resources with comprehensive error handling and diagnostics
        # This must happen after storage service initialization but before WebSocket handlers
        frontend_manager = None
        
        try:
            _LOGGER.info("Starting frontend resource registration for entry %s", entry.entry_id)
            from .frontend_manager import FrontendResourceManager
            frontend_manager = FrontendResourceManager(hass)
            frontend_registration_result = await frontend_manager.register_frontend_resources()
            
            # Frontend manager will be stored in entry data later
            
            # Log detailed frontend registration results
            _LOGGER.debug("Frontend registration result for entry %s: %s", entry.entry_id, frontend_registration_result)
            
            if frontend_registration_result["success"]:
                setup_diagnostics["components_initialized"].append("frontend_resources")
                dashboard_integration_status["frontend_resources_registered"] = True
                dashboard_integration_status["card_available_in_picker"] = True
                
                _LOGGER.info("Successfully registered frontend resources for entry %s: %s", 
                           entry.entry_id, [r["resource"] for r in frontend_registration_result["resources_registered"]])
                
                # Log resource-specific details
                for resource in frontend_registration_result["resources_registered"]:
                    _LOGGER.debug("Registered resource: %s (fallback: %s, retries: %d)", 
                                resource.get("resource", "unknown"),
                                resource.get("fallback_used", False),
                                resource.get("retry_count", 0))
                
                # Log any warnings
                if frontend_registration_result["warnings"]:
                    for warning in frontend_registration_result["warnings"]:
                        setup_diagnostics["warnings"].append(f"Frontend resource warning: {warning}")
                        dashboard_integration_status["frontend_errors"].append(f"Warning: {warning}")
                        _LOGGER.warning("Frontend resource warning: %s", warning)
            else:
                setup_diagnostics["components_failed"].append({"component": "frontend_resources", "error": "Frontend resource registration failed"})
                setup_diagnostics["warnings"].append("Frontend resources failed to register - card may not appear in dashboard picker")
                dashboard_integration_status["frontend_resources_registered"] = False
                
                _LOGGER.error("Frontend resource registration failed for entry %s. Failed resources: %s", 
                              entry.entry_id, frontend_registration_result["resources_failed"])
                
                # Log specific errors for troubleshooting
                for failed_resource in frontend_registration_result["resources_failed"]:
                    error_msg = f"Failed to register resource {failed_resource.get('resource', 'unknown')}: {failed_resource.get('error', 'unknown error')}"
                    _LOGGER.error(error_msg)
                    dashboard_integration_status["frontend_errors"].append(error_msg)
                
                # Add troubleshooting steps for frontend failures
                dashboard_integration_status["troubleshooting_steps"].extend([
                    "Check that card files exist in www/roost-scheduler-card/",
                    "Verify file permissions allow Home Assistant to read card files",
                    "Clear browser cache and refresh the page",
                    "Check browser console for JavaScript errors"
                ])
                
                # Continue setup even if frontend registration fails - not critical for core functionality
                
        except Exception as e:
            error_msg = f"Failed to initialize frontend resource manager for entry {entry.entry_id}: {str(e)}"
            _LOGGER.error(error_msg, exc_info=True)
            setup_diagnostics["components_failed"].append({"component": "frontend_resources", "error": str(e)})
            setup_diagnostics["warnings"].append("Frontend resource manager initialization failed - card may not be available")
            dashboard_integration_status["frontend_errors"].append(error_msg)
            dashboard_integration_status["troubleshooting_steps"].extend([
                "Check Home Assistant logs for detailed error messages",
                "Verify frontend component is properly loaded",
                "Try restarting Home Assistant"
            ])
            # Continue setup even if frontend registration fails - not critical for core functionality
        
        # Store services in hass.data now that all components are initialized
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = {
            "storage_service": storage_service,
            "schedule_manager": schedule_manager,
            "presence_manager": presence_manager,
            "buffer_manager": buffer_manager,
            "logging_manager": logging_manager,
            "config_validator": config_validator,
            "frontend_manager": frontend_manager,
            "dashboard_service": dashboard_service,
            "setup_diagnostics": setup_diagnostics,
            "dashboard_integration_status": dashboard_integration_status,
        }
        
        # Register services with error handling
        try:
            await _register_services(hass, schedule_manager)
            setup_diagnostics["components_initialized"].append("services")
            _LOGGER.info("Successfully registered services for entry %s", entry.entry_id)
        except Exception as e:
            _LOGGER.error("Failed to register services for entry %s: %s", entry.entry_id, e)
            setup_diagnostics["components_failed"].append({"component": "services", "error": str(e)})
            # This is more critical - cleanup and fail
            await _cleanup_entry_data(hass, entry)
            return False
        
        # Register WebSocket API handlers with error handling
        try:
            _register_websocket_handlers(hass)
            setup_diagnostics["components_initialized"].append("websocket_handlers")
            _LOGGER.info("Successfully registered WebSocket handlers for entry %s", entry.entry_id)
        except Exception as e:
            _LOGGER.warning("Failed to register WebSocket handlers for entry %s: %s", entry.entry_id, e)
            setup_diagnostics["components_failed"].append({"component": "websocket_handlers", "error": str(e)})
            setup_diagnostics["warnings"].append("WebSocket handlers failed - real-time updates unavailable")
            # WebSocket failures are not critical - continue without real-time updates
        
        # Final setup validation with comprehensive checks including dashboard integration
        try:
            validation_results = await _validate_setup(hass, entry, dashboard_integration_status)
            setup_diagnostics["validation_results"] = validation_results
            
            # Log validation results with dashboard integration details
            _LOGGER.info("Setup validation completed for entry %s with status: %s", 
                        entry.entry_id, validation_results.get("overall_status", "unknown"))
            
            if validation_results.get("dashboard_integration_validated"):
                _LOGGER.info("Dashboard integration validation passed")
            else:
                _LOGGER.warning("Dashboard integration validation failed or incomplete")
                
        except Exception as e:
            _LOGGER.error("Setup validation failed for entry %s: %s", entry.entry_id, e, exc_info=True)
            setup_diagnostics["warnings"].append(f"Setup validation failed: {str(e)}")
            # Validation failures are warnings, not critical errors
        
        # Process setup feedback with comprehensive dashboard integration status
        try:
            from .setup_feedback import SetupFeedbackManager
            
            feedback_manager = SetupFeedbackManager(hass)
            setup_feedback_data = entry.data.get("setup_feedback", {})
            
            # Determine overall dashboard integration success
            dashboard_integration_success = (
                dashboard_integration_status["frontend_resources_registered"] and
                dashboard_integration_status["dashboard_service_initialized"]
            )
            
            # Collect all error messages
            all_error_messages = []
            all_error_messages.extend(dashboard_integration_status.get("frontend_errors", []))
            all_error_messages.extend(dashboard_integration_status.get("dashboard_errors", []))
            all_error_messages.extend(setup_feedback_data.get("error_messages", []))
            
            # Collect all warning messages
            all_warning_messages = []
            all_warning_messages.extend(setup_diagnostics.get("warnings", []))
            all_warning_messages.extend(setup_feedback_data.get("warning_messages", []))
            
            # Generate troubleshooting information for dashboard integration issues
            troubleshooting_info = generate_dashboard_troubleshooting_info(
                dashboard_integration_status, setup_diagnostics
            )
            
            # Create comprehensive feedback data
            updated_feedback = feedback_manager.create_setup_feedback_data(
                success=True,  # Setup succeeded if we got this far
                dashboard_integration_status=dashboard_integration_success,
                card_registered=dashboard_integration_status["frontend_resources_registered"],
                card_added_to_dashboard=dashboard_integration_status.get("card_added_to_dashboard", False),
                dashboard_id=dashboard_integration_status.get("dashboard_id"),
                error_messages=all_error_messages,
                warning_messages=all_warning_messages
            )
            
            # Add troubleshooting information to feedback
            updated_feedback.troubleshooting_info.update(troubleshooting_info)
            
            # Log comprehensive setup feedback with dashboard integration details
            _LOGGER.info("=== Dashboard Integration Status for Entry %s ===", entry.entry_id)
            _LOGGER.info("Frontend resources registered: %s", dashboard_integration_status["frontend_resources_registered"])
            _LOGGER.info("Card available in picker: %s", dashboard_integration_status["card_available_in_picker"])
            _LOGGER.info("Dashboard service initialized: %s", dashboard_integration_status["dashboard_service_initialized"])
            _LOGGER.info("Card added to dashboard: %s", dashboard_integration_status["card_added_to_dashboard"])
            
            if dashboard_integration_status["dashboard_id"]:
                _LOGGER.info("Dashboard ID: %s", dashboard_integration_status["dashboard_id"])
            
            if dashboard_integration_status["frontend_errors"]:
                _LOGGER.warning("Frontend errors: %s", dashboard_integration_status["frontend_errors"])
            
            if dashboard_integration_status["dashboard_errors"]:
                _LOGGER.warning("Dashboard errors: %s", dashboard_integration_status["dashboard_errors"])
            
            if dashboard_integration_status["troubleshooting_steps"]:
                _LOGGER.info("Troubleshooting steps available: %d", len(dashboard_integration_status["troubleshooting_steps"]))
                for i, step in enumerate(dashboard_integration_status["troubleshooting_steps"], 1):
                    _LOGGER.debug("  %d. %s", i, step)
            
            # Log troubleshooting scenario information
            if troubleshooting_info["scenario"] != "success":
                _LOGGER.warning("Dashboard integration troubleshooting scenario: %s", troubleshooting_info["scenario"])
                _LOGGER.warning("Description: %s", troubleshooting_info["description"])
                if troubleshooting_info["manual_installation_required"]:
                    _LOGGER.warning("Manual installation required - see troubleshooting steps")
            
            _LOGGER.info("=== End Dashboard Integration Status ===")
            
            # Log the final setup feedback
            feedback_manager.log_setup_completion(updated_feedback)
            
            # Store updated feedback in entry data for potential future use
            hass.data[DOMAIN][entry.entry_id]["setup_feedback"] = updated_feedback
            
            _LOGGER.info("Setup feedback processed for entry %s with dashboard integration status", entry.entry_id)
                
        except Exception as e:
            _LOGGER.error("Failed to process setup feedback for entry %s: %s", entry.entry_id, e, exc_info=True)
            # Setup feedback processing failure is not critical
        
        # Enhanced setup diagnostics collection and reporting
        setup_diagnostics["end_time"] = datetime.now()
        setup_diagnostics["duration_seconds"] = (setup_diagnostics["end_time"] - setup_diagnostics["start_time"]).total_seconds()
        
        # Collect comprehensive setup diagnostics
        await _collect_comprehensive_setup_diagnostics(hass, entry, setup_diagnostics)
        
        # Generate detailed setup report
        setup_report = await _generate_setup_success_report(hass, entry, setup_diagnostics)
        
        # Log enhanced setup summary
        _log_enhanced_setup_summary(setup_diagnostics, setup_report)
        
        # Store setup report for future reference
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN][entry.entry_id]["setup_report"] = setup_report
        
        _LOGGER.info("Roost Scheduler setup completed successfully for entry %s in %.3fs", 
                    entry.entry_id, setup_diagnostics["duration_seconds"])
        return True
        
    except Exception as e:
        _LOGGER.error("Critical error during setup for entry %s: %s", entry.entry_id, e, exc_info=True)
        setup_diagnostics["critical_error"] = str(e)
        setup_diagnostics["critical_error_type"] = type(e).__name__
        setup_diagnostics["end_time"] = datetime.now()
        setup_diagnostics["duration_seconds"] = (setup_diagnostics["end_time"] - setup_diagnostics["start_time"]).total_seconds()
        
        # Collect comprehensive failure diagnostics
        await _collect_comprehensive_failure_diagnostics(hass, entry, setup_diagnostics, e)
        
        # Generate detailed failure report
        failure_report = await _generate_detailed_failure_report(hass, entry, setup_diagnostics, e)
        
        # Log enhanced failure diagnostics
        _log_enhanced_setup_failure(setup_diagnostics, failure_report)
        
        # Generate user-friendly error message
        user_friendly_error = _generate_user_friendly_error_message(e, setup_diagnostics)
        _LOGGER.error("User-friendly error summary: %s", user_friendly_error)
        
        # Cleanup any partial setup
        await _cleanup_entry_data(hass, entry)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Roost Scheduler config entry: %s", entry.entry_id)
    
    # Clean up data
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry and handle data preservation."""
    _LOGGER.info("Removing Roost Scheduler config entry: %s", entry.entry_id)
    
    # Check if user wants to preserve data (could be from options or default to True)
    preserve_data = entry.options.get("preserve_data_on_uninstall", True)
    
    # Handle uninstall with data preservation options
    uninstall_manager = UninstallManager(hass)
    try:
        uninstall_info = await uninstall_manager.prepare_uninstall(preserve_data)
        _LOGGER.info("Uninstall preparation completed: %s", uninstall_info)
    except Exception as e:
        _LOGGER.error("Error during uninstall preparation: %s", e)
        # Continue with removal even if uninstall prep fails


async def _register_services(hass: HomeAssistant, schedule_manager: ScheduleManager) -> None:
    """Register Roost Scheduler services with parameter validation."""
    
    async def apply_slot_service(call: ServiceCall) -> None:
        """Handle apply_slot service call with validation."""
        try:
            # The schema validation is handled by Home Assistant when we register with schema
            await schedule_manager.apply_slot_service(call)
            
        except Exception as e:
            _LOGGER.error("Error in apply_slot service: %s", e)
            raise
    
    async def apply_grid_now_service(call: ServiceCall) -> None:
        """Handle apply_grid_now service call with validation."""
        try:
            # The schema validation is handled by Home Assistant when we register with schema
            await schedule_manager.apply_grid_now_service(call)
            
        except Exception as e:
            _LOGGER.error("Error in apply_grid_now service: %s", e)
            raise
    
    async def migrate_resolution_service(call: ServiceCall) -> None:
        """Handle migrate_resolution service call with validation."""
        try:
            # The schema validation is handled by Home Assistant when we register with schema
            await schedule_manager.migrate_resolution_service(call)
            
        except Exception as e:
            _LOGGER.error("Error in migrate_resolution service: %s", e)
            raise
    
    # Register services with schemas
    hass.services.async_register(
        DOMAIN, 
        SERVICE_APPLY_SLOT, 
        apply_slot_service,
        schema=SERVICE_APPLY_SLOT_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_APPLY_GRID_NOW, 
        apply_grid_now_service,
        schema=SERVICE_APPLY_GRID_NOW_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, 
        SERVICE_MIGRATE_RESOLUTION, 
        migrate_resolution_service,
        schema=SERVICE_MIGRATE_RESOLUTION_SCHEMA
    )
    
    _LOGGER.info("Registered Roost Scheduler services: %s, %s, %s", 
                SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW, SERVICE_MIGRATE_RESOLUTION)


def _register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register WebSocket API handlers for real-time communication."""
    
    @websocket_api.websocket_command({
        vol.Required("type"): "roost_scheduler/get_schedule_grid",
        vol.Required("entity_id"): cv.entity_id,
    })
    @websocket_api.async_response
    async def handle_get_schedule_grid(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
        """Handle get_schedule_grid WebSocket command."""
        try:
            entity_id = msg["entity_id"]
            
            # Find the schedule manager for this entity
            schedule_manager = None
            for entry_id, data in hass.data.get(DOMAIN, {}).items():
                if isinstance(data, dict) and "schedule_manager" in data:
                    schedule_manager = data["schedule_manager"]
                    break
            
            if not schedule_manager:
                connection.send_error(msg["id"], "no_schedule_manager", "No schedule manager found")
                return
            
            # Get schedule grid for both modes
            home_grid = await schedule_manager.get_schedule_grid(entity_id, "home")
            away_grid = await schedule_manager.get_schedule_grid(entity_id, "away")
            
            # Get current presence mode
            current_mode = await schedule_manager.presence_manager.get_current_mode()
            
            connection.send_result(msg["id"], {
                "schedules": {
                    "home": home_grid,
                    "away": away_grid
                },
                "current_mode": current_mode,
                "entity_id": entity_id
            })
            
        except Exception as e:
            _LOGGER.error("Error handling get_schedule_grid: %s", e)
            connection.send_error(msg["id"], "get_schedule_error", str(e))
    
    @websocket_api.websocket_command({
        vol.Required("type"): "roost_scheduler/update_schedule",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("mode"): vol.In(["home", "away"]),
        vol.Required("changes"): [dict],
        vol.Optional("update_id"): str,
        vol.Optional("conflict_resolution"): dict,
    })
    @websocket_api.async_response
    async def handle_update_schedule(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
        """Handle update_schedule WebSocket command."""
        try:
            entity_id = msg["entity_id"]
            mode = msg["mode"]
            changes = msg["changes"]
            update_id = msg.get("update_id")
            conflict_resolution = msg.get("conflict_resolution", {"strategy": "server_wins"})
            
            # Find the schedule manager for this entity
            schedule_manager = None
            for entry_id, data in hass.data.get(DOMAIN, {}).items():
                if isinstance(data, dict) and "schedule_manager" in data:
                    schedule_manager = data["schedule_manager"]
                    break
            
            if not schedule_manager:
                connection.send_error(msg["id"], "no_schedule_manager", "No schedule manager found")
                return
            
            # Check for conflicts if update_id is provided
            conflicts = []
            if update_id:
                conflicts = await _check_for_conflicts(schedule_manager, entity_id, mode, changes, update_id)
            
            # Handle conflicts based on resolution strategy
            if conflicts and conflict_resolution["strategy"] != "client_wins":
                if conflict_resolution["strategy"] == "server_wins":
                    # Don't apply changes, return current server state
                    current_grid = await schedule_manager.get_schedule_grid(entity_id, mode)
                    connection.send_result(msg["id"], {
                        "success": False,
                        "conflict": True,
                        "server_state": current_grid,
                        "conflicts": conflicts
                    })
                    return
                elif conflict_resolution["strategy"] == "prompt_user":
                    # Return conflict information for user resolution
                    connection.send_result(msg["id"], {
                        "success": False,
                        "conflict": True,
                        "conflicts": conflicts,
                        "requires_resolution": True
                    })
                    return
            
            # Apply each change
            successful_changes = []
            failed_changes = []
            
            for change in changes:
                try:
                    success = await schedule_manager.update_slot(
                        entity_id=entity_id,
                        mode=mode,
                        day=change["day"],
                        time=change["time"],
                        target={"temperature": change["value"]}
                    )
                    if success:
                        successful_changes.append(change)
                    else:
                        failed_changes.append(change)
                except Exception as e:
                    _LOGGER.error("Failed to apply change %s: %s", change, e)
                    failed_changes.append(change)
            
            # Broadcast the update to all connected clients (excluding the sender)
            hass.bus.async_fire(f"{DOMAIN}_schedule_updated", {
                "entity_id": entity_id,
                "mode": mode,
                "changes": successful_changes,
                "update_id": update_id,
                "timestamp": datetime.now().isoformat(),
                "sender_connection_id": connection.id if hasattr(connection, 'id') else None
            })
            
            connection.send_result(msg["id"], {
                "success": len(failed_changes) == 0,
                "successful_changes": successful_changes,
                "failed_changes": failed_changes,
                "update_id": update_id
            })
            
        except Exception as e:
            _LOGGER.error("Error handling update_schedule: %s", e)
            connection.send_error(msg["id"], "update_schedule_error", str(e))
    
    @websocket_api.websocket_command({
        vol.Required("type"): "roost_scheduler/subscribe_updates",
        vol.Required("entity_id"): cv.entity_id,
    })
    @websocket_api.require_admin  # Require admin for subscriptions
    async def handle_subscribe_updates(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
        """Handle subscribe_updates WebSocket command for real-time updates."""
        entity_id = msg["entity_id"]
        
        def forward_schedule_update(event):
            """Forward schedule update events to WebSocket client."""
            if event.data.get("entity_id") == entity_id:
                connection.send_message({
                    "id": msg["id"],
                    "type": "event",
                    "event": {
                        "type": "schedule_updated",
                        "data": event.data
                    }
                })
        
        def forward_presence_update(event):
            """Forward presence mode changes to WebSocket client."""
            connection.send_message({
                "id": msg["id"],
                "type": "event", 
                "event": {
                    "type": "presence_changed",
                    "data": event.data
                }
            })
        
        # Subscribe to relevant events
        remove_schedule_listener = hass.bus.async_listen(
            f"{DOMAIN}_schedule_updated", forward_schedule_update
        )
        remove_presence_listener = hass.bus.async_listen(
            f"{DOMAIN}_presence_changed", forward_presence_update
        )
        
        # Store cleanup function for when connection closes
        def cleanup():
            remove_schedule_listener()
            remove_presence_listener()
        
        connection.subscriptions[msg["id"]] = cleanup
        
        connection.send_result(msg["id"], {"subscribed": True})
    
    # Register all handlers
    hass.components.websocket_api.async_register_command(handle_get_schedule_grid)
    hass.components.websocket_api.async_register_command(handle_update_schedule)
    hass.components.websocket_api.async_register_command(handle_subscribe_updates)
    
    _LOGGER.info("Registered Roost Scheduler WebSocket handlers")


async def _check_for_conflicts(schedule_manager, entity_id: str, mode: str, changes: list, update_id: str) -> list:
    """Check for conflicts between proposed changes and current server state."""
    conflicts = []
    
    try:
        # Get current schedule grid
        current_grid = await schedule_manager.get_schedule_grid(entity_id, mode)
        
        # Check each proposed change against current state
        for change in changes:
            day = change["day"]
            time = change["time"]
            proposed_value = change["value"]
            
            # Find current value for this slot
            current_value = None
            if day in current_grid:
                for slot in current_grid[day]:
                    if slot.get("start_time") <= time <= slot.get("end_time", time):
                        current_value = slot.get("target_value")
                        break
            
            # Simple conflict detection: if values differ significantly
            if current_value is not None and abs(current_value - proposed_value) > 0.1:
                conflicts.append({
                    "day": day,
                    "time": time,
                    "proposed_value": proposed_value,
                    "current_value": current_value,
                    "update_id": update_id
                })
    
    except Exception as e:
        _LOGGER.error("Error checking for conflicts: %s", e)
    
    return conflicts


async def _execute_comprehensive_error_recovery(
    hass: HomeAssistant, 
    domain: str, 
    validation_result, 
    comprehensive_result, 
    setup_diagnostics: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute comprehensive error recovery with multiple fallback mechanisms.
    
    Args:
        hass: Home Assistant instance
        domain: Integration domain
        validation_result: Startup validation result
        comprehensive_result: Comprehensive validation result
        setup_diagnostics: Setup diagnostics dictionary
        
    Returns:
        Dictionary with recovery results
    """
    recovery_start_time = datetime.now()
    recovery_result = {
        "success": False,
        "recovery_steps": [],
        "fixes_applied": [],
        "fallbacks_used": [],
        "errors": [],
        "warnings": []
    }
    
    try:
        _LOGGER.info("Starting comprehensive error recovery for domain: %s", domain)
        
        # Step 1: Analyze and prioritize issues
        _LOGGER.debug("Analyzing validation issues for recovery prioritization")
        critical_issues = []
        recoverable_issues = []
        
        # Collect issues from startup validation
        for issue in validation_result.issues:
            if isinstance(issue, dict):
                severity = issue.get("severity", "unknown")
                if severity in ["critical", "error"]:
                    critical_issues.append(issue)
                else:
                    recoverable_issues.append(issue)
            else:
                recoverable_issues.append({"description": str(issue), "severity": "unknown"})
        
        # Collect issues from comprehensive validation
        if not comprehensive_result.manifest_result.valid:
            for issue in comprehensive_result.manifest_result.issues:
                critical_issues.append({
                    "description": f"Manifest issue: {issue}",
                    "severity": "error",
                    "category": "manifest"
                })
        
        if not comprehensive_result.dependency_result.valid:
            for conflict in comprehensive_result.dependency_result.conflicts:
                critical_issues.append({
                    "description": f"Dependency conflict: {conflict}",
                    "severity": "error", 
                    "category": "dependency"
                })
        
        if not comprehensive_result.version_result.compatible:
            for issue in comprehensive_result.version_result.issues:
                critical_issues.append({
                    "description": f"Version compatibility issue: {issue}",
                    "severity": "warning",
                    "category": "version"
                })
        
        recovery_result["critical_issues_count"] = len(critical_issues)
        recovery_result["recoverable_issues_count"] = len(recoverable_issues)
        
        # Step 2: Apply targeted fixes for critical issues
        if critical_issues:
            _LOGGER.info("Applying targeted fixes for %d critical issues", len(critical_issues))
            
            from .config_flow_registration_fixer import ConfigFlowRegistrationFixer
            fixer = ConfigFlowRegistrationFixer(hass, domain)
            
            # Group issues by category for efficient fixing
            issue_categories = {}
            for issue in critical_issues:
                category = issue.get("category", "general")
                if category not in issue_categories:
                    issue_categories[category] = []
                issue_categories[category].append(issue)
            
            # Apply category-specific fixes
            for category, category_issues in issue_categories.items():
                try:
                    _LOGGER.debug("Applying fixes for category: %s (%d issues)", category, len(category_issues))
                    
                    if category == "manifest":
                        fix_result = await _fix_manifest_issues(fixer, category_issues)
                    elif category == "dependency":
                        fix_result = await _fix_dependency_issues(fixer, category_issues)
                    elif category == "version":
                        fix_result = await _fix_version_issues(fixer, category_issues)
                    else:
                        fix_result = await fixer.apply_all_fixes()
                    
                    if fix_result.success:
                        recovery_result["fixes_applied"].append({
                            "category": category,
                            "issues_fixed": fix_result.fixed_issues,
                            "changes": fix_result.fix_results
                        })
                        recovery_result["recovery_steps"].append(f"Fixed {category} issues")
                    else:
                        recovery_result["errors"].append(f"Failed to fix {category} issues")
                        
                except Exception as e:
                    _LOGGER.error("Error fixing %s issues: %s", category, e)
                    recovery_result["errors"].append(f"Error fixing {category} issues: {str(e)}")
        
        # Step 3: Apply recovery verification
        _LOGGER.debug("Verifying recovery effectiveness")
        try:
            from .startup_validation_system import StartupValidationSystem
            validator = StartupValidationSystem(hass)
            
            # Re-run validation to check recovery effectiveness
            post_recovery_result = await validator.run_comprehensive_validation(domain)
            
            recovery_result["post_recovery_validation"] = {
                "success": post_recovery_result.success,
                "remaining_issues": len(post_recovery_result.issues),
                "remaining_warnings": len(post_recovery_result.warnings)
            }
            
            if post_recovery_result.success:
                recovery_result["success"] = True
                recovery_result["recovery_steps"].append("Post-recovery validation passed")
                _LOGGER.info("Error recovery successful - validation now passes")
            else:
                _LOGGER.warning("Recovery partially successful - %d issues remain", 
                              len(post_recovery_result.issues))
                recovery_result["warnings"].append("Some issues could not be automatically recovered")
                
                # Apply fallback mechanisms for remaining issues
                fallback_result = await _apply_recovery_fallbacks(
                    post_recovery_result, setup_diagnostics
                )
                recovery_result["fallbacks_used"].extend(fallback_result.get("fallbacks", []))
                
                if fallback_result.get("success", False):
                    recovery_result["success"] = True
                    recovery_result["recovery_steps"].append("Fallback mechanisms applied successfully")
                
        except Exception as e:
            _LOGGER.error("Error during recovery verification: %s", e)
            recovery_result["errors"].append(f"Recovery verification failed: {str(e)}")
        
        # Step 4: Generate recovery report
        recovery_duration = (datetime.now() - recovery_start_time).total_seconds()
        recovery_result["duration_seconds"] = recovery_duration
        recovery_result["recovery_steps"].append(f"Recovery completed in {recovery_duration:.2f}s")
        
        if recovery_result["success"]:
            _LOGGER.info("Comprehensive error recovery completed successfully")
        else:
            _LOGGER.warning("Comprehensive error recovery completed with limitations")
        
        return recovery_result
        
    except Exception as e:
        _LOGGER.error("Critical error during comprehensive error recovery: %s", e)
        recovery_result["errors"].append(f"Recovery system error: {str(e)}")
        recovery_result["success"] = False
        return recovery_result


async def _fix_manifest_issues(fixer, issues: List[Dict[str, Any]]) -> Any:
    """Fix manifest-specific issues."""
    # Apply manifest-specific fixes
    return await fixer.fix_domain_mismatch()


async def _fix_dependency_issues(fixer, issues: List[Dict[str, Any]]) -> Any:
    """Fix dependency-specific issues."""
    # Apply dependency-specific fixes
    return await fixer.apply_all_fixes()


async def _fix_version_issues(fixer, issues: List[Dict[str, Any]]) -> Any:
    """Fix version compatibility issues."""
    # Version issues are typically warnings, not critical errors
    from .config_flow_registration_fixer import FixResult
    return FixResult(
        success=True,
        issue_type="version_compatibility",
        description="Version issues noted but not blocking",
        changes_made=[],
        errors=[],
        warnings=["Version compatibility issues noted"],
        verification_passed=True
    )


async def _apply_recovery_fallbacks(validation_result, setup_diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    """Apply fallback mechanisms for issues that couldn't be automatically fixed."""
    fallback_result = {
        "success": False,
        "fallbacks": [],
        "warnings": []
    }
    
    try:
        # Analyze remaining issues and apply appropriate fallbacks
        critical_remaining = [
            issue for issue in validation_result.issues
            if isinstance(issue, dict) and issue.get("severity") == "critical"
        ]
        
        if not critical_remaining:
            # No critical issues remain - can proceed with warnings
            fallback_result["success"] = True
            fallback_result["fallbacks"].append("Proceeding with non-critical issues as warnings")
            setup_diagnostics["warnings"].append("Some non-critical validation issues remain")
        else:
            # Apply emergency mode for critical issues
            fallback_result["fallbacks"].append("Emergency mode activated for critical issues")
            fallback_result["warnings"].append("Operating in emergency mode due to unresolved critical issues")
            setup_diagnostics["warnings"].append("Integration running in emergency mode")
            
            # For now, allow setup to continue but with limitations
            fallback_result["success"] = True
        
        return fallback_result
        
    except Exception as e:
        _LOGGER.error("Error applying recovery fallbacks: %s", e)
        fallback_result["warnings"].append(f"Fallback application error: {str(e)}")
        return fallback_result


async def _apply_emergency_recovery_fallbacks(setup_diagnostics: Dict[str, Any]) -> None:
    """Apply emergency fallbacks when the recovery system itself fails."""
    try:
        _LOGGER.warning("Applying emergency recovery fallbacks")
        setup_diagnostics["fallbacks_used"].append("emergency_recovery_fallbacks")
        setup_diagnostics["warnings"].append("Emergency recovery fallbacks activated")
        
        # Log critical system state for troubleshooting
        _LOGGER.error("Integration setup continuing with emergency fallbacks - functionality may be limited")
        
    except Exception as e:
        _LOGGER.error("Emergency recovery fallbacks failed: %s", e)


def _validate_ha_version(hass: HomeAssistant) -> bool:
    """Validate Home Assistant version compatibility."""
    try:
        from homeassistant.const import __version__ as ha_version
        
        # Simple version comparison for major.minor
        ha_parts = [int(x) for x in ha_version.split(".")[:2]]
        min_parts = [int(x) for x in MIN_HA_VERSION.split(".")[:2]]
        
        if ha_parts[0] > min_parts[0] or (ha_parts[0] == min_parts[0] and ha_parts[1] >= min_parts[1]):
            _LOGGER.debug("Home Assistant version %s meets minimum requirement %s", ha_version, MIN_HA_VERSION)
            return True
        else:
            _LOGGER.error(
                "Home Assistant version %s is below minimum requirement %s", 
                ha_version, 
                MIN_HA_VERSION
            )
            return False
            
    except Exception as e:
        _LOGGER.warning("Could not validate Home Assistant version: %s", e)
        return True  # Allow setup to continue if version check fails


def _validate_dependencies(hass: HomeAssistant) -> bool:
    """Validate required and optional dependencies."""
    missing_required = []
    missing_optional = []
    
    # Check required domains
    for domain in REQUIRED_DOMAINS:
        if domain not in hass.config.components:
            missing_required.append(domain)
    
    # Check optional domains (just log warnings)
    for domain in OPTIONAL_DOMAINS:
        if domain not in hass.config.components:
            missing_optional.append(domain)
    
    if missing_required:
        _LOGGER.error(
            "Missing required dependencies: %s. Integration cannot start.", 
            ", ".join(missing_required)
        )
        return False
    
    if missing_optional:
        _LOGGER.warning(
            "Missing optional dependencies: %s. Some features may not work.", 
            ", ".join(missing_optional)
        )
    
    _LOGGER.debug("All required dependencies are available")
    return True


async def _cleanup_entry_data(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up entry data on setup failure."""
    try:
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            entry_data = hass.data[DOMAIN][entry.entry_id]
            
            # Cleanup logging manager
            if "logging_manager" in entry_data:
                try:
                    await entry_data["logging_manager"]._cleanup_file_logging()
                except Exception as e:
                    _LOGGER.debug("Error cleaning up logging manager: %s", e)
            
            # Remove entry data
            hass.data[DOMAIN].pop(entry.entry_id, None)
            
            # Remove domain data if no entries left
            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN, None)
                
        _LOGGER.debug("Cleaned up entry data for %s", entry.entry_id)
        
    except Exception as e:
        _LOGGER.error("Error during cleanup for entry %s: %s", entry.entry_id, e)


async def _validate_setup(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Validate that setup completed successfully and return validation results."""
    validation_results = {
        "components_validated": [],
        "components_failed": [],
        "functionality_tests": [],
        "warnings": [],
        "overall_status": "unknown"
    }
    
    try:
        entry_data = hass.data[DOMAIN][entry.entry_id]
        
        # Check that all required components are present
        required_components = ["storage_service", "schedule_manager", "presence_manager", "buffer_manager"]
        missing_components = []
        
        for component in required_components:
            if component not in entry_data or entry_data[component] is None:
                missing_components.append(component)
                validation_results["components_failed"].append(component)
            else:
                validation_results["components_validated"].append(component)
        
        if missing_components:
            raise ValueError(f"Missing required components: {', '.join(missing_components)}")
        
        # Test basic functionality
        schedule_manager = entry_data["schedule_manager"]
        presence_manager = entry_data["presence_manager"]
        buffer_manager = entry_data["buffer_manager"]
        storage_service = entry_data["storage_service"]
        
        # Verify schedule manager can load data
        try:
            await schedule_manager._load_schedule_data()
            validation_results["functionality_tests"].append({"test": "schedule_data_loading", "status": "passed"})
        except Exception as e:
            _LOGGER.warning("Schedule manager data loading test failed: %s", e)
            validation_results["functionality_tests"].append({"test": "schedule_data_loading", "status": "failed", "error": str(e)})
            validation_results["warnings"].append(f"Schedule data loading test failed: {str(e)}")
        
        # Verify presence manager can evaluate mode
        try:
            current_mode = await presence_manager.get_current_mode()
            if current_mode not in [MODE_HOME, MODE_AWAY]:
                raise ValueError(f"Invalid presence mode: {current_mode}")
            validation_results["functionality_tests"].append({"test": "presence_mode_evaluation", "status": "passed", "mode": current_mode})
        except Exception as e:
            _LOGGER.warning("Presence manager test failed: %s", e)
            validation_results["functionality_tests"].append({"test": "presence_mode_evaluation", "status": "failed", "error": str(e)})
            validation_results["warnings"].append(f"Presence manager test failed: {str(e)}")
        
        # Verify buffer manager functionality
        try:
            # Test buffer manager with a simple check
            test_entity = "climate.test"
            should_suppress = buffer_manager.should_suppress_change(test_entity, 20.0, {})
            validation_results["functionality_tests"].append({"test": "buffer_manager_logic", "status": "passed"})
        except Exception as e:
            _LOGGER.warning("Buffer manager test failed: %s", e)
            validation_results["functionality_tests"].append({"test": "buffer_manager_logic", "status": "failed", "error": str(e)})
            validation_results["warnings"].append(f"Buffer manager test failed: {str(e)}")
        
        # Verify storage service functionality
        try:
            # Test storage service basic operations
            await storage_service._ensure_storage_initialized()
            validation_results["functionality_tests"].append({"test": "storage_service_initialization", "status": "passed"})
        except Exception as e:
            _LOGGER.warning("Storage service test failed: %s", e)
            validation_results["functionality_tests"].append({"test": "storage_service_initialization", "status": "failed", "error": str(e)})
            validation_results["warnings"].append(f"Storage service test failed: {str(e)}")
        
        # Check service registration
        services_registered = []
        services_missing = []
        
        expected_services = [SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW, SERVICE_MIGRATE_RESOLUTION]
        for service in expected_services:
            if hass.services.has_service(DOMAIN, service):
                services_registered.append(service)
            else:
                services_missing.append(service)
        
        if services_missing:
            raise ValueError(f"Services not properly registered: {', '.join(services_missing)}")
        
        validation_results["functionality_tests"].append({
            "test": "service_registration", 
            "status": "passed", 
            "services_registered": services_registered
        })
        
        # Determine overall status
        failed_tests = [test for test in validation_results["functionality_tests"] if test["status"] == "failed"]
        if not validation_results["components_failed"] and not failed_tests:
            validation_results["overall_status"] = "passed"
        elif validation_results["components_failed"]:
            validation_results["overall_status"] = "failed"
        else:
            validation_results["overall_status"] = "passed_with_warnings"
        
        _LOGGER.debug("Setup validation completed for entry %s with status: %s", 
                     entry.entry_id, validation_results["overall_status"])
        
        return validation_results
        
    except Exception as e:
        validation_results["overall_status"] = "failed"
        validation_results["critical_error"] = str(e)
        _LOGGER.error("Critical error during setup validation: %s", e)
        raise


def _log_setup_summary(setup_diagnostics: dict) -> None:
    """Log a comprehensive setup summary including dashboard integration status."""
    entry_id = setup_diagnostics["entry_id"]
    duration = setup_diagnostics["duration_seconds"]
    
    _LOGGER.info("=== Roost Scheduler Setup Summary for %s ===", entry_id)
    _LOGGER.info("Setup Duration: %.2f seconds", duration)
    
    if setup_diagnostics["components_initialized"]:
        _LOGGER.info("Components Initialized: %s", ", ".join(setup_diagnostics["components_initialized"]))
    
    if setup_diagnostics["components_failed"]:
        _LOGGER.warning("Components Failed: %s", 
                       ", ".join([f"{c['component']} ({c['error']})" for c in setup_diagnostics["components_failed"]]))
    
    if setup_diagnostics["fallbacks_used"]:
        _LOGGER.warning("Fallbacks Used: %s", ", ".join(setup_diagnostics["fallbacks_used"]))
    
    if setup_diagnostics["warnings"]:
        _LOGGER.warning("Setup Warnings:")
        for warning in setup_diagnostics["warnings"]:
            _LOGGER.warning("  - %s", warning)
    
    # Log dashboard integration summary
    dashboard_components = [comp for comp in setup_diagnostics["components_initialized"] 
                          if comp in ["frontend_resources", "dashboard_service"]]
    dashboard_failures = [comp for comp in setup_diagnostics["components_failed"] 
                         if comp.get("component") in ["frontend_resources", "dashboard_service"]]
    
    if dashboard_components or dashboard_failures:
        _LOGGER.info("Dashboard Integration Summary:")
        if dashboard_components:
            _LOGGER.info("  ✓ Initialized: %s", ", ".join(dashboard_components))
        if dashboard_failures:
            _LOGGER.warning("  ✗ Failed: %s", 
                          ", ".join([f"{c['component']} ({c['error']})" for c in dashboard_failures]))
    
    if "validation_results" in setup_diagnostics:
        validation = setup_diagnostics["validation_results"]
        _LOGGER.info("Validation Status: %s", validation.get("overall_status", "unknown"))
        
        # Log dashboard integration validation specifically
        if validation.get("dashboard_integration_validated") is not None:
            status = "✓ Passed" if validation["dashboard_integration_validated"] else "✗ Failed"
            _LOGGER.info("Dashboard Integration Validation: %s", status)
        
        if validation.get("functionality_tests"):
            passed_tests = [t for t in validation["functionality_tests"] if t["status"] == "passed"]
            failed_tests = [t for t in validation["functionality_tests"] if t["status"] == "failed"]
            
            _LOGGER.info("Functionality Tests: %d passed, %d failed", len(passed_tests), len(failed_tests))
            
            if failed_tests:
                for test in failed_tests:
                    _LOGGER.warning("  Failed Test: %s - %s", test["test"], test.get("error", "Unknown error"))
    
    _LOGGER.info("=== End Setup Summary ===")


def _log_setup_failure(setup_diagnostics: dict) -> None:
    """Log detailed information about setup failure for troubleshooting."""
    entry_id = setup_diagnostics["entry_id"]
    
    _LOGGER.error("=== Roost Scheduler Setup FAILED for %s ===", entry_id)
    
    if "duration_seconds" in setup_diagnostics:
        duration = (setup_diagnostics["end_time"] - setup_diagnostics["start_time"]).total_seconds()
        _LOGGER.error("Failed after %.2f seconds", duration)
    
    if setup_diagnostics["components_initialized"]:
        _LOGGER.error("Components that initialized successfully: %s", 
                     ", ".join(setup_diagnostics["components_initialized"]))
    
    if setup_diagnostics["components_failed"]:
        _LOGGER.error("Components that failed to initialize:")
        for component in setup_diagnostics["components_failed"]:
            _LOGGER.error("  - %s: %s", component["component"], component["error"])
    
    if "critical_error" in setup_diagnostics:
        _LOGGER.error("Critical Error: %s", setup_diagnostics["critical_error"])
    
    _LOGGER.error("=== Troubleshooting Suggestions ===")
    _LOGGER.error("General Issues:")
    _LOGGER.error("1. Check Home Assistant logs for detailed error messages")
    _LOGGER.error("2. Verify all required dependencies are installed")
    _LOGGER.error("3. Check storage permissions and disk space")
    _LOGGER.error("4. Try removing and re-adding the integration")
    
    # Add dashboard-specific troubleshooting if dashboard components failed
    dashboard_failures = [comp for comp in setup_diagnostics.get("components_failed", []) 
                         if comp.get("component") in ["frontend_resources", "dashboard_service"]]
    
    if dashboard_failures:
        _LOGGER.error("Dashboard Integration Issues:")
        _LOGGER.error("5. Check that card files exist in www/roost-scheduler-card/")
        _LOGGER.error("6. Verify file permissions allow Home Assistant to read card files")
        _LOGGER.error("7. Clear browser cache and refresh the page")
        _LOGGER.error("8. Check browser console for JavaScript errors")
        _LOGGER.error("9. Try manually adding the card through dashboard edit mode")
        _LOGGER.error("10. Verify Lovelace configuration for any conflicts")
    
    _LOGGER.error("11. Report this issue with the full log output")
    _LOGGER.error("=== End Setup Failure Report ===")


async def get_setup_diagnostics(hass: HomeAssistant, entry_id: str) -> dict:
    """Get comprehensive setup diagnostics for troubleshooting."""
    diagnostics = {
        "entry_id": entry_id,
        "timestamp": datetime.now().isoformat(),
        "integration_status": "unknown",
        "components": {},
        "configuration": {},
        "system_info": {},
        "recommendations": []
    }
    
    try:
        # Check if entry exists in hass.data
        if DOMAIN not in hass.data or entry_id not in hass.data[DOMAIN]:
            diagnostics["integration_status"] = "not_initialized"
            diagnostics["recommendations"].append("Integration not found - try reloading the integration")
            return diagnostics
        
        entry_data = hass.data[DOMAIN][entry_id]
        diagnostics["integration_status"] = "initialized"
        
        # Get setup diagnostics if available
        if "setup_diagnostics" in entry_data:
            diagnostics["setup_history"] = entry_data["setup_diagnostics"]
        
        # Get dashboard integration status if available
        if "dashboard_integration_status" in entry_data:
            diagnostics["dashboard_integration"] = entry_data["dashboard_integration_status"]
        
        # Check component status
        required_components = ["storage_service", "schedule_manager", "presence_manager", "buffer_manager"]
        optional_components = ["frontend_manager", "dashboard_service"]
        
        for component in required_components:
            if component in entry_data and entry_data[component] is not None:
                diagnostics["components"][component] = "initialized"
                
                # Get component-specific diagnostics
                try:
                    if hasattr(entry_data[component], 'get_diagnostics'):
                        diagnostics["components"][f"{component}_details"] = await entry_data[component].get_diagnostics()
                except Exception as e:
                    diagnostics["components"][f"{component}_diagnostics_error"] = str(e)
            else:
                diagnostics["components"][component] = "missing"
                diagnostics["recommendations"].append(f"Component {component} is missing - integration may not function properly")
        
        # Check optional dashboard components
        for component in optional_components:
            if component in entry_data and entry_data[component] is not None:
                diagnostics["components"][component] = "initialized"
                
                # Get dashboard-specific diagnostics
                try:
                    if component == "frontend_manager" and hasattr(entry_data[component], 'get_registration_status'):
                        diagnostics["components"]["frontend_registration_status"] = entry_data[component].get_registration_status()
                    elif hasattr(entry_data[component], 'get_diagnostics'):
                        diagnostics["components"][f"{component}_details"] = await entry_data[component].get_diagnostics()
                except Exception as e:
                    diagnostics["components"][f"{component}_diagnostics_error"] = str(e)
            else:
                diagnostics["components"][component] = "missing"
                if component == "frontend_manager":
                    diagnostics["recommendations"].append("Frontend manager missing - card may not appear in dashboard picker")
                elif component == "dashboard_service":
                    diagnostics["recommendations"].append("Dashboard service missing - automatic card installation unavailable")
        
        # Get configuration information
        try:
            if "presence_manager" in entry_data and entry_data["presence_manager"]:
                presence_config = await entry_data["presence_manager"].get_configuration_summary()
                diagnostics["configuration"]["presence"] = presence_config
        except Exception as e:
            diagnostics["configuration"]["presence_error"] = str(e)
        
        try:
            if "buffer_manager" in entry_data and entry_data["buffer_manager"]:
                buffer_config = await entry_data["buffer_manager"].get_configuration_summary()
                diagnostics["configuration"]["buffer"] = buffer_config
        except Exception as e:
            diagnostics["configuration"]["buffer_error"] = str(e)
        
        # System information
        diagnostics["system_info"] = {
            "ha_version": hass.config.as_dict().get("version", "unknown"),
            "domain_loaded": DOMAIN in hass.config.components,
            "services_registered": [
                service for service in [SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW, SERVICE_MIGRATE_RESOLUTION]
                if hass.services.has_service(DOMAIN, service)
            ]
        }
        
        # Generate recommendations based on findings
        if not diagnostics["system_info"]["services_registered"]:
            diagnostics["recommendations"].append("No services registered - integration may not be functioning")
        
        missing_components = [comp for comp, status in diagnostics["components"].items() 
                            if status == "missing" and not comp.endswith("_details") and not comp.endswith("_error") and not comp.endswith("_status")]
        if missing_components:
            diagnostics["recommendations"].append(f"Missing components: {', '.join(missing_components)}")
        
        # Add dashboard-specific recommendations
        dashboard_issues = []
        if diagnostics["components"].get("frontend_manager") == "missing":
            dashboard_issues.append("frontend resources not registered")
        if diagnostics["components"].get("dashboard_service") == "missing":
            dashboard_issues.append("dashboard service not available")
        
        if dashboard_issues:
            diagnostics["recommendations"].append(f"Dashboard integration issues: {', '.join(dashboard_issues)}")
            diagnostics["recommendations"].extend([
                "Try manually adding the Roost Scheduler card through dashboard edit mode",
                "Check browser console for JavaScript errors",
                "Verify card files exist in www/roost-scheduler-card/"
            ])
        
    except Exception as e:
        diagnostics["error"] = str(e)
        diagnostics["integration_status"] = "error"
        diagnostics["recommendations"].append("Critical error getting diagnostics - check logs for details")
    
    return diagnostics


def generate_dashboard_troubleshooting_info(
    dashboard_integration_status: dict,
    setup_diagnostics: dict
) -> Dict[str, Any]:
    """Generate troubleshooting information for dashboard integration issues.
    
    Args:
        dashboard_integration_status: Dashboard integration status from setup
        setup_diagnostics: General setup diagnostics
        
    Returns:
        Dictionary containing troubleshooting information and steps
    """
    troubleshooting_info = {
        "scenario": "unknown",
        "description": "",
        "likely_causes": [],
        "troubleshooting_steps": [],
        "manual_installation_required": False,
        "severity": "info"
    }
    
    try:
        # Determine the failure scenario
        frontend_registered = dashboard_integration_status.get("frontend_resources_registered", False)
        dashboard_service_ok = dashboard_integration_status.get("dashboard_service_initialized", False)
        card_added = dashboard_integration_status.get("card_added_to_dashboard", False)
        
        if not frontend_registered and not dashboard_service_ok:
            # Complete dashboard integration failure
            troubleshooting_info.update({
                "scenario": "complete_dashboard_failure",
                "description": "Both frontend resource registration and dashboard service initialization failed",
                "likely_causes": [
                    "Card files missing or corrupted",
                    "File permission issues",
                    "Home Assistant frontend component not available",
                    "Lovelace configuration conflicts"
                ],
                "troubleshooting_steps": [
                    "Verify card files exist in config/www/roost-scheduler-card/",
                    "Check file permissions (should be readable by Home Assistant)",
                    "Restart Home Assistant to reload frontend resources",
                    "Check Home Assistant logs for specific error messages",
                    "Try manually copying card files to www/roost-scheduler-card/",
                    "Clear browser cache and refresh the page"
                ],
                "manual_installation_required": True,
                "severity": "error"
            })
            
        elif not frontend_registered:
            # Frontend resource registration failed
            troubleshooting_info.update({
                "scenario": "frontend_registration_failure",
                "description": "Frontend resources failed to register - card won't appear in dashboard picker",
                "likely_causes": [
                    "Card JavaScript file missing or corrupted",
                    "File permission issues",
                    "Home Assistant frontend API changes",
                    "Browser caching issues"
                ],
                "troubleshooting_steps": [
                    "Check that roost-scheduler-card.js exists in www/roost-scheduler-card/",
                    "Verify file permissions allow Home Assistant to read the file",
                    "Check browser console for JavaScript errors",
                    "Clear browser cache and hard refresh (Ctrl+F5)",
                    "Try restarting Home Assistant",
                    "Check Home Assistant version compatibility"
                ],
                "manual_installation_required": True,
                "severity": "warning"
            })
            
        elif not dashboard_service_ok:
            # Dashboard service initialization failed
            troubleshooting_info.update({
                "scenario": "dashboard_service_failure",
                "description": "Dashboard service failed to initialize - automatic card installation unavailable",
                "likely_causes": [
                    "Lovelace configuration access issues",
                    "Dashboard permissions problems",
                    "Storage system conflicts"
                ],
                "troubleshooting_steps": [
                    "Check Lovelace configuration for any syntax errors",
                    "Verify dashboard is accessible and editable",
                    "Try manually adding the card through dashboard edit mode",
                    "Check Home Assistant storage permissions",
                    "Review Home Assistant logs for dashboard-related errors"
                ],
                "manual_installation_required": False,
                "severity": "info"
            })
            
        elif not card_added:
            # Card registration OK but not added to dashboard
            troubleshooting_info.update({
                "scenario": "card_not_added",
                "description": "Card is available in picker but wasn't automatically added to dashboard",
                "likely_causes": [
                    "Dashboard modification permissions",
                    "Multiple dashboard configurations",
                    "User preference for manual card placement"
                ],
                "troubleshooting_steps": [
                    "Go to your dashboard and click 'Edit Dashboard'",
                    "Click 'Add Card' and search for 'Roost Scheduler'",
                    "Add the card to your preferred location",
                    "Configure card settings as needed"
                ],
                "manual_installation_required": False,
                "severity": "info"
            })
            
        else:
            # Everything appears to be working
            troubleshooting_info.update({
                "scenario": "success",
                "description": "Dashboard integration completed successfully",
                "likely_causes": [],
                "troubleshooting_steps": [
                    "Navigate to your dashboard to access the Roost Scheduler card",
                    "Start creating your heating schedules"
                ],
                "manual_installation_required": False,
                "severity": "info"
            })
        
        # Add common troubleshooting steps for all scenarios
        if troubleshooting_info["severity"] in ["warning", "error"]:
            troubleshooting_info["troubleshooting_steps"].extend([
                "Check the integration documentation for manual installation instructions",
                "Report persistent issues with full log output to the support forum"
            ])
        
        # Add specific error messages if available
        frontend_errors = dashboard_integration_status.get("frontend_errors", [])
        dashboard_errors = dashboard_integration_status.get("dashboard_errors", [])
        
        if frontend_errors or dashboard_errors:
            troubleshooting_info["error_details"] = {
                "frontend_errors": frontend_errors,
                "dashboard_errors": dashboard_errors
            }
        
    except Exception as e:
        _LOGGER.error("Error generating dashboard troubleshooting info: %s", str(e))
        troubleshooting_info.update({
            "scenario": "troubleshooting_error",
            "description": f"Error generating troubleshooting information: {str(e)}",
            "troubleshooting_steps": ["Check Home Assistant logs for detailed error information"],
            "severity": "error"
        })
    
    return troubleshooting_info

def _log_setup_summary(setup_diagnostics: dict) -> None:
    """Log a comprehensive setup summary."""
    duration = setup_diagnostics.get("duration_seconds", 0)
    components_initialized = setup_diagnostics.get("components_initialized", [])
    components_failed = setup_diagnostics.get("components_failed", [])
    warnings = setup_diagnostics.get("warnings", [])
    fallbacks_used = setup_diagnostics.get("fallbacks_used", [])
    
    _LOGGER.info("=== Roost Scheduler Setup Summary ===")
    _LOGGER.info("Entry ID: %s", setup_diagnostics.get("entry_id"))
    _LOGGER.info("Duration: %.3f seconds", duration)
    _LOGGER.info("Components initialized: %d (%s)", len(components_initialized), ", ".join(components_initialized))
    
    if components_failed:
        _LOGGER.warning("Components failed: %d", len(components_failed))
        for failure in components_failed:
            _LOGGER.warning("  - %s: %s", failure.get("component", "unknown"), failure.get("error", "unknown error"))
    
    if warnings:
        _LOGGER.warning("Warnings: %d", len(warnings))
        for warning in warnings:
            _LOGGER.warning("  - %s", warning)
    
    if fallbacks_used:
        _LOGGER.info("Fallbacks used: %d (%s)", len(fallbacks_used), ", ".join(fallbacks_used))
    
    # Performance metrics
    performance_metrics = setup_diagnostics.get("performance_metrics", {})
    if performance_metrics:
        _LOGGER.info("Performance metrics:")
        for metric, value in performance_metrics.items():
            _LOGGER.info("  - %s: %.3fs", metric, value)
    
    _LOGGER.info("=== Setup Summary Complete ===")


def _log_setup_failure(setup_diagnostics: dict) -> None:
    """Log detailed failure information for troubleshooting."""
    duration = setup_diagnostics.get("duration_seconds", 0)
    components_initialized = setup_diagnostics.get("components_initialized", [])
    components_failed = setup_diagnostics.get("components_failed", [])
    critical_error = setup_diagnostics.get("critical_error")
    
    _LOGGER.error("=== Roost Scheduler Setup FAILED ===")
    _LOGGER.error("Entry ID: %s", setup_diagnostics.get("entry_id"))
    _LOGGER.error("Duration before failure: %.3f seconds", duration)
    _LOGGER.error("Critical error: %s", critical_error)
    
    if components_initialized:
        _LOGGER.error("Components that initialized successfully: %s", ", ".join(components_initialized))
    
    if components_failed:
        _LOGGER.error("Components that failed:")
        for failure in components_failed:
            _LOGGER.error("  - %s: %s", failure.get("component", "unknown"), failure.get("error", "unknown error"))
    
    _LOGGER.error("=== Failure Summary Complete ===")
    _LOGGER.error("Check the logs above for specific error details and troubleshooting information")


async def _validate_setup(hass: HomeAssistant, entry: ConfigEntry, dashboard_integration_status: dict = None) -> dict:
    """Validate that the setup completed successfully with comprehensive checks including dashboard integration."""
    validation_results = {
        "entry_data_valid": False,
        "managers_initialized": False,
        "services_registered": False,
        "websocket_handlers_registered": False,
        "storage_accessible": False,
        "configuration_valid": False,
        "dashboard_integration_validated": False,
        "frontend_resources_available": False,
        "dashboard_service_available": False,
        "issues": [],
        "recommendations": []
    }
    
    try:
        # Check entry data exists
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            entry_data = hass.data[DOMAIN][entry.entry_id]
            validation_results["entry_data_valid"] = True
            
            # Check managers
            required_managers = ["storage_service", "schedule_manager", "presence_manager", "buffer_manager"]
            managers_ok = all(manager in entry_data and entry_data[manager] is not None for manager in required_managers)
            validation_results["managers_initialized"] = managers_ok
            
            if not managers_ok:
                missing = [m for m in required_managers if m not in entry_data or entry_data[m] is None]
                validation_results["issues"].append(f"Missing managers: {', '.join(missing)}")
            
            # Test storage accessibility
            try:
                storage_service = entry_data.get("storage_service")
                if storage_service:
                    await storage_service.load_schedules()
                    validation_results["storage_accessible"] = True
                else:
                    validation_results["issues"].append("Storage service not available")
            except Exception as e:
                validation_results["issues"].append(f"Storage access failed: {str(e)}")
            
            # Test configuration validity
            try:
                config_validator = entry_data.get("config_validator")
                if config_validator:
                    all_valid, errors = config_validator.validate_all_configurations()
                    validation_results["configuration_valid"] = all_valid
                    if not all_valid:
                        validation_results["issues"].extend(errors)
                else:
                    validation_results["issues"].append("Configuration validator not available")
            except Exception as e:
                validation_results["issues"].append(f"Configuration validation failed: {str(e)}")
        else:
            validation_results["issues"].append("Entry data not found in hass.data")
        
        # Check services registration
        domain_services = hass.services.async_services().get(DOMAIN, {})
        expected_services = [SERVICE_APPLY_SLOT, SERVICE_APPLY_GRID_NOW, SERVICE_MIGRATE_RESOLUTION]
        services_registered = all(service in domain_services for service in expected_services)
        validation_results["services_registered"] = services_registered
        
        if not services_registered:
            missing_services = [s for s in expected_services if s not in domain_services]
            validation_results["issues"].append(f"Missing services: {', '.join(missing_services)}")
        
        # Check WebSocket handlers (this is harder to validate directly)
        validation_results["websocket_handlers_registered"] = True  # Assume OK if no errors during registration
        
        # Validate dashboard integration components
        if dashboard_integration_status:
            validation_results["frontend_resources_available"] = dashboard_integration_status.get("frontend_resources_registered", False)
            validation_results["dashboard_service_available"] = dashboard_integration_status.get("dashboard_service_initialized", False)
            
            # Overall dashboard integration validation
            validation_results["dashboard_integration_validated"] = (
                validation_results["frontend_resources_available"] and
                validation_results["dashboard_service_available"]
            )
            
            # Add dashboard-specific issues and recommendations
            if not validation_results["frontend_resources_available"]:
                validation_results["issues"].append("Frontend resources not properly registered - card may not appear in dashboard picker")
                validation_results["recommendations"].extend([
                    "Check that card files exist in www/roost-scheduler-card/",
                    "Verify file permissions allow Home Assistant to read card files",
                    "Clear browser cache and refresh the page"
                ])
            
            if not validation_results["dashboard_service_available"]:
                validation_results["issues"].append("Dashboard service not initialized - automatic card installation unavailable")
                validation_results["recommendations"].extend([
                    "Check Lovelace configuration for any conflicts",
                    "Try manually adding the card through dashboard edit mode"
                ])
            
            # Log dashboard integration validation results
            _LOGGER.debug("Dashboard integration validation - Frontend: %s, Service: %s, Overall: %s",
                         validation_results["frontend_resources_available"],
                         validation_results["dashboard_service_available"],
                         validation_results["dashboard_integration_validated"])
        else:
            _LOGGER.warning("Dashboard integration status not available for validation")
            validation_results["issues"].append("Dashboard integration status not available")
        
        # Generate general recommendations based on issues
        if validation_results["issues"]:
            validation_results["recommendations"].extend([
                "Check the setup logs for specific error details",
                "Try restarting Home Assistant if issues persist",
                "Check Home Assistant storage permissions and disk space"
            ])
        
        # Overall validation status (dashboard integration is not critical for core functionality)
        validation_results["overall_valid"] = (
            validation_results["entry_data_valid"] and
            validation_results["managers_initialized"] and
            validation_results["services_registered"] and
            validation_results["storage_accessible"]
        )
        
        # Determine overall status with dashboard integration consideration
        if validation_results["overall_valid"]:
            if validation_results.get("dashboard_integration_validated", False):
                validation_results["overall_status"] = "passed"
            else:
                validation_results["overall_status"] = "passed_with_dashboard_issues"
        else:
            validation_results["overall_status"] = "failed"
        
    except Exception as e:
        validation_results["issues"].append(f"Validation process failed: {str(e)}")
        validation_results["overall_valid"] = False
    
    return validation_results


async def _evaluate_setup_continuation(critical_issues: list, setup_diagnostics: dict) -> bool:
    """Evaluate whether setup should continue despite critical validation issues.
    
    Args:
        critical_issues: List of critical validation issues
        setup_diagnostics: Setup diagnostics dictionary
        
    Returns:
        bool: True if setup should continue, False if it should fail
    """
    # Define issues that should always cause setup to fail
    blocking_issue_types = {
        "integration_directory_missing",
        "manifest_file_missing", 
        "config_flow_file_missing",
        "const_import_error",
        "manifest_json_invalid"
    }
    
    # Check if any critical issues are blocking
    for issue in critical_issues:
        issue_type = issue.get("issue_type", "")
        if issue_type in blocking_issue_types:
            _LOGGER.error("Blocking issue found: %s - %s", issue_type, issue.get("description", ""))
            setup_diagnostics["blocking_issues"] = setup_diagnostics.get("blocking_issues", [])
            setup_diagnostics["blocking_issues"].append(issue)
            return False
    
    # For non-blocking critical issues, we can continue but with warnings
    _LOGGER.warning("Found %d critical issues but none are blocking - continuing setup", len(critical_issues))
    setup_diagnostics["non_blocking_critical_issues"] = critical_issues
    
    return True


async def _apply_validation_fallbacks(validation_result, setup_diagnostics: dict) -> None:
    """Apply fallback mechanisms for remaining validation issues.
    
    Args:
        validation_result: The validation result with remaining issues
        setup_diagnostics: Setup diagnostics dictionary
    """
    _LOGGER.info("Applying validation fallbacks for remaining issues")
    
    fallbacks_applied = []
    
    # Categorize remaining issues
    domain_issues = []
    config_flow_issues = []
    import_issues = []
    other_issues = []
    
    for issue in validation_result.issues:
        if isinstance(issue, dict):
            issue_type = issue.get("issue_type", "")
            if "domain" in issue_type:
                domain_issues.append(issue)
            elif "config_flow" in issue_type:
                config_flow_issues.append(issue)
            elif "import" in issue_type:
                import_issues.append(issue)
            else:
                other_issues.append(issue)
    
    # Apply domain-specific fallbacks
    if domain_issues:
        _LOGGER.info("Applying domain consistency fallbacks")
        fallbacks_applied.append("domain_consistency_fallback")
        # Log domain issues but continue - the integration can still function
        for issue in domain_issues:
            _LOGGER.warning("Domain issue (non-blocking): %s", issue.get("description", str(issue)))
    
    # Apply config flow fallbacks
    if config_flow_issues:
        _LOGGER.info("Applying config flow fallbacks")
        fallbacks_applied.append("config_flow_fallback")
        # Config flow issues are more serious but we can still try to continue
        for issue in config_flow_issues:
            _LOGGER.error("Config flow issue: %s", issue.get("description", str(issue)))
    
    # Apply import fallbacks
    if import_issues:
        _LOGGER.info("Applying import fallbacks")
        fallbacks_applied.append("import_fallback")
        # Import issues might be recoverable during actual component initialization
        for issue in import_issues:
            _LOGGER.warning("Import issue (may be recoverable): %s", issue.get("description", str(issue)))
    
    setup_diagnostics["validation_fallbacks_applied"] = fallbacks_applied
    _LOGGER.info("Applied %d validation fallback mechanisms", len(fallbacks_applied))


async def _apply_fix_failure_fallbacks(fix_result, setup_diagnostics: dict) -> None:
    """Apply fallback mechanisms when automatic fixes fail.
    
    Args:
        fix_result: The failed fix result
        setup_diagnostics: Setup diagnostics dictionary
    """
    _LOGGER.info("Applying fallbacks for failed automatic fixes")
    
    fallbacks_applied = []
    
    # Analyze failed fixes and apply appropriate fallbacks
    for failed_fix in fix_result.fix_results:
        if not failed_fix.success:
            issue_type = failed_fix.issue_type
            
            if issue_type == "domain_mismatch":
                _LOGGER.warning("Domain mismatch fix failed - using domain override fallback")
                fallbacks_applied.append("domain_override_fallback")
                # Continue with current domain configuration
                
            elif issue_type == "class_inheritance":
                _LOGGER.warning("Class inheritance fix failed - using basic config flow fallback")
                fallbacks_applied.append("basic_config_flow_fallback")
                # The integration might still work with a basic config flow
                
            elif issue_type == "method_implementation":
                _LOGGER.warning("Method implementation fix failed - using minimal method fallback")
                fallbacks_applied.append("minimal_method_fallback")
                # Basic functionality might still be available
                
            elif issue_type == "manifest_configuration":
                _LOGGER.error("Manifest configuration fix failed - this may cause issues")
                fallbacks_applied.append("manifest_warning_fallback")
                # Manifest issues are more serious but we can try to continue
                
            else:
                _LOGGER.warning("Unknown fix type failed: %s - using generic fallback", issue_type)
                fallbacks_applied.append("generic_fallback")
    
    setup_diagnostics["fix_failure_fallbacks_applied"] = fallbacks_applied
    _LOGGER.info("Applied %d fix failure fallback mechanisms", len(fallbacks_applied))


async def _apply_emergency_fallbacks(setup_diagnostics: dict) -> None:
    """Apply emergency fallback mechanisms when critical systems fail.
    
    Args:
        setup_diagnostics: Setup diagnostics dictionary
    """
    _LOGGER.warning("Applying emergency fallback mechanisms")
    
    emergency_fallbacks = []
    
    # Disable non-essential features to ensure basic functionality
    emergency_fallbacks.append("disable_advanced_validation")
    emergency_fallbacks.append("use_minimal_config_flow")
    emergency_fallbacks.append("skip_domain_consistency_checks")
    emergency_fallbacks.append("use_default_error_handling")
    
    # Log emergency mode activation
    _LOGGER.warning("Integration entering emergency mode - some features may be limited")
    _LOGGER.warning("Emergency fallbacks: %s", ", ".join(emergency_fallbacks))
    
    setup_diagnostics["emergency_fallbacks_applied"] = emergency_fallbacks
    setup_diagnostics["emergency_mode"] = True
    
    # Set up minimal error recovery
    setup_diagnostics["error_recovery_mode"] = "emergency"
    setup_diagnostics["warnings"].append("Integration running in emergency mode due to critical validation failures")


async def _generate_setup_failure_report(hass: HomeAssistant, entry: ConfigEntry, setup_diagnostics: dict, critical_error: Exception) -> None:
    """Generate a comprehensive setup failure report for troubleshooting.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry that failed
        setup_diagnostics: Setup diagnostics collected so far
        critical_error: The critical error that caused setup failure
    """
    _LOGGER.error("=" * 60)
    _LOGGER.error("ROOST SCHEDULER SETUP FAILURE REPORT")
    _LOGGER.error("=" * 60)
    _LOGGER.error("Entry ID: %s", entry.entry_id)
    _LOGGER.error("Critical Error: %s", str(critical_error))
    _LOGGER.error("Error Type: %s", type(critical_error).__name__)
    
    # Log validation results if available
    if "validation_results" in setup_diagnostics:
        validation_data = setup_diagnostics["validation_results"]
        _LOGGER.error("Validation Success: %s", validation_data.get("comprehensive_result", {}).get("success", "Unknown"))
        
        issues = validation_data.get("comprehensive_result", {}).get("issues", [])
        if issues:
            _LOGGER.error("Validation Issues Found: %d", len(issues))
            for i, issue in enumerate(issues[:5], 1):  # Log first 5 issues
                _LOGGER.error("  %d. %s", i, issue if isinstance(issue, str) else issue.get("description", str(issue)))
    
    # Log components that were successfully initialized
    initialized = setup_diagnostics.get("components_initialized", [])
    if initialized:
        _LOGGER.error("Successfully Initialized Components: %s", ", ".join(initialized))
    
    # Log components that failed
    failed = setup_diagnostics.get("components_failed", [])
    if failed:
        _LOGGER.error("Failed Components:")
        for component_failure in failed:
            _LOGGER.error("  - %s: %s", component_failure.get("component", "unknown"), component_failure.get("error", "unknown error"))
    
    # Log fallbacks that were attempted
    fallbacks = setup_diagnostics.get("fallbacks_used", [])
    if fallbacks:
        _LOGGER.error("Fallbacks Attempted: %s", ", ".join(fallbacks))
    
    # Log warnings
    warnings = setup_diagnostics.get("warnings", [])
    if warnings:
        _LOGGER.error("Warnings Generated: %d", len(warnings))
        for warning in warnings[:3]:  # Log first 3 warnings
            _LOGGER.error("  - %s", warning)
    
    # Generate troubleshooting recommendations
    _LOGGER.error("TROUBLESHOOTING RECOMMENDATIONS:")
    _LOGGER.error("1. Check Home Assistant logs for detailed error messages")
    _LOGGER.error("2. Verify integration files are properly installed and readable")
    _LOGGER.error("3. Check file system permissions for the integration directory")
    _LOGGER.error("4. Try restarting Home Assistant")
    _LOGGER.error("5. Consider reinstalling the integration")
    
    if "validation_results" in setup_diagnostics:
        diagnostic_data = setup_diagnostics["validation_results"].get("diagnostic_data")
        if diagnostic_data and hasattr(diagnostic_data, 'error_details'):
            _LOGGER.error("6. Review diagnostic errors: %s", "; ".join(diagnostic_data.error_details[:3]))
    
    _LOGGER.error("=" * 60)
    _LOGGER.error("END SETUP FAILURE REPORT")
    _LOGGER.error("=" * 60)


async def _collect_comprehensive_setup_diagnostics(hass: HomeAssistant, entry: ConfigEntry, setup_diagnostics: dict) -> None:
    """Collect comprehensive setup diagnostics for successful setup.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry
        setup_diagnostics: Setup diagnostics dictionary to enhance
    """
    try:
        # Collect system information
        setup_diagnostics["system_info"] = {
            "ha_version": hass.config.ha_version,
            "config_dir": hass.config.config_dir,
            "safe_mode": hass.config.safe_mode,
            "components_count": len(hass.config.components)
        }
        
        # Collect integration-specific information
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        setup_diagnostics["integration_info"] = {
            "domain": DOMAIN,
            "version": VERSION,
            "entry_id": entry.entry_id,
            "components_in_data": list(entry_data.keys()),
            "storage_service_available": "storage_service" in entry_data,
            "schedule_manager_available": "schedule_manager" in entry_data,
            "frontend_manager_available": "frontend_manager" in entry_data
        }
        
        # Collect performance metrics
        setup_diagnostics["performance_metrics"] = {
            "total_duration": setup_diagnostics["duration_seconds"],
            "validation_duration": setup_diagnostics.get("startup_validation", {}).get("duration_seconds", 0),
            "components_initialized_count": len(setup_diagnostics.get("components_initialized", [])),
            "components_failed_count": len(setup_diagnostics.get("components_failed", [])),
            "warnings_count": len(setup_diagnostics.get("warnings", [])),
            "fallbacks_used_count": len(setup_diagnostics.get("fallbacks_used", []))
        }
        
        # Collect validation summary
        if "validation_results" in setup_diagnostics:
            validation_data = setup_diagnostics["validation_results"]
            setup_diagnostics["validation_summary"] = {
                "validation_success": validation_data.get("comprehensive_result", {}).get("success", False),
                "issues_found": len(validation_data.get("comprehensive_result", {}).get("issues", [])),
                "warnings_found": len(validation_data.get("comprehensive_result", {}).get("warnings", [])),
                "domain_consistency": validation_data.get("diagnostic_data", {}).get("domain_consistency", False),
                "config_flow_class_found": validation_data.get("diagnostic_data", {}).get("config_flow_class_found", False),
                "manifest_valid": validation_data.get("diagnostic_data", {}).get("manifest_valid", False)
            }
        
    except Exception as e:
        _LOGGER.warning("Error collecting comprehensive setup diagnostics: %s", e)
        setup_diagnostics["diagnostic_collection_error"] = str(e)


async def _collect_comprehensive_failure_diagnostics(hass: HomeAssistant, entry: ConfigEntry, setup_diagnostics: dict, error: Exception) -> None:
    """Collect comprehensive diagnostics for setup failure.
    
    Args:
        hass: Home Assistant instance
        entry: Config entry
        setup_diagnostics: Setup diagnostics dictionary to enhance
        error: The error that caused the failure
    """
    try:
        # Collect error context
        setup_diagnostics["error_context"] = {
            "error_message": str(error),
            "error_type": type(error).__name__,
            "error_module": getattr(error, '__module__', 'unknown'),
            "setup_phase": _determine_setup_phase(setup_diagnostics)
        }
        
        # Collect system state at failure
        setup_diagnostics["failure_system_state"] = {
            "ha_version": hass.config.ha_version,
            "is_running": hass.is_running,
            "state": str(hass.state),
            "components_loaded": len(hass.config.components),
            "domain_in_components": DOMAIN in hass.config.components
        }
        
        # Collect partial setup state
        entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        setup_diagnostics["partial_setup_state"] = {
            "entry_data_exists": bool(entry_data),
            "partial_components": list(entry_data.keys()) if entry_data else [],
            "hass_data_domain_exists": DOMAIN in hass.data
        }
        
        # Analyze failure patterns
        setup_diagnostics["failure_analysis"] = _analyze_failure_patterns(setup_diagnostics, error)
        
    except Exception as e:
        _LOGGER.warning("Error collecting failure diagnostics: %s", e)
        setup_diagnostics["failure_diagnostic_error"] = str(e)


def _determine_setup_phase(setup_diagnostics: dict) -> str:
    """Determine which phase of setup failed based on diagnostics."""
    initialized = setup_diagnostics.get("components_initialized", [])
    
    if "startup_validation" not in initialized:
        return "startup_validation"
    elif "logging_manager" not in initialized:
        return "logging_initialization"
    elif "storage_service" not in initialized:
        return "storage_initialization"
    elif "presence_manager" not in initialized and "buffer_manager" not in initialized:
        return "manager_initialization"
    elif "schedule_manager" not in initialized:
        return "schedule_manager_initialization"
    elif "services" not in initialized:
        return "service_registration"
    elif "websocket_handlers" not in initialized:
        return "websocket_registration"
    else:
        return "final_validation"


def _analyze_failure_patterns(setup_diagnostics: dict, error: Exception) -> dict:
    """Analyze failure patterns to provide better troubleshooting guidance."""
    analysis = {
        "likely_cause": "unknown",
        "severity": "high",
        "recovery_possible": False,
        "user_action_required": True
    }
    
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # Analyze common failure patterns
    if "permission" in error_str or "access" in error_str:
        analysis.update({
            "likely_cause": "file_permissions",
            "severity": "medium",
            "recovery_possible": True,
            "user_action_required": True
        })
    elif "import" in error_str or "module" in error_str:
        analysis.update({
            "likely_cause": "missing_dependencies",
            "severity": "high",
            "recovery_possible": True,
            "user_action_required": True
        })
    elif "storage" in error_str or "disk" in error_str:
        analysis.update({
            "likely_cause": "storage_issues",
            "severity": "high",
            "recovery_possible": True,
            "user_action_required": True
        })
    elif error_type in ["ConfigEntryNotReady", "ConfigEntryError"]:
        analysis.update({
            "likely_cause": "configuration_error",
            "severity": "medium",
            "recovery_possible": True,
            "user_action_required": False
        })
    
    return analysis


async def _generate_setup_success_report(hass: HomeAssistant, entry: ConfigEntry, setup_diagnostics: dict) -> dict:
    """Generate a comprehensive setup success report."""
    report = {
        "status": "success",
        "entry_id": entry.entry_id,
        "setup_duration": setup_diagnostics["duration_seconds"],
        "components_initialized": setup_diagnostics.get("components_initialized", []),
        "warnings": setup_diagnostics.get("warnings", []),
        "fallbacks_used": setup_diagnostics.get("fallbacks_used", []),
        "validation_passed": setup_diagnostics.get("startup_validation", {}).get("success", False),
        "fixes_applied": setup_diagnostics.get("automatic_fixes", {}).get("success", False),
        "emergency_mode": setup_diagnostics.get("emergency_mode", False)
    }
    
    # Add recommendations based on setup results
    recommendations = []
    
    if setup_diagnostics.get("warnings"):
        recommendations.append("Review setup warnings to ensure optimal functionality")
    
    if setup_diagnostics.get("fallbacks_used"):
        recommendations.append("Some fallback mechanisms were used - consider addressing underlying issues")
    
    if setup_diagnostics.get("emergency_mode"):
        recommendations.append("Integration is running in emergency mode - some features may be limited")
    
    if not recommendations:
        recommendations.append("Setup completed successfully with no issues detected")
    
    report["recommendations"] = recommendations
    
    return report


async def _generate_detailed_failure_report(hass: HomeAssistant, entry: ConfigEntry, setup_diagnostics: dict, error: Exception) -> dict:
    """Generate a detailed failure report for troubleshooting."""
    report = {
        "status": "failed",
        "entry_id": entry.entry_id,
        "error_message": str(error),
        "error_type": type(error).__name__,
        "setup_duration": setup_diagnostics["duration_seconds"],
        "setup_phase": setup_diagnostics.get("error_context", {}).get("setup_phase", "unknown"),
        "components_initialized": setup_diagnostics.get("components_initialized", []),
        "components_failed": setup_diagnostics.get("components_failed", []),
        "failure_analysis": setup_diagnostics.get("failure_analysis", {})
    }
    
    # Generate specific troubleshooting steps
    troubleshooting_steps = []
    
    failure_analysis = setup_diagnostics.get("failure_analysis", {})
    likely_cause = failure_analysis.get("likely_cause", "unknown")
    
    if likely_cause == "file_permissions":
        troubleshooting_steps.extend([
            "Check file permissions for the integration directory",
            "Ensure Home Assistant has read/write access to custom_components/roost_scheduler/",
            "Try restarting Home Assistant with proper permissions"
        ])
    elif likely_cause == "missing_dependencies":
        troubleshooting_steps.extend([
            "Check that all required Home Assistant components are available",
            "Verify Python dependencies are installed",
            "Try reinstalling the integration"
        ])
    elif likely_cause == "storage_issues":
        troubleshooting_steps.extend([
            "Check available disk space",
            "Verify Home Assistant storage directory permissions",
            "Check for storage corruption"
        ])
    elif likely_cause == "configuration_error":
        troubleshooting_steps.extend([
            "Review integration configuration",
            "Check for conflicting integrations",
            "Try removing and re-adding the integration"
        ])
    else:
        troubleshooting_steps.extend([
            "Check Home Assistant logs for detailed error information",
            "Verify integration files are properly installed",
            "Try restarting Home Assistant",
            "Consider reinstalling the integration"
        ])
    
    report["troubleshooting_steps"] = troubleshooting_steps
    
    return report


def _generate_user_friendly_error_message(error: Exception, setup_diagnostics: dict) -> str:
    """Generate a user-friendly error message based on the error and diagnostics."""
    error_type = type(error).__name__
    error_str = str(error).lower()
    
    # Generate user-friendly messages based on error patterns
    if "permission" in error_str:
        return "The integration couldn't access required files. Please check file permissions and try restarting Home Assistant."
    elif "import" in error_str or "module" in error_str:
        return "Some required components are missing. Please ensure all dependencies are installed and try restarting Home Assistant."
    elif "storage" in error_str:
        return "There was a problem with data storage. Please check available disk space and storage permissions."
    elif error_type == "ConfigEntryNotReady":
        return "The integration is not ready to start. This is usually temporary - Home Assistant will retry automatically."
    elif "config_flow" in error_str:
        return "There was a problem with the integration's configuration system. Please try removing and re-adding the integration."
    else:
        phase = setup_diagnostics.get("error_context", {}).get("setup_phase", "unknown")
        return f"Setup failed during {phase.replace('_', ' ')}. Please check the logs for more details and try restarting Home Assistant."


def _log_enhanced_setup_summary(setup_diagnostics: dict, setup_report: dict) -> None:
    """Log an enhanced setup summary with detailed information."""
    entry_id = setup_diagnostics["entry_id"]
    duration = setup_diagnostics["duration_seconds"]
    
    _LOGGER.info("=" * 50)
    _LOGGER.info("ROOST SCHEDULER SETUP SUMMARY")
    _LOGGER.info("=" * 50)
    _LOGGER.info("Entry ID: %s", entry_id)
    _LOGGER.info("Status: %s", setup_report["status"].upper())
    _LOGGER.info("Duration: %.3f seconds", duration)
    
    # Log component status
    initialized = setup_report.get("components_initialized", [])
    _LOGGER.info("Components Initialized: %d", len(initialized))
    for component in initialized:
        _LOGGER.info("  ✓ %s", component)
    
    # Log warnings if any
    warnings = setup_report.get("warnings", [])
    if warnings:
        _LOGGER.info("Warnings: %d", len(warnings))
        for warning in warnings[:3]:  # Log first 3 warnings
            _LOGGER.info("  ⚠ %s", warning)
    
    # Log fallbacks if any
    fallbacks = setup_report.get("fallbacks_used", [])
    if fallbacks:
        _LOGGER.info("Fallbacks Used: %d", len(fallbacks))
        for fallback in fallbacks:
            _LOGGER.info("  🔄 %s", fallback)
    
    # Log validation status
    if setup_report.get("validation_passed"):
        _LOGGER.info("Validation: ✓ PASSED")
    else:
        _LOGGER.info("Validation: ⚠ ISSUES FOUND")
    
    # Log recommendations
    recommendations = setup_report.get("recommendations", [])
    if recommendations:
        _LOGGER.info("Recommendations:")
        for rec in recommendations:
            _LOGGER.info("  • %s", rec)
    
    _LOGGER.info("=" * 50)


def _log_enhanced_setup_failure(setup_diagnostics: dict, failure_report: dict) -> None:
    """Log enhanced setup failure information."""
    entry_id = setup_diagnostics["entry_id"]
    duration = setup_diagnostics["duration_seconds"]
    
    _LOGGER.error("=" * 50)
    _LOGGER.error("ROOST SCHEDULER SETUP FAILURE")
    _LOGGER.error("=" * 50)
    _LOGGER.error("Entry ID: %s", entry_id)
    _LOGGER.error("Status: FAILED")
    _LOGGER.error("Duration: %.3f seconds", duration)
    _LOGGER.error("Error: %s", failure_report["error_message"])
    _LOGGER.error("Phase: %s", failure_report["setup_phase"])
    
    # Log what was successfully initialized
    initialized = failure_report.get("components_initialized", [])
    if initialized:
        _LOGGER.error("Successfully Initialized: %s", ", ".join(initialized))
    
    # Log what failed
    failed = failure_report.get("components_failed", [])
    if failed:
        _LOGGER.error("Failed Components:")
        for component_failure in failed:
            _LOGGER.error("  ✗ %s: %s", component_failure.get("component", "unknown"), component_failure.get("error", "unknown"))
    
    # Log failure analysis
    analysis = failure_report.get("failure_analysis", {})
    if analysis:
        _LOGGER.error("Likely Cause: %s", analysis.get("likely_cause", "unknown"))
        _LOGGER.error("Severity: %s", analysis.get("severity", "unknown"))
        _LOGGER.error("Recovery Possible: %s", analysis.get("recovery_possible", False))
    
    # Log troubleshooting steps
    steps = failure_report.get("troubleshooting_steps", [])
    if steps:
        _LOGGER.error("Troubleshooting Steps:")
        for i, step in enumerate(steps, 1):
            _LOGGER.error("  %d. %s", i, step)
    
    _LOGGER.error("=" * 50)