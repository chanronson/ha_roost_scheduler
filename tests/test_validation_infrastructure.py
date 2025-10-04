"""Unit tests for validation infrastructure components."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigFlow

from custom_components.roost_scheduler.config_flow_validator import (
    ConfigFlowValidator,
    ValidationResult,
    ValidationIssue
)
from custom_components.roost_scheduler.integration_diagnostics import (
    IntegrationDiagnostics,
    DiagnosticData,
    PermissionStatus,
    DependencyStatus,
    ImportStatus
)
from custom_components.roost_scheduler.config_flow_logging import (
    ConfigFlowLogger,
    ConfigFlowLogEntry,
    DiagnosticLogData,
    ConfigFlowDiagnosticReporter
)
from custom_components.roost_scheduler.config_flow_registration_fixer import (
    ConfigFlowRegistrationFixer,
    RegistrationIssue,
    FixResult,
    OverallFixResult,
    FixVerificationResult,
    RollbackResult
)


class TestConfigFlowValidator:
    """Test cases for ConfigFlowValidator."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        hass.loop.time.return_value = 1234567890.0
        hass.config_entries = MagicMock()
        hass.config_entries.flow = MagicMock()
        hass.config_entries.flow._flows = {}
        hass.components = MagicMock()
        return hass

    @pytest.fixture
    def validator(self, mock_hass):
        """Create a ConfigFlowValidator instance."""
        with patch.object(ConfigFlowValidator, '_get_integration_path') as mock_path:
            mock_path.return_value = Path("/test/integration")
            return ConfigFlowValidator(mock_hass, "test_domain")

    @pytest.mark.asyncio
    async def test_validate_config_flow_registration_success(self, validator, mock_hass):
        """Test successful config flow registration validation."""
        # Mock successful validation methods
        validator._check_config_flow_class = AsyncMock(return_value=ValidationResult(
            success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}
        ))
        validator._check_config_flow_registration = AsyncMock(return_value=ValidationResult(
            success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}
        ))
        validator._check_config_flow_methods = AsyncMock(return_value=ValidationResult(
            success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}
        ))

        result = await validator.validate_config_flow_registration()

        assert result.success is True
        assert len(result.issues) == 0
        assert "Config flow registration validation passed" in result.recommendations

    @pytest.mark.asyncio
    async def test_validate_config_flow_registration_with_errors(self, validator, mock_hass):
        """Test config flow registration validation with errors."""
        # Mock validation methods with errors
        error_issue = ValidationIssue(
            issue_type="test_error",
            description="Test error",
            severity="error",
            fix_available=False,
            fix_description="Fix test error",
            diagnostic_info={}
        )
        
        validator._check_config_flow_class = AsyncMock(return_value=ValidationResult(
            success=False, issues=[error_issue], warnings=[], recommendations=[], diagnostic_data={}
        ))
        validator._check_config_flow_registration = AsyncMock(return_value=ValidationResult(
            success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}
        ))
        validator._check_config_flow_methods = AsyncMock(return_value=ValidationResult(
            success=True, issues=[], warnings=[], recommendations=[], diagnostic_data={}
        ))

        result = await validator.validate_config_flow_registration()

        assert result.success is False
        assert len(result.issues) == 1
        assert result.issues[0].severity == "error"
        assert "Fix config flow registration issues before proceeding" in result.recommendations

    @pytest.mark.asyncio
    async def test_validate_domain_consistency_success(self, validator):
        """Test successful domain consistency validation."""
        validator._get_manifest_domain = AsyncMock(return_value="test_domain")
        validator._get_const_domain = AsyncMock(return_value="test_domain")
        validator._get_config_flow_domain = AsyncMock(return_value="test_domain")

        result = await validator.validate_domain_consistency()

        assert result.success is True
        assert len(result.issues) == 0
        assert result.diagnostic_data["manifest_domain"] == "test_domain"
        assert result.diagnostic_data["const_domain"] == "test_domain"
        assert result.diagnostic_data["config_flow_domain"] == "test_domain"

    @pytest.mark.asyncio
    async def test_validate_domain_consistency_mismatch(self, validator):
        """Test domain consistency validation with mismatch."""
        validator._get_manifest_domain = AsyncMock(return_value="domain1")
        validator._get_const_domain = AsyncMock(return_value="domain2")
        validator._get_config_flow_domain = AsyncMock(return_value="domain3")

        result = await validator.validate_domain_consistency()

        assert result.success is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "domain_mismatch"
        assert result.issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_validate_domain_consistency_missing(self, validator):
        """Test domain consistency validation with missing domains."""
        validator._get_manifest_domain = AsyncMock(return_value=None)
        validator._get_const_domain = AsyncMock(return_value=None)
        validator._get_config_flow_domain = AsyncMock(return_value=None)

        result = await validator.validate_domain_consistency()

        assert result.success is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "domain_missing"
        assert result.issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_validate_manifest_configuration_success(self, validator):
        """Test successful manifest configuration validation."""
        manifest_data = {
            "domain": "test_domain",
            "name": "Test Integration",
            "version": "1.0.0",
            "config_flow": True,
            "dependencies": ["http"]
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(manifest_data))):
            with patch.object(Path, "exists", return_value=True):
                validator._check_dependency_available = AsyncMock(return_value=True)
                
                result = await validator.validate_manifest_configuration()

        assert result.success is True
        assert len(result.issues) == 0
        assert result.diagnostic_data["manifest_data"] == manifest_data

    @pytest.mark.asyncio
    async def test_validate_manifest_configuration_missing_file(self, validator):
        """Test manifest validation with missing file."""
        with patch.object(Path, "exists", return_value=False):
            result = await validator.validate_manifest_configuration()

        assert result.success is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "manifest_missing"
        assert result.issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_validate_manifest_configuration_missing_fields(self, validator):
        """Test manifest validation with missing required fields."""
        manifest_data = {
            "name": "Test Integration",
            "version": "1.0.0"
            # Missing domain and config_flow
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(manifest_data))):
            with patch.object(Path, "exists", return_value=True):
                result = await validator.validate_manifest_configuration()

        assert result.success is False
        assert len(result.issues) >= 2  # Missing domain and config_flow
        missing_field_issues = [i for i in result.issues if i.issue_type == "manifest_missing_field"]
        assert len(missing_field_issues) >= 2

    @pytest.mark.asyncio
    async def test_validate_manifest_configuration_invalid_json(self, validator):
        """Test manifest validation with invalid JSON."""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with patch.object(Path, "exists", return_value=True):
                result = await validator.validate_manifest_configuration()

        assert result.success is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "manifest_json_error"
        assert result.issues[0].severity == "error"

    def test_get_validation_report(self, validator):
        """Test validation report generation."""
        # Add some cached validation results
        validator._validation_cache["test"] = ValidationResult(
            success=True, issues=[], warnings=["test warning"], 
            recommendations=[], diagnostic_data={}
        )
        
        report = validator.get_validation_report()
        
        assert report["domain"] == "test_domain"
        assert "integration_path" in report
        assert "validation_cache" in report
        assert "timestamp" in report

    @pytest.mark.asyncio
    async def test_check_config_flow_class_missing_file(self, validator):
        """Test config flow class check with missing file."""
        with patch.object(Path, "exists", return_value=False):
            result = await validator._check_config_flow_class()

        assert result.success is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "config_flow_file_missing"

    @pytest.mark.asyncio
    async def test_check_config_flow_class_missing_class(self, validator):
        """Test config flow class check with missing class."""
        content = "# No ConfigFlow class here"
        
        with patch("builtins.open", mock_open(read_data=content)):
            with patch.object(Path, "exists", return_value=True):
                result = await validator._check_config_flow_class()

        assert result.success is False
        # Check that we have issues related to missing ConfigFlow class
        class_missing_issues = [i for i in result.issues if "ConfigFlow" in i.description or "class" in i.issue_type]
        assert len(class_missing_issues) > 0

    @pytest.mark.asyncio
    async def test_get_manifest_domain(self, validator):
        """Test manifest domain extraction."""
        manifest_data = {"domain": "test_domain"}
        
        with patch("builtins.open", mock_open(read_data=json.dumps(manifest_data))):
            with patch.object(Path, "exists", return_value=True):
                domain = await validator._get_manifest_domain()

        assert domain == "test_domain"

    @pytest.mark.asyncio
    async def test_get_const_domain(self, validator):
        """Test const domain extraction."""
        content = 'DOMAIN = "test_domain"'
        
        with patch("builtins.open", mock_open(read_data=content)):
            with patch.object(Path, "exists", return_value=True):
                domain = await validator._get_const_domain()

        assert domain == "test_domain"

    @pytest.mark.asyncio
    async def test_get_config_flow_domain(self, validator):
        """Test config flow domain extraction."""
        content = 'class TestConfigFlow(ConfigFlow):\n    domain = "test_domain"'
        
        with patch("builtins.open", mock_open(read_data=content)):
            with patch.object(Path, "exists", return_value=True):
                domain = await validator._get_config_flow_domain()

        assert domain == "test_domain"


