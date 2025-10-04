"""Tests for Config Flow Registration Fixer."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from homeassistant.core import HomeAssistant

from custom_components.roost_scheduler.config_flow_registration_fixer import (
    ConfigFlowRegistrationFixer,
    RegistrationIssue,
    FixResult,
    OverallFixResult,
    FixVerificationResult,
)


class TestConfigFlowRegistrationFixerIssueDiagnosis:
    """Test cases for issue diagnosis functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        hass.config_entries = MagicMock()
        hass.components = MagicMock()
        return hass

    @pytest.fixture
    def fixer(self, mock_hass):
        """Create a ConfigFlowRegistrationFixer instance."""
        with patch.object(ConfigFlowRegistrationFixer, '_get_integration_path') as mock_path:
            mock_path.return_value = Path("/test/integration")
            return ConfigFlowRegistrationFixer(mock_hass, "test_domain")

    @pytest.mark.asyncio
    async def test_diagnose_registration_issues_empty(self, fixer):
        """Test diagnosis when no issues are found."""
        # Mock all diagnosis methods to return empty lists
        fixer._diagnose_domain_issues = AsyncMock(return_value=[])
        fixer._diagnose_class_issues = AsyncMock(return_value=[])
        fixer._diagnose_manifest_issues = AsyncMock(return_value=[])
        fixer._diagnose_import_issues = AsyncMock(return_value=[])
        fixer._diagnose_method_issues = AsyncMock(return_value=[])

        issues = await fixer.diagnose_registration_issues()

        assert isinstance(issues, list)
        assert len(issues) == 0
        
        # Verify all diagnosis methods were called
        fixer._diagnose_domain_issues.assert_called_once()
        fixer._diagnose_class_issues.assert_called_once()
        fixer._diagnose_manifest_issues.assert_called_once()
        fixer._diagnose_import_issues.assert_called_once()
        fixer._diagnose_method_issues.assert_called_once()

    @pytest.mark.asyncio
    async def test_diagnose_registration_issues_with_multiple_issues(self, fixer):
        """Test diagnosis when multiple issues are found."""
        domain_issue = RegistrationIssue(
            issue_type="domain_mismatch",
            description="Domain mismatch",
            severity="critical",
            fix_available=True,
            fix_description="Fix domain",
            diagnostic_info={},
            fix_priority=10
        )
        
        class_issue = RegistrationIssue(
            issue_type="class_missing",
            description="ConfigFlow class missing",
            severity="error",
            fix_available=True,
            fix_description="Create class",
            diagnostic_info={},
            fix_priority=5
        )
        
        # Mock diagnosis methods to return issues
        fixer._diagnose_domain_issues = AsyncMock(return_value=[domain_issue])
        fixer._diagnose_class_issues = AsyncMock(return_value=[class_issue])
        fixer._diagnose_manifest_issues = AsyncMock(return_value=[])
        fixer._diagnose_import_issues = AsyncMock(return_value=[])
        fixer._diagnose_method_issues = AsyncMock(return_value=[])

        issues = await fixer.diagnose_registration_issues()

        assert len(issues) == 2
        # Should be sorted by priority (critical first)
        assert issues[0].issue_type == "domain_mismatch"
        assert issues[0].severity == "critical"
        assert issues[1].issue_type == "class_missing"
        assert issues[1].severity == "error"

    @pytest.mark.asyncio
    async def test_diagnose_registration_issues_exception_handling(self, fixer):
        """Test diagnosis handles exceptions gracefully."""
        # Mock one method to raise an exception
        fixer._diagnose_domain_issues = AsyncMock(side_effect=Exception("Test error"))
        fixer._diagnose_class_issues = AsyncMock(return_value=[])
        fixer._diagnose_manifest_issues = AsyncMock(return_value=[])
        fixer._diagnose_import_issues = AsyncMock(return_value=[])
        fixer._diagnose_method_issues = AsyncMock(return_value=[])

        issues = await fixer.diagnose_registration_issues()

        assert len(issues) == 1
        assert issues[0].issue_type == "diagnosis_error"
        assert issues[0].severity == "error"
        assert "Test error" in issues[0].description

    @pytest.mark.asyncio
    async def test_diagnose_domain_issues_consistent_domain(self, fixer):
        """Test domain issue diagnosis when domain is consistent."""
        mock_consistency_result = MagicMock()
        mock_consistency_result.consistent = True
        mock_consistency_result.manifest_domain = "test_domain"
        mock_consistency_result.const_domain = "test_domain"
        mock_consistency_result.config_flow_domain = "test_domain"
        
        fixer._domain_checker.validate_consistency = AsyncMock(return_value=mock_consistency_result)

        issues = await fixer._diagnose_domain_issues()

        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_diagnose_domain_issues_inconsistent_domain(self, fixer):
        """Test domain issue diagnosis when domain is inconsistent."""
        mock_consistency_result = MagicMock()
        mock_consistency_result.consistent = False
        mock_consistency_result.issues = ["Domain mismatch between manifest and const"]
        mock_consistency_result.manifest_domain = "domain1"
        mock_consistency_result.const_domain = "domain2"
        mock_consistency_result.config_flow_domain = "domain3"
        
        fixer._domain_checker.validate_consistency = AsyncMock(return_value=mock_consistency_result)

        issues = await fixer._diagnose_domain_issues()

        assert len(issues) >= 1
        domain_issues = [i for i in issues if i.issue_type == "domain_mismatch"]
        assert len(domain_issues) == 1
        assert domain_issues[0].severity == "critical"
        assert domain_issues[0].fix_available is True
        assert domain_issues[0].fix_priority == 10

    @pytest.mark.asyncio
    async def test_diagnose_domain_issues_missing_domains(self, fixer):
        """Test domain issue diagnosis when domains are missing."""
        mock_consistency_result = MagicMock()
        mock_consistency_result.consistent = False
        mock_consistency_result.issues = []
        mock_consistency_result.manifest_domain = None
        mock_consistency_result.const_domain = None
        mock_consistency_result.config_flow_domain = "test_domain"
        
        fixer._domain_checker.validate_consistency = AsyncMock(return_value=mock_consistency_result)

        issues = await fixer._diagnose_domain_issues()

        # Should find issues for missing manifest and const domains
        manifest_issues = [i for i in issues if i.issue_type == "manifest_domain_missing"]
        const_issues = [i for i in issues if i.issue_type == "const_domain_missing"]
        
        assert len(manifest_issues) == 1
        assert len(const_issues) == 1
        assert manifest_issues[0].severity == "critical"
        assert const_issues[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_diagnose_class_issues_missing_file(self, fixer):
        """Test class issue diagnosis when config_flow.py is missing."""
        with patch.object(Path, "exists", return_value=False):
            issues = await fixer._diagnose_class_issues()

        assert len(issues) == 1
        assert issues[0].issue_type == "config_flow_file_missing"
        assert issues[0].severity == "critical"
        assert issues[0].fix_available is True
        assert issues[0].fix_priority == 7

    @pytest.mark.asyncio
    async def test_diagnose_class_issues_missing_configflow_class(self, fixer):
        """Test class issue diagnosis when ConfigFlow class is missing."""
        content = "# This file has no ConfigFlow class\nprint('hello')"
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                issues = await fixer._diagnose_class_issues()

        class_issues = [i for i in issues if i.issue_type == "config_flow_class_missing"]
        assert len(class_issues) == 1
        assert class_issues[0].severity == "critical"
        assert class_issues[0].fix_available is True

    @pytest.mark.asyncio
    async def test_diagnose_class_issues_missing_imports(self, fixer):
        """Test class issue diagnosis when ConfigFlow imports are missing."""
        content = """
class TestConfigFlow:
    pass
"""
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                issues = await fixer._diagnose_class_issues()

        import_issues = [i for i in issues if i.issue_type == "config_flow_import_missing"]
        assert len(import_issues) == 1
        assert import_issues[0].severity == "error"
        assert import_issues[0].fix_available is True

    @pytest.mark.asyncio
    async def test_diagnose_manifest_issues_missing_file(self, fixer):
        """Test manifest issue diagnosis when manifest.json is missing."""
        with patch.object(Path, "exists", return_value=False):
            issues = await fixer._diagnose_manifest_issues()

        assert len(issues) == 1
        assert issues[0].issue_type == "manifest_file_missing"
        assert issues[0].severity == "critical"
        assert issues[0].fix_available is True

    @pytest.mark.asyncio
    async def test_diagnose_manifest_issues_config_flow_disabled(self, fixer):
        """Test manifest issue diagnosis when config_flow is disabled."""
        manifest_data = {
            "domain": "test_domain",
            "name": "Test Integration",
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
    async def test_diagnose_manifest_issues_missing_required_fields(self, fixer):
        """Test manifest issue diagnosis when required fields are missing."""
        manifest_data = {
            "config_flow": True
            # Missing domain, name, version
        }
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(manifest_data))):
                issues = await fixer._diagnose_manifest_issues()

        required_field_issues = [i for i in issues if i.issue_type == "manifest_required_field_missing"]
        assert len(required_field_issues) == 3  # domain, name, version
        assert all(issue.severity == "error" for issue in required_field_issues)

    @pytest.mark.asyncio
    async def test_diagnose_manifest_issues_invalid_json(self, fixer):
        """Test manifest issue diagnosis when JSON is invalid."""
        invalid_json = '{"domain": "test", invalid json}'
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=invalid_json)):
                issues = await fixer._diagnose_manifest_issues()

        json_issues = [i for i in issues if i.issue_type == "manifest_json_invalid"]
        assert len(json_issues) == 1
        assert json_issues[0].severity == "critical"
        assert json_issues[0].fix_available is False

    @pytest.mark.asyncio
    async def test_diagnose_method_issues_missing_file(self, fixer):
        """Test method issue diagnosis when config_flow.py is missing."""
        with patch.object(Path, "exists", return_value=False):
            issues = await fixer._diagnose_method_issues()

        # Should return empty list since file missing is handled by class issues
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_diagnose_method_issues_missing_required_methods(self, fixer):
        """Test method issue diagnosis when required methods are missing."""
        content = """
class TestConfigFlow(ConfigFlow):
    VERSION = 1
    # Missing the required user step method
    
    async def some_other_method(self):
        pass
"""
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                issues = await fixer._diagnose_method_issues()

        method_issues = [i for i in issues if i.issue_type == "config_flow_method_missing"]
        
        # Should find the missing method issue
        assert len(method_issues) == 1
        assert method_issues[0].severity == "error"
        assert method_issues[0].fix_available is True
        assert "async_step_user" in method_issues[0].description

    @pytest.mark.asyncio
    async def test_diagnose_method_issues_no_async_methods(self, fixer):
        """Test method issue diagnosis when no async methods are found."""
        content = """
class TestConfigFlow(ConfigFlow):
    VERSION = 1
    
    def step_user(self):
        pass
"""
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                issues = await fixer._diagnose_method_issues()

        async_issues = [i for i in issues if i.issue_type == "config_flow_no_async_methods"]
        assert len(async_issues) == 1
        assert async_issues[0].severity == "warning"
        assert async_issues[0].fix_available is True


