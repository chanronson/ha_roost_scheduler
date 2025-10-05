"""Validation system integration tests for config flow handler fix.

This test suite focuses on testing the validation system integration,
orchestration, and coordination between different validation components.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
from custom_components.roost_scheduler.config_flow_validator import (
    ConfigFlowValidator,
    ValidationResult
)
from custom_components.roost_scheduler.integration_diagnostics import (
    IntegrationDiagnostics,
    DiagnosticData
)
from custom_components.roost_scheduler.domain_consistency_checker import (
    DomainConsistencyChecker,
    ConsistencyResult
)
from custom_components.roost_scheduler.comprehensive_validator import (
    ComprehensiveValidator,
    ComprehensiveValidationResult
)


class TestValidationSystemIntegration:
    """Test suite for validation system integration."""

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

    @pytest.fixture
    def temp_integration_dir(self):
        """Create a temporary integration directory."""
        temp_dir = tempfile.mkdtemp()
        integration_path = Path(temp_dir) / "custom_components" / "roost_scheduler"
        integration_path.mkdir(parents=True)
        
        # Create valid integration files
        self._create_valid_integration_files(integration_path)
        
        yield integration_path
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
                
                mock_enhanced_result = MagicMock(spec=ComprehensiveResult)
                mock_enhanced_result.success = True
                mock_enhanced_result.startup_diagnostics = {"orchestration": "completed"}
                mock_enhance.return_value = mock_enhanced_result
                
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
                    
                    # Verify orchestration result
                    assert result.success
                    assert "orchestration" in result.startup_diagnostics

    @pytest.mark.asyncio
    async def test_config_flow_validator_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of config flow validator with startup validation."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            # Mock config flow validator
            with patch('custom_components.roost_scheduler.config_flow_validator.ConfigFlowValidator') as mock_validator_class:
                mock_validator = MagicMock(spec=ConfigFlowValidator)
                mock_validator_class.return_value = mock_validator
                
                # Mock successful config flow validation
                mock_validation_result = MagicMock(spec=ValidationResult)
                mock_validation_result.success = True
                mock_validation_result.issues = []
                mock_validation_result.warnings = []
                mock_validation_result.recommendations = []
                mock_validation_result.diagnostic_data = {
                    "config_flow_registered": True,
                    "config_flow_class_found": True
                }
                
                mock_validator.validate_config_flow_registration.return_value = mock_validation_result
                
                with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                     patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                     patch.object(startup_validator, '_is_domain_available', return_value=True):
                    
                    # Run validation
                    result = await startup_validator.run_comprehensive_validation(DOMAIN)
                    
                    # Verify config flow validator integration
                    assert isinstance(result, ComprehensiveResult)
                    assert result.config_flow_availability_result.success
                    assert result.config_flow_availability_result.diagnostic_data["config_flow_registered"]

    @pytest.mark.asyncio
    async def test_domain_consistency_checker_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of domain consistency checker with startup validation."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            # Mock domain consistency checker
            with patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker') as mock_checker_class:
                mock_checker = MagicMock(spec=DomainConsistencyChecker)
                mock_checker_class.return_value = mock_checker
                
                # Mock successful domain consistency validation
                mock_consistency_result = MagicMock(spec=ConsistencyResult)
                mock_consistency_result.consistent = True
                mock_consistency_result.manifest_domain = "roost_scheduler"
                mock_consistency_result.const_domain = "roost_scheduler"
                mock_consistency_result.config_flow_domain = "roost_scheduler"
                mock_consistency_result.issues = []
                
                mock_checker.validate_consistency.return_value = mock_consistency_result
                
                with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                     patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                     patch.object(startup_validator, '_is_domain_available', return_value=True):
                    
                    # Run validation
                    result = await startup_validator.run_comprehensive_validation(DOMAIN)
                    
                    # Verify domain consistency checker integration
                    assert isinstance(result, ComprehensiveResult)
                    assert result.domain_consistency_result.consistent
                    assert result.domain_consistency_result.manifest_domain == "roost_scheduler"
                    assert result.domain_consistency_result.const_domain == "roost_scheduler"

    @pytest.mark.asyncio
    async def test_integration_diagnostics_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of integration diagnostics with startup validation."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            # Mock integration diagnostics
            with patch('custom_components.roost_scheduler.integration_diagnostics.IntegrationDiagnostics') as mock_diagnostics_class:
                mock_diagnostics = MagicMock(spec=IntegrationDiagnostics)
                mock_diagnostics_class.return_value = mock_diagnostics
                
                # Mock successful diagnostics collection
                mock_diagnostic_data = MagicMock(spec=DiagnosticData)
                mock_diagnostic_data.ha_version = "2023.12.0"
                mock_diagnostic_data.integration_version = "1.0.0"
                mock_diagnostic_data.domain_consistency = True
                mock_diagnostic_data.file_permissions = {"manifest.json": True, "const.py": True}
                mock_diagnostic_data.import_status = {"homeassistant": True, "config_entries": True}
                mock_diagnostic_data.dependency_status = {"http": True}
                mock_diagnostic_data.config_flow_class_found = True
                mock_diagnostic_data.manifest_valid = True
                mock_diagnostic_data.error_details = []
                
                mock_diagnostics.collect_diagnostic_data.return_value = mock_diagnostic_data
                
                with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                     patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                     patch.object(startup_validator, '_is_domain_available', return_value=True):
                    
                    # Run validation
                    result = await startup_validator.run_comprehensive_validation(DOMAIN)
                    
                    # Verify integration diagnostics integration
                    assert isinstance(result, ComprehensiveResult)
                    assert result.diagnostic_data.ha_version == "2023.12.0"
                    assert result.diagnostic_data.integration_version == "1.0.0"
                    assert result.diagnostic_data.domain_consistency
                    assert result.diagnostic_data.config_flow_class_found
                    assert result.diagnostic_data.manifest_valid

    @pytest.mark.asyncio
    async def test_comprehensive_validator_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of comprehensive validator with validation system."""
        comprehensive_validator = ComprehensiveValidator(hass, temp_integration_dir)
        
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
            
            # Verify comprehensive validator integration
            assert isinstance(result, ComprehensiveValidationResult)
            assert result.valid
            assert result.manifest_result.valid
            assert result.dependency_result.valid
            assert result.version_result.compatible
            
            # Verify all validators were called
            mock_manifest_instance.validate_manifest.assert_called_once()
            mock_dependency_instance.validate_dependencies.assert_called_once()
            mock_version_instance.validate_compatibility.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_cache_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of validation caching system."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                # First validation run (should populate cache)
                start_time = time.time()
                first_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                first_duration = time.time() - start_time
                
                # Verify cache population
                assert len(startup_validator._validation_cache) == 1
                assert DOMAIN in startup_validator._validation_cache
                
                # Second validation run (should use cache)
                start_time = time.time()
                second_result = await startup_validator.run_comprehensive_validation(DOMAIN)
                second_duration = time.time() - start_time
                
                # Verify cache usage
                assert first_result == second_result
                # Second run should be faster due to caching
                # Note: In mock environment, timing might not be reliable, so we just verify cache usage
                assert len(startup_validator._validation_cache) == 1
                
                # Verify cache diagnostics
                diagnostics = startup_validator.get_startup_diagnostics(DOMAIN)
                assert diagnostics["validation_cache_size"] == 1
                assert DOMAIN in diagnostics["cached_domains"]
                assert f"{DOMAIN}_validation" in diagnostics

    @pytest.mark.asyncio
    async def test_validation_error_aggregation_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of validation error aggregation across components."""
        # Create files with multiple issues
        # Modify const.py to have wrong domain
        const_content = '''"""Constants for Roost Scheduler integration."""
DOMAIN = "wrong_domain"
VERSION = "1.0.0"
REQUIRED_DOMAINS = ["http"]
OPTIONAL_DOMAINS = []
'''
        with open(temp_integration_dir / "const.py", "w") as f:
            f.write(const_content)
        
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                # Run validation with issues
                result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify error aggregation
                assert isinstance(result, ComprehensiveResult)
                assert not result.success  # Should fail due to domain mismatch
                assert not result.domain_consistency_result.consistent
                
                # Verify issues are aggregated from multiple components
                assert len(result.issues) > 0
                
                # Verify domain consistency issues are captured
                assert result.domain_consistency_result.manifest_domain == "roost_scheduler"
                assert result.domain_consistency_result.const_domain == "wrong_domain"

    @pytest.mark.asyncio
    async def test_validation_performance_monitoring_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of validation performance monitoring."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                # Run validation with performance monitoring
                start_time = time.time()
                result = await startup_validator.run_comprehensive_validation(DOMAIN)
                end_time = time.time()
                
                # Verify performance monitoring
                assert isinstance(result, ComprehensiveResult)
                validation_duration = end_time - start_time
                
                # Verify performance is reasonable
                assert validation_duration < 10.0  # Should complete within 10 seconds
                
                # Verify diagnostic data includes performance information
                assert result.diagnostic_data is not None
                assert result.startup_diagnostics is not None
                
                # Verify performance metrics in diagnostics
                diagnostics = startup_validator.get_startup_diagnostics(DOMAIN)
                assert "validation_cache_size" in diagnostics
                assert "cached_domains" in diagnostics

    @pytest.mark.asyncio
    async def test_validation_component_coordination_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of validation component coordination."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            # Track component calls to verify coordination
            component_calls = []
            
            def track_config_flow_validator(*args, **kwargs):
                component_calls.append("config_flow_validator")
                mock_validator = MagicMock(spec=ConfigFlowValidator)
                mock_result = MagicMock(spec=ValidationResult)
                mock_result.success = True
                mock_result.issues = []
                mock_result.warnings = []
                mock_result.recommendations = []
                mock_result.diagnostic_data = {}
                mock_validator.validate_config_flow_registration.return_value = mock_result
                return mock_validator
            
            def track_domain_consistency_checker(*args, **kwargs):
                component_calls.append("domain_consistency_checker")
                mock_checker = MagicMock(spec=DomainConsistencyChecker)
                mock_result = MagicMock(spec=ConsistencyResult)
                mock_result.consistent = True
                mock_result.manifest_domain = "roost_scheduler"
                mock_result.const_domain = "roost_scheduler"
                mock_result.config_flow_domain = "roost_scheduler"
                mock_result.issues = []
                mock_checker.validate_consistency.return_value = mock_result
                return mock_checker
            
            def track_integration_diagnostics(*args, **kwargs):
                component_calls.append("integration_diagnostics")
                mock_diagnostics = MagicMock(spec=IntegrationDiagnostics)
                mock_data = MagicMock(spec=DiagnosticData)
                mock_data.ha_version = "2023.12.0"
                mock_data.integration_version = "1.0.0"
                mock_data.domain_consistency = True
                mock_data.file_permissions = {}
                mock_data.import_status = {}
                mock_data.dependency_status = {}
                mock_data.config_flow_class_found = True
                mock_data.manifest_valid = True
                mock_data.error_details = []
                mock_diagnostics.collect_diagnostic_data.return_value = mock_data
                return mock_diagnostics
            
            with patch('custom_components.roost_scheduler.config_flow_validator.ConfigFlowValidator', side_effect=track_config_flow_validator), \
                 patch('custom_components.roost_scheduler.domain_consistency_checker.DomainConsistencyChecker', side_effect=track_domain_consistency_checker), \
                 patch('custom_components.roost_scheduler.integration_diagnostics.IntegrationDiagnostics', side_effect=track_integration_diagnostics), \
                 patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                 patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                 patch.object(startup_validator, '_is_domain_available', return_value=True):
                
                # Run validation
                result = await startup_validator.run_comprehensive_validation(DOMAIN)
                
                # Verify component coordination
                assert isinstance(result, ComprehensiveResult)
                assert result.success
                
                # Verify all components were called in coordination
                assert "config_flow_validator" in component_calls
                assert "domain_consistency_checker" in component_calls
                assert "integration_diagnostics" in component_calls
                
                # Verify results from all components are integrated
                assert result.config_flow_availability_result.success
                assert result.domain_consistency_result.consistent
                assert result.diagnostic_data.ha_version == "2023.12.0"

    @pytest.mark.asyncio
    async def test_validation_exception_handling_integration(self, hass, config_entry, temp_integration_dir):
        """Test integration of validation exception handling across components."""
        with patch('custom_components.roost_scheduler.startup_validation_system.Path') as mock_path:
            mock_path.return_value.parent = temp_integration_dir
            
            startup_validator = StartupValidationSystem(hass)
            
            # Mock component that raises exception
            with patch('custom_components.roost_scheduler.config_flow_validator.ConfigFlowValidator') as mock_validator_class:
                mock_validator_class.side_effect = Exception("Config flow validator exception")
                
                with patch.object(startup_validator, '_check_ha_dependencies', return_value=[]), \
                     patch.object(startup_validator, '_check_integration_imports', return_value=[]), \
                     patch.object(startup_validator, '_is_domain_available', return_value=True):
                    
                    # Run validation with exception
                    result = await startup_validator.run_comprehensive_validation(DOMAIN)
                    
                    # Verify graceful exception handling
                    assert isinstance(result, ComprehensiveResult)
                    assert not result.success  # Should fail due to exception
                    assert len(result.issues) > 0
                    
                    # Verify exception is captured in issues
                    exception_captured = any(
                        "exception" in str(issue).lower() or "error" in str(issue).lower()
                        for issue in result.issues
                    )
                    assert exception_captured