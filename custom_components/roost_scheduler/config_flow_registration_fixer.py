"""Config Flow Registration Fixer for Roost Scheduler integration."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN
from .config_flow_validator import ValidationIssue, ValidationResult
from .domain_consistency_checker import DomainConsistencyChecker, ConsistencyResult

_LOGGER = logging.getLogger(__name__)


@dataclass
class RegistrationIssue:
    """Represents a config flow registration issue."""
    issue_type: str
    description: str
    severity: str  # "critical", "error", "warning", "info"
    fix_available: bool
    fix_description: str
    diagnostic_info: Dict[str, Any]
    fix_priority: int = 0  # Higher number = higher priority


@dataclass
class FixResult:
    """Result of applying a fix."""
    success: bool
    issue_type: str
    description: str
    changes_made: List[str]
    errors: List[str]
    warnings: List[str]
    verification_passed: bool = False


@dataclass
class OverallFixResult:
    """Result of applying all fixes."""
    success: bool
    total_issues: int
    fixed_issues: int
    failed_fixes: int
    fix_results: List[FixResult]
    remaining_issues: List[RegistrationIssue]
    backup_created: bool = False


class ConfigFlowRegistrationFixer:
    """Automatically fixes common config flow registration issues."""

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize the registration fixer."""
        self.hass = hass
        self.domain = domain
        self._integration_path = self._get_integration_path()
        self._domain_checker = DomainConsistencyChecker(str(self._integration_path))
        
        # File paths
        self._manifest_path = self._integration_path / "manifest.json"
        self._const_path = self._integration_path / "const.py"
        self._config_flow_path = self._integration_path / "config_flow.py"
        self._init_path = self._integration_path / "__init__.py"

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        current_file = Path(__file__)
        return current_file.parent

    async def diagnose_registration_issues(self) -> List[RegistrationIssue]:
        """Identify specific config flow registration problems.
        
        Returns:
            List of registration issues found
        """
        _LOGGER.debug("Diagnosing config flow registration issues for domain: %s", self.domain)
        
        issues = []
        
        try:
            # Check domain consistency issues
            domain_issues = await self._diagnose_domain_issues()
            issues.extend(domain_issues)
            
            # Check config flow class issues
            class_issues = await self._diagnose_class_issues()
            issues.extend(class_issues)
            
            # Check manifest configuration issues
            manifest_issues = await self._diagnose_manifest_issues()
            issues.extend(manifest_issues)
            
            # Check import and dependency issues
            import_issues = await self._diagnose_import_issues()
            issues.extend(import_issues)
            
            # Check method implementation issues
            method_issues = await self._diagnose_method_issues()
            issues.extend(method_issues)
            
            # Sort issues by priority (critical first)
            issues.sort(key=lambda x: (-x.fix_priority, x.severity))
            
            _LOGGER.info("Found %d registration issues", len(issues))
            return issues
            
        except Exception as e:
            _LOGGER.error("Error during registration issue diagnosis: %s", e)
            issues.append(RegistrationIssue(
                issue_type="diagnosis_error",
                description=f"Failed to diagnose registration issues: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e), "error_type": type(e).__name__},
                fix_priority=0
            ))
            return issues

    async def fix_domain_mismatch(self) -> FixResult:
        """Fix domain configuration issues.
        
        Returns:
            FixResult with details of domain fixes applied
        """
        _LOGGER.debug("Fixing domain mismatch issues")
        
        changes_made = []
        errors = []
        warnings = []
        
        try:
            # Use domain consistency checker to fix issues
            fix_result = await self._domain_checker.fix_inconsistencies()
            
            if fix_result.success:
                changes_made.extend(fix_result.fixes_applied)
                warnings.extend(fix_result.warnings)
                
                # Verify the fix
                consistency_result = await self._domain_checker.validate_consistency()
                verification_passed = consistency_result.consistent
                
                return FixResult(
                    success=True,
                    issue_type="domain_mismatch",
                    description="Domain consistency issues fixed",
                    changes_made=changes_made,
                    errors=errors,
                    warnings=warnings,
                    verification_passed=verification_passed
                )
            else:
                errors.extend(fix_result.errors)
                warnings.extend(fix_result.warnings)
                
                return FixResult(
                    success=False,
                    issue_type="domain_mismatch",
                    description="Failed to fix domain consistency issues",
                    changes_made=changes_made,
                    errors=errors,
                    warnings=warnings,
                    verification_passed=False
                )
                
        except Exception as e:
            _LOGGER.error("Error fixing domain mismatch: %s", e)
            errors.append(f"Unexpected error: {str(e)}")
            
            return FixResult(
                success=False,
                issue_type="domain_mismatch",
                description="Domain mismatch fix failed with error",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=False
            )

    async def fix_class_inheritance(self) -> FixResult:
        """Fix config flow class inheritance issues.
        
        Returns:
            FixResult with details of class inheritance fixes applied
        """
        _LOGGER.debug("Fixing config flow class inheritance issues")
        
        changes_made = []
        errors = []
        warnings = []
        
        try:
            if not self._config_flow_path.exists():
                # Create basic config flow file
                await self._create_basic_config_flow()
                changes_made.append("Created basic config_flow.py file")
            else:
                # Fix existing config flow class
                fixes_applied = await self._fix_config_flow_class()
                changes_made.extend(fixes_applied)
            
            # Verify the fix
            verification_passed = await self._verify_config_flow_class()
            
            return FixResult(
                success=len(errors) == 0,
                issue_type="class_inheritance",
                description="Config flow class inheritance issues addressed",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=verification_passed
            )
            
        except Exception as e:
            _LOGGER.error("Error fixing class inheritance: %s", e)
            errors.append(f"Unexpected error: {str(e)}")
            
            return FixResult(
                success=False,
                issue_type="class_inheritance",
                description="Class inheritance fix failed with error",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=False
            )

    async def fix_method_implementation(self) -> FixResult:
        """Fix config flow method implementation issues.
        
        Returns:
            FixResult with details of method implementation fixes applied
        """
        _LOGGER.debug("Fixing config flow method implementation issues")
        
        changes_made = []
        errors = []
        warnings = []
        
        try:
            if not self._config_flow_path.exists():
                errors.append("config_flow.py file does not exist")
                return FixResult(
                    success=False,
                    issue_type="method_implementation",
                    description="Cannot fix methods - config flow file missing",
                    changes_made=changes_made,
                    errors=errors,
                    warnings=warnings,
                    verification_passed=False
                )
            
            # Fix missing or incorrect methods
            method_fixes = await self._fix_config_flow_methods()
            changes_made.extend(method_fixes)
            
            # Verify the fix
            verification_passed = await self._verify_config_flow_methods()
            
            return FixResult(
                success=len(errors) == 0,
                issue_type="method_implementation",
                description="Config flow method implementation issues addressed",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=verification_passed
            )
            
        except Exception as e:
            _LOGGER.error("Error fixing method implementation: %s", e)
            errors.append(f"Unexpected error: {str(e)}")
            
            return FixResult(
                success=False,
                issue_type="method_implementation",
                description="Method implementation fix failed with error",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=False
            )

    async def apply_all_fixes(self) -> OverallFixResult:
        """Apply all available fixes for registration issues.
        
        Returns:
            OverallFixResult with comprehensive fix results
        """
        _LOGGER.info("Applying all config flow registration fixes")
        
        fix_results = []
        backup_created = False
        
        try:
            # Create backup before making changes
            try:
                await self._create_backup()
                backup_created = True
                _LOGGER.info("Created backup before applying fixes")
            except Exception as e:
                _LOGGER.warning("Could not create backup: %s", e)
            
            # Diagnose all issues first
            issues = await self.diagnose_registration_issues()
            total_issues = len(issues)
            
            if total_issues == 0:
                return OverallFixResult(
                    success=True,
                    total_issues=0,
                    fixed_issues=0,
                    failed_fixes=0,
                    fix_results=[],
                    remaining_issues=[],
                    backup_created=backup_created
                )
            
            # Apply fixes in priority order
            domain_fix = await self.fix_domain_mismatch()
            fix_results.append(domain_fix)
            
            manifest_fix = await self.fix_manifest_configuration()
            fix_results.append(manifest_fix)
            
            import_fix = await self.fix_import_issues()
            fix_results.append(import_fix)
            
            class_fix = await self.fix_class_inheritance()
            fix_results.append(class_fix)
            
            method_fix = await self.fix_method_implementation()
            fix_results.append(method_fix)
            
            # Count successful fixes
            fixed_issues = sum(1 for fix in fix_results if fix.success)
            failed_fixes = sum(1 for fix in fix_results if not fix.success)
            
            # Check remaining issues
            remaining_issues = await self.diagnose_registration_issues()
            
            overall_success = len(remaining_issues) == 0 or all(
                issue.severity in ["warning", "info"] for issue in remaining_issues
            )
            
            return OverallFixResult(
                success=overall_success,
                total_issues=total_issues,
                fixed_issues=fixed_issues,
                failed_fixes=failed_fixes,
                fix_results=fix_results,
                remaining_issues=remaining_issues,
                backup_created=backup_created
            )
            
        except Exception as e:
            _LOGGER.error("Error applying fixes: %s", e)
            
            try:
                total_issues = len(await self.diagnose_registration_issues())
            except Exception:
                total_issues = 0
            
            return OverallFixResult(
                success=False,
                total_issues=total_issues,
                fixed_issues=0,
                failed_fixes=len(fix_results),
                fix_results=fix_results,
                remaining_issues=[],
                backup_created=backup_created
            )

    async def _diagnose_domain_issues(self) -> List[RegistrationIssue]:
        """Diagnose domain-related registration issues."""
        issues = []
        
        try:
            consistency_result = await self._domain_checker.validate_consistency()
            
            if not consistency_result.consistent:
                for issue_desc in consistency_result.issues:
                    issues.append(RegistrationIssue(
                        issue_type="domain_mismatch",
                        description=issue_desc,
                        severity="critical",
                        fix_available=True,
                        fix_description="Fix domain consistency across all files",
                        diagnostic_info={
                            "manifest_domain": consistency_result.manifest_domain,
                            "const_domain": consistency_result.const_domain,
                            "config_flow_domain": consistency_result.config_flow_domain
                        },
                        fix_priority=10
                    ))
            
            # Check for missing domain definitions
            if consistency_result.manifest_domain is None:
                issues.append(RegistrationIssue(
                    issue_type="manifest_domain_missing",
                    description="Domain not defined in manifest.json",
                    severity="critical",
                    fix_available=True,
                    fix_description="Add domain field to manifest.json",
                    diagnostic_info={"manifest_path": str(self._manifest_path)},
                    fix_priority=9
                ))
            
            if consistency_result.const_domain is None:
                issues.append(RegistrationIssue(
                    issue_type="const_domain_missing",
                    description="DOMAIN constant not defined in const.py",
                    severity="critical",
                    fix_available=True,
                    fix_description="Add DOMAIN constant to const.py",
                    diagnostic_info={"const_path": str(self._const_path)},
                    fix_priority=8
                ))
                
        except Exception as e:
            issues.append(RegistrationIssue(
                issue_type="domain_diagnosis_error",
                description=f"Error diagnosing domain issues: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)},
                fix_priority=0
            ))
        
        return issues

    async def _diagnose_class_issues(self) -> List[RegistrationIssue]:
        """Diagnose config flow class-related issues."""
        issues = []
        
        try:
            if not self._config_flow_path.exists():
                issues.append(RegistrationIssue(
                    issue_type="config_flow_file_missing",
                    description="config_flow.py file does not exist",
                    severity="critical",
                    fix_available=True,
                    fix_description="Create config_flow.py with proper ConfigFlow class",
                    diagnostic_info={"config_flow_path": str(self._config_flow_path)},
                    fix_priority=7
                ))
                return issues
            
            # Read config flow file
            with open(self._config_flow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for ConfigFlow class
            if not re.search(r'class\s+\w+.*ConfigFlow', content):
                issues.append(RegistrationIssue(
                    issue_type="config_flow_class_missing",
                    description="No ConfigFlow class found in config_flow.py",
                    severity="critical",
                    fix_available=True,
                    fix_description="Add ConfigFlow class that inherits from config_entries.ConfigFlow",
                    diagnostic_info={"has_class": "class" in content},
                    fix_priority=6
                ))
            
            # Check for proper imports
            if "from homeassistant.config_entries import ConfigFlow" not in content and "config_entries" not in content:
                issues.append(RegistrationIssue(
                    issue_type="config_flow_import_missing",
                    description="Missing import for ConfigFlow",
                    severity="error",
                    fix_available=True,
                    fix_description="Add proper imports for ConfigFlow",
                    diagnostic_info={"content_length": len(content)},
                    fix_priority=5
                ))
            
            # Check for domain specification
            if f"domain={self.domain}" not in content and f'domain="{self.domain}"' not in content and "domain=DOMAIN" not in content:
                issues.append(RegistrationIssue(
                    issue_type="config_flow_domain_not_specified",
                    description="ConfigFlow class does not specify domain",
                    severity="error",
                    fix_available=True,
                    fix_description="Add domain specification to ConfigFlow class",
                    diagnostic_info={"expected_domain": self.domain},
                    fix_priority=4
                ))
                
        except Exception as e:
            issues.append(RegistrationIssue(
                issue_type="class_diagnosis_error",
                description=f"Error diagnosing class issues: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)},
                fix_priority=0
            ))
        
        return issues

    async def _diagnose_manifest_issues(self) -> List[RegistrationIssue]:
        """Diagnose manifest.json configuration issues."""
        issues = []
        
        try:
            if not self._manifest_path.exists():
                issues.append(RegistrationIssue(
                    issue_type="manifest_file_missing",
                    description="manifest.json file does not exist",
                    severity="critical",
                    fix_available=True,
                    fix_description="Create manifest.json with required fields",
                    diagnostic_info={"manifest_path": str(self._manifest_path)},
                    fix_priority=9
                ))
                return issues
            
            # Load manifest
            with open(self._manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            # Check config_flow setting
            if not manifest_data.get("config_flow"):
                issues.append(RegistrationIssue(
                    issue_type="config_flow_not_enabled",
                    description="config_flow is not enabled in manifest.json",
                    severity="critical",
                    fix_available=True,
                    fix_description="Set 'config_flow': true in manifest.json",
                    diagnostic_info={"config_flow_value": manifest_data.get("config_flow")},
                    fix_priority=8
                ))
            
            # Check required fields
            required_fields = ["domain", "name", "version"]
            for field in required_fields:
                if field not in manifest_data:
                    issues.append(RegistrationIssue(
                        issue_type="manifest_required_field_missing",
                        description=f"Required field '{field}' missing from manifest.json",
                        severity="error",
                        fix_available=True,
                        fix_description=f"Add '{field}' field to manifest.json",
                        diagnostic_info={"missing_field": field},
                        fix_priority=3
                    ))
                    
        except json.JSONDecodeError as e:
            issues.append(RegistrationIssue(
                issue_type="manifest_json_invalid",
                description=f"Invalid JSON in manifest.json: {str(e)}",
                severity="critical",
                fix_available=False,
                fix_description="Fix JSON syntax errors in manifest.json",
                diagnostic_info={"json_error": str(e)},
                fix_priority=0
            ))
        except Exception as e:
            issues.append(RegistrationIssue(
                issue_type="manifest_diagnosis_error",
                description=f"Error diagnosing manifest issues: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)},
                fix_priority=0
            ))
        
        return issues

    async def _diagnose_import_issues(self) -> List[RegistrationIssue]:
        """Diagnose import and dependency issues."""
        issues = []
        
        try:
            # Check if we can import the config flow module
            try:
                from . import config_flow
                if not hasattr(config_flow, 'RoostSchedulerConfigFlow'):
                    issues.append(RegistrationIssue(
                        issue_type="config_flow_class_not_exported",
                        description="ConfigFlow class not found in config_flow module",
                        severity="error",
                        fix_available=True,
                        fix_description="Ensure ConfigFlow class is properly defined and named",
                        diagnostic_info={"module_attributes": dir(config_flow)},
                        fix_priority=2
                    ))
            except ImportError as e:
                issues.append(RegistrationIssue(
                    issue_type="config_flow_import_error",
                    description=f"Cannot import config_flow module: {str(e)}",
                    severity="critical",
                    fix_available=True,
                    fix_description="Fix import errors in config_flow.py",
                    diagnostic_info={"import_error": str(e)},
                    fix_priority=6
                ))
            
            # Check const.py import
            try:
                from .const import DOMAIN
                if DOMAIN != self.domain:
                    issues.append(RegistrationIssue(
                        issue_type="const_domain_mismatch",
                        description=f"DOMAIN constant '{DOMAIN}' doesn't match expected '{self.domain}'",
                        severity="error",
                        fix_available=True,
                        fix_description="Update DOMAIN constant in const.py",
                        diagnostic_info={"const_domain": DOMAIN, "expected_domain": self.domain},
                        fix_priority=4
                    ))
            except ImportError as e:
                issues.append(RegistrationIssue(
                    issue_type="const_import_error",
                    description=f"Cannot import DOMAIN from const.py: {str(e)}",
                    severity="error",
                    fix_available=True,
                    fix_description="Fix const.py import issues",
                    diagnostic_info={"import_error": str(e)},
                    fix_priority=3
                ))
                
        except Exception as e:
            issues.append(RegistrationIssue(
                issue_type="import_diagnosis_error",
                description=f"Error diagnosing import issues: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)},
                fix_priority=0
            ))
        
        return issues

    async def _diagnose_method_issues(self) -> List[RegistrationIssue]:
        """Diagnose config flow method implementation issues."""
        issues = []
        
        try:
            if not self._config_flow_path.exists():
                return issues  # Will be handled by class issues
            
            with open(self._config_flow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for required methods
            required_methods = ["async_step_user"]
            
            for method in required_methods:
                if method not in content:
                    issues.append(RegistrationIssue(
                        issue_type="config_flow_method_missing",
                        description=f"Required method '{method}' not found",
                        severity="error",
                        fix_available=True,
                        fix_description=f"Implement '{method}' method in ConfigFlow class",
                        diagnostic_info={"missing_method": method},
                        fix_priority=2
                    ))
            
            # Check for proper async method definitions
            if "async def" not in content:
                issues.append(RegistrationIssue(
                    issue_type="config_flow_no_async_methods",
                    description="No async methods found in config flow",
                    severity="warning",
                    fix_available=True,
                    fix_description="Ensure config flow methods are properly defined as async",
                    diagnostic_info={"has_def": "def" in content},
                    fix_priority=1
                ))
                
        except Exception as e:
            issues.append(RegistrationIssue(
                issue_type="method_diagnosis_error",
                description=f"Error diagnosing method issues: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)},
                fix_priority=0
            ))
        
        return issues

    async def _create_backup(self) -> None:
        """Create backup of files before modification."""
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self._integration_path / f"backup_registration_fix_{timestamp}"
        backup_dir.mkdir(exist_ok=True)
        
        files_to_backup = [
            self._manifest_path,
            self._const_path,
            self._config_flow_path,
            self._init_path
        ]
        
        for file_path in files_to_backup:
            if file_path.exists():
                backup_path = backup_dir / file_path.name
                shutil.copy2(file_path, backup_path)
                _LOGGER.info("Created backup: %s", backup_path)

    async def _create_basic_config_flow(self) -> None:
        """Create a basic config_flow.py file."""
        config_flow_content = f'''"""Config flow for {self.domain} integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RoostSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for {self.domain}."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({{}}),
            )

        return self.async_create_entry(title="Roost Scheduler", data=user_input)
'''
        
        with open(self._config_flow_path, 'w', encoding='utf-8') as f:
            f.write(config_flow_content)
        
        _LOGGER.info("Created basic config_flow.py file")

    async def _fix_config_flow_class(self) -> List[str]:
        """Fix existing config flow class issues."""
        fixes_applied = []
        
        with open(self._config_flow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Add missing imports
        if "from homeassistant import config_entries" not in content and "config_entries" not in content:
            import_line = "from homeassistant import config_entries\n"
            if "from homeassistant" in content:
                # Add to existing homeassistant imports
                content = re.sub(
                    r'(from homeassistant[^\n]*\n)',
                    r'\1' + import_line,
                    content,
                    count=1
                )
            else:
                # Add at the top after existing imports
                lines = content.split('\n')
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.startswith('"""') and not line.startswith('from') and not line.startswith('import'):
                        insert_index = i
                        break
                lines.insert(insert_index, import_line.strip())
                content = '\n'.join(lines)
            fixes_applied.append("Added missing config_entries import")
        
        # Fix class definition if needed
        if not re.search(r'class\s+\w+.*ConfigFlow', content):
            # Add basic class definition
            class_def = f'''

class RoostSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for {self.domain}."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({{}}))
        return self.async_create_entry(title="Roost Scheduler", data=user_input)
'''
            content += class_def
            fixes_applied.append("Added ConfigFlow class definition")
        
        # Add domain specification if missing
        if f"domain={self.domain}" not in content and f'domain="{self.domain}"' not in content and "domain=DOMAIN" not in content:
            # Try to add domain to existing class
            content = re.sub(
                r'(class\s+\w+.*ConfigFlow[^:]*)',
                r'\1, domain=DOMAIN',
                content
            )
            fixes_applied.append("Added domain specification to ConfigFlow class")
        
        if content != original_content:
            with open(self._config_flow_path, 'w', encoding='utf-8') as f:
                f.write(content)
            fixes_applied.append("Updated config_flow.py file")
        
        return fixes_applied

    async def _fix_config_flow_methods(self) -> List[str]:
        """Fix missing or incorrect config flow methods."""
        fixes_applied = []
        
        with open(self._config_flow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Add missing imports for voluptuous if needed
        if "async_step_user" not in content and "vol.Schema" not in content and "import voluptuous" not in content:
            if "import voluptuous as vol" not in content:
                import_line = "import voluptuous as vol\n"
                lines = content.split('\n')
                # Find a good place to insert the import
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.startswith('"""') and not line.startswith('from') and not line.startswith('import'):
                        insert_index = i
                        break
                lines.insert(insert_index, import_line.strip())
                content = '\n'.join(lines)
                fixes_applied.append("Added voluptuous import")
        
        # Check if async_step_user method exists
        if "async_step_user" not in content:
            # Add the method to the class
            method_def = '''
    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
        return self.async_create_entry(title="Roost Scheduler", data=user_input)
'''
            
            # Find the class definition and add the method
            if "class" in content and "ConfigFlow" in content:
                # Try to find the end of the class definition to add the method
                class_match = re.search(r'(class\s+\w+.*ConfigFlow[^:]*:)', content)
                if class_match:
                    class_end = class_match.end()
                    # Insert method after class definition
                    content = content[:class_end] + method_def + content[class_end:]
                    fixes_applied.append("Added async_step_user method")
        
        # Fix method signatures if they're incorrect
        if "async_step_user" in content:
            # Check if method has proper signature
            if re.search(r'def async_step_user\s*\([^)]*\):', content) and not re.search(r'async def async_step_user', content):
                # Fix missing async keyword
                content = re.sub(
                    r'def async_step_user',
                    'async def async_step_user',
                    content
                )
                fixes_applied.append("Fixed async_step_user method signature")
        
        if content != original_content:
            with open(self._config_flow_path, 'w', encoding='utf-8') as f:
                f.write(content)
            fixes_applied.append("Updated config flow methods")
        
        return fixes_applied

    async def fix_manifest_configuration(self) -> FixResult:
        """Fix manifest.json configuration issues.
        
        Returns:
            FixResult with details of manifest fixes applied
        """
        _LOGGER.debug("Fixing manifest configuration issues")
        
        changes_made = []
        errors = []
        warnings = []
        
        try:
            if not self._manifest_path.exists():
                # Create basic manifest.json
                await self._create_basic_manifest()
                changes_made.append("Created basic manifest.json file")
            else:
                # Fix existing manifest
                manifest_fixes = await self._fix_manifest_content()
                changes_made.extend(manifest_fixes)
            
            # Verify the fix
            verification_passed = await self._verify_manifest_configuration()
            
            return FixResult(
                success=len(errors) == 0,
                issue_type="manifest_configuration",
                description="Manifest configuration issues addressed",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=verification_passed
            )
            
        except Exception as e:
            _LOGGER.error("Error fixing manifest configuration: %s", e)
            errors.append(f"Unexpected error: {str(e)}")
            
            return FixResult(
                success=False,
                issue_type="manifest_configuration",
                description="Manifest configuration fix failed with error",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=False
            )

    async def fix_import_issues(self) -> FixResult:
        """Fix import and dependency issues.
        
        Returns:
            FixResult with details of import fixes applied
        """
        _LOGGER.debug("Fixing import and dependency issues")
        
        changes_made = []
        errors = []
        warnings = []
        
        try:
            # Fix const.py issues
            const_fixes = await self._fix_const_imports()
            changes_made.extend(const_fixes)
            
            # Fix config_flow.py import issues
            config_flow_fixes = await self._fix_config_flow_imports()
            changes_made.extend(config_flow_fixes)
            
            # Verify the fix
            verification_passed = await self._verify_imports()
            
            return FixResult(
                success=len(errors) == 0,
                issue_type="import_issues",
                description="Import and dependency issues addressed",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=verification_passed
            )
            
        except Exception as e:
            _LOGGER.error("Error fixing import issues: %s", e)
            errors.append(f"Unexpected error: {str(e)}")
            
            return FixResult(
                success=False,
                issue_type="import_issues",
                description="Import issues fix failed with error",
                changes_made=changes_made,
                errors=errors,
                warnings=warnings,
                verification_passed=False
            )

    async def _create_basic_manifest(self) -> None:
        """Create a basic manifest.json file."""
        manifest_data = {
            "domain": self.domain,
            "name": "Roost Scheduler",
            "version": "0.4.0",
            "config_flow": True,
            "documentation": "https://github.com/user/roost-scheduler",
            "issue_tracker": "https://github.com/user/roost-scheduler/issues",
            "dependencies": ["frontend", "websocket_api"],
            "codeowners": ["@user"],
            "iot_class": "local_polling"
        }
        
        with open(self._manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        
        _LOGGER.info("Created basic manifest.json file")

    async def _fix_manifest_content(self) -> List[str]:
        """Fix existing manifest.json content."""
        fixes_applied = []
        
        with open(self._manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        
        original_data = manifest_data.copy()
        
        # Fix domain if incorrect
        if manifest_data.get("domain") != self.domain:
            manifest_data["domain"] = self.domain
            fixes_applied.append(f"Updated domain to '{self.domain}'")
        
        # Enable config_flow if not enabled
        if not manifest_data.get("config_flow"):
            manifest_data["config_flow"] = True
            fixes_applied.append("Enabled config_flow in manifest")
        
        # Add required fields if missing
        required_fields = {
            "name": "Roost Scheduler",
            "version": "0.4.0"
        }
        
        for field, default_value in required_fields.items():
            if field not in manifest_data:
                manifest_data[field] = default_value
                fixes_applied.append(f"Added missing '{field}' field")
        
        # Ensure dependencies include required components
        dependencies = manifest_data.get("dependencies", [])
        required_deps = ["frontend", "websocket_api"]
        
        for dep in required_deps:
            if dep not in dependencies:
                dependencies.append(dep)
                fixes_applied.append(f"Added required dependency '{dep}'")
        
        if dependencies != manifest_data.get("dependencies", []):
            manifest_data["dependencies"] = dependencies
        
        if manifest_data != original_data:
            with open(self._manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)
            fixes_applied.append("Updated manifest.json file")
        
        return fixes_applied

    async def _fix_const_imports(self) -> List[str]:
        """Fix const.py import issues."""
        fixes_applied = []
        
        if not self._const_path.exists():
            # Create basic const.py
            const_content = f'''"""Constants for the {self.domain} integration."""
from __future__ import annotations

DOMAIN = "{self.domain}"
NAME = "Roost Scheduler"
VERSION = "0.4.0"
'''
            with open(self._const_path, 'w', encoding='utf-8') as f:
                f.write(const_content)
            fixes_applied.append("Created basic const.py file")
        else:
            # Check if DOMAIN is properly defined
            with open(self._const_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if f'DOMAIN = "{self.domain}"' not in content and f"DOMAIN = '{self.domain}'" not in content:
                # Try to fix existing DOMAIN definition
                if "DOMAIN" in content:
                    content = re.sub(
                        r'DOMAIN\s*=\s*["\'][^"\']*["\']',
                        f'DOMAIN = "{self.domain}"',
                        content
                    )
                    fixes_applied.append("Fixed DOMAIN constant value")
                else:
                    # Add DOMAIN constant
                    lines = content.split('\n')
                    insert_index = 0
                    for i, line in enumerate(lines):
                        if line.strip() and not line.startswith('"""') and not line.startswith('from') and not line.startswith('import'):
                            insert_index = i
                            break
                    lines.insert(insert_index, f'DOMAIN = "{self.domain}"')
                    content = '\n'.join(lines)
                    fixes_applied.append("Added DOMAIN constant")
                
                with open(self._const_path, 'w', encoding='utf-8') as f:
                    f.write(content)
        
        return fixes_applied

    async def _fix_config_flow_imports(self) -> List[str]:
        """Fix config_flow.py import issues."""
        fixes_applied = []
        
        if not self._config_flow_path.exists():
            return fixes_applied  # Will be handled by class creation
        
        with open(self._config_flow_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Add missing imports
        required_imports = [
            ("from homeassistant import config_entries", "config_entries"),
            ("from homeassistant.core import HomeAssistant", "HomeAssistant"),
            ("from homeassistant.data_entry_flow import FlowResult", "FlowResult"),
            ("from .const import DOMAIN", "DOMAIN")
        ]
        
        for import_line, check_text in required_imports:
            if check_text not in content:
                # Add the import
                lines = content.split('\n')
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.strip() and not line.startswith('"""') and not line.startswith('from') and not line.startswith('import'):
                        insert_index = i
                        break
                lines.insert(insert_index, import_line)
                content = '\n'.join(lines)
                fixes_applied.append(f"Added import: {import_line}")
        
        if content != original_content:
            with open(self._config_flow_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return fixes_applied

    async def _verify_manifest_configuration(self) -> bool:
        """Verify that manifest.json is properly configured."""
        try:
            if not self._manifest_path.exists():
                return False
            
            with open(self._manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            # Check required fields and values
            checks = [
                manifest_data.get("domain") == self.domain,
                manifest_data.get("config_flow") is True,
                "name" in manifest_data,
                "version" in manifest_data
            ]
            
            return all(checks)
            
        except Exception as e:
            _LOGGER.error("Error verifying manifest configuration: %s", e)
            return False

    async def _verify_imports(self) -> bool:
        """Verify that all imports are working correctly."""
        try:
            # Try to import const
            from .const import DOMAIN
            if DOMAIN != self.domain:
                return False
            
            # Try to import config flow if it exists
            if self._config_flow_path.exists():
                try:
                    from . import config_flow
                    return True
                except ImportError:
                    return False
            
            return True
            
        except Exception as e:
            _LOGGER.error("Error verifying imports: %s", e)
            return False

    async def verify_all_fixes(self) -> FixVerificationResult:
        """Verify that all applied fixes are working correctly.
        
        Returns:
            FixVerificationResult with comprehensive verification details
        """
        _LOGGER.debug("Verifying all applied fixes")
        
        verification_results = []
        overall_success = True
        
        try:
            # Verify domain consistency
            domain_verification = await self._verify_domain_consistency()
            verification_results.append(domain_verification)
            if not domain_verification.success:
                overall_success = False
            
            # Verify manifest configuration
            manifest_verification = await self._verify_manifest_fix()
            verification_results.append(manifest_verification)
            if not manifest_verification.success:
                overall_success = False
            
            # Verify config flow class
            class_verification = await self._verify_config_flow_fix()
            verification_results.append(class_verification)
            if not class_verification.success:
                overall_success = False
            
            # Verify imports
            import_verification = await self._verify_import_fix()
            verification_results.append(import_verification)
            if not import_verification.success:
                overall_success = False
            
            # Verify methods
            method_verification = await self._verify_method_fix()
            verification_results.append(method_verification)
            if not method_verification.success:
                overall_success = False
            
            # Run final integration test
            integration_verification = await self._verify_integration_loading()
            verification_results.append(integration_verification)
            if not integration_verification.success:
                overall_success = False
            
            return FixVerificationResult(
                success=overall_success,
                verification_results=verification_results,
                total_checks=len(verification_results),
                passed_checks=sum(1 for v in verification_results if v.success),
                failed_checks=sum(1 for v in verification_results if not v.success),
                recommendations=self._generate_verification_recommendations(verification_results)
            )
            
        except Exception as e:
            _LOGGER.error("Error during fix verification: %s", e)
            return FixVerificationResult(
                success=False,
                verification_results=[],
                total_checks=0,
                passed_checks=0,
                failed_checks=1,
                recommendations=[f"Fix verification failed with error: {str(e)}"]
            )

    async def rollback_fixes(self, backup_path: Optional[str] = None) -> RollbackResult:
        """Rollback applied fixes using backup files.
        
        Args:
            backup_path: Optional specific backup directory to use
            
        Returns:
            RollbackResult with details of rollback operation
        """
        _LOGGER.info("Rolling back config flow registration fixes")
        
        rollback_actions = []
        errors = []
        warnings = []
        
        try:
            # Find backup directory
            if backup_path:
                backup_dir = Path(backup_path)
            else:
                backup_dir = await self._find_latest_backup()
            
            if not backup_dir or not backup_dir.exists():
                errors.append("No backup directory found for rollback")
                return RollbackResult(
                    success=False,
                    rollback_actions=rollback_actions,
                    errors=errors,
                    warnings=warnings
                )
            
            # Restore files from backup
            files_to_restore = [
                ("manifest.json", self._manifest_path),
                ("const.py", self._const_path),
                ("config_flow.py", self._config_flow_path),
                ("__init__.py", self._init_path)
            ]
            
            for backup_filename, target_path in files_to_restore:
                backup_file = backup_dir / backup_filename
                
                if backup_file.exists():
                    try:
                        import shutil
                        shutil.copy2(backup_file, target_path)
                        rollback_actions.append(f"Restored {backup_filename} from backup")
                    except Exception as e:
                        errors.append(f"Failed to restore {backup_filename}: {str(e)}")
                else:
                    warnings.append(f"Backup file {backup_filename} not found")
            
            # Verify rollback
            verification_passed = len(errors) == 0
            if verification_passed:
                rollback_actions.append("Rollback verification passed")
            
            return RollbackResult(
                success=len(errors) == 0,
                rollback_actions=rollback_actions,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            _LOGGER.error("Error during rollback: %s", e)
            errors.append(f"Rollback failed with error: {str(e)}")
            
            return RollbackResult(
                success=False,
                rollback_actions=rollback_actions,
                errors=errors,
                warnings=warnings
            )

    def generate_fix_report(self, fix_result: OverallFixResult) -> str:
        """Generate a comprehensive fix report.
        
        Args:
            fix_result: The overall fix result to report on
            
        Returns:
            Formatted fix report string
        """
        report_lines = [
            "=" * 60,
            "CONFIG FLOW REGISTRATION FIX REPORT",
            "=" * 60,
            "",
            f"Overall Status: {'SUCCESS' if fix_result.success else 'FAILED'}",
            f"Total Issues Found: {fix_result.total_issues}",
            f"Issues Fixed: {fix_result.fixed_issues}",
            f"Failed Fixes: {fix_result.failed_fixes}",
            f"Backup Created: {'Yes' if fix_result.backup_created else 'No'}",
            "",
            "DETAILED FIX RESULTS:",
            "-" * 30
        ]
        
        for i, fix in enumerate(fix_result.fix_results, 1):
            report_lines.extend([
                f"{i}. {fix.issue_type.upper()}",
                f"   Status: {'SUCCESS' if fix.success else 'FAILED'}",
                f"   Description: {fix.description}",
                f"   Verification: {'PASSED' if fix.verification_passed else 'FAILED'}"
            ])
            
            if fix.changes_made:
                report_lines.append("   Changes Made:")
                for change in fix.changes_made:
                    report_lines.append(f"     - {change}")
            
            if fix.errors:
                report_lines.append("   Errors:")
                for error in fix.errors:
                    report_lines.append(f"     - {error}")
            
            if fix.warnings:
                report_lines.append("   Warnings:")
                for warning in fix.warnings:
                    report_lines.append(f"     - {warning}")
            
            report_lines.append("")
        
        if fix_result.remaining_issues:
            report_lines.extend([
                "REMAINING ISSUES:",
                "-" * 20
            ])
            
            for issue in fix_result.remaining_issues:
                report_lines.extend([
                    f"- {issue.description}",
                    f"  Severity: {issue.severity}",
                    f"  Fix Available: {'Yes' if issue.fix_available else 'No'}",
                    f"  Fix Description: {issue.fix_description}",
                    ""
                ])
        
        report_lines.extend([
            "=" * 60,
            "END OF REPORT",
            "=" * 60
        ])
        
        return "\n".join(report_lines)

    async def _verify_domain_consistency(self) -> VerificationResult:
        """Verify domain consistency fix."""
        try:
            consistency_result = await self._domain_checker.validate_consistency()
            
            return VerificationResult(
                check_name="domain_consistency",
                success=consistency_result.consistent,
                description="Domain consistency across all files",
                details={
                    "manifest_domain": consistency_result.manifest_domain,
                    "const_domain": consistency_result.const_domain,
                    "config_flow_domain": consistency_result.config_flow_domain,
                    "issues": consistency_result.issues
                }
            )
        except Exception as e:
            return VerificationResult(
                check_name="domain_consistency",
                success=False,
                description="Failed to verify domain consistency",
                details={"error": str(e)}
            )

    async def _verify_manifest_fix(self) -> VerificationResult:
        """Verify manifest configuration fix."""
        try:
            success = await self._verify_manifest_configuration()
            
            details = {}
            if self._manifest_path.exists():
                with open(self._manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                details = {
                    "domain": manifest_data.get("domain"),
                    "config_flow": manifest_data.get("config_flow"),
                    "has_required_fields": all(
                        field in manifest_data for field in ["domain", "name", "version"]
                    )
                }
            
            return VerificationResult(
                check_name="manifest_configuration",
                success=success,
                description="Manifest.json configuration",
                details=details
            )
        except Exception as e:
            return VerificationResult(
                check_name="manifest_configuration",
                success=False,
                description="Failed to verify manifest configuration",
                details={"error": str(e)}
            )

    async def _verify_config_flow_fix(self) -> VerificationResult:
        """Verify config flow class fix."""
        try:
            success = await self._verify_config_flow_class()
            
            details = {}
            if self._config_flow_path.exists():
                with open(self._config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                details = {
                    "file_exists": True,
                    "has_config_flow_class": "ConfigFlow" in content,
                    "has_domain_spec": "domain=" in content,
                    "has_imports": "config_entries" in content
                }
            else:
                details = {"file_exists": False}
            
            return VerificationResult(
                check_name="config_flow_class",
                success=success,
                description="Config flow class implementation",
                details=details
            )
        except Exception as e:
            return VerificationResult(
                check_name="config_flow_class",
                success=False,
                description="Failed to verify config flow class",
                details={"error": str(e)}
            )

    async def _verify_import_fix(self) -> VerificationResult:
        """Verify import fix."""
        try:
            success = await self._verify_imports()
            
            return VerificationResult(
                check_name="imports",
                success=success,
                description="Import and dependency resolution",
                details={"can_import_const": True, "can_import_config_flow": success}
            )
        except Exception as e:
            return VerificationResult(
                check_name="imports",
                success=False,
                description="Failed to verify imports",
                details={"error": str(e)}
            )

    async def _verify_method_fix(self) -> VerificationResult:
        """Verify method implementation fix."""
        try:
            success = await self._verify_config_flow_methods()
            
            details = {}
            if self._config_flow_path.exists():
                with open(self._config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                details = {
                    "has_async_step_user": "async_step_user" in content,
                    "has_async_methods": "async def" in content
                }
            
            return VerificationResult(
                check_name="method_implementation",
                success=success,
                description="Config flow method implementation",
                details=details
            )
        except Exception as e:
            return VerificationResult(
                check_name="method_implementation",
                success=False,
                description="Failed to verify method implementation",
                details={"error": str(e)}
            )

    async def _verify_integration_loading(self) -> VerificationResult:
        """Verify that the integration can be loaded."""
        try:
            # Try to import the integration components
            can_import_const = False
            can_import_config_flow = False
            
            try:
                from .const import DOMAIN
                can_import_const = True
            except ImportError:
                pass
            
            try:
                from . import config_flow
                can_import_config_flow = True
            except ImportError:
                pass
            
            success = can_import_const and can_import_config_flow
            
            return VerificationResult(
                check_name="integration_loading",
                success=success,
                description="Integration component loading",
                details={
                    "can_import_const": can_import_const,
                    "can_import_config_flow": can_import_config_flow
                }
            )
        except Exception as e:
            return VerificationResult(
                check_name="integration_loading",
                success=False,
                description="Failed to verify integration loading",
                details={"error": str(e)}
            )

    async def _find_latest_backup(self) -> Optional[Path]:
        """Find the latest backup directory."""
        try:
            backup_dirs = []
            for item in self._integration_path.iterdir():
                if item.is_dir() and item.name.startswith("backup_registration_fix_"):
                    backup_dirs.append(item)
            
            if backup_dirs:
                # Sort by modification time and return the latest
                backup_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return backup_dirs[0]
            
            return None
        except Exception as e:
            _LOGGER.error("Error finding latest backup: %s", e)
            return None

    def _generate_verification_recommendations(self, verification_results: List[VerificationResult]) -> List[str]:
        """Generate recommendations based on verification results."""
        recommendations = []
        
        failed_checks = [v for v in verification_results if not v.success]
        
        if not failed_checks:
            recommendations.append("All fixes have been successfully verified")
            recommendations.append("Config flow registration should now work correctly")
        else:
            recommendations.append("Some fixes failed verification - manual intervention may be required")
            
            for failed_check in failed_checks:
                if failed_check.check_name == "domain_consistency":
                    recommendations.append("Check domain consistency across manifest.json, const.py, and config_flow.py")
                elif failed_check.check_name == "manifest_configuration":
                    recommendations.append("Verify manifest.json has correct domain and config_flow: true")
                elif failed_check.check_name == "config_flow_class":
                    recommendations.append("Ensure config_flow.py has proper ConfigFlow class definition")
                elif failed_check.check_name == "imports":
                    recommendations.append("Check for import errors in const.py and config_flow.py")
                elif failed_check.check_name == "method_implementation":
                    recommendations.append("Verify async_step_user method is properly implemented")
                elif failed_check.check_name == "integration_loading":
                    recommendations.append("Test integration loading manually to identify remaining issues")
        
        return recommendations

    async def _verify_config_flow_class(self) -> bool:
        """Verify that config flow class is properly implemented."""
        try:
            if not self._config_flow_path.exists():
                return False
            
            with open(self._config_flow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for required elements
            checks = [
                "class" in content and "ConfigFlow" in content,
                "config_entries" in content,
                "domain=" in content or "DOMAIN" in content,
            ]
            
            return all(checks)
            
        except Exception as e:
            _LOGGER.error("Error verifying config flow class: %s", e)
            return False

    async def _verify_config_flow_methods(self) -> bool:
        """Verify that required config flow methods are implemented."""
        try:
            if not self._config_flow_path.exists():
                return False
            
            with open(self._config_flow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for required methods
            required_methods = ["async_step_user"]
            
            for method in required_methods:
                if method not in content:
                    return False
            
            return True
            
        except Exception as e:
            _LOGGER.error("Error verifying config flow methods: %s", e)
            return False


@dataclass
class VerificationResult:
    """Result of a single verification check."""
    check_name: str
    success: bool
    description: str
    details: Dict[str, Any]


@dataclass
class FixVerificationResult:
    """Result of comprehensive fix verification."""
    success: bool
    verification_results: List[VerificationResult]
    total_checks: int
    passed_checks: int
    failed_checks: int
    recommendations: List[str]


@dataclass
class RollbackResult:
    """Result of rollback operation."""
    success: bool
    rollback_actions: List[str]
    errors: List[str]
    warnings: List[str]