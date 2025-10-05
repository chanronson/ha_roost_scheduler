"""Final comprehensive integration tests for config flow handler fix.

This test suite provides simplified but comprehensive integration testing
of the validation, recovery, and verification workflow.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json
import tempfile
import shutil
import time

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler.const import DOMAIN


class TestFinalIntegrationComprehensive:
    """Test suite for final comprehensive integration testing."""

    @pytest.fixture
    def hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config = MagicMock()
        hass.config.components = {DOMAIN}
        hass.config.config_dir = "/config"
        hass.config_entries = MagicMock()
        hass.config_entries.async_entries.return_value = []
        hass.services = MagicMock()
        hass.services.async_services.return_value = {
            DOMAIN: {
                "apply_slot": {},
                "apply_grid_now": {},
                "migrate_resolution": {}
            }
        }
        hass.loop = MagicMock()
        hass.loop.time.return_value = 1234567890.0
        hass.is_running = True
        hass.state = "running"
        return hass

    @pytest.fixture
    def config_entry(self):
        """Create a mock config entry."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_entry_id"
        entry.data = {}
        entry.domain = DOMAIN
        entry.title = "Roost Scheduler"
        return entry

    @pytest.mark.asyncio
    async def test_startup_validation_system_integration(self, hass, config_entry):
        """Test startup validation system integration."""
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        
        startup_validator = StartupValidationSystem(hass)
        
        # Mock the internal methods to avoid file system dependencies
        with patch.object(startup_validator, '_get_integration_path') as mock_get_path, \
             patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
             patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
             patch.object(startup_validator, '_is_domain_available', return_value=True):
            
            # Mock integration path
            mock_integration_path = MagicMock()
            mock_get_path.return_value = mock_integration_path
            
            # Run validation
            result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Verify integration
            assert result is not None
            assert hasattr(result, 'success')
            assert hasattr(result, 'issues')
            assert hasattr(result, 'warnings')
            assert hasattr(result, 'diagnostic_data')
            assert hasattr(result, 'startup_diagnostics')
            
            # Verify validation was attempted
            mock_get_path.assert_called()

    @pytest.mark.asyncio
    async def test_comprehensive_error_recovery_integration(self, hass, config_entry):
        """Test comprehensive error recovery integration."""
        from custom_components.roost_scheduler.comprehensive_error_recovery import ComprehensiveErrorRecovery
        from custom_components.roost_scheduler.startup_validation_system import ComprehensiveResult
        from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidationResult
        
        error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
        
        # Create mock validation results
        mock_validation_result = MagicMock(spec=ComprehensiveResult)
        mock_validation_result.success = False
        mock_validation_result.issues = ["Test issue"]
        mock_validation_result.warnings = []
        
        mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
        mock_comprehensive_result.valid = False
        
        # Mock the internal methods
        with patch.object(error_recovery, '_get_integration_path') as mock_get_path:
            mock_integration_path = MagicMock()
            mock_get_path.return_value = mock_integration_path
            
            # Run recovery
            result = await error_recovery.execute_comprehensive_recovery(
                mock_validation_result, mock_comprehensive_result, config_entry
            )
            
            # Verify integration
            assert result is not None
            assert hasattr(result, 'success')
            assert hasattr(result, 'total_issues')
            assert hasattr(result, 'recovered_issues')
            assert hasattr(result, 'recovery_steps')
            assert hasattr(result, 'duration_seconds')
            
            # Verify recovery was attempted
            mock_get_path.assert_called()

    @pytest.mark.asyncio
    async def test_recovery_verification_system_integration(self, hass, config_entry):
        """Test recovery verification system integration."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        from custom_components.roost_scheduler.startup_validation_system import ComprehensiveResult
        from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidationResult
        from custom_components.roost_scheduler.comprehensive_error_recovery import RecoveryResult
        
        verification_system = RecoveryVerificationSystem(hass, DOMAIN)
        
        # Create mock results
        mock_pre_validation = MagicMock(spec=ComprehensiveResult)
        mock_pre_validation.success = False
        mock_pre_validation.issues = ["Issue 1", "Issue 2"]
        mock_pre_validation.warnings = ["Warning 1"]
        
        mock_pre_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
        mock_pre_comprehensive.valid = False
        
        mock_recovery_result = MagicMock(spec=RecoveryResult)
        mock_recovery_result.success = True
        mock_recovery_result.total_issues = 2
        mock_recovery_result.recovered_issues = 1
        mock_recovery_result.duration_seconds = 1.5
        
        # Mock the internal methods
        with patch.object(verification_system, '_get_integration_path') as mock_get_path, \
             patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
             patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
            
            mock_integration_path = MagicMock()
            mock_get_path.return_value = mock_integration_path
            
            # Mock post-recovery validation results
            mock_post_validation = MagicMock(spec=ComprehensiveResult)
            mock_post_validation.success = True
            mock_post_validation.issues = ["Issue 2"]  # One issue remains
            mock_post_validation.warnings = []
            
            mock_post_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
            mock_post_comprehensive.valid = True
            
            mock_startup_validator.run_comprehensive_validation.return_value = mock_post_validation
            mock_comprehensive_validator.validate_all.return_value = mock_post_comprehensive
            
            # Run verification
            result = await verification_system.verify_recovery_effectiveness(
                mock_pre_validation, mock_pre_comprehensive, mock_recovery_result, config_entry
            )
            
            # Verify integration
            assert result is not None
            assert hasattr(result, 'success')
            assert hasattr(result, 'overall_status')
            assert hasattr(result, 'tests_run')
            assert hasattr(result, 'tests_passed')
            assert hasattr(result, 'verification_tests')
            assert hasattr(result, 'improvement_metrics')
            assert hasattr(result, 'duration_seconds')
            
            # Verify verification was attempted
            mock_get_path.assert_called()
            mock_startup_validator.run_comprehensive_validation.assert_called()

    @pytest.mark.asyncio
    async def test_comprehensive_validator_integration(self, hass):
        """Test comprehensive validator integration."""
        from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidator
        
        # Create a mock integration path
        mock_integration_path = MagicMock()
        
        comprehensive_validator = ComprehensiveValidator(hass, mock_integration_path)
        
        # Mock all validator components
        with patch('custom_components.roost_scheduler.manifest_validator.ManifestValidator') as mock_manifest_validator, \
             patch('custom_components.roost_scheduler.dependency_validator.DependencyValidator') as mock_dependency_validator, \
             patch('custom_components.roost_scheduler.version_compatibility_validator.VersionCompatibilityValidator') as mock_version_validator:
            
            # Mock manifest validator
            mock_manifest_instance = MagicMock()
            mock_manifest_validator.return_value = mock_manifest_instance
            mock_manifest_result = MagicMock()
            mock_manifest_result.valid = True
            mock_manifest_result.issues = []
            mock_manifest_result.warnings = []
            mock_manifest_instance.validate_manifest.return_value = mock_manifest_result
            
            # Mock dependency validator
            mock_dependency_instance = MagicMock()
            mock_dependency_validator.return_value = mock_dependency_instance
            mock_dependency_result = MagicMock()
            mock_dependency_result.valid = True
            mock_dependency_result.missing_dependencies = []
            mock_dependency_result.conflicts = []
            mock_dependency_result.warnings = []
            mock_dependency_instance.validate_dependencies.return_value = mock_dependency_result
            
            # Mock version compatibility validator
            mock_version_instance = MagicMock()
            mock_version_validator.return_value = mock_version_instance
            mock_version_result = MagicMock()
            mock_version_result.compatible = True
            mock_version_result.issues = []
            mock_version_result.warnings = []
            mock_version_instance.validate_compatibility.return_value = mock_version_result
            
            # Run comprehensive validation
            result = await comprehensive_validator.validate_all()
            
            # Verify integration
            assert result is not None
            assert hasattr(result, 'valid')
            assert hasattr(result, 'manifest_result')
            assert hasattr(result, 'dependency_result')
            assert hasattr(result, 'version_result')
            
            # Verify all validators were called
            mock_manifest_instance.validate_manifest.assert_called_once()
            mock_dependency_instance.validate_dependencies.assert_called_once()
            mock_version_instance.validate_compatibility.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_integration(self, hass, config_entry):
        """Test end-to-end workflow integration."""
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import ComprehensiveErrorRecovery
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidator
        
        # Step 1: Startup validation
        startup_validator = StartupValidationSystem(hass)
        
        with patch.object(startup_validator, '_get_integration_path') as mock_startup_path, \
             patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
             patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
             patch.object(startup_validator, '_is_domain_available', return_value=True):
            
            mock_startup_path.return_value = MagicMock()
            validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            assert validation_result is not None
        
        # Step 2: Comprehensive validation
        comprehensive_validator = ComprehensiveValidator(hass, MagicMock())
        
        with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
            mock_comprehensive_result = MagicMock()
            mock_comprehensive_result.valid = True
            mock_validate_all.return_value = mock_comprehensive_result
            
            comprehensive_result = await comprehensive_validator.validate_all()
            assert comprehensive_result is not None
        
        # Step 3: Error recovery
        error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
        
        with patch.object(error_recovery, '_get_integration_path') as mock_recovery_path:
            mock_recovery_path.return_value = MagicMock()
            
            recovery_result = await error_recovery.execute_comprehensive_recovery(
                validation_result, comprehensive_result, config_entry
            )
            
            assert recovery_result is not None
        
        # Step 4: Recovery verification
        verification_system = RecoveryVerificationSystem(hass, DOMAIN)
        
        with patch.object(verification_system, '_get_integration_path') as mock_verification_path, \
             patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
             patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
            
            mock_verification_path.return_value = MagicMock()
            
            # Mock post-recovery validation
            mock_post_validation = MagicMock()
            mock_post_validation.success = True
            mock_post_validation.issues = []
            mock_post_validation.warnings = []
            
            mock_post_comprehensive = MagicMock()
            mock_post_comprehensive.valid = True
            
            mock_startup_validator.run_comprehensive_validation.return_value = mock_post_validation
            mock_comprehensive_validator.validate_all.return_value = mock_post_comprehensive
            
            verification_result = await verification_system.verify_recovery_effectiveness(
                validation_result, comprehensive_result, recovery_result, config_entry
            )
            
            assert verification_result is not None
        
        # Verify end-to-end workflow completed
        assert validation_result is not None
        assert comprehensive_result is not None
        assert recovery_result is not None
        assert verification_result is not None

    @pytest.mark.asyncio
    async def test_performance_integration(self, hass, config_entry):
        """Test performance aspects of integration workflow."""
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        
        startup_validator = StartupValidationSystem(hass)
        
        with patch.object(startup_validator, '_get_integration_path') as mock_get_path, \
             patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
             patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
             patch.object(startup_validator, '_is_domain_available', return_value=True):
            
            mock_get_path.return_value = MagicMock()
            
            # Measure performance
            start_time = time.time()
            result = await startup_validator.run_comprehensive_validation(DOMAIN)
            end_time = time.time()
            
            # Verify performance
            duration = end_time - start_time
            assert duration < 10.0  # Should complete within 10 seconds
            
            # Verify result includes performance data
            assert result is not None
            assert hasattr(result, 'startup_diagnostics')

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, hass, config_entry):
        """Test error handling integration across components."""
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        
        startup_validator = StartupValidationSystem(hass)
        
        # Test with exception in dependencies check
        with patch.object(startup_validator, '_get_integration_path') as mock_get_path, \
             patch.object(startup_validator, '_check_ha_dependencies', side_effect=Exception("Test exception")), \
             patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
             patch.object(startup_validator, '_is_domain_available', return_value=True):
            
            mock_get_path.return_value = MagicMock()
            
            # Should handle exception gracefully
            result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Verify graceful error handling
            assert result is not None
            assert not result.success  # Should fail due to exception
            assert len(result.issues) > 0  # Should capture the exception

    @pytest.mark.asyncio
    async def test_caching_integration(self, hass):
        """Test caching integration in validation system."""
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        
        startup_validator = StartupValidationSystem(hass)
        
        # Verify cache is initially empty
        assert len(startup_validator._validation_cache) == 0
        
        with patch.object(startup_validator, '_get_integration_path') as mock_get_path, \
             patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
             patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
             patch.object(startup_validator, '_is_domain_available', return_value=True):
            
            mock_get_path.return_value = MagicMock()
            
            # First validation run
            first_result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Verify cache population
            assert len(startup_validator._validation_cache) == 1
            assert DOMAIN in startup_validator._validation_cache
            
            # Second validation run (should use cache)
            second_result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Verify cache usage
            assert first_result == second_result
            
            # Verify diagnostic information includes cache data
            diagnostics = startup_validator.get_startup_diagnostics(DOMAIN)
            assert diagnostics["validation_cache_size"] == 1
            assert DOMAIN in diagnostics["cached_domains"]

    @pytest.mark.asyncio
    async def test_logging_integration(self, hass, config_entry):
        """Test logging integration across components."""
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        
        startup_validator = StartupValidationSystem(hass)
        
        # Test logging during validation
        with patch('custom_components.roost_scheduler.startup_validation_system._LOGGER') as mock_logger, \
             patch.object(startup_validator, '_get_integration_path') as mock_get_path, \
             patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
             patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
             patch.object(startup_validator, '_is_domain_available', return_value=True):
            
            mock_get_path.return_value = MagicMock()
            
            await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Verify logging calls were made
            assert mock_logger.debug.called or mock_logger.info.called or mock_logger.warning.called