class TestIntegrationDiagnostics:
    """Test cases for IntegrationDiagnostics."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        hass.loop.time.return_value = 1234567890.0
        hass.config = MagicMock()
        hass.config.components = ["http", "frontend"]
        hass.config_entries = MagicMock()
        hass.config_entries.async_entries.return_value = []
        hass.components = MagicMock()
        return hass

    @pytest.fixture
    def diagnostics(self, mock_hass):
        """Create an IntegrationDiagnostics instance."""
        with patch.object(IntegrationDiagnostics, '_get_integration_path') as mock_path:
            mock_path.return_value = Path("/test/integration")
            return IntegrationDiagnostics(mock_hass, "test_domain")

    @pytest.mark.asyncio
    async def test_collect_diagnostic_data_success(self, diagnostics):
        """Test successful diagnostic data collection."""
        # Mock all the collection methods
        diagnostics._collect_system_info = AsyncMock(return_value={"platform": "test"})
        diagnostics._collect_integration_info = AsyncMock(return_value={"loaded": True})
        diagnostics._check_all_file_permissions = AsyncMock(return_value={})
        diagnostics._verify_all_dependencies = AsyncMock(return_value={})
        diagnostics._validate_all_imports = AsyncMock(return_value={})
        diagnostics._check_domain_consistency = AsyncMock(return_value=True)
        diagnostics._check_config_flow_class = AsyncMock(return_value=True)
        diagnostics._validate_manifest = AsyncMock(return_value=True)
        diagnostics._collect_error_details = AsyncMock(return_value=[])

        result = await diagnostics.collect_diagnostic_data()

        assert isinstance(result, DiagnosticData)
        assert result.domain_consistency is True
        assert result.config_flow_class_found is True
        assert result.manifest_valid is True
        assert len(result.error_details) == 0

    @pytest.mark.asyncio
    async def test_collect_diagnostic_data_with_error(self, diagnostics):
        """Test diagnostic data collection with error."""
        # Mock methods to raise an exception
        diagnostics._collect_system_info = AsyncMock(side_effect=Exception("Test error"))

        result = await diagnostics.collect_diagnostic_data()

        assert isinstance(result, DiagnosticData)
        assert result.domain_consistency is False
        assert len(result.error_details) == 1
        assert "Diagnostic collection failed" in result.error_details[0]

    @pytest.mark.asyncio
    async def test_check_file_permissions_existing_file(self, diagnostics):
        """Test file permission checking for existing file."""
        test_path = "/test/file.py"
        
        with patch.object(Path, "exists", return_value=True):
            with patch("os.access") as mock_access:
                mock_access.side_effect = lambda path, mode: {
                    os.R_OK: True,
                    os.W_OK: False,
                    os.X_OK: False
                }.get(mode, False)
                
                result = await diagnostics.check_file_permissions(test_path)

        assert result.exists is True
        assert result.readable is True
        assert result.writable is False
        assert result.executable is False
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_check_file_permissions_missing_file(self, diagnostics):
        """Test file permission checking for missing file."""
        test_path = "/test/missing.py"
        
        with patch.object(Path, "exists", return_value=False):
            result = await diagnostics.check_file_permissions(test_path)

        assert result.exists is False
        assert result.readable is False
        assert result.writable is False
        assert result.executable is False
        assert "Path does not exist" in result.error_message

    @pytest.mark.asyncio
    async def test_verify_dependencies(self, diagnostics):
        """Test dependency verification."""
        diagnostics._check_single_dependency = AsyncMock(return_value=DependencyStatus(available=True))
        diagnostics._check_python_dependency = AsyncMock(return_value=DependencyStatus(available=True))

        result = await diagnostics.verify_dependencies()

        assert isinstance(result, dict)
        assert len(result) > 0
        # Should have both required and optional dependencies
        required_deps = [k for k in result.keys() if k.startswith("required_")]
        optional_deps = [k for k in result.keys() if k.startswith("optional_")]
        python_deps = [k for k in result.keys() if k.startswith("python_")]
        
        assert len(required_deps) > 0
        assert len(optional_deps) > 0
        assert len(python_deps) > 0

    @pytest.mark.asyncio
    async def test_validate_imports(self, diagnostics):
        """Test import validation."""
        diagnostics._check_module_import = AsyncMock(return_value=ImportStatus(importable=True))

        result = await diagnostics.validate_imports()

        assert isinstance(result, dict)
        assert len(result) > 0
        # Should have both integration and HA imports
        integration_imports = [k for k in result.keys() if k.startswith("integration_")]
        ha_imports = [k for k in result.keys() if k.startswith("ha_")]
        
        assert len(integration_imports) > 0
        assert len(ha_imports) > 0

    def test_generate_troubleshooting_report(self, diagnostics):
        """Test troubleshooting report generation."""
        diagnostic_data = DiagnosticData(
            ha_version="2023.1.0",
            integration_version="1.0.0",
            domain_consistency=False,
            file_permissions={"test.py": PermissionStatus(True, True, True, True)},
            import_status={"test_module": ImportStatus(False, "Import error")},
            dependency_status={"required_http": DependencyStatus(True)},
            config_flow_class_found=False,
            manifest_valid=True,
            error_details=["Test error"],
            system_info={"platform": "test"},
            integration_info={"loaded": False}
        )

        report = diagnostics.generate_troubleshooting_report(diagnostic_data)

        assert "ROOST SCHEDULER INTEGRATION TROUBLESHOOTING REPORT" in report
        assert "Integration Version: 1.0.0" in report
        assert "Home Assistant Version: 2023.1.0" in report
        assert "VALIDATION STATUS:" in report
        assert "FILE PERMISSIONS:" in report
        assert "DEPENDENCY STATUS:" in report
        assert "IMPORT STATUS:" in report
        assert "ERROR DETAILS:" in report
        assert "RECOMMENDATIONS:" in report

    @pytest.mark.asyncio
    async def test_check_domain_consistency_success(self, diagnostics):
        """Test domain consistency check success."""
        manifest_data = {"domain": "test_domain"}
        const_content = 'DOMAIN = "test_domain"'
        
        with patch("builtins.open") as mock_file:
            mock_file.side_effect = [
                mock_open(read_data=json.dumps(manifest_data)).return_value,
                mock_open(read_data=const_content).return_value
            ]
            with patch.object(Path, "exists", return_value=True):
                result = await diagnostics._check_domain_consistency()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_domain_consistency_mismatch(self, diagnostics):
        """Test domain consistency check with mismatch."""
        manifest_data = {"domain": "domain1"}
        const_content = 'DOMAIN = "domain2"'
        
        with patch("builtins.open") as mock_file:
            mock_file.side_effect = [
                mock_open(read_data=json.dumps(manifest_data)).return_value,
                mock_open(read_data=const_content).return_value
            ]
            with patch.object(Path, "exists", return_value=True):
                result = await diagnostics._check_domain_consistency()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_single_dependency_available(self, diagnostics, mock_hass):
        """Test single dependency check when available."""
        mock_hass.components.test_dep = MagicMock()
        
        result = await diagnostics._check_single_dependency("test_dep")

        assert result.available is True
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_check_single_dependency_unavailable(self, diagnostics, mock_hass):
        """Test single dependency check when unavailable."""
        # Remove the dependency from components
        del mock_hass.components.test_dep
        
        with patch("builtins.__import__", side_effect=ImportError("Module not found")):
            result = await diagnostics._check_single_dependency("test_dep")

        assert result.available is False
        assert "Module not found" in result.error_message

    @pytest.mark.asyncio
    async def test_check_python_dependency_available(self, diagnostics):
        """Test Python dependency check when available."""
        mock_module = MagicMock()
        mock_module.__version__ = "1.0.0"
        
        with patch("builtins.__import__", return_value=mock_module):
            result = await diagnostics._check_python_dependency("test_module")

        assert result.available is True
        assert result.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_check_python_dependency_unavailable(self, diagnostics):
        """Test Python dependency check when unavailable."""
        with patch("builtins.__import__", side_effect=ImportError("Module not found")):
            result = await diagnostics._check_python_dependency("test_module")

        assert result.available is False
        assert "Module not found" in result.error_message

    @pytest.mark.asyncio
    async def test_check_module_import_success(self, diagnostics):
        """Test module import check success."""
        mock_module = MagicMock()
        mock_module.__file__ = "/test/module.py"
        
        with patch("builtins.__import__", return_value=mock_module):
            result = await diagnostics._check_module_import("test_module")

        assert result.importable is True
        assert result.module_path == "/test/module.py"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_check_module_import_failure(self, diagnostics):
        """Test module import check failure."""
        with patch("builtins.__import__", side_effect=ImportError("Import failed")):
            result = await diagnostics._check_module_import("test_module")

        assert result.importable is False
        assert "Import failed" in result.error_message


class TestConfigFlowLogger:
    """Test cases for ConfigFlowLogger."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        hass.loop.time.return_value = 1234567890.0
        return hass

    @pytest.fixture
    def mock_store(self):
        """Create a mock Store instance."""
        store = MagicMock()
        store.async_save = AsyncMock()
        store.async_load = AsyncMock(return_value=None)
        return store

    @pytest.fixture
    def logger(self, mock_hass, mock_store):
        """Create a ConfigFlowLogger instance."""
        with patch('custom_components.roost_scheduler.config_flow_logging.Store', return_value=mock_store):
            return ConfigFlowLogger(mock_hass, "test_domain")

    @pytest.mark.asyncio
    async def test_log_config_flow_start(self, logger):
        """Test logging config flow start."""
        await logger.log_config_flow_start("test_flow_id", {"test": "data"})

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "INFO"
        assert entry.operation == "config_flow_start"
        assert "test_flow_id" in entry.message
        assert entry.details["flow_id"] == "test_flow_id"
        assert entry.details["user_input"] == {"test": "data"}

    @pytest.mark.asyncio
    async def test_log_config_flow_step_success(self, logger):
        """Test logging config flow step without errors."""
        await logger.log_config_flow_step("user", "test_flow_id", {"input": "value"})

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "INFO"
        assert entry.operation == "config_flow_step"
        assert "step 'user' executed" in entry.message
        assert entry.details["step_id"] == "user"
        assert entry.details["errors"] is None

    @pytest.mark.asyncio
    async def test_log_config_flow_step_with_errors(self, logger):
        """Test logging config flow step with errors."""
        errors = {"base": "invalid_config"}
        await logger.log_config_flow_step("user", "test_flow_id", {"input": "value"}, errors)

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "ERROR"
        assert entry.operation == "config_flow_step"
        assert "with errors" in entry.message
        assert entry.details["errors"] == errors

    @pytest.mark.asyncio
    async def test_log_config_flow_error(self, logger):
        """Test logging config flow error."""
        test_error = ValueError("Test error")
        await logger.log_config_flow_error(test_error, "test_context", "test_flow_id")

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "ERROR"
        assert entry.operation == "config_flow_error"
        assert "Test error" in entry.message
        assert entry.error_info["error_type"] == "ValueError"
        assert entry.error_info["error_message"] == "Test error"
        assert "traceback" in entry.error_info

    @pytest.mark.asyncio
    async def test_log_registration_attempt_success(self, logger):
        """Test logging successful registration attempt."""
        await logger.log_registration_attempt(True, {"detail": "success"})

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "INFO"
        assert entry.operation == "registration_attempt"
        assert "succeeded" in entry.message
        assert entry.details["success"] is True

    @pytest.mark.asyncio
    async def test_log_registration_attempt_failure(self, logger):
        """Test logging failed registration attempt."""
        await logger.log_registration_attempt(False, {"detail": "failure"})

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "ERROR"
        assert entry.operation == "registration_attempt"
        assert "failed" in entry.message
        assert entry.details["success"] is False

    @pytest.mark.asyncio
    async def test_log_validation_result_success(self, logger):
        """Test logging successful validation result."""
        await logger.log_validation_result("domain_check", True, [], {"test": "data"})

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "INFO"
        assert entry.operation == "validation_result"
        assert "passed" in entry.message
        assert entry.details["validation_type"] == "domain_check"
        assert entry.details["success"] is True

    @pytest.mark.asyncio
    async def test_log_validation_result_with_issues(self, logger):
        """Test logging validation result with issues."""
        issues = ["Issue 1", "Issue 2"]
        await logger.log_validation_result("domain_check", False, issues, {"test": "data"})

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "WARNING"
        assert entry.operation == "validation_result"
        assert "failed" in entry.message
        assert "2 issues" in entry.message
        assert entry.details["issues"] == issues

    @pytest.mark.asyncio
    async def test_log_diagnostic_collection(self, logger):
        """Test logging diagnostic collection."""
        data = {"key1": "value1", "key2": "value2"}
        await logger.log_diagnostic_collection("system_info", data)

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "INFO"
        assert entry.operation == "diagnostic_collection"
        assert "completed" in entry.message
        assert entry.details["diagnostic_type"] == "system_info"
        assert entry.details["data_keys"] == ["key1", "key2"]

    @pytest.mark.asyncio
    async def test_log_fix_attempt_success(self, logger):
        """Test logging successful fix attempt."""
        before_state = {"issue": True}
        after_state = {"issue": False}
        await logger.log_fix_attempt("domain_fix", True, before_state, after_state)

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "INFO"
        assert entry.operation == "fix_attempt"
        assert "succeeded" in entry.message
        assert entry.details["before_state"] == before_state
        assert entry.details["after_state"] == after_state

    @pytest.mark.asyncio
    async def test_log_fix_attempt_failure(self, logger):
        """Test logging failed fix attempt."""
        before_state = {"issue": True}
        after_state = {"issue": True}
        error_msg = "Fix failed"
        await logger.log_fix_attempt("domain_fix", False, before_state, after_state, error_msg)

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "ERROR"
        assert entry.operation == "fix_attempt"
        assert "failed" in entry.message
        assert error_msg in entry.message
        assert entry.error_info["fix_error"] == error_msg

    @pytest.mark.asyncio
    async def test_log_integration_setup(self, logger):
        """Test logging integration setup."""
        await logger.log_integration_setup("initialization", True, {"component": "test"}, 150.5)

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "INFO"
        assert entry.operation == "integration_setup"
        assert "completed" in entry.message
        assert "150.5ms" in entry.message
        assert entry.details["phase"] == "initialization"
        assert entry.details["duration_ms"] == 150.5

    @pytest.mark.asyncio
    async def test_log_troubleshooting_info(self, logger):
        """Test logging troubleshooting info."""
        data = {"info": "test"}
        await logger.log_troubleshooting_info("system_check", data)

        assert len(logger._log_entries) == 1
        entry = logger._log_entries[0]
        assert entry.level == "INFO"
        assert entry.operation == "troubleshooting_info"
        assert "system_check" in entry.message
        assert entry.details["info_type"] == "system_check"
        assert entry.details["info"] == "test"

    @pytest.mark.asyncio
    async def test_get_diagnostic_logs(self, logger):
        """Test getting diagnostic logs."""
        # Add some log entries
        await logger.log_config_flow_start("test_flow", {})
        await logger.log_config_flow_error(ValueError("test"), "test_context")

        diagnostic_data = await logger.get_diagnostic_logs()

        assert isinstance(diagnostic_data, DiagnosticLogData)
        assert len(diagnostic_data.entries) == 2
        assert diagnostic_data.session_id == logger._session_id
        assert "total_entries" in diagnostic_data.summary
        assert diagnostic_data.summary["total_entries"] == 2

    @pytest.mark.asyncio
    async def test_get_diagnostic_logs_with_limit(self, logger):
        """Test getting diagnostic logs with limit."""
        # Add multiple log entries
        for i in range(5):
            await logger.log_config_flow_start(f"test_flow_{i}", {})

        diagnostic_data = await logger.get_diagnostic_logs(limit=3)

        assert len(diagnostic_data.entries) == 3
        # Should get the last 3 entries
        assert diagnostic_data.entries[0].details["flow_id"] == "test_flow_2"
        assert diagnostic_data.entries[2].details["flow_id"] == "test_flow_4"

    @pytest.mark.asyncio
    async def test_export_logs_to_file(self, logger):
        """Test exporting logs to file."""
        # Add some log entries
        await logger.log_config_flow_start("test_flow", {})
        await logger.log_config_flow_error(ValueError("test error"), "test_context")

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            result = await logger.export_logs_to_file(temp_path)
            assert result is True

            # Verify file contents
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()

            assert "Config Flow Diagnostic Logs" in content
            assert "SUMMARY:" in content
            assert "DETAILED LOGS:" in content
            assert "test_flow" in content
            assert "test error" in content

        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_clear_logs(self, logger, mock_store):
        """Test clearing logs."""
        # Add some log entries
        await logger.log_config_flow_start("test_flow", {})
        assert len(logger._log_entries) == 1

        await logger.clear_logs()

        assert len(logger._log_entries) == 0
        mock_store.async_save.assert_called_with([])

    @pytest.mark.asyncio
    async def test_save_logs(self, logger, mock_store):
        """Test saving logs."""
        # Add some log entries
        await logger.log_config_flow_start("test_flow", {})

        await logger.save_logs()

        mock_store.async_save.assert_called_once()
        saved_data = mock_store.async_save.call_args[0][0]
        assert "session_id" in saved_data
        assert "entries" in saved_data
        assert len(saved_data["entries"]) == 1

    @pytest.mark.asyncio
    async def test_load_logs(self, logger, mock_store):
        """Test loading logs."""
        # Mock stored data
        stored_data = {
            "session_id": "test_session",
            "entries": [{
                "timestamp": "2023-01-01T00:00:00",
                "level": "INFO",
                "operation": "test_op",
                "message": "test message",
                "details": {"test": "data"},
                "error_info": None
            }]
        }
        mock_store.async_load.return_value = stored_data

        await logger.load_logs()

        assert logger._session_id == "test_session"
        assert len(logger._log_entries) == 1
        assert logger._log_entries[0].operation == "test_op"

    def test_generate_log_summary(self, logger):
        """Test log summary generation."""
        # Create some test entries
        entries = [
            ConfigFlowLogEntry(
                timestamp="2023-01-01T00:00:00",
                level="INFO",
                operation="config_flow_start",
                message="Test message",
                details={"test": "data"}
            ),
            ConfigFlowLogEntry(
                timestamp="2023-01-01T00:01:00",
                level="ERROR",
                operation="config_flow_error",
                message="Error message",
                details={"test": "error"},
                error_info={"error_type": "ValueError"}
            )
        ]

        summary = logger._generate_log_summary(entries)

        assert summary["total_entries"] == 2
        assert summary["levels"]["INFO"] == 1
        assert summary["levels"]["ERROR"] == 1
        assert summary["operations"]["config_flow_start"] == 1
        assert summary["operations"]["config_flow_error"] == 1
        assert len(summary["errors"]) == 1
        assert summary["errors"][0]["error_type"] == "ValueError"

    def test_max_entries_limit(self, logger):
        """Test that log entries are limited to prevent memory issues."""
        logger._max_entries = 3

        # Add more entries than the limit
        for i in range(5):
            logger._log_entries.append(ConfigFlowLogEntry(
                timestamp=f"2023-01-01T00:0{i}:00",
                level="INFO",
                operation="test",
                message=f"Message {i}",
                details={"index": i}
            ))

        # Simulate the trimming that happens in _add_log_entry
        if len(logger._log_entries) > logger._max_entries:
            logger._log_entries = logger._log_entries[-logger._max_entries:]

        assert len(logger._log_entries) == 3
        # Should keep the last 3 entries
        assert logger._log_entries[0].details["index"] == 2
        assert logger._log_entries[2].details["index"] == 4


