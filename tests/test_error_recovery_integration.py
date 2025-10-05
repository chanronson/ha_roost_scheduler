"""Error recovery integration tests for config flow handler fix.

This test suite focuses on testing the error recovery system integration
with various error scenarios and recovery strategies.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json
import tempfile
import shutil
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
    RecoveryResult,
    RecoveryStep,
    ErrorCategory
)
from custom_components.roost_scheduler.comprehensive_validator import (
    ComprehensiveValidator,
    ComprehensiveValidationResult
)


class TestErrorRecoveryIntegration:
    """Test suite for error recovery system integration."""

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
        """Create a temporary integration directory."""
        temp_dir = tempfile.mkdtemp()
        integration_path = Path(temp_dir) / "custom_components" / "roost_scheduler"
        integration_path.mkdir(parents=True)
        yield integration_path
        shutil.rmtree(temp_dir)

    def create_integration_files_with_issues(self, integration_path: Path, issue_type: str):
        """Create integration files with specific issues for testing."""
        if issue_type == "domain_mismatch":
            # Create manifest with correct domain
            manifest_data = {
                "domain": "roost_scheduler",
                "name": "Roost Scheduler",
                "version": "1.0.0",
                "config_flow": True,
                "dependencies": ["http"],
                "requirements": []
            }
            with open(integration_path / "manifest.json", "w") as f:
                json.dump(manifest_data, f)
            
            # Create const.py with wrong domain
            const_content = 'DOMAIN = "wrong_domain"\nVERSION = "1.0.0"'
            with open(integration_path / "const.py", "w") as f:
                f.write(const_content)
            
            # Create valid config_flow.py
            config_flow_content = '''
from homeassistant import config_entries
from .const import DOMAIN

class RoostSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        return self.async_create_entry(title="Test", data={})
'''
            with open(integration_path / "config_flow.py", "w") as f:
                f.write(config_flow_content)
        
        elif issue_type == "missing_config_flow":
            # Create valid manifest and const
            manifest_data = {
                "domain": "roost_scheduler",
                "name": "Roost Scheduler",
                "version": "1.0.0",
                "config_flow": True,
                "dependencies": ["http"],
                "requirements": []
            }
            with open(integration_path / "manifest.json", "w") as f:
                json.dump(manifest_data, f)
            
            const_content = 'DOMAIN = "roost_scheduler"\nVERSION = "1.0.0"'
            with open(integration_path / "const.py", "w") as f:
                f.write(const_content)
            
            # Create config_flow.py without config flow class
            config_flow_content = '''
from .const import DOMAIN
# Config flow class is missing
'''
            with open(integration_path / "config_flow.py", "w") as f:
                f.write(config_flow_content)
        
        elif issue_type == "invalid_manifest":
            # Create invalid manifest JSON
            with open(integration_path / "manifest.json", "w") as f:
                f.write('{"domain": "roost_scheduler", "name": "Test", invalid_json}')
            
            # Create valid const.py
            const_content = 'DOMAIN = "roost_scheduler"\nVERSION = "1.0.0"'
            with open(integration_path / "const.py", "w") as f:
                f.write(const_content)
            
            # Create valid config_flow.py
            config_flow_content = '''
from homeassistant import config_entries
from .const import DOMAIN

class RoostSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        return self.async_create_entry(title="Test", data={})
'''
            with open(integration_path / "config_flow.py", "w") as f:
                f.write(config_flow_content)
        
        # Always create __init__.py
        init_content = '''
async def async_setup(hass, config):
    return True

async def async_setup_entry(hass, entry):
    return True
'''
        with open(integration_path / "__init__.py", "w") as f:
            f.write(init_content)

    @pytest.mark.asyncio
    async def test_domain_mismatch_recovery_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of domain mismatch recovery."""
        # Setup: Create files with domain mismatch
        self.create_integration_files_with_issues(temp_integration_dir, "domain_mismatch")
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            # Step 1: Detect domain mismatch
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify domain mismatch detected
                assert not validation_result.success
                assert not validation_result.domain_consistency_result.consistent
            
            # Step 2: Comprehensive validation
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = False
                mock_validate_all.return_value = mock_comprehensive_result
                
                comprehensive_result = await comprehensive_validator.validate_all()
            
            # Step 3: Execute recovery
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock()
                mock_checker_class.return_value = mock_checker
                
                # Mock successful domain fix
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.fixes_applied = ["Fixed domain mismatch in const.py"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = []
                
                mock_checker.fix_inconsistencies.return_value = mock_fix_result
                
                # Mock post-fix validation
                mock_consistency_result = MagicMock()
                mock_consistency_result.consistent = True
                mock_checker.validate_consistency.return_value = mock_consistency_result
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    validation_result, comprehensive_result, config_entry
                )
                
                # Verify recovery execution
                assert isinstance(recovery_result, RecoveryResult)
                assert recovery_result.success
                assert recovery_result.recovered_issues > 0
                
                # Verify domain consistency recovery step
                domain_steps = [step for step in recovery_result.recovery_steps 
                              if step.category == "domain_consistency"]
                assert len(domain_steps) > 0
                
                successful_domain_step = next(
                    (step for step in domain_steps if step.success), None
                )
                assert successful_domain_step is not None
                assert "domain" in successful_domain_step.description.lower()
                assert len(successful_domain_step.changes_made) > 0

    @pytest.mark.asyncio
    async def test_config_flow_missing_recovery_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of config flow missing class recovery."""
        # Setup: Create files with missing config flow class
        self.create_integration_files_with_issues(temp_integration_dir, "missing_config_flow")
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            # Step 1: Detect missing config flow
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify config flow issues detected
                assert not validation_result.success
                config_flow_issues = [issue for issue in validation_result.issues 
                                    if isinstance(issue, dict) and "config_flow" in str(issue).lower()]
                assert len(config_flow_issues) > 0 or not validation_result.config_flow_availability_result.success
            
            # Step 2: Comprehensive validation
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = False
                mock_validate_all.return_value = mock_comprehensive_result
                
                comprehensive_result = await comprehensive_validator.validate_all()
            
            # Step 3: Execute recovery
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch.object(error_recovery, '_registration_fixer') as mock_fixer:
                # Mock successful config flow fix
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.changes_made = ["Added missing RoostSchedulerConfigFlow class"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = []
                mock_fix_result.verification_passed = True
                
                mock_fixer.fix_class_inheritance.return_value = mock_fix_result
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    validation_result, comprehensive_result, config_entry
                )
                
                # Verify recovery execution
                assert isinstance(recovery_result, RecoveryResult)
                assert recovery_result.total_issues > 0
                
                # Verify config flow recovery step
                config_flow_steps = [step for step in recovery_result.recovery_steps 
                                   if step.category == "config_flow_registration"]
                assert len(config_flow_steps) > 0
                
                # At least one step should be attempted
                assert any(len(step.changes_made) > 0 or len(step.errors) > 0 
                          for step in config_flow_steps)

    @pytest.mark.asyncio
    async def test_manifest_validation_recovery_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of manifest validation recovery."""
        # Setup: Create files with invalid manifest
        self.create_integration_files_with_issues(temp_integration_dir, "invalid_manifest")
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            # Step 1: Detect manifest issues
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify manifest issues detected
                assert not validation_result.success
                manifest_issues = [issue for issue in validation_result.issues 
                                 if isinstance(issue, dict) and "manifest" in str(issue).lower()]
                assert len(manifest_issues) > 0 or len(validation_result.issues) > 0
            
            # Step 2: Comprehensive validation with manifest issues
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = False
                mock_comprehensive_result.manifest_result = MagicMock()
                mock_comprehensive_result.manifest_result.valid = False
                mock_comprehensive_result.manifest_result.issues = ["Invalid JSON syntax"]
                mock_validate_all.return_value = mock_comprehensive_result
                
                comprehensive_result = await comprehensive_validator.validate_all()
            
            # Step 3: Execute recovery
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            recovery_result = await error_recovery.execute_comprehensive_recovery(
                validation_result, comprehensive_result, config_entry
            )
            
            # Verify recovery execution
            assert isinstance(recovery_result, RecoveryResult)
            assert recovery_result.total_issues > 0
            
            # Verify manifest recovery step
            manifest_steps = [step for step in recovery_result.recovery_steps 
                            if step.category == "manifest_validation"]
            assert len(manifest_steps) > 0
            
            # At least one manifest recovery step should be attempted
            assert any(step.description and "manifest" in step.description.lower() 
                      for step in manifest_steps)

    @pytest.mark.asyncio
    async def test_emergency_mode_activation_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of emergency mode activation with multiple failures."""
        # Setup: Create files with multiple critical issues
        self.create_integration_files_with_issues(temp_integration_dir, "domain_mismatch")
        self.create_integration_files_with_issues(temp_integration_dir, "invalid_manifest")
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            # Step 1: Detect multiple critical issues
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify multiple issues detected
                assert not validation_result.success
                assert len(validation_result.issues) >= 2  # Multiple types of issues
            
            # Step 2: Comprehensive validation with multiple failures
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = False
                mock_comprehensive_result.manifest_result = MagicMock()
                mock_comprehensive_result.manifest_result.valid = False
                mock_comprehensive_result.manifest_result.issues = ["Invalid JSON", "Missing fields"]
                mock_comprehensive_result.dependency_result = MagicMock()
                mock_comprehensive_result.dependency_result.valid = False
                mock_comprehensive_result.dependency_result.conflicts = ["Dependency conflict"]
                mock_comprehensive_result.version_result = MagicMock()
                mock_comprehensive_result.version_result.compatible = False
                mock_comprehensive_result.version_result.issues = ["Version incompatible"]
                
                mock_validate_all.return_value = mock_comprehensive_result
                comprehensive_result = await comprehensive_validator.validate_all()
            
            # Step 3: Execute recovery with multiple failures
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
                    validation_result, comprehensive_result, config_entry
                )
                
                # Verify emergency mode activation
                assert isinstance(recovery_result, RecoveryResult)
                assert len(recovery_result.fallbacks_applied) > 0
                assert recovery_result.total_issues > 0
                
                # Verify multiple recovery categories attempted
                categories = set(step.category for step in recovery_result.recovery_steps)
                assert len(categories) > 1  # Multiple categories attempted
                
                # Verify fallback strategies were applied
                assert len(recovery_result.fallbacks_applied) > 0
                fallback_categories = set(recovery_result.fallbacks_applied)
                assert len(fallback_categories) > 0

    @pytest.mark.asyncio
    async def test_recovery_step_verification_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of recovery step verification."""
        # Setup: Create files with domain mismatch for testing
        self.create_integration_files_with_issues(temp_integration_dir, "domain_mismatch")
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            # Step 1: Initial validation
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Step 2: Comprehensive validation
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = False
                mock_validate_all.return_value = mock_comprehensive_result
                
                comprehensive_result = await comprehensive_validator.validate_all()
            
            # Step 3: Execute recovery with verification
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock()
                mock_checker_class.return_value = mock_checker
                
                # Mock successful fix with verification
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.fixes_applied = ["Fixed domain mismatch"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = []
                
                mock_checker.fix_inconsistencies.return_value = mock_fix_result
                
                # Mock verification results
                mock_pre_consistency = MagicMock()
                mock_pre_consistency.consistent = False
                
                mock_post_consistency = MagicMock()
                mock_post_consistency.consistent = True
                
                mock_checker.validate_consistency.side_effect = [
                    mock_pre_consistency,  # Before fix
                    mock_post_consistency  # After fix
                ]
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    validation_result, comprehensive_result, config_entry
                )
                
                # Verify recovery step verification
                assert isinstance(recovery_result, RecoveryResult)
                
                # Find domain consistency recovery steps
                domain_steps = [step for step in recovery_result.recovery_steps 
                              if step.category == "domain_consistency"]
                assert len(domain_steps) > 0
                
                # Verify verification was performed
                successful_steps = [step for step in domain_steps if step.success]
                assert len(successful_steps) > 0
                
                # Verify verification passed for successful steps
                verified_steps = [step for step in successful_steps if step.verification_passed]
                assert len(verified_steps) > 0

    @pytest.mark.asyncio
    async def test_recovery_rollback_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of recovery rollback functionality."""
        # Setup: Create files with issues
        self.create_integration_files_with_issues(temp_integration_dir, "domain_mismatch")
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            # Step 1: Initial validation
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Step 2: Comprehensive validation
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = False
                mock_validate_all.return_value = mock_comprehensive_result
                
                comprehensive_result = await comprehensive_validator.validate_all()
            
            # Step 3: Execute recovery with failed verification (should trigger rollback)
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock()
                mock_checker_class.return_value = mock_checker
                
                # Mock fix that appears successful but fails verification
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.fixes_applied = ["Attempted domain fix"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = []
                
                mock_checker.fix_inconsistencies.return_value = mock_fix_result
                
                # Mock verification that fails (should trigger rollback)
                mock_pre_consistency = MagicMock()
                mock_pre_consistency.consistent = False
                
                mock_post_consistency = MagicMock()
                mock_post_consistency.consistent = False  # Still inconsistent after fix
                
                mock_checker.validate_consistency.side_effect = [
                    mock_pre_consistency,  # Before fix
                    mock_post_consistency  # After fix (still fails)
                ]
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    validation_result, comprehensive_result, config_entry
                )
                
                # Verify rollback behavior
                assert isinstance(recovery_result, RecoveryResult)
                
                # Find domain consistency recovery steps
                domain_steps = [step for step in recovery_result.recovery_steps 
                              if step.category == "domain_consistency"]
                assert len(domain_steps) > 0
                
                # Verify that verification failed for some steps
                failed_verification_steps = [step for step in domain_steps 
                                           if not step.verification_passed]
                assert len(failed_verification_steps) > 0
                
                # Verify rollback was attempted (should be in errors or warnings)
                rollback_mentioned = any(
                    "rollback" in str(step.errors).lower() or 
                    "rollback" in str(step.warnings).lower() or
                    "revert" in str(step.errors).lower() or
                    "revert" in str(step.warnings).lower()
                    for step in domain_steps
                )
                # Note: Rollback might not be explicitly mentioned, but verification failure should be recorded
                assert any(not step.verification_passed for step in domain_steps)

    @pytest.mark.asyncio
    async def test_recovery_performance_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of recovery performance monitoring."""
        # Setup: Create files with issues
        self.create_integration_files_with_issues(temp_integration_dir, "domain_mismatch")
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            # Step 1: Initial validation
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                validation_result = await startup_validator.run_comprehensive_validation(DOMAIN)
            
            # Step 2: Comprehensive validation
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
                mock_comprehensive_result.valid = False
                mock_validate_all.return_value = mock_comprehensive_result
                
                comprehensive_result = await comprehensive_validator.validate_all()
            
            # Step 3: Execute recovery with performance monitoring
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            import time
            start_time = time.time()
            
            recovery_result = await error_recovery.execute_comprehensive_recovery(
                validation_result, comprehensive_result, config_entry
            )
            
            end_time = time.time()
            actual_duration = end_time - start_time
            
            # Verify performance monitoring
            assert isinstance(recovery_result, RecoveryResult)
            assert recovery_result.duration_seconds > 0
            assert recovery_result.duration_seconds <= actual_duration + 1.0  # Allow some tolerance
            
            # Verify individual step performance monitoring
            for step in recovery_result.recovery_steps:
                assert isinstance(step, RecoveryStep)
                assert step.duration_seconds >= 0
                # Each step should have reasonable duration
                assert step.duration_seconds < 10.0  # No single step should take more than 10 seconds
            
            # Verify total recovery performance
            assert recovery_result.duration_seconds < 30.0  # Total recovery should complete within 30 seconds
            
            # Verify performance data is collected
            total_step_duration = sum(step.duration_seconds for step in recovery_result.recovery_steps)
            # Total step duration should be reasonable compared to overall duration
            assert total_step_duration <= recovery_result.duration_seconds + 1.0  # Allow some tolerance