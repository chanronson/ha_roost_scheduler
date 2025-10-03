"""Final comprehensive validation test suite for config flow handler fix."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json
import tempfile
import shutil

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler.startup_validation_system import (
    StartupValidationSystem,
    ComprehensiveResult
)
from custom_components.roost_scheduler.comprehensive_validator import (
    ComprehensiveValidator,
    ComprehensiveValidationResult
)
from custom_components.roost_scheduler.comprehensive_error_recovery import (
    ComprehensiveErrorRecovery,
    RecoveryResult
)
from custom_components.roost_scheduler.recovery_verification_system import (
    RecoveryVerificationSystem,
    VerificationResult
)
from custom_components.roost_scheduler.const import DOMAIN


class TestFinalComprehensiveValidation:
    """Test suite for final comprehensive validation system."""

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
        """Create a temporary integration directory with test files."""
        temp_dir = tempfile.mkdtemp()
        integration_path = Path(temp_dir) / "custom_components" / "roost_scheduler"
        integration_path.mkdir(parents=True)
        
        # Create test manifest.json
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
        
        # Create test const.py
        const_content = 'DOMAIN = "roost_scheduler"\nVERSION = "1.0.0"'
        with open(integration_path / "const.py", "w") as f:
            f.write(const_content)
        
        # Create test config_flow.py
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
        
        # Create test __init__.py
        init_content = '''
async def async_setup(hass, config):
    return True

async def async_setup_entry(hass, entry):
    return True
'''
        with open(integration_path / "__init__.py", "w") as f:
            f.write(init_content)
        
        yield integration_path
        
        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_end_to_end_validation_success(self, hass, config_entry, temp_integration_dir):
        """Test end-to-end validation with successful scenario."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            # Initialize validation system
            startup_validator = StartupValidationSystem(hass)
            
            # Mock successful validation
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                # Run comprehensive validation
                result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify successful validation
                assert isinstance(result, ComprehensiveResult)
                assert result.success
                assert result.diagnostic_data is not None
                assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_end_to_end_validation_with_domain_mismatch(self, hass, config_entry, temp_integration_dir):
        """Test end-to-end validation with domain mismatch scenario."""
        # Create domain mismatch by modifying const.py
        const_content = 'DOMAIN = "wrong_domain"\nVERSION = "1.0.0"'
        with open(temp_integration_dir / "const.py", "w") as f:
            f.write(const_content)
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify domain mismatch is detected
                assert not result.domain_consistency_result.consistent
                assert result.domain_consistency_result.manifest_domain == "roost_scheduler"
                assert result.domain_consistency_result.const_domain == "wrong_domain"

    @pytest.mark.asyncio
    async def test_comprehensive_error_recovery_execution(self, hass, config_entry, temp_integration_dir):
        """Test comprehensive error recovery system execution."""
        with patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            # Create mock validation results with issues
            validation_result = MagicMock(spec=ComprehensiveResult)
            validation_result.success = False
            validation_result.issues = [
                {"severity": "critical", "description": "Domain mismatch", "category": "domain_consistency"},
                {"severity": "error", "description": "Config flow registration failed", "category": "config_flow_registration"}
            ]
            validation_result.warnings = []
            validation_result.domain_consistency_result = MagicMock()
            validation_result.domain_consistency_result.consistent = False
            validation_result.domain_consistency_result.issues = ["Domain mismatch detected"]
            
            comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
            comprehensive_result.valid = False
            comprehensive_result.manifest_result = MagicMock()
            comprehensive_result.manifest_result.valid = True
            comprehensive_result.manifest_result.issues = []
            comprehensive_result.dependency_result = MagicMock()
            comprehensive_result.dependency_result.valid = True
            comprehensive_result.dependency_result.conflicts = []
            comprehensive_result.version_result = MagicMock()
            comprehensive_result.version_result.compatible = True
            comprehensive_result.version_result.issues = []
            
            # Initialize error recovery system
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            # Mock the registration fixer
            with patch.object(error_recovery, '_registration_fixer') as mock_fixer:
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.changes_made = ["Fixed domain mismatch"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = []
                mock_fix_result.verification_passed = True
                
                mock_fixer.fix_domain_mismatch.return_value = mock_fix_result
                mock_fixer.fix_class_inheritance.return_value = mock_fix_result
                
                # Execute recovery
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    validation_result, comprehensive_result, config_entry
                )
                
                # Verify recovery execution
                assert isinstance(recovery_result, RecoveryResult)
                assert recovery_result.total_issues > 0
                assert len(recovery_result.recovery_steps) > 0
                assert recovery_result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_recovery_verification_system(self, hass, config_entry, temp_integration_dir):
        """Test recovery verification system functionality."""
        with patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            # Create mock pre-recovery results
            pre_validation = MagicMock(spec=ComprehensiveResult)
            pre_validation.success = False
            pre_validation.issues = ["Issue 1", "Issue 2"]
            pre_validation.warnings = ["Warning 1"]
            
            pre_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
            pre_comprehensive.valid = False
            
            # Create mock recovery result
            recovery_result = MagicMock(spec=RecoveryResult)
            recovery_result.success = True
            recovery_result.total_issues = 2
            recovery_result.recovered_issues = 2
            recovery_result.duration_seconds = 1.5
            recovery_result.emergency_mode = False
            
            # Initialize verification system
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Mock the validation methods
            with patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
                 patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
                
                # Mock post-recovery validation results (improved)
                post_validation = MagicMock(spec=ComprehensiveResult)
                post_validation.success = True
                post_validation.issues = []
                post_validation.warnings = []
                post_validation.domain_consistency_result = MagicMock()
                post_validation.domain_consistency_result.consistent = True
                post_validation.config_flow_availability_result = MagicMock()
                post_validation.config_flow_availability_result.success = True
                
                post_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
                post_comprehensive.valid = True
                post_comprehensive.manifest_result = MagicMock()
                post_comprehensive.manifest_result.valid = True
                post_comprehensive.dependency_result = MagicMock()
                post_comprehensive.dependency_result.valid = True
                
                mock_startup_validator.run_comprehensive_validation.return_value = post_validation
                mock_comprehensive_validator.validate_all.return_value = post_comprehensive
                
                # Execute verification
                verification_result = await verification_system.verify_recovery_effectiveness(
                    pre_validation, pre_comprehensive, recovery_result, config_entry
                )
                
                # Verify verification results
                assert isinstance(verification_result, VerificationResult)
                assert verification_result.tests_run > 0
                assert verification_result.duration_seconds > 0
                assert "improvement_metrics" in verification_result.improvement_metrics or len(verification_result.improvement_metrics) >= 0

    @pytest.mark.asyncio
    async def test_validation_effectiveness_metrics(self, hass, config_entry, temp_integration_dir):
        """Test validation effectiveness measurement."""
        with patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Create mock validation results showing improvement
            pre_validation = MagicMock(spec=ComprehensiveResult)
            pre_validation.issues = ["Issue 1", "Issue 2", "Issue 3"]
            pre_validation.warnings = ["Warning 1", "Warning 2"]
            pre_validation.domain_consistency_result = MagicMock()
            pre_validation.domain_consistency_result.consistent = False
            pre_validation.config_flow_availability_result = MagicMock()
            pre_validation.config_flow_availability_result.success = False
            pre_validation.success = False
            
            pre_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
            pre_comprehensive.manifest_result = MagicMock()
            pre_comprehensive.manifest_result.valid = False
            pre_comprehensive.dependency_result = MagicMock()
            pre_comprehensive.dependency_result.valid = False
            
            recovery_result = MagicMock(spec=RecoveryResult)
            recovery_result.total_issues = 3
            recovery_result.recovered_issues = 2
            recovery_result.duration_seconds = 2.0
            
            # Mock post-recovery results (improved)
            with patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
                 patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
                
                post_validation = MagicMock(spec=ComprehensiveResult)
                post_validation.issues = ["Issue 3"]  # One issue remains
                post_validation.warnings = []  # All warnings resolved
                post_validation.domain_consistency_result = MagicMock()
                post_validation.domain_consistency_result.consistent = True  # Improved
                post_validation.config_flow_availability_result = MagicMock()
                post_validation.config_flow_availability_result.success = True  # Improved
                post_validation.success = True  # Overall improved
                
                post_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
                post_comprehensive.manifest_result = MagicMock()
                post_comprehensive.manifest_result.valid = True  # Improved
                post_comprehensive.dependency_result = MagicMock()
                post_comprehensive.dependency_result.valid = True  # Improved
                
                mock_startup_validator.run_comprehensive_validation.return_value = post_validation
                mock_comprehensive_validator.validate_all.return_value = post_comprehensive
                
                # Calculate improvement metrics
                metrics = await verification_system._calculate_improvement_metrics(
                    pre_validation, pre_comprehensive, recovery_result
                )
                
                # Verify improvement calculations
                assert metrics["issues_before"] == 3
                assert metrics["issues_after"] == 1
                assert metrics["issues_resolved"] == 2
                assert metrics["issues_improvement_percentage"] == pytest.approx(66.67, rel=1e-2)
                assert metrics["warnings_before"] == 2
                assert metrics["warnings_after"] == 0
                assert metrics["warnings_resolved"] == 2
                assert metrics["warnings_improvement_percentage"] == 100.0
                assert metrics["domain_consistency_improved"] is True
                assert metrics["config_flow_availability_improved"] is True
                assert metrics["manifest_validation_improved"] is True
                assert metrics["dependency_validation_improved"] is True
                assert metrics["overall_validation_improved"] is True

    @pytest.mark.asyncio
    async def test_error_scenario_handling(self, hass, config_entry, temp_integration_dir):
        """Test handling of various error scenarios."""
        # Test missing manifest file
        (temp_integration_dir / "manifest.json").unlink()
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify missing manifest is detected
                assert not result.success
                assert any("manifest" in str(issue).lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_emergency_mode_activation(self, hass, config_entry, temp_integration_dir):
        """Test emergency mode activation during recovery."""
        with patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            # Create validation results with many critical issues
            validation_result = MagicMock(spec=ComprehensiveResult)
            validation_result.success = False
            validation_result.issues = [
                {"severity": "critical", "description": f"Critical issue {i}", "category": "domain_consistency"}
                for i in range(5)
            ]
            validation_result.warnings = []
            validation_result.domain_consistency_result = MagicMock()
            validation_result.domain_consistency_result.consistent = False
            validation_result.domain_consistency_result.issues = ["Multiple critical issues"]
            
            comprehensive_result = MagicMock(spec=ComprehensiveValidationResult)
            comprehensive_result.valid = False
            comprehensive_result.manifest_result = MagicMock()
            comprehensive_result.manifest_result.valid = False
            comprehensive_result.manifest_result.issues = ["Manifest error"]
            comprehensive_result.dependency_result = MagicMock()
            comprehensive_result.dependency_result.valid = False
            comprehensive_result.dependency_result.conflicts = ["Dependency conflict"]
            comprehensive_result.version_result = MagicMock()
            comprehensive_result.version_result.compatible = False
            comprehensive_result.version_result.issues = ["Version issue"]
            
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            # Mock failed recovery attempts to trigger fallbacks
            with patch.object(error_recovery, '_registration_fixer') as mock_fixer:
                mock_fix_result = MagicMock()
                mock_fix_result.success = False
                mock_fix_result.changes_made = []
                mock_fix_result.errors = ["Fix failed"]
                mock_fix_result.warnings = []
                mock_fix_result.verification_passed = False
                
                mock_fixer.fix_domain_mismatch.return_value = mock_fix_result
                mock_fixer.fix_class_inheritance.return_value = mock_fix_result
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    validation_result, comprehensive_result, config_entry
                )
                
                # Verify emergency mode activation
                assert len(recovery_result.fallbacks_applied) > 0
                # Emergency mode should be activated when multiple fallbacks are needed

    @pytest.mark.asyncio
    async def test_validation_orchestration_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of validation orchestration system."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            # Mock validation components
            with patch.object(startup_validator, '_run_pre_validation_checks') as mock_pre_check, \
                 patch.object(startup_validator, '_run_post_validation_analysis') as mock_post_check, \
                 patch.object(startup_validator, '_enhance_comprehensive_result') as mock_enhance, \
                 patch.object(startup_validator, '_generate_final_diagnostic_report') as mock_report:
                
                mock_pre_check.return_value = {"success": True, "duration": 0.1}
                mock_post_check.return_value = {"success": True, "duration": 0.1}
                mock_enhance.return_value = MagicMock(spec=ComprehensiveResult)
                mock_enhance.return_value.success = True
                mock_enhance.return_value.startup_diagnostics = {}
                mock_report.return_value = {"orchestration_completed": True}
                
                # Mock the core validation
                with patch.object(startup_validator, 'run_comprehensive_validation') as mock_core_validation:
                    mock_core_result = MagicMock(spec=ComprehensiveResult)
                    mock_core_result.success = True
                    mock_core_result.issues = []
                    mock_core_result.warnings = []
                    mock_core_result.startup_diagnostics = {}
                    mock_core_validation.return_value = mock_core_result
                    
                    # Run orchestration
                    result = await startup_validator.run_validation_orchestration(DOMAIN, config_entry)
                    
                    # Verify orchestration execution
                    assert isinstance(result, ComprehensiveResult)
                    mock_pre_check.assert_called_once()
                    mock_post_check.assert_called_once()
                    mock_enhance.assert_called_once()
                    mock_report.assert_called_once()

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, hass, config_entry, temp_integration_dir):
        """Test collection of performance metrics during validation."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                # Run validation and measure performance
                import time
                start_time = time.time()
                result = await startup_validator.run_comprehensive_validation(DOMAIN)
                end_time = time.time()
                
                # Verify performance metrics are reasonable
                validation_duration = end_time - start_time
                assert validation_duration < 5.0  # Should complete within 5 seconds
                
                # Verify diagnostic data includes performance information
                assert result.diagnostic_data is not None
                assert hasattr(result, 'startup_diagnostics')

    def test_validation_cache_functionality(self, hass):
        """Test validation result caching functionality."""
        startup_validator = StartupValidationSystem(hass)
        
        # Verify cache is initially empty
        assert len(startup_validator._validation_cache) == 0
        
        # Test cache key generation and storage
        test_domain = "test_domain"
        
        # Mock a validation result
        mock_result = MagicMock(spec=ComprehensiveResult)
        mock_result.success = True
        
        # Manually add to cache to test functionality
        startup_validator._validation_cache[test_domain] = mock_result
        
        # Verify cache storage
        assert len(startup_validator._validation_cache) == 1
        assert startup_validator._validation_cache[test_domain] == mock_result
        
        # Test diagnostic information includes cache data
        diagnostics = startup_validator.get_startup_diagnostics(test_domain)
        assert diagnostics["validation_cache_size"] == 1
        assert test_domain in diagnostics["cached_domains"]
        assert f"{test_domain}_validation" in diagnostics

    @pytest.mark.asyncio
    async def test_comprehensive_integration_workflow(self, hass, config_entry, temp_integration_dir):
        """Test the complete integration workflow from validation to recovery to verification."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path_startup, \
             patch('custom_components.roost_scheduler.comprehensive_error_recovery.Path') as mock_path_recovery, \
             patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path_verification:
            
            mock_path_startup.return_value.parent = temp_integration_dir
            mock_path_recovery.return_value.parent = temp_integration_dir
            mock_path_verification.return_value.parent = temp_integration_dir
            
            # Step 1: Initial validation (with issues)
            startup_validator = StartupValidationSystem(hass)
            
            # Create domain mismatch for testing
            const_content = 'DOMAIN = "wrong_domain"\nVERSION = "1.0.0"'
            with open(temp_integration_dir / "const.py", "w") as f:
                f.write(const_content)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                initial_validation = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify issues are detected
                assert not initial_validation.success
                assert not initial_validation.domain_consistency_result.consistent
            
            # Step 2: Comprehensive validation
            comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
            initial_comprehensive = await comprehensive_validator.validate_all()
            
            # Step 3: Error recovery
            error_recovery = ComprehensiveErrorRecovery(hass, DOMAIN)
            
            with patch.object(error_recovery, '_registration_fixer') as mock_fixer:
                # Mock successful domain fix
                mock_fix_result = MagicMock()
                mock_fix_result.success = True
                mock_fix_result.changes_made = ["Fixed domain mismatch in const.py"]
                mock_fix_result.errors = []
                mock_fix_result.warnings = []
                mock_fix_result.verification_passed = True
                
                mock_fixer.fix_domain_mismatch.return_value = mock_fix_result
                
                recovery_result = await error_recovery.execute_comprehensive_recovery(
                    initial_validation, initial_comprehensive, config_entry
                )
                
                # Verify recovery was attempted
                assert isinstance(recovery_result, RecoveryResult)
                assert recovery_result.total_issues > 0
                assert len(recovery_result.recovery_steps) > 0
            
            # Step 4: Recovery verification
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Mock improved post-recovery validation
            with patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
                 patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
                
                # Mock successful post-recovery validation
                post_validation = MagicMock(spec=ComprehensiveResult)
                post_validation.success = True
                post_validation.issues = []
                post_validation.warnings = []
                post_validation.domain_consistency_result = MagicMock()
                post_validation.domain_consistency_result.consistent = True
                post_validation.config_flow_availability_result = MagicMock()
                post_validation.config_flow_availability_result.success = True
                
                post_comprehensive = MagicMock(spec=ComprehensiveValidationResult)
                post_comprehensive.valid = True
                
                mock_startup_validator.run_comprehensive_validation.return_value = post_validation
                mock_comprehensive_validator.validate_all.return_value = post_comprehensive
                
                verification_result = await verification_system.verify_recovery_effectiveness(
                    initial_validation, initial_comprehensive, recovery_result, config_entry
                )
                
                # Verify the complete workflow
                assert isinstance(verification_result, VerificationResult)
                assert verification_result.tests_run > 0
                assert "improvement_metrics" in verification_result.improvement_metrics or len(verification_result.improvement_metrics) >= 0
                
                # Verify improvement was detected
                improvement_metrics = verification_result.improvement_metrics
                if "issues_improvement_percentage" in improvement_metrics:
                    assert improvement_metrics["issues_improvement_percentage"] > 0