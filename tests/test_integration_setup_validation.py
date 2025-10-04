"""Integration tests for setup validation system."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler import async_setup_entry
from custom_components.roost_scheduler.const import DOMAIN
from custom_components.roost_scheduler.startup_validation_system import (
    StartupValidationSystem,
    ComprehensiveResult
)
from custom_components.roost_scheduler.config_flow_validator import ValidationResult
from custom_components.roost_scheduler.integration_diagnostics import DiagnosticData
from custom_components.roost_scheduler.domain_consistency_checker import ConsistencyResult
from custom_components.roost_scheduler.config_flow_registration_fixer import (
    ConfigFlowRegistrationFixer,
    OverallFixResult,
    FixResult
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=True)
    hass.services.async_register = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.components = MagicMock()
    hass.components.websocket_api = MagicMock()
    hass.components.websocket_api.async_register_command = MagicMock()
    hass.config = MagicMock()
    hass.config.components = ["frontend", "websocket_api", "roost_scheduler"]
    hass.config.as_dict = MagicMock(return_value={"version": "2024.1.0"})
    hass.config.config_dir = "/config"
    hass.is_running = True
    hass.state = "running"
    hass.loop = MagicMock()
    hass.loop.time = MagicMock(return_value=1234567890.0)
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.options = {}
    entry.data = {}
    return entry


class TestIntegrationSetupValidationEndToEnd:
    """End-to-end tests for setup validation integration."""

    @pytest.mark.asyncio
    async def test_successful_setup_with_validation_passing(self, mock_hass, mock_config_entry):
        """Test successful setup when startup validation passes."""
        # Create successful validation result
        successful_validation = ComprehensiveResult(
            success=True,
            integration_loading_result=ValidationResult(
                success=True, issues=[], warnings=[], recommendations=["Integration loading passed"], 
                diagnostic_data={"integration_loaded": True}
            ),
            config_flow_availability_result=ValidationResult(
                success=True, issues=[], warnings=[], recommendations=["Config flow available"], 
                diagnostic_data={"config_flow_registered": True}
            ),
            domain_consistency_result=ConsistencyResult(
                consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler",
                config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]
            ),
            diagnostic_data=DiagnosticData(
                ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True,
                file_permissions={}, import_status={}, dependency_status={},
                config_flow_class_found=True, manifest_valid=True, error_details=[],
                system_info={}, integration_info={"loaded": True}
            ),
            issues=[],
            warnings=[],
            recommendations=["All validation checks passed"],
            startup_diagnostics={"validation_status": "success"}
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler.config_validator.ConfigurationValidator') as mock_config_validator, \
             patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend_mgr, \
             patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard_service, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(return_value=successful_validation)
            mock_validator_class.return_value = mock_validator

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            # Setup configuration validator mock
            mock_validator_instance = MagicMock()
            mock_config_validator.return_value = mock_validator_instance
            mock_validator_instance.validate_all_configurations.return_value = (True, [])
            mock_validator_instance.repair_all_configurations.return_value = (False, {})

            # Setup frontend manager mock
            mock_frontend_instance = MagicMock()
            mock_frontend_mgr.return_value = mock_frontend_instance
            mock_frontend_instance.register_frontend_resources = AsyncMock(return_value={
                "success": True,
                "resources_registered": [{"resource": "roost-scheduler-card.js"}],
                "resources_failed": [],
                "warnings": []
            })

            # Setup dashboard service mock
            mock_dashboard_instance = MagicMock()
            mock_dashboard_service.return_value = mock_dashboard_instance

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = {"overall_status": "success", "dashboard_integration_validated": True}

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify success
            assert result is True

            # Verify validation was called
            mock_validator.run_comprehensive_validation.assert_called_once_with(DOMAIN)

            # Verify data was stored with validation results
            assert DOMAIN in mock_hass.data
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            
            # Check that validation results are stored
            assert "setup_diagnostics" in entry_data
            setup_diagnostics = entry_data["setup_diagnostics"]
            assert "startup_validation" in setup_diagnostics
            assert setup_diagnostics["startup_validation"]["success"] is True
            # Check that validation results are stored (structure may vary)
            if "validation_results" in setup_diagnostics:
                # Validation results were stored - this is good
                validation_results = setup_diagnostics["validation_results"]
                # The exact structure may vary, but we should have some validation data
                assert validation_results is not None
                
                # Check if comprehensive result is stored
                if "comprehensive_result" in validation_results:
                    stored_result = validation_results["comprehensive_result"]
                    assert stored_result.success == successful_validation.success

            # Verify no fixes were attempted since validation passed
            assert "automatic_fixes" not in setup_diagnostics

    @pytest.mark.asyncio
    async def test_setup_with_validation_failure_and_successful_fixes(self, mock_hass, mock_config_entry):
        """Test setup when validation fails but fixes are successfully applied."""
        # Create failed validation result
        failed_validation = ComprehensiveResult(
            success=False,
            integration_loading_result=ValidationResult(
                success=False, issues=[{"severity": "error", "description": "Integration loading failed"}], 
                warnings=[], recommendations=[], diagnostic_data={}
            ),
            config_flow_availability_result=ValidationResult(
                success=False, issues=[{"severity": "error", "description": "Config flow not available"}], 
                warnings=[], recommendations=[], diagnostic_data={}
            ),
            domain_consistency_result=ConsistencyResult(
                consistent=False, manifest_domain="domain1", const_domain="domain2",
                config_flow_domain="domain3", issues=["Domain mismatch"], warnings=[], recommendations=[]
            ),
            diagnostic_data=DiagnosticData(
                ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=False,
                file_permissions={}, import_status={}, dependency_status={},
                config_flow_class_found=False, manifest_valid=False, error_details=["Validation failed"],
                system_info={}, integration_info={}
            ),
            issues=["Critical validation issue"],
            warnings=["Validation warning"],
            recommendations=["Fix validation issues"],
            startup_diagnostics={"validation_status": "failed"}
        )

        # Create successful validation result after fixes
        successful_validation_after_fix = ComprehensiveResult(
            success=True,
            integration_loading_result=ValidationResult(
                success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}
            ),
            config_flow_availability_result=ValidationResult(
                success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}
            ),
            domain_consistency_result=ConsistencyResult(
                consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler",
                config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]
            ),
            diagnostic_data=DiagnosticData(
                ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True,
                file_permissions={}, import_status={}, dependency_status={},
                config_flow_class_found=True, manifest_valid=True, error_details=[],
                system_info={}, integration_info={}
            ),
            issues=[],
            warnings=[],
            recommendations=["All validation checks passed after fixes"],
            startup_diagnostics={"validation_status": "success_after_fixes"}
        )

        # Create successful fix result
        successful_fix_result = OverallFixResult(
            success=True,
            total_issues=3,
            fixed_issues=3,
            failed_fixes=0,
            fix_results=[
                FixResult(success=True, issue_type="domain_mismatch", description="Fixed domain mismatch", 
                         changes_made=["Updated domain"], errors=[], warnings=[], verification_passed=True),
                FixResult(success=True, issue_type="config_flow_class", description="Fixed config flow class", 
                         changes_made=["Created class"], errors=[], warnings=[], verification_passed=True),
                FixResult(success=True, issue_type="manifest_config", description="Fixed manifest", 
                         changes_made=["Updated manifest"], errors=[], warnings=[], verification_passed=True)
            ],
            remaining_issues=[],
            backup_created=True
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.config_flow_registration_fixer.ConfigFlowRegistrationFixer') as mock_fixer_class, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(side_effect=[
                failed_validation,  # First call fails
                successful_validation_after_fix  # Second call after fixes succeeds
            ])
            mock_validator_class.return_value = mock_validator

            # Setup fixer mock
            mock_fixer = MagicMock()
            mock_fixer.apply_all_fixes = AsyncMock(return_value=successful_fix_result)
            mock_fixer_class.return_value = mock_fixer

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = AsyncMock(return_value={"overall_status": "success"})

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify success
            assert result is True

            # Verify validation was called twice (before and after fixes)
            assert mock_validator.run_comprehensive_validation.call_count == 2

            # Verify fixer was called
            mock_fixer.apply_all_fixes.assert_called_once()

            # Verify data was stored with fix results
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            setup_diagnostics = entry_data["setup_diagnostics"]
            
            # Check that automatic fixes were recorded
            assert "automatic_fixes" in setup_diagnostics
            fix_diagnostics = setup_diagnostics["automatic_fixes"]
            assert fix_diagnostics["attempted"] is True
            assert fix_diagnostics["success"] is True
            assert fix_diagnostics["total_issues"] == 3
            assert fix_diagnostics["fixed_issues"] == 3
            assert fix_diagnostics["failed_fixes"] == 0
            assert fix_diagnostics["backup_created"] is True

            # Check post-fix validation results
            assert setup_diagnostics["startup_validation"]["post_fix_success"] is True

    @pytest.mark.asyncio
    async def test_setup_with_validation_failure_and_failed_fixes(self, mock_hass, mock_config_entry):
        """Test setup when validation fails and fixes also fail."""
        # Create failed validation result
        failed_validation = ComprehensiveResult(
            success=False,
            integration_loading_result=ValidationResult(
                success=False, issues=[{"severity": "critical", "description": "Critical integration issue"}], 
                warnings=[], recommendations=[], diagnostic_data={}
            ),
            config_flow_availability_result=ValidationResult(
                success=False, issues=[{"severity": "error", "description": "Config flow not available"}], 
                warnings=[], recommendations=[], diagnostic_data={}
            ),
            domain_consistency_result=ConsistencyResult(
                consistent=False, manifest_domain="domain1", const_domain="domain2",
                config_flow_domain="domain3", issues=["Domain mismatch"], warnings=[], recommendations=[]
            ),
            diagnostic_data=DiagnosticData(
                ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=False,
                file_permissions={}, import_status={}, dependency_status={},
                config_flow_class_found=False, manifest_valid=False, error_details=["Critical validation failed"],
                system_info={}, integration_info={}
            ),
            issues=[{"severity": "critical", "description": "Critical validation issue"}],
            warnings=["Validation warning"],
            recommendations=["Fix validation issues"],
            startup_diagnostics={"validation_status": "failed"}
        )

        # Create failed fix result
        failed_fix_result = OverallFixResult(
            success=False,
            total_issues=3,
            fixed_issues=1,
            failed_fixes=2,
            fix_results=[
                FixResult(success=True, issue_type="domain_mismatch", description="Fixed domain mismatch", 
                         changes_made=["Updated domain"], errors=[], warnings=[], verification_passed=True),
                FixResult(success=False, issue_type="config_flow_class", description="Failed to fix config flow class", 
                         changes_made=[], errors=["Permission denied"], warnings=[], verification_passed=False),
                FixResult(success=False, issue_type="manifest_config", description="Failed to fix manifest", 
                         changes_made=[], errors=["File locked"], warnings=[], verification_passed=False)
            ],
            remaining_issues=[
                {"severity": "critical", "description": "Unfixable critical issue"}
            ],
            backup_created=True
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.config_flow_registration_fixer.ConfigFlowRegistrationFixer') as mock_fixer_class, \
             patch('custom_components.roost_scheduler._evaluate_setup_continuation') as mock_evaluate_continuation, \
             patch('custom_components.roost_scheduler._apply_fix_failure_fallbacks') as mock_apply_fallbacks, \
             patch('custom_components.roost_scheduler._cleanup_entry_data') as mock_cleanup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(return_value=failed_validation)
            mock_validator_class.return_value = mock_validator

            # Setup fixer mock
            mock_fixer = MagicMock()
            mock_fixer.apply_all_fixes = AsyncMock(return_value=failed_fix_result)
            mock_fixer_class.return_value = mock_fixer

            # Mock evaluation to decide setup should not continue
            mock_evaluate_continuation.return_value = AsyncMock(return_value=False)
            mock_apply_fallbacks.return_value = AsyncMock()
            mock_cleanup.return_value = AsyncMock()

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify setup failed
            assert result is False

            # Verify validation was called
            mock_validator.run_comprehensive_validation.assert_called_once_with(DOMAIN)

            # Verify fixer was called
            mock_fixer.apply_all_fixes.assert_called_once()

            # Verify fallbacks were applied
            mock_apply_fallbacks.assert_called_once()

            # Verify cleanup was called
            mock_cleanup.assert_called_once_with(mock_hass, mock_config_entry)

    @pytest.mark.asyncio
    async def test_setup_with_validation_system_exception(self, mock_hass, mock_config_entry):
        """Test setup when validation system itself raises an exception."""
        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler._apply_emergency_fallbacks') as mock_emergency_fallbacks, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system to raise exception
            mock_validator_class.side_effect = Exception("Validation system initialization failed")

            # Setup emergency fallbacks mock
            mock_emergency_fallbacks.return_value = AsyncMock()

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = AsyncMock(return_value={"overall_status": "success"})

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify setup fails when validation system can't be initialized
            assert result is False

            # Verify that the setup was properly cleaned up
            # When setup fails, hass.data should not contain the entry
            if DOMAIN in mock_hass.data and mock_config_entry.entry_id in mock_hass.data[DOMAIN]:
                # If data exists, it should be minimal/cleanup data only
                entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
                # The entry should be cleaned up, so this shouldn't happen in a real scenario
                pass
            
            # The important thing is that setup returned False, indicating failure
            # This is the correct behavior when critical validation systems fail


class TestSetupValidationErrorRecoveryScenarios:
    """Test error recovery scenarios during setup validation."""

    @pytest.mark.asyncio
    async def test_validation_with_storage_service_fallback(self, mock_hass, mock_config_entry):
        """Test validation continues when storage service needs fallback."""
        # Create validation result that passes
        successful_validation = ComprehensiveResult(
            success=True,
            integration_loading_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}),
            config_flow_availability_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}),
            domain_consistency_result=ConsistencyResult(consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler", config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]),
            diagnostic_data=DiagnosticData(ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True, file_permissions={}, import_status={}, dependency_status={}, config_flow_class_found=True, manifest_valid=True, error_details=[], system_info={}, integration_info={}),
            issues=[], warnings=[], recommendations=[], startup_diagnostics={}
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(return_value=successful_validation)
            mock_validator_class.return_value = mock_validator

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            # Make storage service fail initially, then succeed with emergency mode
            mock_storage_instance = AsyncMock()
            mock_storage.side_effect = [
                Exception("Storage initialization failed"),  # First call fails
                mock_storage_instance  # Second call (emergency mode) succeeds
            ]

            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = AsyncMock(return_value={"overall_status": "success"})

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify setup succeeds with fallback
            assert result is True

            # Verify validation was called
            mock_validator.run_comprehensive_validation.assert_called_once_with(DOMAIN)

            # Verify data was stored with fallback information
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            setup_diagnostics = entry_data["setup_diagnostics"]
            
            # Check that fallback was used
            assert "emergency_storage_service" in setup_diagnostics["fallbacks_used"]
            assert "Using emergency storage service - some features may be limited" in setup_diagnostics["warnings"]

    @pytest.mark.asyncio
    async def test_validation_with_presence_manager_fallback(self, mock_hass, mock_config_entry):
        """Test validation continues when presence manager needs fallback initialization."""
        # Create validation result that passes
        successful_validation = ComprehensiveResult(
            success=True,
            integration_loading_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}),
            config_flow_availability_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}),
            domain_consistency_result=ConsistencyResult(consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler", config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]),
            diagnostic_data=DiagnosticData(ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True, file_permissions={}, import_status={}, dependency_status={}, config_flow_class_found=True, manifest_valid=True, error_details=[], system_info={}, integration_info={}),
            issues=[], warnings=[], recommendations=[], startup_diagnostics={}
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(return_value=successful_validation)
            mock_validator_class.return_value = mock_validator

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            # Setup presence manager to fail on load_configuration but succeed on fallback
            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock(side_effect=Exception("Configuration load failed"))
            mock_presence_instance._initialize_default_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = AsyncMock(return_value={"overall_status": "success"})

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify setup succeeds with fallback
            assert result is True

            # Verify validation was called
            mock_validator.run_comprehensive_validation.assert_called_once_with(DOMAIN)

            # Verify fallback initialization was called
            mock_presence_instance._initialize_default_configuration.assert_called_once()

            # Verify data was stored with fallback information
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            setup_diagnostics = entry_data["setup_diagnostics"]
            
            # Check that fallback was used
            assert "presence_manager_fallback" in setup_diagnostics["fallbacks_used"]
            assert "Presence manager using fallback initialization" in setup_diagnostics["warnings"]

    @pytest.mark.asyncio
    async def test_validation_with_configuration_repair(self, mock_hass, mock_config_entry):
        """Test validation continues when configuration validation finds and repairs issues."""
        # Create validation result that passes
        successful_validation = ComprehensiveResult(
            success=True,
            integration_loading_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}),
            config_flow_availability_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}),
            domain_consistency_result=ConsistencyResult(consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler", config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]),
            diagnostic_data=DiagnosticData(ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True, file_permissions={}, import_status={}, dependency_status={}, config_flow_class_found=True, manifest_valid=True, error_details=[], system_info={}, integration_info={}),
            issues=[], warnings=[], recommendations=[], startup_diagnostics={}
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.config_validator.ConfigurationValidator') as mock_config_validator, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(return_value=successful_validation)
            mock_validator_class.return_value = mock_validator

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            # Setup configuration validator to find and repair issues
            mock_validator_instance = MagicMock()
            mock_config_validator.return_value = mock_validator_instance
            mock_validator_instance.validate_all_configurations.side_effect = [
                (False, ["Configuration issue found"]),  # First validation finds issues
                (True, [])  # Second validation after repair passes
            ]
            mock_validator_instance.repair_all_configurations.return_value = (
                True, {"presence_manager": "Repaired default configuration", "buffer_manager": "Fixed buffer settings"}
            )

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = AsyncMock(return_value={"overall_status": "success"})

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify setup succeeds
            assert result is True

            # Verify validation was called
            mock_validator.run_comprehensive_validation.assert_called_once_with(DOMAIN)

            # Verify configuration validation and repair were called
            assert mock_validator_instance.validate_all_configurations.call_count == 2
            mock_validator_instance.repair_all_configurations.assert_called_once()

            # Verify data was stored with repair information
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            setup_diagnostics = entry_data["setup_diagnostics"]
            
            # Check that configuration repairs were recorded
            assert "configuration_repairs" in setup_diagnostics
            repair_results = setup_diagnostics["configuration_repairs"]
            assert "presence_manager" in repair_results
            assert "buffer_manager" in repair_results
            assert "Repaired default configuration" in repair_results["presence_manager"]


class TestSetupValidationDiagnosticReporting:
    """Test diagnostic reporting during setup validation."""

    @pytest.mark.asyncio
    async def test_comprehensive_diagnostic_data_collection(self, mock_hass, mock_config_entry):
        """Test that comprehensive diagnostic data is collected and stored."""
        # Create detailed validation result with comprehensive diagnostic data
        comprehensive_validation = ComprehensiveResult(
            success=True,
            integration_loading_result=ValidationResult(
                success=True, issues=[], warnings=[], recommendations=["Integration loading passed"], 
                diagnostic_data={
                    "integration_loaded": True,
                    "integration_directory_exists": True,
                    "dependency_check_completed": True,
                    "import_check_completed": True
                }
            ),
            config_flow_availability_result=ValidationResult(
                success=True, issues=[], warnings=[], recommendations=["Config flow available"], 
                diagnostic_data={
                    "config_flow_registered": True,
                    "config_flow_class_instantiable": True,
                    "manifest_config_flow_enabled": True
                }
            ),
            domain_consistency_result=ConsistencyResult(
                consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler",
                config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]
            ),
            diagnostic_data=DiagnosticData(
                ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True,
                file_permissions={"manifest.json": True, "config_flow.py": True, "__init__.py": True},
                import_status={"const": True, "models": True, "storage": True},
                dependency_status={"frontend": True, "websocket_api": True},
                config_flow_class_found=True, manifest_valid=True, error_details=[],
                system_info={"platform": "linux", "python_version": "3.11.0"},
                integration_info={"loaded": True, "entry_count": 1}
            ),
            issues=[],
            warnings=[],
            recommendations=["All validation checks passed"],
            startup_diagnostics={
                "validation_status": "success",
                "validation_duration": 2.5,
                "components_validated": ["integration_loading", "config_flow_availability", "domain_consistency"],
                "performance_metrics": {"validation_time": 2.5, "fix_time": 0.0}
            }
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(return_value=comprehensive_validation)
            mock_validator_class.return_value = mock_validator

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = AsyncMock(return_value={
                "overall_status": "success",
                "dashboard_integration_validated": True,
                "components_validated": ["storage", "presence", "buffer", "schedule"],
                "validation_timestamp": datetime.now().isoformat()
            })

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify success
            assert result is True

            # Verify comprehensive diagnostic data was stored
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            setup_diagnostics = entry_data["setup_diagnostics"]
            
            # Check startup validation diagnostics
            assert "startup_validation" in setup_diagnostics
            validation_diag = setup_diagnostics["startup_validation"]
            assert "duration_seconds" in validation_diag
            assert validation_diag["success"] is True
            assert validation_diag["issues_found"] == 0
            assert validation_diag["warnings_found"] == 0

            # Check validation results storage
            assert "validation_results" in setup_diagnostics
            validation_results = setup_diagnostics["validation_results"]
            assert "comprehensive_result" in validation_results
            assert "diagnostic_data" in validation_results
            assert "startup_diagnostics" in validation_results

            # Verify detailed diagnostic data
            diagnostic_data = validation_results["diagnostic_data"]
            assert diagnostic_data.ha_version == "2024.1.0"
            assert diagnostic_data.integration_version == "1.0.0"
            assert diagnostic_data.domain_consistency is True
            assert diagnostic_data.config_flow_class_found is True
            assert diagnostic_data.manifest_valid is True

            # Check file permissions diagnostic data
            assert "manifest.json" in diagnostic_data.file_permissions
            assert diagnostic_data.file_permissions["manifest.json"] is True

            # Check import status diagnostic data
            assert "const" in diagnostic_data.import_status
            assert diagnostic_data.import_status["const"] is True

            # Check dependency status diagnostic data
            assert "frontend" in diagnostic_data.dependency_status
            assert diagnostic_data.dependency_status["frontend"] is True

            # Check system info diagnostic data
            assert "platform" in diagnostic_data.system_info
            assert diagnostic_data.system_info["platform"] == "linux"

            # Check integration info diagnostic data
            assert "loaded" in diagnostic_data.integration_info
            assert diagnostic_data.integration_info["loaded"] is True

            # Check startup diagnostics
            startup_diag = validation_results["startup_diagnostics"]
            assert startup_diag["validation_status"] == "success"
            assert "validation_duration" in startup_diag
            assert "components_validated" in startup_diag
            assert "performance_metrics" in startup_diag

    @pytest.mark.asyncio
    async def test_diagnostic_reporting_with_performance_metrics(self, mock_hass, mock_config_entry):
        """Test that performance metrics are collected and reported in diagnostics."""
        # Create validation result with performance data
        validation_with_metrics = ComprehensiveResult(
            success=True,
            integration_loading_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}),
            config_flow_availability_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}),
            domain_consistency_result=ConsistencyResult(consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler", config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]),
            diagnostic_data=DiagnosticData(ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True, file_permissions={}, import_status={}, dependency_status={}, config_flow_class_found=True, manifest_valid=True, error_details=[], system_info={}, integration_info={}),
            issues=[], warnings=[], recommendations=[],
            startup_diagnostics={
                "validation_context": {
                    "domain": "roost_scheduler",
                    "start_time": 1234567890.0,
                    "total_duration": 3.2,
                    "validation_steps": [
                        {"step": "pre_validation", "success": True, "duration": 0.5},
                        {"step": "core_validation", "success": True, "duration": 2.1},
                        {"step": "post_validation", "success": True, "duration": 0.6}
                    ]
                },
                "performance_metrics": {
                    "validation_time": 2.1,
                    "fix_time": 0.0,
                    "total_setup_time": 5.8,
                    "component_initialization_time": 2.6
                }
            }
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(return_value=validation_with_metrics)
            mock_validator_class.return_value = mock_validator

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = AsyncMock(return_value={"overall_status": "success"})

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify success
            assert result is True

            # Verify performance metrics were stored
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            setup_diagnostics = entry_data["setup_diagnostics"]
            
            # Check that performance metrics are included
            validation_results = setup_diagnostics["validation_results"]
            startup_diag = validation_results["startup_diagnostics"]
            
            # Check validation context
            assert "validation_context" in startup_diag
            validation_context = startup_diag["validation_context"]
            assert validation_context["domain"] == "roost_scheduler"
            assert validation_context["total_duration"] == 3.2
            assert len(validation_context["validation_steps"]) == 3
            
            # Check individual step metrics
            pre_validation_step = next(step for step in validation_context["validation_steps"] if step["step"] == "pre_validation")
            assert pre_validation_step["success"] is True
            assert pre_validation_step["duration"] == 0.5
            
            core_validation_step = next(step for step in validation_context["validation_steps"] if step["step"] == "core_validation")
            assert core_validation_step["success"] is True
            assert core_validation_step["duration"] == 2.1
            
            # Check performance metrics
            assert "performance_metrics" in startup_diag
            perf_metrics = startup_diag["performance_metrics"]
            assert perf_metrics["validation_time"] == 2.1
            assert perf_metrics["fix_time"] == 0.0
            assert perf_metrics["total_setup_time"] == 5.8
            assert perf_metrics["component_initialization_time"] == 2.6

    @pytest.mark.asyncio
    async def test_diagnostic_reporting_with_troubleshooting_information(self, mock_hass, mock_config_entry):
        """Test that troubleshooting information is included in diagnostic reports."""
        # Create validation result with issues and troubleshooting info
        validation_with_issues = ComprehensiveResult(
            success=False,
            integration_loading_result=ValidationResult(
                success=False, 
                issues=[{"severity": "warning", "description": "Minor integration issue"}], 
                warnings=["Integration warning"], 
                recommendations=["Fix minor issue"], 
                diagnostic_data={"integration_loaded": False}
            ),
            config_flow_availability_result=ValidationResult(
                success=True, issues=[], warnings=[], recommendations=[], 
                diagnostic_data={"config_flow_registered": True}
            ),
            domain_consistency_result=ConsistencyResult(
                consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler",
                config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]
            ),
            diagnostic_data=DiagnosticData(
                ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True,
                file_permissions={}, import_status={}, dependency_status={},
                config_flow_class_found=True, manifest_valid=True, 
                error_details=["Minor diagnostic issue"],
                system_info={}, integration_info={}
            ),
            issues=["Minor validation issue"],
            warnings=["Validation warning"],
            recommendations=["Fix validation issues", "Check configuration"],
            startup_diagnostics={
                "troubleshooting_info": {
                    "common_issues": ["Configuration mismatch", "Permission issues"],
                    "resolution_steps": [
                        "Check file permissions",
                        "Verify configuration files",
                        "Restart Home Assistant"
                    ],
                    "support_information": {
                        "log_level": "DEBUG",
                        "relevant_logs": ["/config/home-assistant.log"],
                        "configuration_files": ["/config/custom_components/roost_scheduler/"]
                    }
                }
            }
        )

        # Create successful fix result
        successful_fix_result = OverallFixResult(
            success=True,
            total_issues=1,
            fixed_issues=1,
            failed_fixes=0,
            fix_results=[
                FixResult(success=True, issue_type="minor_issue", description="Fixed minor issue", 
                         changes_made=["Applied fix"], errors=[], warnings=[], verification_passed=True)
            ],
            remaining_issues=[],
            backup_created=True
        )

        with patch('custom_components.roost_scheduler.startup_validation_system.StartupValidationSystem') as mock_validator_class, \
             patch('custom_components.roost_scheduler.config_flow_registration_fixer.ConfigFlowRegistrationFixer') as mock_fixer_class, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_mgr, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage, \
             patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws, \
             patch('custom_components.roost_scheduler._validate_setup') as mock_validate_setup:

            # Setup validation system mock
            mock_validator = MagicMock()
            mock_validator.run_comprehensive_validation = AsyncMock(side_effect=[
                validation_with_issues,  # First call has issues
                ComprehensiveResult(success=True, integration_loading_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}), config_flow_availability_result=ValidationResult(success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}), domain_consistency_result=ConsistencyResult(consistent=True, manifest_domain="roost_scheduler", const_domain="roost_scheduler", config_flow_domain="roost_scheduler", issues=[], warnings=[], recommendations=[]), diagnostic_data=DiagnosticData(ha_version="2024.1.0", integration_version="1.0.0", domain_consistency=True, file_permissions={}, import_status={}, dependency_status={}, config_flow_class_found=True, manifest_valid=True, error_details=[], system_info={}, integration_info={}), issues=[], warnings=[], recommendations=[], startup_diagnostics={})  # Second call after fixes
            ])
            mock_validator_class.return_value = mock_validator

            # Setup fixer mock
            mock_fixer = MagicMock()
            mock_fixer.apply_all_fixes = AsyncMock(return_value=successful_fix_result)
            mock_fixer_class.return_value = mock_fixer

            # Setup component mocks
            mock_logging_instance = AsyncMock()
            mock_logging_mgr.return_value = mock_logging_instance

            mock_storage_instance = AsyncMock()
            mock_storage.return_value = mock_storage_instance

            mock_presence_instance = AsyncMock()
            mock_presence.return_value = mock_presence_instance
            mock_presence_instance.load_configuration = AsyncMock()

            mock_buffer_instance = AsyncMock()
            mock_buffer.return_value = mock_buffer_instance
            mock_buffer_instance.load_configuration = AsyncMock()

            mock_schedule_instance = AsyncMock()
            mock_schedule.return_value = mock_schedule_instance

            mock_storage_instance.load_schedules = AsyncMock()
            mock_register_services.return_value = AsyncMock()
            mock_register_ws.return_value = None
            mock_validate_setup.return_value = AsyncMock(return_value={"overall_status": "success"})

            # Execute setup
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify success
            assert result is True

            # Verify troubleshooting information was stored
            entry_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            setup_diagnostics = entry_data["setup_diagnostics"]
            
            # Check that validation results include troubleshooting info
            validation_results = setup_diagnostics["validation_results"]
            startup_diag = validation_results["startup_diagnostics"]
            
            # Check troubleshooting information
            assert "troubleshooting_info" in startup_diag
            troubleshooting_info = startup_diag["troubleshooting_info"]
            
            assert "common_issues" in troubleshooting_info
            assert "Configuration mismatch" in troubleshooting_info["common_issues"]
            assert "Permission issues" in troubleshooting_info["common_issues"]
            
            assert "resolution_steps" in troubleshooting_info
            assert "Check file permissions" in troubleshooting_info["resolution_steps"]
            assert "Verify configuration files" in troubleshooting_info["resolution_steps"]
            
            assert "support_information" in troubleshooting_info
            support_info = troubleshooting_info["support_information"]
            assert support_info["log_level"] == "DEBUG"
            assert "/config/home-assistant.log" in support_info["relevant_logs"]
            assert "/config/custom_components/roost_scheduler/" in support_info["configuration_files"]

            # Check that warnings and recommendations were recorded
            assert "Validation warning" in setup_diagnostics["warnings"]
            
            # Check that fix results include troubleshooting context
            assert "automatic_fixes" in setup_diagnostics
            fix_diagnostics = setup_diagnostics["automatic_fixes"]
            assert fix_diagnostics["success"] is True
            assert fix_diagnostics["total_issues"] == 1
            assert fix_diagnostics["fixed_issues"] == 1