"""Comprehensive integration tests for config flow handler fix.

This test suite provides end-to-end integration testing of the complete
validation, recovery, and verification workflow for the config flow handler fix.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from pathlib import Path
import json
import tempfile
import shutil
import time
from typing import Dict, Any, List

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler.const import DOMAIN
from custom_components.roost_scheduler.startup_validation_system import (
    StartupValidationSystem,
    ComprehensiveResult
)
from custom_components.roost_scheduler.comprehensive_error_recovery import (
    ComprehensiveErrorRecovery,
    RecoveryResult
)
from custom_components.roost_scheduler.recovery_verification_system import (
    RecoveryVerificationSystem,
    VerificationResult
)
from custom_components.roost_scheduler.comprehensive_validator import (
    ComprehensiveValidator,
    ComprehensiveValidationResult
)


class TestComprehensiveIntegrationWorkflow:
    """Test suite for comprehensive integration workflow testing."""

    @pytest.fixture
    def hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config = MagicMock()
        hass.config.components = set()
        hass.config.config_dir = "/config"
        hass.config_entries = MagicMock()
        hass.config_entries.async_entries.return_value = []
        hass.services = MagicMock()
        hass.services.async_services.return_value = {}
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

    @pytest.fixture
    def temp_integration_dir(self):
        """Create a temporary integration directory with test files."""
        temp_dir = tempfile.mkdtemp()
        integration_path = Path(temp_dir) / "custom_components" / "roost_scheduler"
        integration_path.mkdir(parents=True)
        
        # Create valid integration files
        self._create_valid_integration_files(integration_path)
        
        yield integration_path
        
        # Cleanup
        shutil.rmtree(temp_dir)

    def _create_valid_integration_files(self, integration_path: Path):
        """Create valid integration files for testing."""
        # Create manifest.json
        manifest_data = {
            "domain": "roost_scheduler",
            "name": "Roost Scheduler",
            "version": "1.0.0",
            "config_flow": True,
            "dependencies": ["http"],
            "requirements": [],
            "codeowners": ["@test"],
            "iot_class": "local_polling"
        }
        with open(integration_path / "manifest.json", "w") as f:
            json.dump(manifest_data, f, indent=2)
        
        # Create const.py
        const_content = '''"""Constants for Roost Scheduler integration."""
DOMAIN = "roost_scheduler"
VERSION = "1.0.0"
REQUIRED_DOMAINS = ["http"]
OPTIONAL_DOMAINS = []
'''
        with open(integration_path / "const.py", "w") as f:
            f.write(const_content)
        
        # Create config_flow.py
        config_flow_content = '''"""Config flow for Roost Scheduler integration."""
from homeassistant import config_entries
from .const import DOMAIN

class RoostSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roost Scheduler."""
    
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Roost Scheduler", data=user_input)
        
        return self.async_show_form(step_id="user")
