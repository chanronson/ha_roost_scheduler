"""Validation effectiveness verification tests for config flow handler fix."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json
import tempfile
import shutil

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.roost_scheduler.const import DOMAIN


class TestValidationEffectivenessVerification:
    """Test suite for verifying validation system effectiveness."""

    @pytest.fixture
    def hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.config = MagicMock()
        hass.config.components = {DOMAIN}  # Integration is loaded
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
        return entry

    @pytest.fixture
    def temp_integration_dir(self):
        """Create a temporary integration directory."""
        temp_dir = tempfile.mkdtemp()
        integration_path = Path(temp_dir) / "custom_components" / "roost_scheduler"
        integration_path.mkdir(parents=True)
        
        # Create valid integration files
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
        
        init_content = '''
async def async_setup(hass, config):
    return True

async def async_setup_entry(hass, entry):
    return True
'''
        with open(integration_path / "__init__.py", "w") as f:
            f.write(init_content)
        
        yield integration_path
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_domain_consistency_verification_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of domain consistency verification."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        with patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Mock domain consistency checker
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock()
                mock_checker_class.return_value = mock_checker
                
                # Test successful domain consistency
                mock_result = MagicMock()
                mock_result.consistent = True
                mock_result.manifest_domain = "roost_scheduler"
                mock_result.const_domain = "roost_scheduler"
                mock_result.config_flow_domain = "roost_scheduler"
                
                mock_checker.validate_consistency.return_value = mock_result
                
                # Execute verification test
                test_result = await verification_system._verify_domain_consistency()
                
                # Verify effectiveness
                assert test_result["success"] is True
                assert test_result["details"]["consistent"] is True
                assert test_result["details"]["manifest_domain"] == "roost_scheduler"
                assert test_result["details"]["const_domain"] == "roost_scheduler"
                assert test_result["details"]["config_flow_domain"] == "roost_scheduler"
                assert len(test_result["errors"]) == 0
                
                # Test domain mismatch detection
                mock_result.consistent = False
                mock_result.const_domain = "wrong_domain"
                
                test_result = await verification_system._verify_domain_consistency()
                
                # Verify mismatch detection effectiveness
                assert test_result["success"] is False
                assert test_result["details"]["consistent"] is False
                assert len(test_result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_config_flow_registration_verification_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of config flow registration verification."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        with patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Mock config flow validator
            with patch('custom_components.roost_scheduler.config_flow_validator.ConfigFlowValidator') as mock_validator_class:
                mock_validator = MagicMock()
                mock_validator_class.return_value = mock_validator
                
                # Test successful config flow registration
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.diagnostic_data = {
                    "config_flow_registered": True,
                    "config_flow_class_instantiable": True
                }
                mock_result.issues = []
                mock_result.warnings = []
                
                mock_validator.validate_config_flow_registration.return_value = mock_result
                
                # Execute verification test
                test_result = await verification_system._verify_config_flow_registration()
                
                # Verify effectiveness
                assert test_result["success"] is True
                assert test_result["details"]["config_flow_registered"] is True
                assert test_result["details"]["config_flow_class_instantiable"] is True
                assert len(test_result["errors"]) == 0
                
                # Test config flow registration failure detection
                mock_result.success = False
                mock_result.issues = ["Config flow class not found"]
                mock_result.diagnostic_data["config_flow_registered"] = False
                
                test_result = await verification_system._verify_config_flow_registration()
                
                # Verify failure detection effectiveness
                assert test_result["success"] is False
                assert len(test_result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_manifest_validation_verification_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of manifest validation verification."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        with patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Mock manifest validator
            with patch('custom_components.roost_scheduler.manifest_validator.ManifestValidator') as mock_validator_class:
                mock_validator = MagicMock()
                mock_validator_class.return_value = mock_validator
                
                # Test successful manifest validation
                mock_result = MagicMock()
                mock_result.valid = True
                mock_result.issues = []
                mock_result.warnings = []
                
                mock_validator.validate_manifest.return_value = mock_result
                
                # Execute verification test
                test_result = await verification_system._verify_manifest_validation()
                
                # Verify effectiveness
                assert test_result["success"] is True
                assert test_result["details"]["valid"] is True
                assert len(test_result["errors"]) == 0
                
                # Test manifest validation failure detection
                mock_result.valid = False
                mock_result.issues = ["Missing required field: config_flow"]
                
                test_result = await verification_system._verify_manifest_validation()
                
                # Verify failure detection effectiveness
                assert test_result["success"] is False
                assert len(test_result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_integration_loading_verification_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of integration loading verification."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        verification_system = RecoveryVerificationSystem(hass, DOMAIN)
        
        # Test successful integration loading (integration is loaded in hass fixture)
        test_result = await verification_system._verify_integration_loading()
        
        # Verify effectiveness
        assert test_result["success"] is True
        assert test_result["details"]["integration_loaded"] is True
        assert len(test_result["errors"]) == 0
        
        # Test integration not loaded detection
        hass.config.components.remove(DOMAIN)
        
        test_result = await verification_system._verify_integration_loading()
        
        # Verify failure detection effectiveness
        assert test_result["success"] is False
        assert test_result["details"]["integration_loaded"] is False
        assert len(test_result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_service_registration_verification_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of service registration verification."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        verification_system = RecoveryVerificationSystem(hass, DOMAIN)
        
        # Test successful service registration (services are registered in hass fixture)
        test_result = await verification_system._verify_service_registration()
        
        # Verify effectiveness
        assert test_result["success"] is True
        assert test_result["details"]["total_services"] == 3
        assert len(test_result["details"]["missing_services"]) == 0
        assert len(test_result["errors"]) == 0
        
        # Test missing services detection
        hass.services.async_services.return_value = {DOMAIN: {"apply_slot": {}}}  # Missing services
        
        test_result = await verification_system._verify_service_registration()
        
        # Verify missing services detection effectiveness
        assert test_result["success"] is False
        assert len(test_result["details"]["missing_services"]) > 0
        assert len(test_result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_end_to_end_verification_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of end-to-end verification."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        with patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Mock startup validator for end-to-end test
            with patch.object(verification_system, '_startup_validator') as mock_startup_validator:
                # Test successful end-to-end validation
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.issues = []
                mock_result.warnings = []
                mock_result.domain_consistency_result = MagicMock()
                mock_result.domain_consistency_result.consistent = True
                mock_result.config_flow_availability_result = MagicMock()
                mock_result.config_flow_availability_result.success = True
                
                mock_startup_validator.run_comprehensive_validation.return_value = mock_result
                
                # Execute verification test
                test_result = await verification_system._verify_end_to_end()
                
                # Verify effectiveness
                assert test_result["success"] is True
                assert test_result["details"]["comprehensive_validation_success"] is True
                assert test_result["details"]["domain_consistent"] is True
                assert test_result["details"]["config_flow_available"] is True
                assert len(test_result["errors"]) == 0
                
                # Test end-to-end failure detection
                mock_result.success = False
                mock_result.issues = ["Critical validation failure"]
                mock_result.domain_consistency_result.consistent = False
                mock_result.config_flow_availability_result.success = False
                
                test_result = await verification_system._verify_end_to_end()
                
                # Verify failure detection effectiveness
                assert test_result["success"] is False
                assert test_result["details"]["comprehensive_validation_success"] is False
                assert test_result["details"]["domain_consistent"] is False
                assert test_result["details"]["config_flow_available"] is False
                assert len(test_result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_improvement_metrics_calculation_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of improvement metrics calculation."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import RecoveryResult
        
        with patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Create mock pre-recovery results (with issues)
            pre_validation = MagicMock()
            pre_validation.issues = ["Issue 1", "Issue 2", "Issue 3", "Issue 4"]
            pre_validation.warnings = ["Warning 1", "Warning 2"]
            pre_validation.domain_consistency_result = MagicMock()
            pre_validation.domain_consistency_result.consistent = False
            pre_validation.config_flow_availability_result = MagicMock()
            pre_validation.config_flow_availability_result.success = False
            pre_validation.success = False
            
            pre_comprehensive = MagicMock()
            pre_comprehensive.manifest_result = MagicMock()
            pre_comprehensive.manifest_result.valid = False
            pre_comprehensive.dependency_result = MagicMock()
            pre_comprehensive.dependency_result.valid = False
            
            # Create mock recovery result
            recovery_result = MagicMock(spec=RecoveryResult)
            recovery_result.total_issues = 4
            recovery_result.recovered_issues = 3
            recovery_result.duration_seconds = 2.5
            
            # Mock post-recovery validation results (improved)
            with patch.object(verification_system, '_startup_validator') as mock_startup_validator, \
                 patch.object(verification_system, '_comprehensive_validator') as mock_comprehensive_validator:
                
                post_validation = MagicMock()
                post_validation.issues = ["Issue 4"]  # Only 1 issue remains
                post_validation.warnings = []  # All warnings resolved
                post_validation.domain_consistency_result = MagicMock()
                post_validation.domain_consistency_result.consistent = True  # Improved
                post_validation.config_flow_availability_result = MagicMock()
                post_validation.config_flow_availability_result.success = True  # Improved
                post_validation.success = True  # Overall improved
                
                post_comprehensive = MagicMock()
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
                
                # Verify calculation effectiveness
                assert metrics["issues_before"] == 4
                assert metrics["issues_after"] == 1
                assert metrics["issues_resolved"] == 3
                assert metrics["issues_improvement_percentage"] == 75.0
                
                assert metrics["warnings_before"] == 2
                assert metrics["warnings_after"] == 0
                assert metrics["warnings_resolved"] == 2
                assert metrics["warnings_improvement_percentage"] == 100.0
                
                assert metrics["domain_consistency_improved"] is True
                assert metrics["config_flow_availability_improved"] is True
                assert metrics["manifest_validation_improved"] is True
                assert metrics["dependency_validation_improved"] is True
                assert metrics["overall_validation_improved"] is True
                
                assert metrics["recovery_duration"] == 2.5
                assert metrics["recovery_success_rate"] == 75.0

    @pytest.mark.asyncio
    async def test_verification_status_determination_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of verification status determination."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        
        verification_system = RecoveryVerificationSystem(hass, DOMAIN)
        
        # Test "verified" status (high pass rate + significant improvement)
        improvement_metrics = {
            "issues_improvement_percentage": 80.0,
            "overall_validation_improved": True,
            "domain_consistency_improved": True,
            "config_flow_availability_improved": True
        }
        
        status, success = verification_system._determine_verification_status(9, 1, improvement_metrics)
        assert status == "verified"
        assert success is True
        
        # Test "partial" status (moderate pass rate or some improvement)
        improvement_metrics = {
            "issues_improvement_percentage": 40.0,
            "overall_validation_improved": True,
            "domain_consistency_improved": False,
            "config_flow_availability_improved": True
        }
        
        status, success = verification_system._determine_verification_status(7, 3, improvement_metrics)
        assert status == "partial"
        assert success is True
        
        # Test "limited" status (low pass rate but some tests pass)
        improvement_metrics = {
            "issues_improvement_percentage": 20.0,
            "overall_validation_improved": False,
            "domain_consistency_improved": False,
            "config_flow_availability_improved": False
        }
        
        status, success = verification_system._determine_verification_status(5, 5, improvement_metrics)
        assert status == "limited"
        assert success is True
        
        # Test "failed" status (very low pass rate and no improvement)
        status, success = verification_system._determine_verification_status(2, 8, improvement_metrics)
        assert status == "failed"
        assert success is False

    @pytest.mark.asyncio
    async def test_verification_recommendations_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of verification recommendations generation."""
        from custom_components.roost_scheduler.recovery_verification_system import (
            RecoveryVerificationSystem, VerificationTest
        )
        from custom_components.roost_scheduler.comprehensive_error_recovery import RecoveryResult
        
        verification_system = RecoveryVerificationSystem(hass, DOMAIN)
        
        # Create mock verification tests with mixed results
        verification_tests = [
            VerificationTest(
                test_id="domain_test",
                name="Domain Consistency Test",
                description="Test domain consistency",
                category="domain_consistency",
                priority=10,
                success=True,
                duration_seconds=0.1,
                details={},
                errors=[],
                warnings=[]
            ),
            VerificationTest(
                test_id="config_flow_test",
                name="Config Flow Test",
                description="Test config flow registration",
                category="config_flow_registration",
                priority=9,
                success=False,
                duration_seconds=0.2,
                details={},
                errors=["Config flow registration failed"],
                warnings=[]
            ),
            VerificationTest(
                test_id="manifest_test",
                name="Manifest Test",
                description="Test manifest validation",
                category="manifest_validation",
                priority=8,
                success=True,
                duration_seconds=0.1,
                details={},
                errors=[],
                warnings=[]
            )
        ]
        
        # Create mock improvement metrics
        improvement_metrics = {
            "issues_improvement_percentage": 60.0,
            "overall_validation_improved": True
        }
        
        # Create mock recovery result
        recovery_result = MagicMock(spec=RecoveryResult)
        recovery_result.emergency_mode = False
        recovery_result.fallbacks_applied = ["fallback1"]
        
        # Generate recommendations
        recommendations = verification_system._generate_verification_recommendations(
            verification_tests, improvement_metrics, recovery_result
        )
        
        # Verify recommendation effectiveness
        assert len(recommendations) > 0
        
        # Should identify critical failures
        critical_failure_mentioned = any(
            "critical" in rec.lower() or "config flow" in rec.lower() 
            for rec in recommendations
        )
        assert critical_failure_mentioned
        
        # Should mention improvement rate
        improvement_mentioned = any(
            "issue resolution" in rec.lower() or "improvement" in rec.lower()
            for rec in recommendations
        )
        assert improvement_mentioned
        
        # Should mention fallbacks if applied
        fallback_mentioned = any(
            "fallback" in rec.lower() for rec in recommendations
        )
        assert fallback_mentioned
        
        # Test emergency mode recommendations
        recovery_result.emergency_mode = True
        recovery_result.fallbacks_applied = ["fallback1", "fallback2", "fallback3"]
        
        recommendations = verification_system._generate_verification_recommendations(
            verification_tests, improvement_metrics, recovery_result
        )
        
        # Should mention emergency mode
        emergency_mentioned = any(
            "emergency" in rec.lower() for rec in recommendations
        )
        assert emergency_mentioned
        
        # Should mention multiple fallbacks
        multiple_fallbacks_mentioned = any(
            "multiple fallback" in rec.lower() for rec in recommendations
        )
        assert multiple_fallbacks_mentioned

    @pytest.mark.asyncio
    async def test_comprehensive_verification_workflow_effectiveness(self, hass, config_entry, temp_integration_dir):
        """Test effectiveness of the complete verification workflow."""
        from custom_components.roost_scheduler.recovery_verification_system import RecoveryVerificationSystem
        from custom_components.roost_scheduler.comprehensive_error_recovery import RecoveryResult
        
        with patch('custom_components.roost_scheduler.recovery_verification_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            verification_system = RecoveryVerificationSystem(hass, DOMAIN)
            
            # Create comprehensive test scenario
            pre_validation = MagicMock()
            pre_validation.issues = ["Issue 1", "Issue 2"]
            pre_validation.warnings = ["Warning 1"]
            pre_validation.success = False
            
            pre_comprehensive = MagicMock()
            pre_comprehensive.valid = False
            
            recovery_result = MagicMock(spec=RecoveryResult)
            recovery_result.success = True
            recovery_result.total_issues = 2
            recovery_result.recovered_issues = 2
            recovery_result.duration_seconds = 1.0
            recovery_result.emergency_mode = False
            recovery_result.fallbacks_applied = []
            
            # Mock all verification test methods to return success
            verification_methods = [
                '_verify_domain_consistency',
                '_verify_config_flow_registration',
                '_verify_manifest_validation',
                '_verify_dependency_resolution',
                '_verify_file_system',
                '_verify_version_compatibility',
                '_verify_integration_loading',
                '_verify_config_flow_instantiation',
                '_verify_service_registration',
                '_verify_end_to_end'
            ]
            
            for method_name in verification_methods:
                mock_method = AsyncMock(return_value={
                    "success": True,
                    "details": {"test_passed": True},
                    "errors": [],
                    "warnings": []
                })
                setattr(verification_system, method_name, mock_method)
            
            # Mock improvement metrics calculation
            with patch.object(verification_system, '_calculate_improvement_metrics') as mock_calc_metrics:
                mock_calc_metrics.return_value = {
                    "issues_before": 2,
                    "issues_after": 0,
                    "issues_resolved": 2,
                    "issues_improvement_percentage": 100.0,
                    "warnings_before": 1,
                    "warnings_after": 0,
                    "warnings_resolved": 1,
                    "warnings_improvement_percentage": 100.0,
                    "overall_validation_improved": True,
                    "domain_consistency_improved": True,
                    "config_flow_availability_improved": True,
                    "recovery_duration": 1.0,
                    "recovery_success_rate": 100.0
                }
                
                # Execute comprehensive verification
                result = await verification_system.verify_recovery_effectiveness(
                    pre_validation, pre_comprehensive, recovery_result, config_entry
                )
                
                # Verify comprehensive workflow effectiveness
                assert result.success is True
                assert result.overall_status == "verified"
                assert result.tests_run == len(verification_methods)
                assert result.tests_passed == len(verification_methods)
                assert result.tests_failed == 0
                assert result.duration_seconds > 0
                assert len(result.verification_tests) == len(verification_methods)
                assert len(result.recommendations) > 0
                
                # Verify all tests were executed
                for method_name in verification_methods:
                    method = getattr(verification_system, method_name)
                    method.assert_called_once()
                
                # Verify improvement metrics were calculated
                mock_calc_metrics.assert_called_once_with(
                    pre_validation, pre_comprehensive, recovery_result
                )
                
                # Verify test results structure
                for test in result.verification_tests:
                    assert test.test_id is not None
                    assert test.name is not None
                    assert test.success is True
                    assert test.duration_seconds >= 0