"""Config Flow Validator for Roost Scheduler integration."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    issue_type: str
    description: str
    severity: str  # "error", "warning", "info"
    fix_available: bool
    fix_description: str
    diagnostic_info: Dict[str, Any]


@dataclass
class ValidationResult:
    """Result of a validation check."""
    success: bool
    issues: List[ValidationIssue]
    warnings: List[str]
    recommendations: List[str]
    diagnostic_data: Dict[str, Any]


class ConfigFlowValidator:
    """Validates config flow registration and domain consistency."""

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize the validator."""
        self.hass = hass
        self.domain = domain
        self._integration_path = self._get_integration_path()
        self._validation_cache: Dict[str, ValidationResult] = {}

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        # Get the path from the current file location
        current_file = Path(__file__)
        return current_file.parent

    async def validate_config_flow_registration(self) -> ValidationResult:
        """Validate that the config flow can be properly registered."""
        _LOGGER.debug("Validating config flow registration for domain: %s", self.domain)
        
        issues = []
        warnings = []
        recommendations = []
        diagnostic_data = {}
        
        try:
            # Check if config flow class exists and is properly defined
            config_flow_result = await self._check_config_flow_class()
            issues.extend(config_flow_result.issues)
            warnings.extend(config_flow_result.warnings)
            diagnostic_data.update(config_flow_result.diagnostic_data)
            
            # Check if config flow is registered with Home Assistant
            registration_result = await self._check_config_flow_registration()
            issues.extend(registration_result.issues)
            warnings.extend(registration_result.warnings)
            diagnostic_data.update(registration_result.diagnostic_data)
            
            # Check config flow methods
            methods_result = await self._check_config_flow_methods()
            issues.extend(methods_result.issues)
            warnings.extend(methods_result.warnings)
            diagnostic_data.update(methods_result.diagnostic_data)
            
            success = not any(issue.severity == "error" for issue in issues)
            
            if success:
                recommendations.append("Config flow registration validation passed")
            else:
                recommendations.append("Fix config flow registration issues before proceeding")
            
            return ValidationResult(
                success=success,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                diagnostic_data=diagnostic_data
            )
            
        except Exception as e:
            _LOGGER.error("Error during config flow registration validation: %s", e)
            issues.append(ValidationIssue(
                issue_type="validation_error",
                description=f"Validation failed with error: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e), "error_type": type(e).__name__}
            ))
            
            return ValidationResult(
                success=False,
                issues=issues,
                warnings=warnings,
                recommendations=["Fix validation errors before proceeding"],
                diagnostic_data=diagnostic_data
            )

    async def validate_domain_consistency(self) -> ValidationResult:
        """Validate domain consistency across all integration files."""
        _LOGGER.debug("Validating domain consistency for domain: %s", self.domain)
        
        issues = []
        warnings = []
        recommendations = []
        diagnostic_data = {}
        
        try:
            # Check manifest.json domain
            manifest_domain = await self._get_manifest_domain()
            diagnostic_data["manifest_domain"] = manifest_domain
            
            # Check const.py domain
            const_domain = await self._get_const_domain()
            diagnostic_data["const_domain"] = const_domain
            
            # Check config_flow.py domain
            config_flow_domain = await self._get_config_flow_domain()
            diagnostic_data["config_flow_domain"] = config_flow_domain
            
            # Validate consistency
            domains = {
                "manifest": manifest_domain,
                "const": const_domain,
                "config_flow": config_flow_domain
            }
            
            unique_domains = set(filter(None, domains.values()))
            
            if len(unique_domains) > 1:
                issues.append(ValidationIssue(
                    issue_type="domain_mismatch",
                    description=f"Domain mismatch detected: {domains}",
                    severity="error",
                    fix_available=True,
                    fix_description="Update all files to use consistent domain",
                    diagnostic_info={"domains": domains}
                ))
            elif len(unique_domains) == 0:
                issues.append(ValidationIssue(
                    issue_type="domain_missing",
                    description="No domain found in any file",
                    severity="error",
                    fix_available=True,
                    fix_description="Add domain definition to integration files",
                    diagnostic_info={"domains": domains}
                ))
            else:
                expected_domain = list(unique_domains)[0]
                if expected_domain != self.domain:
                    warnings.append(f"Expected domain '{self.domain}' but found '{expected_domain}'")
                    diagnostic_data["expected_domain"] = self.domain
                    diagnostic_data["actual_domain"] = expected_domain
            
            success = not any(issue.severity == "error" for issue in issues)
            
            if success:
                recommendations.append("Domain consistency validation passed")
            else:
                recommendations.append("Fix domain consistency issues")
            
            return ValidationResult(
                success=success,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                diagnostic_data=diagnostic_data
            )
            
        except Exception as e:
            _LOGGER.error("Error during domain consistency validation: %s", e)
            issues.append(ValidationIssue(
                issue_type="validation_error",
                description=f"Domain consistency validation failed: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e), "error_type": type(e).__name__}
            ))
            
            return ValidationResult(
                success=False,
                issues=issues,
                warnings=warnings,
                recommendations=["Fix validation errors before proceeding"],
                diagnostic_data=diagnostic_data
            )

    async def validate_config_flow_class(self) -> ValidationResult:
        """Validate config flow class existence, inheritance, and structure."""
        _LOGGER.debug("Validating config flow class for domain: %s", self.domain)
        
        issues = []
        warnings = []
        recommendations = []
        diagnostic_data = {}
        
        try:
            # Check class existence
            class_result = await self._validate_class_existence()
            issues.extend(class_result.issues)
            warnings.extend(class_result.warnings)
            diagnostic_data.update(class_result.diagnostic_data)
            
            # Check inheritance
            inheritance_result = await self._validate_class_inheritance()
            issues.extend(inheritance_result.issues)
            warnings.extend(inheritance_result.warnings)
            diagnostic_data.update(inheritance_result.diagnostic_data)
            
            # Check method signatures
            signature_result = await self._validate_method_signatures()
            issues.extend(signature_result.issues)
            warnings.extend(signature_result.warnings)
            diagnostic_data.update(signature_result.diagnostic_data)
            
            success = not any(issue.severity == "error" for issue in issues)
            
            if success:
                recommendations.append("Config flow class validation passed")
            else:
                recommendations.append("Fix config flow class issues before proceeding")
            
            return ValidationResult(
                success=success,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                diagnostic_data=diagnostic_data
            )
            
        except Exception as e:
            _LOGGER.error("Error during config flow class validation: %s", e)
            issues.append(ValidationIssue(
                issue_type="validation_error",
                description=f"Config flow class validation failed: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e), "error_type": type(e).__name__}
            ))
            
            return ValidationResult(
                success=False,
                issues=issues,
                warnings=warnings,
                recommendations=["Fix validation errors before proceeding"],
                diagnostic_data=diagnostic_data
            )

    async def validate_config_flow_methods(self) -> ValidationResult:
        """Validate config flow method implementation and parameters."""
        _LOGGER.debug("Validating config flow methods for domain: %s", self.domain)
        
        issues = []
        warnings = []
        recommendations = []
        diagnostic_data = {}
        
        try:
            # Check required method presence
            method_presence_result = await self._validate_required_methods()
            issues.extend(method_presence_result.issues)
            warnings.extend(method_presence_result.warnings)
            diagnostic_data.update(method_presence_result.diagnostic_data)
            
            # Check method implementation
            implementation_result = await self._validate_method_implementation()
            issues.extend(implementation_result.issues)
            warnings.extend(implementation_result.warnings)
            diagnostic_data.update(implementation_result.diagnostic_data)
            
            # Check method parameters
            parameter_result = await self._validate_method_parameters()
            issues.extend(parameter_result.issues)
            warnings.extend(parameter_result.warnings)
            diagnostic_data.update(parameter_result.diagnostic_data)
            
            success = not any(issue.severity == "error" for issue in issues)
            
            if success:
                recommendations.append("Config flow method validation passed")
            else:
                recommendations.append("Fix config flow method issues before proceeding")
            
            return ValidationResult(
                success=success,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                diagnostic_data=diagnostic_data
            )
            
        except Exception as e:
            _LOGGER.error("Error during config flow method validation: %s", e)
            issues.append(ValidationIssue(
                issue_type="validation_error",
                description=f"Config flow method validation failed: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e), "error_type": type(e).__name__}
            ))
            
            return ValidationResult(
                success=False,
                issues=issues,
                warnings=warnings,
                recommendations=["Fix validation errors before proceeding"],
                diagnostic_data=diagnostic_data
            )

    async def validate_config_flow_registration_test(self) -> ValidationResult:
        """Test config flow registration simulation and verification."""
        _LOGGER.debug("Testing config flow registration for domain: %s", self.domain)
        
        issues = []
        warnings = []
        recommendations = []
        diagnostic_data = {}
        
        try:
            # Simulate registration
            registration_result = await self._simulate_config_flow_registration()
            issues.extend(registration_result.issues)
            warnings.extend(registration_result.warnings)
            diagnostic_data.update(registration_result.diagnostic_data)
            
            # Verify registration success
            verification_result = await self._verify_registration_success()
            issues.extend(verification_result.issues)
            warnings.extend(verification_result.warnings)
            diagnostic_data.update(verification_result.diagnostic_data)
            
            # Detect registration errors
            error_detection_result = await self._detect_registration_errors()
            issues.extend(error_detection_result.issues)
            warnings.extend(error_detection_result.warnings)
            diagnostic_data.update(error_detection_result.diagnostic_data)
            
            success = not any(issue.severity == "error" for issue in issues)
            
            if success:
                recommendations.append("Config flow registration test passed")
            else:
                recommendations.append("Fix config flow registration issues before proceeding")
            
            return ValidationResult(
                success=success,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                diagnostic_data=diagnostic_data
            )
            
        except Exception as e:
            _LOGGER.error("Error during config flow registration test: %s", e)
            issues.append(ValidationIssue(
                issue_type="validation_error",
                description=f"Config flow registration test failed: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e), "error_type": type(e).__name__}
            ))
            
            return ValidationResult(
                success=False,
                issues=issues,
                warnings=warnings,
                recommendations=["Fix validation errors before proceeding"],
                diagnostic_data=diagnostic_data
            )

    async def validate_manifest_configuration(self) -> ValidationResult:
        """Validate manifest.json configuration."""
        _LOGGER.debug("Validating manifest configuration for domain: %s", self.domain)
        
        issues = []
        warnings = []
        recommendations = []
        diagnostic_data = {}
        
        try:
            manifest_path = self._integration_path / "manifest.json"
            
            if not manifest_path.exists():
                issues.append(ValidationIssue(
                    issue_type="manifest_missing",
                    description="manifest.json file not found",
                    severity="error",
                    fix_available=True,
                    fix_description="Create manifest.json file with required fields",
                    diagnostic_info={"manifest_path": str(manifest_path)}
                ))
                return ValidationResult(
                    success=False,
                    issues=issues,
                    warnings=warnings,
                    recommendations=["Create manifest.json file"],
                    diagnostic_data=diagnostic_data
                )
            
            # Load and parse manifest
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            diagnostic_data["manifest_data"] = manifest_data
            
            # Check required fields
            required_fields = ["domain", "name", "version", "config_flow"]
            for field in required_fields:
                if field not in manifest_data:
                    issues.append(ValidationIssue(
                        issue_type="manifest_missing_field",
                        description=f"Required field '{field}' missing from manifest.json",
                        severity="error",
                        fix_available=True,
                        fix_description=f"Add '{field}' field to manifest.json",
                        diagnostic_info={"missing_field": field}
                    ))
            
            # Check config_flow setting
            if manifest_data.get("config_flow") is not True:
                issues.append(ValidationIssue(
                    issue_type="config_flow_disabled",
                    description="config_flow is not enabled in manifest.json",
                    severity="error",
                    fix_available=True,
                    fix_description="Set 'config_flow': true in manifest.json",
                    diagnostic_info={"config_flow_value": manifest_data.get("config_flow")}
                ))
            
            # Check domain consistency
            manifest_domain = manifest_data.get("domain")
            if manifest_domain != self.domain:
                issues.append(ValidationIssue(
                    issue_type="manifest_domain_mismatch",
                    description=f"Manifest domain '{manifest_domain}' doesn't match expected '{self.domain}'",
                    severity="error",
                    fix_available=True,
                    fix_description=f"Update domain in manifest.json to '{self.domain}'",
                    diagnostic_info={"manifest_domain": manifest_domain, "expected_domain": self.domain}
                ))
            
            # Check dependencies
            dependencies = manifest_data.get("dependencies", [])
            diagnostic_data["dependencies"] = dependencies
            
            # Validate that dependencies are available
            for dep in dependencies:
                if not await self._check_dependency_available(dep):
                    warnings.append(f"Dependency '{dep}' may not be available")
            
            success = not any(issue.severity == "error" for issue in issues)
            
            if success:
                recommendations.append("Manifest configuration validation passed")
            else:
                recommendations.append("Fix manifest configuration issues")
            
            return ValidationResult(
                success=success,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                diagnostic_data=diagnostic_data
            )
            
        except json.JSONDecodeError as e:
            issues.append(ValidationIssue(
                issue_type="manifest_json_error",
                description=f"Invalid JSON in manifest.json: {str(e)}",
                severity="error",
                fix_available=True,
                fix_description="Fix JSON syntax errors in manifest.json",
                diagnostic_info={"json_error": str(e)}
            ))
        except Exception as e:
            _LOGGER.error("Error during manifest validation: %s", e)
            issues.append(ValidationIssue(
                issue_type="validation_error",
                description=f"Manifest validation failed: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e), "error_type": type(e).__name__}
            ))
        
        return ValidationResult(
            success=False,
            issues=issues,
            warnings=warnings,
            recommendations=["Fix manifest validation errors"],
            diagnostic_data=diagnostic_data
        )

    def get_validation_report(self) -> Dict[str, Any]:
        """Get a comprehensive validation report."""
        return {
            "domain": self.domain,
            "integration_path": str(self._integration_path),
            "validation_cache": {k: {
                "success": v.success,
                "issue_count": len(v.issues),
                "warning_count": len(v.warnings),
                "error_count": len([i for i in v.issues if i.severity == "error"])
            } for k, v in self._validation_cache.items()},
            "timestamp": self.hass.loop.time()
        }

    async def _check_config_flow_class(self) -> ValidationResult:
        """Check if config flow class is properly defined."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            # Try to import the config flow module
            config_flow_path = self._integration_path / "config_flow.py"
            
            if not config_flow_path.exists():
                issues.append(ValidationIssue(
                    issue_type="config_flow_file_missing",
                    description="config_flow.py file not found",
                    severity="error",
                    fix_available=True,
                    fix_description="Create config_flow.py file with ConfigFlow class",
                    diagnostic_info={"config_flow_path": str(config_flow_path)}
                ))
                return ValidationResult(False, issues, warnings, [], diagnostic_data)
            
            # Check if we can find a config flow class in the file
            with open(config_flow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            diagnostic_data["config_flow_file_exists"] = True
            diagnostic_data["config_flow_content_length"] = len(content)
            
            # Look for config flow class definition
            if "class" not in content or "ConfigFlow" not in content:
                issues.append(ValidationIssue(
                    issue_type="config_flow_class_missing",
                    description="No ConfigFlow class found in config_flow.py",
                    severity="error",
                    fix_available=True,
                    fix_description="Define a ConfigFlow class that inherits from config_entries.ConfigFlow",
                    diagnostic_info={"has_class": "class" in content, "has_config_flow": "ConfigFlow" in content}
                ))
            
            # Check for domain specification
            if f"domain={self.domain}" not in content and f'domain="{self.domain}"' not in content:
                issues.append(ValidationIssue(
                    issue_type="config_flow_domain_missing",
                    description=f"ConfigFlow class doesn't specify domain '{self.domain}'",
                    severity="error",
                    fix_available=True,
                    fix_description=f"Add 'domain={self.domain}' to ConfigFlow class",
                    diagnostic_info={"domain": self.domain}
                ))
            
            diagnostic_data["config_flow_class_found"] = "ConfigFlow" in content
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="config_flow_check_error",
                description=f"Error checking config flow class: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _check_config_flow_registration(self) -> ValidationResult:
        """Check if config flow is registered with Home Assistant."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            # Check if the domain is in the config flow registry
            if hasattr(self.hass.config_entries, 'flow') and hasattr(self.hass.config_entries.flow, '_flows'):
                registered_flows = getattr(self.hass.config_entries.flow, '_flows', {})
                diagnostic_data["registered_flows"] = list(registered_flows.keys())
                
                if self.domain not in registered_flows:
                    warnings.append(f"Config flow for domain '{self.domain}' not found in registry")
                    diagnostic_data["domain_registered"] = False
                else:
                    diagnostic_data["domain_registered"] = True
            else:
                warnings.append("Cannot access config flow registry")
                diagnostic_data["registry_accessible"] = False
            
            # Check if we can create an instance of the config flow
            try:
                from . import config_flow
                if hasattr(config_flow, 'RoostSchedulerConfigFlow'):
                    flow_class = getattr(config_flow, 'RoostSchedulerConfigFlow')
                    diagnostic_data["config_flow_class_importable"] = True
                    
                    # Check if it's a proper ConfigFlow subclass
                    if issubclass(flow_class, ConfigFlow):
                        diagnostic_data["config_flow_inheritance_correct"] = True
                    else:
                        issues.append(ValidationIssue(
                            issue_type="config_flow_inheritance_error",
                            description="ConfigFlow class doesn't inherit from config_entries.ConfigFlow",
                            severity="error",
                            fix_available=True,
                            fix_description="Make ConfigFlow class inherit from config_entries.ConfigFlow",
                            diagnostic_info={"class_name": flow_class.__name__}
                        ))
                else:
                    issues.append(ValidationIssue(
                        issue_type="config_flow_class_not_found",
                        description="ConfigFlow class not found in config_flow module",
                        severity="error",
                        fix_available=True,
                        fix_description="Define a ConfigFlow class in config_flow.py",
                        diagnostic_info={"module_attributes": dir(config_flow)}
                    ))
            except ImportError as e:
                issues.append(ValidationIssue(
                    issue_type="config_flow_import_error",
                    description=f"Cannot import config_flow module: {str(e)}",
                    severity="error",
                    fix_available=True,
                    fix_description="Fix import errors in config_flow.py",
                    diagnostic_info={"import_error": str(e)}
                ))
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="registration_check_error",
                description=f"Error checking config flow registration: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _check_config_flow_methods(self) -> ValidationResult:
        """Check if required config flow methods are implemented."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            config_flow_path = self._integration_path / "config_flow.py"
            
            if config_flow_path.exists():
                with open(config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for required methods
                required_methods = ["async_step_user"]
                optional_methods = ["async_step_import", "async_step_discovery"]
                
                for method in required_methods:
                    if method not in content:
                        issues.append(ValidationIssue(
                            issue_type="config_flow_method_missing",
                            description=f"Required method '{method}' not found in ConfigFlow class",
                            severity="error",
                            fix_available=True,
                            fix_description=f"Implement '{method}' method in ConfigFlow class",
                            diagnostic_info={"missing_method": method}
                        ))
                    else:
                        diagnostic_data[f"{method}_found"] = True
                
                for method in optional_methods:
                    diagnostic_data[f"{method}_found"] = method in content
                
                # Check for proper async method definitions
                if "async def" not in content:
                    warnings.append("No async methods found in config flow")
                
                diagnostic_data["method_check_completed"] = True
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="method_check_error",
                description=f"Error checking config flow methods: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _get_manifest_domain(self) -> Optional[str]:
        """Get domain from manifest.json."""
        try:
            manifest_path = self._integration_path / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                return manifest_data.get("domain")
        except Exception as e:
            _LOGGER.debug("Error reading manifest domain: %s", e)
        return None

    async def _get_const_domain(self) -> Optional[str]:
        """Get domain from const.py."""
        try:
            const_path = self._integration_path / "const.py"
            if const_path.exists():
                with open(const_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Look for DOMAIN = "..." pattern
                import re
                match = re.search(r'DOMAIN\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        except Exception as e:
            _LOGGER.debug("Error reading const domain: %s", e)
        return None

    async def _get_config_flow_domain(self) -> Optional[str]:
        """Get domain from config_flow.py."""
        try:
            config_flow_path = self._integration_path / "config_flow.py"
            if config_flow_path.exists():
                with open(config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Look for domain=... pattern in class definition
                import re
                match = re.search(r'domain\s*=\s*["\']?([^"\')\s,]+)["\']?', content)
                if match:
                    return match.group(1)
        except Exception as e:
            _LOGGER.debug("Error reading config flow domain: %s", e)
        return None

    async def _check_dependency_available(self, dependency: str) -> bool:
        """Check if a dependency is available in Home Assistant."""
        try:
            # Check if it's a built-in Home Assistant component
            if hasattr(self.hass.components, dependency):
                return True
            
            # Try to import it
            try:
                __import__(f"homeassistant.components.{dependency}")
                return True
            except ImportError:
                pass
            
            return False
        except Exception:
            return False

    async def _validate_class_existence(self) -> ValidationResult:
        """Validate that the config flow class exists and is properly defined."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            config_flow_path = self._integration_path / "config_flow.py"
            
            if not config_flow_path.exists():
                issues.append(ValidationIssue(
                    issue_type="config_flow_file_missing",
                    description="config_flow.py file not found",
                    severity="error",
                    fix_available=True,
                    fix_description="Create config_flow.py file with ConfigFlow class",
                    diagnostic_info={"config_flow_path": str(config_flow_path)}
                ))
                return ValidationResult(False, issues, warnings, [], diagnostic_data)
            
            # Read and analyze the file content
            with open(config_flow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            diagnostic_data["config_flow_file_exists"] = True
            diagnostic_data["config_flow_content_length"] = len(content)
            
            # Check for class definition
            import re
            class_pattern = r'class\s+(\w+)\s*\([^)]*ConfigFlow[^)]*\)'
            class_matches = re.findall(class_pattern, content)
            
            if not class_matches:
                issues.append(ValidationIssue(
                    issue_type="config_flow_class_missing",
                    description="No ConfigFlow class found in config_flow.py",
                    severity="error",
                    fix_available=True,
                    fix_description="Define a ConfigFlow class that inherits from config_entries.ConfigFlow",
                    diagnostic_info={"class_pattern": class_pattern}
                ))
            else:
                diagnostic_data["config_flow_classes_found"] = class_matches
                
                # Check for domain specification in class
                domain_pattern = rf'domain\s*=\s*["\']?{re.escape(self.domain)}["\']?'
                if not re.search(domain_pattern, content):
                    issues.append(ValidationIssue(
                        issue_type="config_flow_domain_missing",
                        description=f"ConfigFlow class doesn't specify domain '{self.domain}'",
                        severity="error",
                        fix_available=True,
                        fix_description=f"Add 'domain={self.domain}' to ConfigFlow class",
                        diagnostic_info={"domain": self.domain, "domain_pattern": domain_pattern}
                    ))
                else:
                    diagnostic_data["domain_specified"] = True
            
            # Check for VERSION attribute
            if "VERSION" not in content:
                warnings.append("VERSION attribute not found in ConfigFlow class")
                diagnostic_data["version_attribute_found"] = False
            else:
                diagnostic_data["version_attribute_found"] = True
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="class_existence_check_error",
                description=f"Error checking config flow class existence: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _validate_class_inheritance(self) -> ValidationResult:
        """Validate that the config flow class properly inherits from ConfigFlow."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            # Try to import the config flow class
            try:
                from . import config_flow
                diagnostic_data["config_flow_module_importable"] = True
                
                # Find the config flow class
                config_flow_class = None
                for attr_name in dir(config_flow):
                    attr = getattr(config_flow, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, '__bases__') and 
                        any('ConfigFlow' in str(base) for base in attr.__bases__)):
                        config_flow_class = attr
                        break
                
                if config_flow_class is None:
                    issues.append(ValidationIssue(
                        issue_type="config_flow_class_not_found",
                        description="ConfigFlow class not found in config_flow module",
                        severity="error",
                        fix_available=True,
                        fix_description="Define a ConfigFlow class that inherits from config_entries.ConfigFlow",
                        diagnostic_info={"module_attributes": [attr for attr in dir(config_flow) if not attr.startswith('_')]}
                    ))
                else:
                    diagnostic_data["config_flow_class_name"] = config_flow_class.__name__
                    
                    # Check inheritance
                    if not issubclass(config_flow_class, ConfigFlow):
                        issues.append(ValidationIssue(
                            issue_type="config_flow_inheritance_error",
                            description="ConfigFlow class doesn't inherit from config_entries.ConfigFlow",
                            severity="error",
                            fix_available=True,
                            fix_description="Make ConfigFlow class inherit from config_entries.ConfigFlow",
                            diagnostic_info={"class_bases": [str(base) for base in config_flow_class.__bases__]}
                        ))
                    else:
                        diagnostic_data["inheritance_correct"] = True
                    
                    # Check domain attribute
                    if hasattr(config_flow_class, 'domain'):
                        class_domain = getattr(config_flow_class, 'domain')
                        if class_domain != self.domain:
                            issues.append(ValidationIssue(
                                issue_type="config_flow_domain_mismatch",
                                description=f"ConfigFlow class domain '{class_domain}' doesn't match expected '{self.domain}'",
                                severity="error",
                                fix_available=True,
                                fix_description=f"Set domain attribute to '{self.domain}' in ConfigFlow class",
                                diagnostic_info={"class_domain": class_domain, "expected_domain": self.domain}
                            ))
                        else:
                            diagnostic_data["domain_matches"] = True
                    else:
                        issues.append(ValidationIssue(
                            issue_type="config_flow_domain_attribute_missing",
                            description="ConfigFlow class doesn't have domain attribute",
                            severity="error",
                            fix_available=True,
                            fix_description=f"Add 'domain = \"{self.domain}\"' to ConfigFlow class",
                            diagnostic_info={"expected_domain": self.domain}
                        ))
                
            except ImportError as e:
                issues.append(ValidationIssue(
                    issue_type="config_flow_import_error",
                    description=f"Cannot import config_flow module: {str(e)}",
                    severity="error",
                    fix_available=True,
                    fix_description="Fix import errors in config_flow.py",
                    diagnostic_info={"import_error": str(e)}
                ))
                diagnostic_data["config_flow_module_importable"] = False
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="inheritance_check_error",
                description=f"Error checking config flow class inheritance: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _validate_method_signatures(self) -> ValidationResult:
        """Validate that config flow methods have correct signatures."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            config_flow_path = self._integration_path / "config_flow.py"
            
            if config_flow_path.exists():
                with open(config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Define expected method signatures
                expected_signatures = {
                    "async_step_user": {
                        "pattern": r'async\s+def\s+async_step_user\s*\(\s*self\s*,\s*user_input[^)]*\)',
                        "description": "async_step_user(self, user_input=None)"
                    },
                    "__init__": {
                        "pattern": r'def\s+__init__\s*\(\s*self\s*\)',
                        "description": "__init__(self)"
                    }
                }
                
                import re
                for method_name, signature_info in expected_signatures.items():
                    pattern = signature_info["pattern"]
                    expected_desc = signature_info["description"]
                    
                    if not re.search(pattern, content):
                        if method_name == "async_step_user":
                            issues.append(ValidationIssue(
                                issue_type="method_signature_invalid",
                                description=f"Method '{method_name}' signature doesn't match expected pattern: {expected_desc}",
                                severity="error",
                                fix_available=True,
                                fix_description=f"Update {method_name} method signature to match: {expected_desc}",
                                diagnostic_info={"method": method_name, "expected": expected_desc, "pattern": pattern}
                            ))
                        else:
                            warnings.append(f"Method '{method_name}' signature may not match expected pattern: {expected_desc}")
                    else:
                        diagnostic_data[f"{method_name}_signature_valid"] = True
                
                # Check for proper return type annotations
                if "-> FlowResult" not in content and "FlowResult" in content:
                    warnings.append("Consider adding return type annotations (-> FlowResult) to async step methods")
                    diagnostic_data["return_type_annotations"] = False
                else:
                    diagnostic_data["return_type_annotations"] = True
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="signature_validation_error",
                description=f"Error validating method signatures: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _validate_required_methods(self) -> ValidationResult:
        """Validate that all required config flow methods are present."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            config_flow_path = self._integration_path / "config_flow.py"
            
            if config_flow_path.exists():
                with open(config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Define required and optional methods
                required_methods = ["async_step_user"]
                optional_methods = ["async_step_import", "async_step_discovery", "__init__"]
                
                for method in required_methods:
                    if f"def {method}" not in content:
                        issues.append(ValidationIssue(
                            issue_type="required_method_missing",
                            description=f"Required method '{method}' not found in ConfigFlow class",
                            severity="error",
                            fix_available=True,
                            fix_description=f"Implement '{method}' method in ConfigFlow class",
                            diagnostic_info={"missing_method": method}
                        ))
                    else:
                        diagnostic_data[f"{method}_found"] = True
                
                for method in optional_methods:
                    diagnostic_data[f"{method}_found"] = f"def {method}" in content
                
                # Check for async methods that should be async
                async_methods = ["async_step_user", "async_step_import", "async_step_discovery"]
                for method in async_methods:
                    if f"def {method}" in content and f"async def {method}" not in content:
                        issues.append(ValidationIssue(
                            issue_type="method_not_async",
                            description=f"Method '{method}' should be async",
                            severity="error",
                            fix_available=True,
                            fix_description=f"Make '{method}' method async",
                            diagnostic_info={"method": method}
                        ))
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="required_methods_check_error",
                description=f"Error checking required methods: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _validate_method_implementation(self) -> ValidationResult:
        """Validate that config flow methods are properly implemented."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            config_flow_path = self._integration_path / "config_flow.py"
            
            if config_flow_path.exists():
                with open(config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check async_step_user implementation
                if "async_step_user" in content:
                    # Check for basic implementation patterns
                    if "user_input is not None" not in content:
                        warnings.append("async_step_user method may not handle user_input properly")
                        diagnostic_data["user_input_handling"] = False
                    else:
                        diagnostic_data["user_input_handling"] = True
                    
                    if "async_show_form" not in content and "async_create_entry" not in content:
                        issues.append(ValidationIssue(
                            issue_type="method_implementation_incomplete",
                            description="async_step_user method doesn't show form or create entry",
                            severity="error",
                            fix_available=True,
                            fix_description="Implement proper form handling or entry creation in async_step_user",
                            diagnostic_info={"method": "async_step_user"}
                        ))
                    else:
                        diagnostic_data["form_or_entry_handling"] = True
                    
                    # Check for error handling
                    if "errors" not in content:
                        warnings.append("async_step_user method may not handle errors properly")
                        diagnostic_data["error_handling"] = False
                    else:
                        diagnostic_data["error_handling"] = True
                
                # Check for proper imports
                required_imports = ["config_entries", "FlowResult"]
                for import_item in required_imports:
                    if import_item not in content:
                        if import_item == "FlowResult":
                            warnings.append(f"Missing import: {import_item} (recommended for type hints)")
                        else:
                            issues.append(ValidationIssue(
                                issue_type="missing_import",
                                description=f"Missing required import: {import_item}",
                                severity="error",
                                fix_available=True,
                                fix_description=f"Add import for {import_item}",
                                diagnostic_info={"missing_import": import_item}
                            ))
                    else:
                        diagnostic_data[f"{import_item}_imported"] = True
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="implementation_validation_error",
                description=f"Error validating method implementation: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _validate_method_parameters(self) -> ValidationResult:
        """Validate that config flow method parameters are correct."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            config_flow_path = self._integration_path / "config_flow.py"
            
            if config_flow_path.exists():
                with open(config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                import re
                
                # Check async_step_user parameters
                user_step_pattern = r'async\s+def\s+async_step_user\s*\(\s*self\s*,\s*([^)]+)\)'
                user_step_match = re.search(user_step_pattern, content)
                
                if user_step_match:
                    params = user_step_match.group(1).strip()
                    diagnostic_data["async_step_user_params"] = params
                    
                    # Check for proper parameter typing
                    if "user_input" not in params:
                        issues.append(ValidationIssue(
                            issue_type="method_parameter_missing",
                            description="async_step_user method missing user_input parameter",
                            severity="error",
                            fix_available=True,
                            fix_description="Add user_input parameter to async_step_user method",
                            diagnostic_info={"method": "async_step_user", "current_params": params}
                        ))
                    
                    # Check for type hints
                    if "Optional[Dict[str, Any]]" not in params and "dict" not in params.lower():
                        warnings.append("Consider adding type hints to async_step_user parameters")
                        diagnostic_data["user_step_type_hints"] = False
                    else:
                        diagnostic_data["user_step_type_hints"] = True
                    
                    # Check for default value
                    if "= None" not in params:
                        warnings.append("user_input parameter should have default value of None")
                        diagnostic_data["user_input_default_none"] = False
                    else:
                        diagnostic_data["user_input_default_none"] = True
                
                # Check __init__ parameters
                init_pattern = r'def\s+__init__\s*\(\s*self\s*([^)]*)\)'
                init_match = re.search(init_pattern, content)
                
                if init_match:
                    init_params = init_match.group(1).strip()
                    diagnostic_data["init_params"] = init_params
                    
                    if init_params and init_params != "":
                        warnings.append("__init__ method should typically only take self parameter")
                        diagnostic_data["init_extra_params"] = True
                    else:
                        diagnostic_data["init_extra_params"] = False
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="parameter_validation_error",
                description=f"Error validating method parameters: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _simulate_config_flow_registration(self) -> ValidationResult:
        """Simulate config flow registration to test for issues."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            # Try to import and instantiate the config flow class
            try:
                from . import config_flow
                diagnostic_data["config_flow_module_imported"] = True
                
                # Find the config flow class
                config_flow_class = None
                for attr_name in dir(config_flow):
                    attr = getattr(config_flow, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, '__bases__') and 
                        any('ConfigFlow' in str(base) for base in attr.__bases__)):
                        config_flow_class = attr
                        break
                
                if config_flow_class:
                    diagnostic_data["config_flow_class_found"] = True
                    diagnostic_data["config_flow_class_name"] = config_flow_class.__name__
                    
                    # Try to instantiate the class
                    try:
                        flow_instance = config_flow_class()
                        diagnostic_data["config_flow_instantiation"] = True
                        
                        # Check domain attribute
                        if hasattr(flow_instance, 'domain'):
                            instance_domain = getattr(flow_instance, 'domain')
                            diagnostic_data["instance_domain"] = instance_domain
                            
                            if instance_domain != self.domain:
                                issues.append(ValidationIssue(
                                    issue_type="registration_domain_mismatch",
                                    description=f"Config flow instance domain '{instance_domain}' doesn't match expected '{self.domain}'",
                                    severity="error",
                                    fix_available=True,
                                    fix_description=f"Set domain to '{self.domain}' in config flow class",
                                    diagnostic_info={"instance_domain": instance_domain, "expected_domain": self.domain}
                                ))
                        else:
                            issues.append(ValidationIssue(
                                issue_type="registration_domain_missing",
                                description="Config flow instance doesn't have domain attribute",
                                severity="error",
                                fix_available=True,
                                fix_description=f"Add domain = '{self.domain}' to config flow class",
                                diagnostic_info={"expected_domain": self.domain}
                            ))
                        
                        # Check VERSION attribute
                        if hasattr(flow_instance, 'VERSION'):
                            diagnostic_data["version_attribute"] = getattr(flow_instance, 'VERSION')
                        else:
                            warnings.append("Config flow class should have VERSION attribute")
                            diagnostic_data["version_attribute"] = None
                        
                    except Exception as e:
                        issues.append(ValidationIssue(
                            issue_type="config_flow_instantiation_error",
                            description=f"Cannot instantiate config flow class: {str(e)}",
                            severity="error",
                            fix_available=True,
                            fix_description="Fix errors preventing config flow class instantiation",
                            diagnostic_info={"instantiation_error": str(e)}
                        ))
                        diagnostic_data["config_flow_instantiation"] = False
                else:
                    issues.append(ValidationIssue(
                        issue_type="config_flow_class_not_found",
                        description="No config flow class found in module",
                        severity="error",
                        fix_available=True,
                        fix_description="Define a config flow class that inherits from ConfigFlow",
                        diagnostic_info={"module_attributes": [attr for attr in dir(config_flow) if not attr.startswith('_')]}
                    ))
                    diagnostic_data["config_flow_class_found"] = False
                
            except ImportError as e:
                issues.append(ValidationIssue(
                    issue_type="config_flow_import_error",
                    description=f"Cannot import config flow module: {str(e)}",
                    severity="error",
                    fix_available=True,
                    fix_description="Fix import errors in config_flow.py",
                    diagnostic_info={"import_error": str(e)}
                ))
                diagnostic_data["config_flow_module_imported"] = False
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="registration_simulation_error",
                description=f"Error simulating config flow registration: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _verify_registration_success(self) -> ValidationResult:
        """Verify that config flow registration would succeed."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            # Check if the domain is already registered
            if hasattr(self.hass.config_entries, 'flow') and hasattr(self.hass.config_entries.flow, '_flows'):
                registered_flows = getattr(self.hass.config_entries.flow, '_flows', {})
                diagnostic_data["currently_registered_flows"] = list(registered_flows.keys())
                
                if self.domain in registered_flows:
                    diagnostic_data["domain_already_registered"] = True
                    warnings.append(f"Domain '{self.domain}' is already registered in config flow registry")
                else:
                    diagnostic_data["domain_already_registered"] = False
            else:
                warnings.append("Cannot access config flow registry for verification")
                diagnostic_data["registry_accessible"] = False
            
            # Check manifest configuration for config flow
            manifest_path = self._integration_path / "manifest.json"
            if manifest_path.exists():
                import json
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                
                config_flow_enabled = manifest_data.get("config_flow", False)
                diagnostic_data["manifest_config_flow_enabled"] = config_flow_enabled
                
                if not config_flow_enabled:
                    issues.append(ValidationIssue(
                        issue_type="config_flow_not_enabled",
                        description="config_flow is not enabled in manifest.json",
                        severity="error",
                        fix_available=True,
                        fix_description="Set 'config_flow': true in manifest.json",
                        diagnostic_info={"current_value": config_flow_enabled}
                    ))
            else:
                issues.append(ValidationIssue(
                    issue_type="manifest_missing",
                    description="manifest.json file not found",
                    severity="error",
                    fix_available=True,
                    fix_description="Create manifest.json with config_flow: true",
                    diagnostic_info={"manifest_path": str(manifest_path)}
                ))
            
            # Verify that all required components are available
            required_components = ["config_entries", "data_entry_flow"]
            for component in required_components:
                try:
                    __import__(f"homeassistant.{component}")
                    diagnostic_data[f"{component}_available"] = True
                except ImportError:
                    issues.append(ValidationIssue(
                        issue_type="required_component_missing",
                        description=f"Required Home Assistant component '{component}' not available",
                        severity="error",
                        fix_available=False,
                        fix_description="Ensure Home Assistant installation is complete",
                        diagnostic_info={"missing_component": component}
                    ))
                    diagnostic_data[f"{component}_available"] = False
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="registration_verification_error",
                description=f"Error verifying registration success: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)

    async def _detect_registration_errors(self) -> ValidationResult:
        """Detect common config flow registration errors."""
        issues = []
        warnings = []
        diagnostic_data = {}
        
        try:
            # Check for common error patterns in logs (if available)
            common_errors = [
                {
                    "pattern": "Invalid handler specified",
                    "description": "Config flow handler not properly registered",
                    "fix": "Ensure config flow class has correct domain and inheritance"
                },
                {
                    "pattern": "No such config flow",
                    "description": "Config flow not found in registry",
                    "fix": "Check config flow registration and domain consistency"
                },
                {
                    "pattern": "Config flow could not be loaded",
                    "description": "Config flow module or class loading failed",
                    "fix": "Check for import errors and class definition issues"
                }
            ]
            
            diagnostic_data["common_error_patterns"] = [error["pattern"] for error in common_errors]
            
            # Check for potential circular import issues
            config_flow_path = self._integration_path / "config_flow.py"
            if config_flow_path.exists():
                with open(config_flow_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Look for imports that might cause circular dependencies
                if f"from .{self.domain}" in content or f"from . import {self.domain}" in content:
                    warnings.append("Potential circular import detected in config_flow.py")
                    diagnostic_data["potential_circular_import"] = True
                else:
                    diagnostic_data["potential_circular_import"] = False
                
                # Check for relative imports that might fail
                import re
                relative_imports = re.findall(r'from\s+\.\s*(\w+)', content)
                diagnostic_data["relative_imports"] = relative_imports
                
                for import_name in relative_imports:
                    import_path = self._integration_path / f"{import_name}.py"
                    if not import_path.exists():
                        issues.append(ValidationIssue(
                            issue_type="missing_import_file",
                            description=f"Relative import '{import_name}' file not found",
                            severity="error",
                            fix_available=True,
                            fix_description=f"Create {import_name}.py file or fix import statement",
                            diagnostic_info={"missing_file": str(import_path), "import_name": import_name}
                        ))
            
            # Check for domain conflicts with built-in components
            try:
                __import__(f"homeassistant.components.{self.domain}")
                warnings.append(f"Domain '{self.domain}' conflicts with built-in Home Assistant component")
                diagnostic_data["domain_conflict"] = True
            except ImportError:
                diagnostic_data["domain_conflict"] = False
            
        except Exception as e:
            issues.append(ValidationIssue(
                issue_type="error_detection_failure",
                description=f"Error detecting registration errors: {str(e)}",
                severity="error",
                fix_available=False,
                fix_description="Check logs for detailed error information",
                diagnostic_info={"error": str(e)}
            ))
        
        success = not any(issue.severity == "error" for issue in issues)
        return ValidationResult(success, issues, warnings, [], diagnostic_data)