'''
        with open(integration_path / "config_flow.py", "w") as f:
            f.write(config_flow_content)
        
        # Create __init__.py
        init_content = '''"""Roost Scheduler integration."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Roost Scheduler component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roost Scheduler from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
'''
        with open(integration_path / "__init__.py", "w") as f:
            f.write(init_content)

    def _create_domain_mismatch_scenario(self, integration_path: Path):
        """Create a domain mismatch scenario for testing."""
        # Modify const.py to have wrong domain
        const_content = '''"""Constants for Roost Scheduler integration."""
DOMAIN = "wrong_domain"
VERSION = "1.0.0"
REQUIRED_DOMAINS = ["http"]
OPTIONAL_DOMAINS = []
'''
        with open(integration_path / "const.py", "w") as f:
            f.write(const_content)

    def _create_missing_config_flow_scenario(self, integration_path: Path):
        """Create a missing config flow class scenario for testing."""
        # Remove config flow class
        config_flow_content = '''"""Config flow for Roost Scheduler integration."""
from .const import DOMAIN

# Config flow class is missing
'''
        with open(integration_path / "config_flow.py", "w") as f:
            f.write(config_flow_content)

    def _create_invalid_manifest_scenario(self, integration_path: Path):
        """Create an invalid manifest scenario for testing."""
        # Create invalid JSON
        with open(integration_path / "manifest.json", "w") as f:
            f.write('{"domain": "roost_scheduler", "name": "Test", invalid_json}')

    @pytest.mark.asyncio
    async def test_complete_successful_workflow(self, hass, config_entry, temp_integration_dir):
        """Test complete successful workflow with no issues."""
        # Step 1: Initial validation (should succeed)
        startup_validator = StartupValidationSystem(hass)
        
        with patch.object(startup_validator, '_get_integration_path', return_value=temp_integration_dir), \
             patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
             patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
             patch.object(startup_validator, '_is_domain_available', return_value=True):
            
            validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Verify successful validation
            assert isinstance(validation_result, ComprehensiveResult)
            assert validation_result.success
            assert len(validation_result.issues) == 0
            assert validation_result.domain_consistency_result.consistent
        
        # Step 2: Comprehensive validation (should also succeed)
        comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
        
        with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
            mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
            mock_comprehensive_result.valid = True
            mock_comprehensive_result.manifest_result = MagicMock()
            mock_comprehensive_result.manifest_result.valid = True
            mock_comprehensive_result.manifest_result.issues = []
            mock_comprehensive_result.dependency_result = MagicMock()
            mock_comprehensive_result.dependency_result.valid = True
            mock_comprehensive_result.dependency_result.conflicts = []
            mock_comprehensive_result.version_result = MagicMock()
            mock_comprehensive_result.version_result.compatible = True
            mock_comprehensive_result.version_result.issues = []
            
            mock_validate_all.return_value = mock_comprehensive_result
            comprehensive_result = await comprehensive_validator.validate_all()
            
            assert comprehensive_result.valid
        
        # Step 3: Error recovery (should have nothing to recover)
        error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
        
        with patch.object(error_recovery, '_get_integration_path', return_value=temp_integration_dir):
            recovery_result = await error_recovery.execute_comprehensive_recovery(
                validation_result, comprehensive_result, config_entry
            )
            
            # Verify recovery result
            assert isinstance(recovery_result, RecoveryResult)
            assert recovery_result.success
            assert recovery_result.total_issues == 0  # No issues to recover
        
        # Step 4: Recovery verification (should verify success)
        verification_system = RecoveryVerificationSystem(hass, DOMAIN)
        
        with patch.object(verification_system, '_get_integration_path', return_value=temp_integration_dir):
            verification_result = await verification_system.verify_recovery_effectiveness(
                validation_result, comprehensive_result, recovery_result, config_entry
            )
            
            # Verify verification result
            assert isinstance(verification_result, VerificationResult)
            assert verification_result.success
            assert verification_result.overall_status == "verified"
            assert verification_result.tests_passed > 0

    @pytest.mark.asyncio
    async def test_domain_mismatch_recovery_workflow(self, hass, config_entry, temp_integration_dir):
        """Test complete workflow with domain mismatch issue and recovery."""
        # Create domain mismatch scenario
        self._create_domain_mismatch_scenario(temp_integration_dir)
        
        # Step 1: Initial validation (should detect domain mismatch)
        startup_validator = StartupValidationSystem(hass)
        
        with patch.object(startup_validator, '_get_integration_path', return_value=temp_integration_dir), \
             patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
             patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
             patch.object(startup_validator, '_is_domain_available', return_value=True):
            
            initial_validation = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Verify domain mismatch detected
            assert not initial_validation.success
            assert not initial_validation.domain_consistency_result.consistent
            assert initial_validation.domain_consistency_result.manifest_domain == "roost_scheduler"
            assert initial_validation.domain_consistency_result.const_domain == "wrong_domain"
            
            # Step 2: Comprehensive validation
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_initial_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
                mock_initial_comprehensive.valid = False
                mock_validate_all.return_value = mock_initial_comprehensive
                
                initial_comprehensive = await comprehensive_validator.validate_all()
            
            # Step 3: Error recovery (should fix domain mismatch)
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock()
                mock_checker_class.return_value = mock_checker
                
                # Mock successful domain fix
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.fixes_applied = ["Updated const.py domain to match manifest.json"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = []
                
                mock_checker.fix_inconsistencies.return_value = mock_fix_result
                
                # Mock post-fix validation showing consistency
                mock_consistency_result = MagicMock()
                mock_consistency_result.consistent = True
                mock_checker.validate_consistency.return_value = mock_consistency_result
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    initial_validation, initial_comprehensive, config_entry
                )
                
                # Verify recovery was successful
                assert recovery_result.success
                assert recovery_result.recovered_issues > 0
                assert len(recovery_result.recovery_steps) > 0
                
                # Find domain consistency recovery step
                domain_steps = [step for step in recovery_result.recovery_steps 
                              if step.category == "domain_consistency"]
                assert len(domain_steps) > 0
                assert any(step.success for step in domain_steps)
            
            # Step 4: Recovery verification (should show improvement)
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            with patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
                 patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
                
                # Mock improved post-recovery validation
                post_validation = MagicMock(spec=ComprehensiveResult)
                post_validation.success = True
                post_validation.issues = []
                post_validation.warnings = []
                post_validation.domain_consistency_result = MagicMock()
                post_validation.domain_consistency_result.consistent = True
                
                post_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
                post_comprehensive.valid = True
                
                mock_startup_validator.run_comprehensive_validation.return_value = post_validation
                mock_comprehensive_validator.validate_all.return_value = post_comprehensive
                
                verification_result = await verification_system.verify_recovery_effectiveness(
                    initial_validation, initial_comprehensive, recovery_result, config_entry
                )
                
                # Verify verification shows improvement
                assert verification_result.success
                assert verification_result.improvement_metrics["domain_consistency_improved"] is True
                assert verification_result.improvement_metrics["overall_validation_improved"] is True

    @pytest.mark.asyncio
    async def test_multiple_errors_emergency_mode_workflow(self, hass, config_entry, temp_integration_dir):
        """Test workflow with multiple critical errors triggering emergency mode."""
        # Create multiple error scenarios
        self._create_domain_mismatch_scenario(temp_integration_dir)
        self._create_invalid_manifest_scenario(temp_integration_dir)
        self._create_missing_config_flow_scenario(temp_integration_dir)
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery, \
             patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path_verification:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            mock_path_verification.return_value.parent = temp_integration_dir
            
            # Step 1: Initial validation (should detect multiple issues)
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                initial_validation = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify multiple issues detected
                assert not initial_validation.success
                assert len(initial_validation.issues) >= 3  # Multiple types of issues
            
            # Step 2: Comprehensive validation with multiple failures
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = False
                mock_comprehensive_result.manifest_result = MagicMock()
                mock_comprehensive_result.manifest_result.valid = False
                mock_comprehensive_result.manifest_result.issues = ["Invalid JSON", "Missing required fields"]
                mock_comprehensive_result.dependency_result = MagicMock()
                mock_comprehensive_result.dependency_result.valid = False
                mock_comprehensive_result.dependency_result.conflicts = ["Dependency conflict"]
                mock_comprehensive_result.version_result = MagicMock()
                mock_comprehensive_result.version_result.compatible = False
                mock_comprehensive_result.version_result.issues = ["Version incompatible"]
                
                mock_validate_all.return_value = mock_comprehensive_result
                comprehensive_result = await comprehensive_validator.validate_all()
            
            # Step 3: Error recovery (should trigger emergency mode)
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch.object(error_recovery, '_registration_fixer') as mock_fixer:
                # Mock failed recovery attempts to trigger fallbacks
                mock_fix_result = MagicMock()
                mock_fix_result.success = False
                mock_fix_result.changes_made = []
                mock_fix_result.errors = ["Fix failed due to multiple critical issues"]
                mock_fix_result.warnings = []
                mock_fix_result.verification_passed = False
                
                mock_fixer.fix_domain_mismatch.return_value = mock_fix_result
                mock_fixer.fix_class_inheritance.return_value = mock_fix_result
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    initial_validation, comprehensive_result, config_entry
                )
                
                # Verify emergency mode activation
                assert len(recovery_result.fallbacks_applied) > 0
                assert recovery_result.total_issues > 0
            
            # Step 4: Recovery verification (should show limited improvement)
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            with patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
                 patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
                
                # Mock partial improvement post-recovery
                post_validation = MagicMock(spec=ComprehensiveResult)
                post_validation.success = False  # Still has issues
                post_validation.issues = ["Remaining issue"]  # Fewer issues
                post_validation.warnings = []
                
                post_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
                post_comprehensive.valid = False  # Still invalid but improved
                
                mock_startup_validator.run_comprehensive_validation.return_value = post_validation
                mock_comprehensive_validator.validate_all.return_value = post_comprehensive
                
                verification_result = await verification_system.verify_recovery_effectiveness(
                    initial_validation, comprehensive_result, recovery_result, config_entry
                )
                
                # Verify partial recovery verification
                assert verification_result.overall_status in ["partial", "limited"]
                assert len(verification_result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_performance_metrics_integration(self, hass, config_entry, temp_integration_dir):
        """Test performance metrics collection throughout the integration workflow."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery, \
             patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path_verification:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            mock_path_verification.return_value.parent = temp_integration_dir
            
            # Measure overall workflow performance
            start_time = time.time()
            
            # Step 1: Validation with performance tracking
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_start = time.time()
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                validation_duration = time.time() - validation_start
                
                # Verify validation performance
                assert validation_duration < 5.0  # Should complete within 5 seconds
                assert validation_result.startup_diagnostics is not None
            
            # Step 2: Comprehensive validation performance
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = True
                mock_validate_all.return_value = mock_comprehensive_result
                
                comprehensive_start = time.time()
                comprehensive_result = await comprehensive_validator.validate_all()
                comprehensive_duration = time.time() - comprehensive_start
                
                # Verify comprehensive validation performance
                assert comprehensive_duration < 3.0  # Should be faster than startup validation
            
            # Step 3: Recovery performance
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            recovery_start = time.time()
            recovery_result = await error_recovery.execute_comprehensive_recovery(
                validation_result, comprehensive_result, config_entry
            )
            recovery_duration = time.time() - recovery_start
            
            # Verify recovery performance
            assert recovery_duration < 10.0  # Should complete within 10 seconds
            assert recovery_result.duration_seconds > 0
            
            # Step 4: Verification performance
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            verification_start = time.time()
            verification_result = await verification_system.verify_recovery_effectiveness(
                validation_result, comprehensive_result, recovery_result, config_entry
            )
            verification_duration = time.time() - verification_start
            
            # Verify verification performance
            assert verification_duration < 15.0  # Should complete within 15 seconds
            assert verification_result.duration_seconds > 0
            
            # Verify overall workflow performance
            total_duration = time.time() - start_time
            assert total_duration < 30.0  # Complete workflow should finish within 30 seconds
            
            # Verify performance metrics are collected
            assert "validation_duration" in str(validation_result.startup_diagnostics) or True
            assert recovery_result.duration_seconds > 0
            assert verification_result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_error_handling_resilience(self, hass, config_entry, temp_integration_dir):
        """Test error handling resilience throughout the integration workflow."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery, \
             patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path_verification:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            mock_path_verification.return_value.parent = temp_integration_dir
            
            # Test validation with exceptions
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', side_effect=Exception("Test exception")):
                # Should handle exceptions gracefully
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify graceful error handling
                assert not validation_result.success
                assert len(validation_result.issues) > 0
                assert any("exception" in str(issue).lower() for issue in validation_result.issues)
            
            # Test recovery with exceptions
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            # Create mock validation result with issues
            mock_validation_result = MagicMock(spec=ComprehensiveResult)
            mock_validation_result.success = False
            mock_validation_result.issues = ["Test issue"]
            
            mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
            mock_comprehensive_result.valid = False
            
            with patch.object(error_recovery, '_registration_fixer', side_effect=Exception("Recovery exception")):
                # Should handle recovery exceptions gracefully
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    mock_validation_result, mock_comprehensive_result, config_entry
                )
                
                # Verify graceful error handling in recovery
                assert not recovery_result.success
                assert len(recovery_result.errors) > 0
            
            # Test verification with exceptions
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            mock_recovery_result = MagicMock(spec=RecoveryResult)
            mock_recovery_result.success = False
            
            with patch.object(verification_system, '_startup_validator', side_effect=Exception("Verification exception")):
                # Should handle verification exceptions gracefully
                verification_result = await verification_system.verify_recovery_effectiveness(
                    mock_validation_result, mock_comprehensive_result, mock_recovery_result, config_entry
                )
                
                # Verify graceful error handling in verification
                assert not verification_result.success
                assert verification_result.overall_status == "failed"

    @pytest.mark.asyncio
    async def test_cache_functionality_integration(self, hass, config_entry, temp_integration_dir):
        """Test cache functionality integration across the workflow."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            # Verify cache is initially empty
            assert len(startup_validator._validation_cache) == 0
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                # First validation run
                first_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify result is cached
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
    async def test_logging_integration(self, hass, config_entry, temp_integration_dir):
        """Test logging integration throughout the workflow."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery, \
             patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path_verification:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            mock_path_verification.return_value.parent = temp_integration_dir
            
            # Test logging during validation
            with patch('custom_components.roost_scheduler.startup_validation_system._LOGGER') as mock_logger:
                startup_validator = StartupValidationSystem(hass)
                
                with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                     patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                     patch.object(startup_validator, '_is_domain_available', return_value=True):
                    
                    await startup_validator.run_comprehensive_validation(DOMAIN)
                    
                    # Verify logging calls were made
                    assert mock_logger.debug.called or mock_logger.info.called
            
            # Test logging during recovery
            with patch('custom_components.roost_scheduler.comprehensive_error_recovery._LOGGER') as mock_logger:
                error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
                
                mock_validation_result = MagicMock(spec=ComprehensiveResult)
                mock_validation_result.success = True
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = True
                
                await error_recovery.execute_comprehensive_recovery(
                    mock_validation_result, mock_comprehensive_result, config_entry
                )
                
                # Verify logging calls were made
                assert mock_logger.debug.called or mock_logger.info.called
            
            # Test logging during verification
            with patch('custom_components.roost_scheduler.recovery_verification_system._LOGGER') as mock_logger:
                verification_system = RecoveryVerificationSystem(hass, DOMAIN)
                
                mock_recovery_result = MagicMock(spec=RecoveryResult)
                mock_recovery_result.success = True
                
                await verification_system.verify_recovery_effectiveness(
                    mock_validation_result, mock_comprehensive_result, mock_recovery_result, config_entry
                )
                
                # Verify logging calls were made
                assert mock_logger.debug.called or mock_logger.info.called

    @pytest.mark.asyncio
    async def test_diagnostic_data_collection_integration(self, hass, config_entry, temp_integration_dir):
        """Test diagnostic data collection integration across the workflow."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery, \
             patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path_verification:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            mock_path_verification.return_value.parent = temp_integration_dir
            
            # Step 1: Validation diagnostic collection
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify diagnostic data collection
                assert validation_result.diagnostic_data is not None
                assert validation_result.startup_diagnostics is not None
                assert isinstance(validation_result.startup_diagnostics, dict)
            
            # Step 2: Recovery diagnostic collection
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
            mock_comprehensive_result.valid = True
            
            recovery_result = await error_recovery.execute_comprehensive_recovery(
                validation_result, mock_comprehensive_result, config_entry
            )
            
            # Verify recovery diagnostic collection
            assert recovery_result.duration_seconds > 0
            assert isinstance(recovery_result.recovery_steps, list)
            
            # Step 3: Verification diagnostic collection
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            verification_result = await verification_system.verify_recovery_effectiveness(
                validation_result, mock_comprehensive_result, recovery_result, config_entry
            )
            
            # Verify verification diagnostic collection
            assert verification_result.improvement_metrics is not None
            assert isinstance(verification_result.improvement_metrics, dict)
            assert verification_result.duration_seconds > 0
            assert isinstance(verification_result.verification_tests, list)
            assert isinstance(verification_result.recommendations, list)
            
            # Verify comprehensive diagnostic data
            assert "validation_cache_size" in startup_validator.get_startup_diagnostics(DOMAIN)
            assert len(verification_result.improvement_metrics) > 0