class TestConfigFlowDiagnosticReporter:
    """Test cases for ConfigFlowDiagnosticReporter."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock ConfigFlowLogger."""
        logger = MagicMock()
        logger.domain = "test_domain"
        return logger

    @pytest.fixture
    def reporter(self, mock_logger):
        """Create a ConfigFlowDiagnosticReporter instance."""
        return ConfigFlowDiagnosticReporter(mock_logger)

    @pytest.mark.asyncio
    async def test_generate_comprehensive_report(self, reporter, mock_logger):
        """Test comprehensive report generation."""
        # Mock diagnostic data
        diagnostic_data = DiagnosticLogData(
            session_id="test_session",
            entries=[
                ConfigFlowLogEntry(
                    timestamp="2023-01-01T00:00:00",
                    level="INFO",
                    operation="config_flow_start",
                    message="Flow started",
                    details={"flow_id": "test"}
                ),
                ConfigFlowLogEntry(
                    timestamp="2023-01-01T00:01:00",
                    level="ERROR",
                    operation="config_flow_error",
                    message="Error occurred",
                    details={"flow_id": "test"},
                    error_info={"error_type": "ValueError", "error_message": "Test error"}
                )
            ],
            summary={
                "total_entries": 2,
                "levels": {"INFO": 1, "ERROR": 1},
                "operations": {"config_flow_start": 1, "config_flow_error": 1},
                "errors": [{
                    "timestamp": "2023-01-01T00:01:00",
                    "operation": "config_flow_error",
                    "message": "Error occurred",
                    "error_type": "ValueError"
                }]
            }
        )
        mock_logger.get_diagnostic_logs = AsyncMock(return_value=diagnostic_data)

        report = await reporter.generate_comprehensive_report()

        assert "CONFIG FLOW DIAGNOSTIC REPORT" in report
        assert "Session ID: test_session" in report
        assert "Domain: test_domain" in report
        assert "SUMMARY:" in report
        assert "ERROR ANALYSIS:" in report
        assert "RECENT LOG ENTRIES:" in report
        assert "ValueError" in report
        assert "Flow started" in report

    @pytest.mark.asyncio
    async def test_generate_troubleshooting_guide_no_errors(self, reporter, mock_logger):
        """Test troubleshooting guide generation with no errors."""
        diagnostic_data = DiagnosticLogData(
            session_id="test_session",
            entries=[],
            summary={"total_entries": 0, "errors": []}
        )
        mock_logger.get_diagnostic_logs = AsyncMock(return_value=diagnostic_data)

        guide = await reporter.generate_troubleshooting_guide()

        assert "CONFIG FLOW TROUBLESHOOTING GUIDE" in guide
        assert "No errors detected" in guide
        assert "appears to be functioning correctly" in guide
        assert "GENERAL TROUBLESHOOTING STEPS:" in guide

    @pytest.mark.asyncio
    async def test_generate_troubleshooting_guide_with_errors(self, reporter, mock_logger):
        """Test troubleshooting guide generation with errors."""
        diagnostic_data = DiagnosticLogData(
            session_id="test_session",
            entries=[],
            summary={
                "total_entries": 1,
                "errors": [{
                    "timestamp": "2023-01-01T00:00:00",
                    "operation": "config_flow_error",
                    "message": "Import error",
                    "error_type": "ImportError"
                }]
            }
        )
        mock_logger.get_diagnostic_logs = AsyncMock(return_value=diagnostic_data)

        guide = await reporter.generate_troubleshooting_guide()

        assert "CONFIG FLOW TROUBLESHOOTING GUIDE" in guide
        assert "1 error(s) detected" in guide
        assert "For ImportError errors:" in guide
        assert "Check that all required dependencies are installed" in guide
        assert "GENERAL TROUBLESHOOTING STEPS:" in guide

    def test_get_error_guidance(self, reporter):
        """Test error guidance generation."""
        # Test known error types
        assert "dependencies" in reporter._get_error_guidance("ImportError")
        assert "methods and attributes" in reporter._get_error_guidance("AttributeError")
        assert "configuration keys" in reporter._get_error_guidance("KeyError")
        assert "input values" in reporter._get_error_guidance("ValueError")
        assert "required integration files" in reporter._get_error_guidance("FileNotFoundError")
        assert "file permissions" in reporter._get_error_guidance("PermissionError")
        assert "JSON syntax" in reporter._get_error_guidance("JSONDecodeError")
        assert "Python modules" in reporter._get_error_guidance("ModuleNotFoundError")
        
        # Test unknown error type
        guidance = reporter._get_error_guidance("UnknownError")
        assert "Review error details" in guidance


