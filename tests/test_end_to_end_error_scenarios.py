"""End-to-end error scenario testing for config flow handler fix."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json
import tempfile
import shutil

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler.const import DOMAIN


class TestEndToEndErrorScenarios:
    """Test suite for end-to-end error scenarios and recovery."""

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
        return entry

    @pytest.fixture
    def temp_integration_dir(self):
        """Create a temporary integration directory."""
        temp_dir = tempfile.mkdtemp()
        integration_path = Path(temp_dir) / "custom_components" / "roost_scheduler"
        integration_path.mkdir(parents=True)
        yield integration_path
        shutil.rmtree(temp_dir)

    def create_valid_integration_files(self, integration_path: Path):
        """Create valid integration files."""
        # Create manifest.json
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
        
        # Create const.py
        const_content = 'DOMAIN = "roost_scheduler"\nVERSION = "1.0.0"'
        with open(integration_path / "const.py", "w") as f:
            f.write(const_content)
        
        # Create config_flow.py
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
        
        # Create __init__.py
        init_content = '''
async def async_setup(hass, config):
    return True

async def async_setup_entry(hass, entry):
    return True
'''
        with open(integration_path / "__init__.py", "w") as f:
            f.write(init_content)

    @pytest.mark.asyncio
    async def test_scenario_1_domain_mismatch_recovery(self, hass, config_entry, temp_integration_dir):
        """Test Scenario 1: Domain mismatch between manifest and const.py with automatic recovery."""
        # Setup: Create files with domain mismatch
        self.create_valid_integration_files(temp_integration_dir)
        
        # Introduce domain mismatch
        const_content = 'DOMAIN = "wrong_domain"\nVERSION = "1.0.0"'
        with open(temp_integration_dir / "const.py", "w") as f:
            f.write(const_content)
        
        # Execute: Run complete validation and recovery workflow
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import ComprehensiveErrorRecovery
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery, \
             patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path_verification:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            mock_path_verification.return_value.parent = temp_integration_dir
            
            # Step 1: Initial validation should detect domain mismatch
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                initial_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify: Domain mismatch detected
                assert not initial_result.success
                assert not initial_result.domain_consistency_result.consistent
                assert initial_result.domain_consistency_result.manifest_domain == "roost_scheduler"
                assert initial_result.domain_consistency_result.const_domain == "wrong_domain"
            
            # Step 2: Error recovery should fix domain mismatch
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            # Mock the domain fixer to simulate successful fix
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock()
                mock_checker_class.return_value = mock_checker
                
                # Mock successful fix
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
                
                # Mock comprehensive validation
                from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidator
                comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
                
                with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                    mock_comprehensive_result = MagicMock()
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
                    
                    recovery_result = await error_recovery.execute_comprehensive_recovery(
                        initial_result, comprehensive_result, config_entry
                    )
                    
                    # Verify: Recovery was successful
                    assert recovery_result.success
                    assert recovery_result.recovered_issues > 0
                    assert len(recovery_result.recovery_steps) > 0
                    
                    # Find domain consistency recovery step
                    domain_steps = [step for step in recovery_result.recovery_steps 
                                  if step.category == "domain_consistency"]
                    assert len(domain_steps) > 0
                    assert any(step.success for step in domain_steps)

    @pytest.mark.asyncio
    async def test_scenario_2_missing_config_flow_class(self, hass, config_entry, temp_integration_dir):
        """Test Scenario 2: Missing config flow class with recovery."""
        # Setup: Create files with missing config flow class
        self.create_valid_integration_files(temp_integration_dir)
        
        # Remove config flow class
        config_flow_content = '''
# Config flow class is missing
from .const import DOMAIN
'''
        with open(temp_integration_dir / "config_flow.py", "w") as f:
            f.write(config_flow_content)
        
        # Execute: Run validation and recovery
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import ComprehensiveErrorRecovery
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                initial_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify: Config flow issues detected
                assert not initial_result.success
                config_flow_issues = [issue for issue in initial_result.issues 
                                    if isinstance(issue, dict) and "config_flow" in str(issue).lower()]
                assert len(config_flow_issues) > 0
            
            # Mock recovery for config flow issues
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
                
                # Mock comprehensive validation
                from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidator
                comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
                
                with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                    mock_comprehensive_result = MagicMock()
                    mock_comprehensive_result.valid = True
                    mock_validate_all.return_value = mock_comprehensive_result
                    
                    comprehensive_result = await comprehensive_validator.validate_all()
                    
                    recovery_result = await error_recovery.execute_comprehensive_recovery(
                        initial_result, comprehensive_result, config_entry
                    )
                    
                    # Verify: Recovery attempted config flow fixes
                    config_flow_steps = [step for step in recovery_result.recovery_steps 
                                       if step.category == "config_flow_registration"]
                    assert len(config_flow_steps) > 0

    @pytest.mark.asyncio
    async def test_scenario_3_invalid_manifest_json(self, hass, config_entry, temp_integration_dir):
        """Test Scenario 3: Invalid manifest.json with recovery."""
        # Setup: Create files with invalid manifest
        self.create_valid_integration_files(temp_integration_dir)
        
        # Create invalid JSON
        with open(temp_integration_dir / "manifest.json", "w") as f:
            f.write('{"domain": "roost_scheduler", "name": "Test", invalid_json}')
        
        # Execute: Run validation and recovery
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import ComprehensiveErrorRecovery
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                initial_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify: Manifest issues detected
                assert not initial_result.success
                manifest_issues = [issue for issue in initial_result.issues 
                                 if isinstance(issue, dict) and "manifest" in str(issue).lower()]
                assert len(manifest_issues) > 0
            
            # Test recovery
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            # Mock comprehensive validation with manifest issues
            from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidator
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_comprehensive_result = MagicMock()
                mock_comprehensive_result.valid = False
                mock_comprehensive_result.manifest_result = MagicMock()
                mock_comprehensive_result.manifest_result.valid = False
                mock_comprehensive_result.manifest_result.issues = ["Invalid JSON syntax"]
                mock_comprehensive_result.dependency_result = MagicMock()
                mock_comprehensive_result.dependency_result.valid = True
                mock_comprehensive_result.dependency_result.conflicts = []
                mock_comprehensive_result.version_result = MagicMock()
                mock_comprehensive_result.version_result.compatible = True
                mock_comprehensive_result.version_result.issues = []
                
                mock_validate_all.return_value = mock_comprehensive_result
                
                comprehensive_result = await comprehensive_validator.validate_all()
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    initial_result, comprehensive_result, config_entry
                )
                
                # Verify: Recovery attempted manifest fixes
                manifest_steps = [step for step in recovery_result.recovery_steps 
                                if step.category == "manifest_validation"]
                assert len(manifest_steps) > 0

    @pytest.mark.asyncio
    async def test_scenario_4_multiple_critical_errors(self, hass, config_entry, temp_integration_dir):
        """Test Scenario 4: Multiple critical errors requiring emergency mode."""
        # Setup: Create files with multiple critical issues
        self.create_valid_integration_files(temp_integration_dir)
        
        # Introduce multiple issues
        # 1. Domain mismatch
        const_content = 'DOMAIN = "wrong_domain"\nVERSION = "1.0.0"'
        with open(temp_integration_dir / "const.py", "w") as f:
            f.write(const_content)
        
        # 2. Invalid manifest
        with open(temp_integration_dir / "manifest.json", "w") as f:
            f.write('{"domain": "roost_scheduler", invalid}')
        
        # 3. Missing config flow class
        config_flow_content = '# Missing config flow class'
        with open(temp_integration_dir / "config_flow.py", "w") as f:
            f.write(config_flow_content)
        
        # Execute: Run validation and recovery
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import ComprehensiveErrorRecovery
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                initial_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify: Multiple critical issues detected
                assert not initial_result.success
                assert len(initial_result.issues) >= 3  # At least 3 different types of issues
            
            # Test recovery with multiple failures to trigger emergency mode
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch.object(error_recovery, '_registration_fixer') as mock_fixer:
                # Mock failed recovery attempts
                mock_fix_result = MagicMock()
                mock_fix_result.success = False
                mock_fix_result.changes_made = []
                mock_fix_result.errors = ["Fix failed due to multiple critical issues"]
                mock_fix_result.warnings = []
                mock_fix_result.verification_passed = False
                
                mock_fixer.fix_domain_mismatch.return_value = mock_fix_result
                mock_fixer.fix_class_inheritance.return_value = mock_fix_result
                
                # Mock comprehensive validation with multiple issues
                from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidator
                comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
                
                with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                    mock_comprehensive_result = MagicMock()
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
                    
                    recovery_result = await error_recovery.execute_comprehensive_recovery(
                        initial_result, comprehensive_result, config_entry
                    )
                    
                    # Verify: Emergency mode activated due to multiple failures
                    assert len(recovery_result.fallbacks_applied) > 0
                    # Should have multiple fallback strategies applied

    @pytest.mark.asyncio
    async def test_scenario_5_successful_complete_workflow(self, hass, config_entry, temp_integration_dir):
        """Test Scenario 5: Complete successful workflow from detection to recovery to verification."""
        # Setup: Create files with a single fixable issue (domain mismatch)
        self.create_valid_integration_files(temp_integration_dir)
        
        # Introduce fixable domain mismatch
        const_content = 'DOMAIN = "wrong_domain"\nVERSION = "1.0.0"'
        with open(temp_integration_dir / "const.py", "w") as f:
            f.write(const_content)
        
        # Execute: Complete workflow
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import ComprehensiveErrorRecovery
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery, \
             patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path_verification:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            mock_path_verification.return_value.parent = temp_integration_dir
            
            # Step 1: Initial validation
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                initial_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify: Issue detected
                assert not initial_result.success
                assert not initial_result.domain_consistency_result.consistent
            
            # Step 2: Comprehensive validation
            from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidator
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            
            with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                mock_initial_comprehensive = MagicMock()
                mock_initial_comprehensive.valid = False
                mock_validate_all.return_value = mock_initial_comprehensive
                
                initial_comprehensive = await comprehensive_validator.validate_all()
            
            # Step 3: Error recovery
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock()
                mock_checker_class.return_value = mock_checker
                
                # Mock successful fix
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.fixes_applied = ["Fixed domain mismatch"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = []
                
                mock_checker.fix_inconsistencies.return_value = mock_fix_result
                
                # Mock post-fix validation
                mock_consistency_result = MagicMock()
                mock_consistency_result.consistent = True
                mock_checker.validate_consistency.return_value = mock_consistency_result
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    initial_result, initial_comprehensive, config_entry
                )
                
                # Verify: Recovery successful
                assert recovery_result.success
                assert recovery_result.recovered_issues > 0
            
            # Step 4: Recovery verification
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            with patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
                 patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
                
                # Mock successful post-recovery validation
                post_validation = MagicMock()
                post_validation.success = True
                post_validation.issues = []
                post_validation.warnings = []
                post_validation.domain_consistency_result = MagicMock()
                post_validation.domain_consistency_result.consistent = True
                post_validation.config_flow_availability_result = MagicMock()
                post_validation.config_flow_availability_result.success = True
                
                post_comprehensive = MagicMock()
                post_comprehensive.valid = True
                
                mock_startup_validator.run_comprehensive_validation.return_value = post_validation
                mock_comprehensive_validator.validate_all.return_value = post_comprehensive
                
                verification_result = await verification_system.verify_recovery_effectiveness(
                    initial_result, initial_comprehensive, recovery_result, config_entry
                )
                
                # Verify: Complete workflow successful
                assert verification_result.success
                assert verification_result.tests_passed > 0
                assert verification_result.improvement_metrics["overall_validation_improved"] is True

    @pytest.mark.asyncio
    async def test_scenario_6_partial_recovery_with_warnings(self, hass, config_entry, temp_integration_dir):
        """Test Scenario 6: Partial recovery where some issues remain but system can continue."""
        # Setup: Create files with mixed critical and non-critical issues
        self.create_valid_integration_files(temp_integration_dir)
        
        # Introduce domain mismatch (fixable)
        const_content = 'DOMAIN = "wrong_domain"\nVERSION = "1.0.0"'
        with open(temp_integration_dir / "const.py", "w") as f:
            f.write(const_content)
        
        # Execute: Run validation and recovery
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import ComprehensiveErrorRecovery
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                initial_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify: Issues detected
                assert not initial_result.success
            
            # Mock partial recovery
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock()
                mock_checker_class.return_value = mock_checker
                
                # Mock successful domain fix
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.fixes_applied = ["Fixed domain mismatch"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = ["Some non-critical issues remain"]
                
                mock_checker.fix_inconsistencies.return_value = mock_fix_result
                
                # Mock post-fix validation with remaining warnings
                mock_consistency_result = MagicMock()
                mock_consistency_result.consistent = True
                mock_checker.validate_consistency.return_value = mock_consistency_result
                
                # Mock comprehensive validation
                from custom_components.roost_scheduler.comprehensive_validator import ComprehensiveValidator
                comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
                
                with patch.object(comprehensive_validator, 'validate_all') as mock_validate_all:
                    mock_comprehensive_result = MagicMock()
                    mock_comprehensive_result.valid = True  # Overall valid but with warnings
                    mock_validate_all.return_value = mock_comprehensive_result
                    
                    comprehensive_result = await comprehensive_validator.validate_all()
                    
                    recovery_result = await error_recovery.execute_comprehensive_recovery(
                        initial_result, comprehensive_result, config_entry
                    )
                    
                    # Verify: Partial recovery successful
                    assert recovery_result.success  # Should succeed even with warnings
                    assert recovery_result.recovered_issues > 0
                    assert recovery_result.remaining_issues >= 0  # Some issues may remain as warnings

    @pytest.mark.asyncio
    async def test_performance_under_load(self, hass, config_entry, temp_integration_dir):
        """Test system performance under load with multiple validation runs."""
        # Setup: Create valid integration files
        self.create_valid_integration_files(temp_integration_dir)
        
        from custom_components.roost_scheduler.startup_validation_system import StartupValidationSystem
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                # Run multiple validations to test performance and caching
                import time
                
                start_time = time.time()
                
                # First run (no cache)
                result1 = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Second run (should use cache if implemented)
                result2 = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Third run
                result3 = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                end_time = time.time()
                total_duration = end_time - start_time
                
                # Verify: All runs successful and performance acceptable
                assert result1.success
                assert result2.success
                assert result3.success
                assert total_duration < 10.0  # Should complete within 10 seconds
                
                # Verify cache functionality if implemented
                diagnostics = startup_validator.get_startup_diagnostics(DOMAIN)
                assert "validation_cache_size" in diagnostics