class TestConfigFlowRegistrationFixerAutomaticFixing:
    """Test cases for automatic fixing functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        hass.config_entries = MagicMock()
        hass.components = MagicMock()
        return hass

    @pytest.fixture
    def fixer(self, mock_hass):
        """Create a ConfigFlowRegistrationFixer instance."""
        with patch.object(ConfigFlowRegistrationFixer, '_get_integration_path') as mock_path:
            mock_path.return_value = Path("/test/integration")
            return ConfigFlowRegistrationFixer(mock_hass, "test_domain")

    @pytest.mark.asyncio
    async def test_fix_domain_mismatch_success(self, fixer):
        """Test successful domain mismatch fix."""
        # Mock domain checker fix result
        mock_fix_result = MagicMock()
        mock_fix_result.success = True
        mock_fix_result.fixes_applied = ["Updated domain in manifest.json", "Updated DOMAIN in const.py"]
        mock_fix_result.warnings = ["Backup created"]
        mock_fix_result.errors = []
        
        # Mock consistency validation after fix
        mock_consistency_result = MagicMock()
        mock_consistency_result.consistent = True
        
        fixer._domain_checker.fix_inconsistencies = AsyncMock(return_value=mock_fix_result)
        fixer._domain_checker.validate_consistency = AsyncMock(return_value=mock_consistency_result)

        result = await fixer.fix_domain_mismatch()

        assert result.success is True
        assert result.issue_type == "domain_mismatch"
        assert result.verification_passed is True
        assert len(result.changes_made) == 2
        assert "Updated domain in manifest.json" in result.changes_made
        assert "Updated DOMAIN in const.py" in result.changes_made
        assert len(result.warnings) == 1
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_fix_domain_mismatch_failure(self, fixer):
        """Test failed domain mismatch fix."""
        # Mock domain checker fix result
        mock_fix_result = MagicMock()
        mock_fix_result.success = False
        mock_fix_result.fixes_applied = []
        mock_fix_result.warnings = []
        mock_fix_result.errors = ["Could not write to manifest.json", "Permission denied"]
        
        fixer._domain_checker.fix_inconsistencies = AsyncMock(return_value=mock_fix_result)

        result = await fixer.fix_domain_mismatch()

        assert result.success is False
        assert result.issue_type == "domain_mismatch"
        assert result.verification_passed is False
        assert len(result.changes_made) == 0
        assert len(result.errors) == 2
        assert "Could not write to manifest.json" in result.errors

    @pytest.mark.asyncio
    async def test_fix_domain_mismatch_exception(self, fixer):
        """Test domain mismatch fix handles exceptions."""
        fixer._domain_checker.fix_inconsistencies = AsyncMock(side_effect=Exception("Unexpected error"))

        result = await fixer.fix_domain_mismatch()

        assert result.success is False
        assert result.issue_type == "domain_mismatch"
        assert result.verification_passed is False
        assert len(result.errors) == 1
        assert "Unexpected error" in result.errors[0]

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
        assert "Created basic config_flow.py file" in result.changes_made
        fixer._create_basic_config_flow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fix_class_inheritance_fix_existing_file(self, fixer):
        """Test class inheritance fix by modifying existing file."""
        # Mock file exists
        with patch.object(Path, "exists", return_value=True):
            fixer._fix_config_flow_class = AsyncMock(return_value=["Added ConfigFlow inheritance", "Fixed imports"])
            fixer._verify_config_flow_class = AsyncMock(return_value=True)

            result = await fixer.fix_class_inheritance()

        assert result.success is True
        assert result.issue_type == "class_inheritance"
        assert result.verification_passed is True
        assert len(result.changes_made) == 2
        assert "Added ConfigFlow inheritance" in result.changes_made
        assert "Fixed imports" in result.changes_made

    @pytest.mark.asyncio
    async def test_fix_class_inheritance_exception(self, fixer):
        """Test class inheritance fix handles exceptions."""
        with patch.object(Path, "exists", side_effect=Exception("File system error")):
            result = await fixer.fix_class_inheritance()

        assert result.success is False
        assert result.issue_type == "class_inheritance"
        assert result.verification_passed is False
        assert len(result.errors) == 1
        assert "File system error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_fix_method_implementation_success(self, fixer):
        """Test successful method implementation fix."""
        # Mock file exists
        with patch.object(Path, "exists", return_value=True):
            fixer._fix_config_flow_methods = AsyncMock(return_value=["Added async_step_user method", "Fixed method signatures"])
            fixer._verify_config_flow_methods = AsyncMock(return_value=True)

            result = await fixer.fix_method_implementation()

        assert result.success is True
        assert result.issue_type == "method_implementation"
        assert result.verification_passed is True
        assert len(result.changes_made) == 2
        assert "Added async_step_user method" in result.changes_made

    @pytest.mark.asyncio
    async def test_fix_method_implementation_missing_file(self, fixer):
        """Test method implementation fix when config flow file is missing."""
        # Mock file doesn't exist
        with patch.object(Path, "exists", return_value=False):
            result = await fixer.fix_method_implementation()

        assert result.success is False
        assert result.issue_type == "method_implementation"
        assert result.verification_passed is False
        assert len(result.errors) == 1
        assert "config flow file missing" in result.description

    @pytest.mark.asyncio
    async def test_fix_method_implementation_exception(self, fixer):
        """Test method implementation fix handles exceptions."""
        with patch.object(Path, "exists", return_value=True):
            fixer._fix_config_flow_methods = AsyncMock(side_effect=Exception("Method fix error"))

            result = await fixer.fix_method_implementation()

        assert result.success is False
        assert result.issue_type == "method_implementation"
        assert result.verification_passed is False
        assert len(result.errors) == 1
        assert "Method fix error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_apply_all_fixes_no_issues(self, fixer):
        """Test applying all fixes when no issues are found."""
        # Mock backup creation
        fixer._create_backup = AsyncMock()
        
        # Mock diagnosis to return no issues
        fixer.diagnose_registration_issues = AsyncMock(return_value=[])

        result = await fixer.apply_all_fixes()

        assert result.success is True
        assert result.total_issues == 0
        assert result.fixed_issues == 0
        assert result.failed_fixes == 0
        assert len(result.fix_results) == 0
        assert len(result.remaining_issues) == 0
        assert result.backup_created is True

    @pytest.mark.asyncio
    async def test_apply_all_fixes_with_successful_fixes(self, fixer):
        """Test applying all fixes with successful results."""
        # Mock backup creation
        fixer._create_backup = AsyncMock()
        
        # Mock initial issues and final state
        initial_issues = [
            RegistrationIssue(
                issue_type="domain_mismatch",
                description="Domain mismatch",
                severity="critical",
                fix_available=True,
                fix_description="Fix domain",
                diagnostic_info={},
                fix_priority=10
            )
        ]
        
        fixer.diagnose_registration_issues = AsyncMock(side_effect=[
            initial_issues,  # Initial diagnosis
            []  # After fixes applied
        ])
        
        # Mock all fix methods to succeed
        successful_fix = FixResult(
            success=True,
            issue_type="test_fix",
            description="Fix applied successfully",
            changes_made=["Made change"],
            errors=[],
            warnings=[],
            verification_passed=True
        )
        
        fixer.fix_domain_mismatch = AsyncMock(return_value=successful_fix)
        fixer.fix_manifest_configuration = AsyncMock(return_value=successful_fix)
        fixer.fix_import_issues = AsyncMock(return_value=successful_fix)
        fixer.fix_class_inheritance = AsyncMock(return_value=successful_fix)
        fixer.fix_method_implementation = AsyncMock(return_value=successful_fix)

        result = await fixer.apply_all_fixes()

        assert result.success is True
        assert result.total_issues == 1
        assert result.fixed_issues == 5  # All fix methods succeeded
        assert result.failed_fixes == 0
        assert len(result.fix_results) == 5
        assert result.backup_created is True

    @pytest.mark.asyncio
    async def test_apply_all_fixes_with_failed_fixes(self, fixer):
        """Test applying all fixes with some failures."""
        # Mock backup creation
        fixer._create_backup = AsyncMock()
        
        # Mock initial issues
        initial_issues = [
            RegistrationIssue(
                issue_type="domain_mismatch",
                description="Domain mismatch",
                severity="critical",
                fix_available=True,
                fix_description="Fix domain",
                diagnostic_info={},
                fix_priority=10
            )
        ]
        
        # Mock remaining issues after fixes
        remaining_issues = [
            RegistrationIssue(
                issue_type="unfixable_issue",
                description="Cannot be fixed",
                severity="error",
                fix_available=False,
                fix_description="Manual intervention required",
                diagnostic_info={},
                fix_priority=1
            )
        ]
        
        fixer.diagnose_registration_issues = AsyncMock(side_effect=[
            initial_issues,  # Initial diagnosis
            remaining_issues  # After fixes applied
        ])
        
        # Mock some fixes to succeed and some to fail
        successful_fix = FixResult(
            success=True,
            issue_type="successful_fix",
            description="Fix applied successfully",
            changes_made=["Made change"],
            errors=[],
            warnings=[],
            verification_passed=True
        )
        
        failed_fix = FixResult(
            success=False,
            issue_type="failed_fix",
            description="Fix failed",
            changes_made=[],
            errors=["Fix error"],
            warnings=[],
            verification_passed=False
        )
        
        fixer.fix_domain_mismatch = AsyncMock(return_value=successful_fix)
        fixer.fix_manifest_configuration = AsyncMock(return_value=failed_fix)
        fixer.fix_import_issues = AsyncMock(return_value=successful_fix)
        fixer.fix_class_inheritance = AsyncMock(return_value=failed_fix)
        fixer.fix_method_implementation = AsyncMock(return_value=successful_fix)

        result = await fixer.apply_all_fixes()

        assert result.success is False  # Has remaining critical issues
        assert result.total_issues == 1
        assert result.fixed_issues == 3  # 3 successful fixes
        assert result.failed_fixes == 2  # 2 failed fixes
        assert len(result.fix_results) == 5
        assert len(result.remaining_issues) == 1
        assert result.backup_created is True

    @pytest.mark.asyncio
    async def test_apply_all_fixes_backup_failure(self, fixer):
        """Test applying all fixes when backup creation fails."""
        # Mock backup creation to fail
        fixer._create_backup = AsyncMock(side_effect=Exception("Backup failed"))
        
        # Mock diagnosis to return no issues
        fixer.diagnose_registration_issues = AsyncMock(return_value=[])

        result = await fixer.apply_all_fixes()

        # Should still proceed even if backup fails
        assert result.success is True
        assert result.backup_created is False

    @pytest.mark.asyncio
    async def test_apply_all_fixes_exception(self, fixer):
        """Test applying all fixes handles exceptions."""
        # Mock backup creation
        fixer._create_backup = AsyncMock()
        
        # Mock diagnosis to raise exception
        fixer.diagnose_registration_issues = AsyncMock(side_effect=Exception("Diagnosis failed"))

        result = await fixer.apply_all_fixes()

        assert result.success is False
        assert result.total_issues == 0
        assert result.fixed_issues == 0
        assert result.failed_fixes == 0
        assert result.backup_created is True


class TestConfigFlowRegistrationFixerFixVerification:
    """Test cases for fix verification functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock(spec=HomeAssistant)
        hass.loop = MagicMock()
        hass.config_entries = MagicMock()
        hass.components = MagicMock()
        return hass

    @pytest.fixture
    def fixer(self, mock_hass):
        """Create a ConfigFlowRegistrationFixer instance."""
        with patch.object(ConfigFlowRegistrationFixer, '_get_integration_path') as mock_path:
            mock_path.return_value = Path("/test/integration")
            return ConfigFlowRegistrationFixer(mock_hass, "test_domain")

    @pytest.mark.asyncio
    async def test_verify_config_flow_class_success(self, fixer):
        """Test successful config flow class verification."""
        content = """
from homeassistant.config_entries import ConfigFlow
from .const import DOMAIN

class TestConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        pass
"""
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                result = await fixer._verify_config_flow_class()

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_config_flow_class_missing_file(self, fixer):
        """Test config flow class verification when file is missing."""
        with patch.object(Path, "exists", return_value=False):
            result = await fixer._verify_config_flow_class()

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_config_flow_class_missing_class(self, fixer):
        """Test config flow class verification when class is missing."""
        content = "# No ConfigFlow class here"
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                result = await fixer._verify_config_flow_class()

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_config_flow_methods_success(self, fixer):
        """Test successful config flow methods verification."""
        content = """
class TestConfigFlow(ConfigFlow):
    async def async_step_user(self, user_input=None):
        return self.async_show_form(step_id="user")
"""
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                result = await fixer._verify_config_flow_methods()

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_config_flow_methods_missing_required_method(self, fixer):
        """Test config flow methods verification when required method is missing."""
        content = """
class TestConfigFlow(ConfigFlow):
    VERSION = 1
    # Missing the required user step method
"""
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=content)):
                result = await fixer._verify_config_flow_methods()

        assert result is False

    @pytest.mark.asyncio
    async def test_create_basic_config_flow_content(self, fixer):
        """Test that basic config flow file is created with correct content."""
        mock_file = mock_open()
        
        with patch("builtins.open", mock_file):
            await fixer._create_basic_config_flow()

        # Verify file was opened for writing
        mock_file.assert_called_once()
        
        # Get the written content
        written_calls = mock_file().write.call_args_list
        written_content = "".join(call.args[0] for call in written_calls)
        
        # Verify essential components are present
        assert "class RoostSchedulerConfigFlow" in written_content
        assert "config_entries.ConfigFlow" in written_content
        assert "domain=DOMAIN" in written_content
        assert "async def async_step_user" in written_content
        assert "from .const import DOMAIN" in written_content

    @pytest.mark.asyncio
    async def test_create_backup_success(self, fixer):
        """Test successful backup creation."""
        # Mock file paths to exist
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "mkdir") as mock_mkdir:
                with patch("shutil.copy2") as mock_copy:
                    await fixer._create_backup()

        # Verify backup directory was created
        mock_mkdir.assert_called_once()
        
        # Verify files were copied (should be at least manifest, const, config_flow, init)
        assert mock_copy.call_count >= 4

    @pytest.mark.asyncio
    async def test_create_backup_partial_files(self, fixer):
        """Test backup creation when only some files exist."""
        def mock_exists(self):
            # Only manifest and const files exist
            return self.name in ["manifest.json", "const.py"]
        
        with patch.object(Path, "exists", mock_exists):
            with patch.object(Path, "mkdir") as mock_mkdir:
                with patch("shutil.copy2") as mock_copy:
                    await fixer._create_backup()

        # Verify backup directory was created
        mock_mkdir.assert_called_once()
        
        # Verify only existing files were copied
        assert mock_copy.call_count == 2

    def test_registration_issue_dataclass(self):
        """Test RegistrationIssue dataclass functionality."""
        issue = RegistrationIssue(
            issue_type="test_issue",
            description="Test description",
            severity="error",
            fix_available=True,
            fix_description="Fix description",
            diagnostic_info={"key": "value"},
            fix_priority=5
        )
        
        assert issue.issue_type == "test_issue"
        assert issue.description == "Test description"
        assert issue.severity == "error"
        assert issue.fix_available is True
        assert issue.fix_description == "Fix description"
        assert issue.diagnostic_info == {"key": "value"}
        assert issue.fix_priority == 5

    def test_fix_result_dataclass(self):
        """Test FixResult dataclass functionality."""
        result = FixResult(
            success=True,
            issue_type="test_fix",
            description="Fix applied",
            changes_made=["Change 1", "Change 2"],
            errors=["Error 1"],
            warnings=["Warning 1"],
            verification_passed=True
        )
        
        assert result.success is True
        assert result.issue_type == "test_fix"
        assert result.description == "Fix applied"
        assert len(result.changes_made) == 2
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.verification_passed is True

    def test_overall_fix_result_dataclass(self):
        """Test OverallFixResult dataclass functionality."""
        fix_result = FixResult(
            success=True,
            issue_type="test",
            description="Test fix",
            changes_made=[],
            errors=[],
            warnings=[],
            verification_passed=True
        )
        
        remaining_issue = RegistrationIssue(
            issue_type="remaining",
            description="Still needs fixing",
            severity="warning",
            fix_available=False,
            fix_description="Manual fix required",
            diagnostic_info={}
        )
        
        overall_result = OverallFixResult(
            success=False,
            total_issues=2,
            fixed_issues=1,
            failed_fixes=0,
            fix_results=[fix_result],
            remaining_issues=[remaining_issue],
            backup_created=True
        )
        
        assert overall_result.success is False
        assert overall_result.total_issues == 2
        assert overall_result.fixed_issues == 1
        assert overall_result.failed_fixes == 0
        assert len(overall_result.fix_results) == 1
        assert len(overall_result.remaining_issues) == 1
        assert overall_result.backup_created is True