class TestConfigFlowRegistrationFixer:
    """Test cases for ConfigFlowRegistrationFixer."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        hass.loop.time.return_value = 1234567890.0
        hass.config_entries = MagicMock()
        hass.config_entries.flow = MagicMock()
        hass.config_entries.flow._flows = {}
        hass.components = MagicMock()
        return hass

    @pytest.fixture
    def fixer(self, mock_hass):
        """Create a ConfigFlowRegistrationFixer instance."""
        with patch.object(ConfigFlowRegistrationFixer, '_get_integration_path') as mock_path:
            mock_path.return_value = Path("/test/integration")
            return ConfigFlowRegistrationFixer(mock_hass, "test_domain")

    @pytest.mark.asyncio
    async def test_diagnose_registration_issues_success(self, fixer):
        """Test successful registration issue diagnosis."""
        # Mock all diagnosis methods to return empty lists
        fixer._diagnose_domain_issues = AsyncMock(return_value=[])
        fixer._diagnose_class_issues = AsyncMock(return_value=[])
        fixer._diagnose_manifest_issues = AsyncMock(return_value=[])
        fixer._diagnose_import_issues = AsyncMock(return_value=[])
        fixer._diagnose_method_issues = AsyncMock(return_value=[])

        issues = await fixer.diagnose_registration_issues()

        assert isinstance(issues, list)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_diagnose_registration_issues_with_issues(self, fixer):
        """Test registration issue diagnosis with issues found."""
        test_issue = RegistrationIssue(
            issue_type="test_issue",
            description="Test issue description",
            severity="error",
            fix_available=True,
            fix_description="Fix test issue",
            diagnostic_info={},
            fix_priority=5
        )
        
        # Mock diagnosis methods to return issues
        fixer._diagnose_domain_issues = AsyncMock(return_value=[test_issue])
        fixer._diagnose_class_issues = AsyncMock(return_value=[])
        fixer._diagnose_manifest_issues = AsyncMock(return_value=[])
        fixer._diagnose_import_issues = AsyncMock(return_value=[])
        fixer._diagnose_method_issues = AsyncMock(return_value=[])

        issues = await fixer.diagnose_registration_issues()

        assert len(issues) == 1
        assert issues[0].issue_type == "test_issue"
        assert issues[0].severity == "error"
        assert issues[0].fix_available is True

    @pytest.mark.asyncio
    async def test_fix_domain_mismatch_success(self, fixer):
        """Test successful domain mismatch fix."""
        # Mock domain checker
        mock_fix_result = MagicMock()
        mock_fix_result.success = True
        mock_fix_result.fixes_applied = ["Fixed domain consistency"]
        mock_fix_result.warnings = []
        mock_fix_result.errors = []
        
        mock_consistency_result = MagicMock()
        mock_consistency_result.consistent = True
        
        fixer._domain_checker.fix_inconsistencies = AsyncMock(return_value=mock_fix_result)
        fixer._domain_checker.validate_consistency = AsyncMock(return_value=mock_consistency_result)

        result = await fixer.fix_domain_mismatch()

        assert result.success is True
        assert result.issue_type == "domain_mismatch"
        assert result.verification_passed is True
        assert "Fixed domain consistency" in result.changes_made

    @pytest.mark.asyncio
    async def test_fix_domain_mismatch_failure(self, fixer):
        """Test failed domain mismatch fix."""
        # Mock domain checker to fail
        mock_fix_result = MagicMock()
        mock_fix_result.success = False
        mock_fix_result.fixes_applied = []
        mock_fix_result.warnings = []
        mock_fix_result.errors = ["Fix failed"]
        
        fixer._domain_checker.fix_inconsistencies = AsyncMock(return_value=mock_fix_result)

        result = await fixer.fix_domain_mismatch()

        assert result.success is False
        assert result.issue_type == "domain_mismatch"
        assert result.verification_passed is False
        assert "Fix failed" in result.errors

    @pytest.mark.asyncio
    async def test_fix_class_inheritance_create_new_file(self, fixer):
        """Test class inheritance fix by creating new config flow file."""
        # Mock file doesn't exist
        with patch.object(Path, "exists", return_value=False):
            fixer._create_basic_config_flow = AsyncMock()
            fixer._verify_config_flow_class = AsyncMock(return_value=True)

            result = await fixer.fix_class_inheritance()

        assert result.success is True
        assert result.issue_type == "class_inheritance"
        assert result.verification_passed is True
        fixer._create_basic_config_flow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fix_class_inheritance_fix_existing_file(self, fixer):
        """Test class inheritance fix by modifying existing file."""
        # Mock file exists
        with patch.object(Path, "exists", return_value=True):
            fixer._fix_config_flow_class = AsyncMock(return_value=["Fixed class definition"])
            fixer._verify_config_flow_class = AsyncMock(return_value=True)

            result = await fixer.fix_class_inheritance()

        assert result.success is True
        assert result.issue_type == "class_inheritance"
        assert result.verification_passed is True
        assert "Fixed class definition" in result.changes_made

    @pytest.mark.asyncio
    async def test_fix_method_implementation_success(self, fixer):
        """Test successful method implementation fix."""
        # Mock file exists
        with patch.object(Path, "exists", return_value=True):
            fixer._fix_config_flow_methods = AsyncMock(return_value=["Added async_step_user method"])
            fixer._verify_config_flow_methods = AsyncMock(return_value=True)

            result = await fixer.fix_method_implementation()

        assert result.success is True
        assert result.issue_type == "method_implementation"
        assert result.verification_passed is True
        assert "Added async_step_user method" in result.changes_made

    @pytest.mark.asyncio
    async def test_fix_method_implementation_missing_file(self, fixer):
        """Test method implementation fix with missing file."""
        # Mock file doesn't exist
        with patch.object(Path, "exists", return_value=False):
            result = await fixer.fix_method_implementation()

        assert result.success is False
        assert result.issue_type == "method_implementation"
        assert result.verification_passed is False
        assert "config flow file missing" in result.description

    @pytest.mark.asyncio
    async def test_apply_all_fixes_success(self, fixer):
        """Test successful application of all fixes."""
        # Mock backup creation
        fixer._create_backup = AsyncMock()
        
        # Mock diagnosis to return no issues
        fixer.diagnose_registration_issues = AsyncMock(return_value=[])
        
        result = await fixer.apply_all_fixes()

        assert result.success is True
        assert result.total_issues == 0
        assert result.fixed_issues == 0
        assert result.failed_fixes == 0
        assert result.backup_created is True

    @pytest.mark.asyncio
    async def test_apply_all_fixes_with_issues(self, fixer):
        """Test application of all fixes with issues present."""
        # Mock backup creation
        fixer._create_backup = AsyncMock()
        
        # Mock diagnosis to return issues initially, then none after fixes
        test_issue = RegistrationIssue(
            issue_type="test_issue",
            description="Test issue",
            severity="error",
            fix_available=True,
            fix_description="Fix test issue",
            diagnostic_info={},
            fix_priority=5
        )
        
        fixer.diagnose_registration_issues = AsyncMock(side_effect=[
            [test_issue],  # Initial diagnosis
            []  # After fixes
        ])
        
        # Mock individual fix methods
        fixer.fix_domain_mismatch = AsyncMock(return_value=FixResult(
            success=True, issue_type="domain_mismatch", description="Fixed",
            changes_made=["Fixed domain"], errors=[], warnings=[], verification_passed=True
        ))
        fixer.fix_manifest_configuration = AsyncMock(return_value=FixResult(
            success=True, issue_type="manifest_configuration", description="Fixed",
            changes_made=["Fixed manifest"], errors=[], warnings=[], verification_passed=True
        ))
        fixer.fix_import_issues = AsyncMock(return_value=FixResult(
            success=True, issue_type="import_issues", description="Fixed",
            changes_made=["Fixed imports"], errors=[], warnings=[], verification_passed=True
        ))
        fixer.fix_class_inheritance = AsyncMock(return_value=FixResult(
            success=True, issue_type="class_inheritance", description="Fixed",
            changes_made=["Fixed class"], errors=[], warnings=[], verification_passed=True
        ))
        fixer.fix_method_implementation = AsyncMock(return_value=FixResult(
            success=True, issue_type="method_implementation", description="Fixed",
            changes_made=["Fixed methods"], errors=[], warnings=[], verification_passed=True
        ))

        result = await fixer.apply_all_fixes()

        assert result.success is True
        assert result.total_issues == 1
        assert result.fixed_issues == 5  # All fix methods succeeded
        assert result.failed_fixes == 0
        assert result.backup_created is True

    @pytest.mark.asyncio
    async def test_verify_all_fixes_success(self, fixer):
        """Test successful verification of all fixes."""
        # Mock all verification methods to succeed
        fixer._verify_domain_consistency = AsyncMock(return_value=MagicMock(success=True))
        fixer._verify_manifest_fix = AsyncMock(return_value=MagicMock(success=True))
        fixer._verify_config_flow_fix = AsyncMock(return_value=MagicMock(success=True))
        fixer._verify_import_fix = AsyncMock(return_value=MagicMock(success=True))
        fixer._verify_method_fix = AsyncMock(return_value=MagicMock(success=True))
        fixer._verify_integration_loading = AsyncMock(return_value=MagicMock(success=True))

        result = await fixer.verify_all_fixes()

        assert result.success is True
        assert result.total_checks == 6
        assert result.passed_checks == 6
        assert result.failed_checks == 0
        assert "All fixes have been successfully verified" in result.recommendations

    @pytest.mark.asyncio
    async def test_verify_all_fixes_with_failures(self, fixer):
        """Test verification of fixes with some failures."""
        # Mock some verification methods to fail
        fixer._verify_domain_consistency = AsyncMock(return_value=MagicMock(success=False))
        fixer._verify_manifest_fix = AsyncMock(return_value=MagicMock(success=True))
        fixer._verify_config_flow_fix = AsyncMock(return_value=MagicMock(success=False))
        fixer._verify_import_fix = AsyncMock(return_value=MagicMock(success=True))
        fixer._verify_method_fix = AsyncMock(return_value=MagicMock(success=True))
        fixer._verify_integration_loading = AsyncMock(return_value=MagicMock(success=True))

        result = await fixer.verify_all_fixes()

        assert result.success is False
        assert result.total_checks == 6
        assert result.passed_checks == 4
        assert result.failed_checks == 2
        assert any("Some fixes failed verification" in rec for rec in result.recommendations)

    @pytest.mark.asyncio
    async def test_rollback_fixes_success(self, fixer):
        """Test successful rollback of fixes."""
        # Mock finding backup directory
        backup_dir = Path("/test/backup")
        fixer._find_latest_backup = AsyncMock(return_value=backup_dir)
        
        # Mock backup directory exists and has files
        with patch.object(Path, "exists", return_value=True):
            with patch("shutil.copy2") as mock_copy:
                result = await fixer.rollback_fixes()

        assert result.success is True
        assert len(result.rollback_actions) > 0
        assert len(result.errors) == 0
        # Should have attempted to restore files
        assert mock_copy.call_count > 0

    @pytest.mark.asyncio
    async def test_rollback_fixes_no_backup(self, fixer):
        """Test rollback when no backup is found."""
        # Mock no backup found
        fixer._find_latest_backup = AsyncMock(return_value=None)

        result = await fixer.rollback_fixes()

        assert result.success is False
        assert len(result.errors) == 1
        assert "No backup directory found" in result.errors[0]

    def test_generate_fix_report(self, fixer):
        """Test fix report generation."""
        # Create mock fix results
        fix_results = [
            FixResult(
                success=True,
                issue_type="domain_mismatch",
                description="Fixed domain issues",
                changes_made=["Updated domain in manifest"],
                errors=[],
                warnings=[],
                verification_passed=True
            ),
            FixResult(
                success=False,
                issue_type="class_inheritance",
                description="Failed to fix class issues",
                changes_made=[],
                errors=["Class fix failed"],
                warnings=["Warning message"],
                verification_passed=False
            )
        ]
        
        overall_result = OverallFixResult(
            success=False,
            total_issues=2,
            fixed_issues=1,
            failed_fixes=1,
            fix_results=fix_results,
            remaining_issues=[],
            backup_created=True
        )

        report = fixer.generate_fix_report(overall_result)

        assert "CONFIG FLOW REGISTRATION FIX REPORT" in report
        assert "Overall Status: FAILED" in report
        assert "Total Issues Found: 2" in report
        assert "Issues Fixed: 1" in report
        assert "Failed Fixes: 1" in report
        assert "Backup Created: Yes" in report
        assert "DOMAIN_MISMATCH" in report
        assert "CLASS_INHERITANCE" in report
        assert "Updated domain in manifest" in report
        assert "Class fix failed" in report

    @pytest.mark.asyncio
    async def test_diagnose_domain_issues(self, fixer):
        """Test domain issue diagnosis."""
        # Mock domain checker to return inconsistent result
        mock_consistency_result = MagicMock()
        mock_consistency_result.consistent = False
        mock_consistency_result.issues = ["Domain mismatch between files"]
        mock_consistency_result.manifest_domain = "domain1"
        mock_consistency_result.const_domain = "domain2"
        mock_consistency_result.config_flow_domain = None
        
        fixer._domain_checker.validate_consistency = AsyncMock(return_value=mock_consistency_result)

        issues = await fixer._diagnose_domain_issues()

        assert len(issues) >= 1
        domain_issues = [i for i in issues if i.issue_type == "domain_mismatch"]
        assert len(domain_issues) == 1
        assert domain_issues[0].severity == "critical"
        assert domain_issues[0].fix_available is True

    @pytest.mark.asyncio
    async def test_diagnose_class_issues_missing_file(self, fixer):
        """Test class issue diagnosis with missing config flow file."""
        with patch.object(Path, "exists", return_value=False):
            issues = await fixer._diagnose_class_issues()

        assert len(issues) == 1
        assert issues[0].issue_type == "config_flow_file_missing"
        assert issues[0].severity == "critical"
        assert issues[0].fix_available is True

    @pytest.mark.asyncio
    async def test_diagnose_class_issues_missing_class(self, fixer):
        """Test class issue diagnosis with missing ConfigFlow class."""
        content = "# No ConfigFlow class here"
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                issues = await fixer._diagnose_class_issues()

        class_missing_issues = [i for i in issues if "class" in i.issue_type or "ConfigFlow" in i.description]
        assert len(class_missing_issues) >= 1
        assert all(issue.severity in ["critical", "error"] for issue in class_missing_issues)

    @pytest.mark.asyncio
    async def test_diagnose_manifest_issues_missing_file(self, fixer):
        """Test manifest issue diagnosis with missing file."""
        with patch.object(Path, "exists", return_value=False):
            issues = await fixer._diagnose_manifest_issues()

        assert len(issues) == 1
        assert issues[0].issue_type == "manifest_file_missing"
        assert issues[0].severity == "critical"
        assert issues[0].fix_available is True

    @pytest.mark.asyncio
    async def test_diagnose_manifest_issues_config_flow_disabled(self, fixer):
        """Test manifest issue diagnosis with config_flow disabled."""
        manifest_data = {
            "domain": "test_domain",
            "name": "Test",
            "version": "1.0.0",
            "config_flow": False
        }
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(manifest_data))):
                issues = await fixer._diagnose_manifest_issues()

        config_flow_issues = [i for i in issues if i.issue_type == "config_flow_not_enabled"]
        assert len(config_flow_issues) == 1
        assert config_flow_issues[0].severity == "critical"
        assert config_flow_issues[0].fix_available is True

    @pytest.mark.asyncio
    async def test_create_basic_config_flow(self, fixer):
        """Test creation of basic config flow file."""
        mock_file = mock_open()
        
        with patch("builtins.open", mock_file):
            await fixer._create_basic_config_flow()

        # Verify file was written
        mock_file.assert_called_once()
        written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)
        
        assert "class RoostSchedulerConfigFlow" in written_content
        assert "config_entries.ConfigFlow" in written_content
        assert "domain=DOMAIN" in written_content
        assert "async_step_user" in written_content

    @pytest.mark.asyncio
    async def test_create_basic_manifest(self, fixer):
        """Test creation of basic manifest file."""
        mock_file = mock_open()
        
        with patch("builtins.open", mock_file):
            await fixer._create_basic_manifest()

        # Verify file was written
        mock_file.assert_called_once()
        written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)
        
        # Parse the JSON to verify structure
        manifest_data = json.loads(written_content)
        assert manifest_data["domain"] == "test_domain"
        assert manifest_data["config_flow"] is True
        assert "name" in manifest_data
        assert "version" in manifest_data
        assert "dependencies" in manifest_data