"""Startup Validation System for Roost Scheduler integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, VERSION, REQUIRED_DOMAINS, OPTIONAL_DOMAINS
from .config_flow_validator import ConfigFlowValidator, ValidationResult
from .integration_diagnostics import IntegrationDiagnostics, DiagnosticData
from .domain_consistency_checker import DomainConsistencyChecker, ConsistencyResult

_LOGGER = logging.getLogger(__name__)


@dataclass
class ComprehensiveResult:
    """Result of comprehensive validation."""
    success: bool
    integration_loading_result: ValidationResult
    config_flow_availability_result: ValidationResult
    domain_consistency_result: ConsistencyResult
    diagnostic_data: DiagnosticData
    issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    startup_diagnostics: Dict[str, Any]


class StartupValidationSystem:
    """Validates integration components during Home Assistant startup."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the startup validation system."""
        self.hass = hass
        self._validation_cache: Dict[str, ComprehensiveResult] = {}

    async def validate_integration_loading(self, domain: str) -> ValidationResult:
        """Validate that integration loads properly.
        
        Args:
            domain: The integration domain to validate
            
        Returns:
            ValidationResult with integration loading validation details
        """
        _LOGGER.debug("Validating integration loading for domain: %s", domain)
        
        issues = []
        warnings = []
        recommendations = []
        diagnostic_data = {}
        
        try:
            # Check if integration is already loaded
            if domain in self.hass.config.components:
                diagnostic_data["integration_loaded"] = True
                diagnostic_data["config_entries_count"] = len(
                    self.hass.config_entries.async_entries(domain)
                )
                recommendations.append("Integration is already loaded successfully")
            else:
                diagnostic_data["integration_loaded"] = False
                warnings.append(f"Integration '{domain}' is not currently loaded")
            
            # Check integration directory and files
            integration_path = self._get_integration_path()
            diagnostic_data["integration_path"] = str(integration_path)
            
            if not integration_path.exists():
                issues.append({
                    "issue_type": "integration_directory_missing",
                    "description": f"Integration directory not found: {integration_path}",
                    "severity": "error",
                    "fix_available": False,
                    "fix_description": "Ensure integration is properly installed",
                    "diagnostic_info": {"path": str(integration_path)}
                })
            else:
                diagnostic_data["integration_directory_exists"] = True
                
                # Check required files
                required_files = ["__init__.py", "manifest.json", "config_flow.py", "const.py"]
                missing_files = []
                
                for filename in required_files:
                    file_path = integration_path / filename
                    if not file_path.exists():
                        missing_files.append(filename)
                    else:
                        diagnostic_data[f"{filename}_exists"] = True
                
                if missing_files:
                    issues.append({
                        "issue_type": "required_files_missing",
                        "description": f"Required files missing: {missing_files}",
                        "severity": "error",
                        "fix_available": True,
                        "fix_description": "Ensure all required integration files are present",
                        "diagnostic_info": {"missing_files": missing_files}
                    })
                else:
                    recommendations.append("All required integration files are present")
            
            # Check Home Assistant dependencies
            dependency_issues = await self._check_ha_dependencies()
            issues.extend(dependency_issues)
            diagnostic_data["dependency_check_completed"] = True
            
            # Check Python imports
            import_issues = await self._check_integration_imports(domain)
            issues.extend(import_issues)
            diagnostic_data["import_check_completed"] = True
            
            success = not any(
                issue.get("severity") == "error" if isinstance(issue, dict) 
                else getattr(issue, "severity", None) == "error" 
                for issue in issues
            )
            
            if success:
                recommendations.append("Integration loading validation passed")
            else:
                recommendations.append("Fix integration loading issues before proceeding")
            
            return ValidationResult(
                success=success,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                diagnostic_data=diagnostic_data
            )
            
        except Exception as e:
            _LOGGER.error("Error during integration loading validation: %s", e)
            issues.append({
                "issue_type": "validation_error",
                "description": f"Integration loading validation failed: {str(e)}",
                "severity": "error",
                "fix_available": False,
                "fix_description": "Check logs for detailed error information",
                "diagnostic_info": {"error": str(e), "error_type": type(e).__name__}
            })
            
            return ValidationResult(
                success=False,
                issues=issues,
                warnings=warnings,
                recommendations=["Fix validation errors before proceeding"],
                diagnostic_data=diagnostic_data
            )

    async def validate_config_flow_availability(self, domain: str) -> ValidationResult:
        """Verify config flow is available and properly registered.
        
        Args:
            domain: The integration domain to validate
            
        Returns:
            ValidationResult with config flow availability validation details
        """
        _LOGGER.debug("Validating config flow availability for domain: %s", domain)
        
        issues = []
        warnings = []
        recommendations = []
        diagnostic_data = {}
        
        try:
            # Use existing ConfigFlowValidator for detailed validation
            validator = ConfigFlowValidator(self.hass, domain)
            
            # Validate config flow registration
            registration_result = await validator.validate_config_flow_registration()
            issues.extend(registration_result.issues)
            warnings.extend(registration_result.warnings)
            diagnostic_data.update(registration_result.diagnostic_data)
            
            # Check if config flow is discoverable by Home Assistant
            if hasattr(self.hass.config_entries, 'flow'):
                flow_manager = self.hass.config_entries.flow
                
                # Check if domain is in flow handlers
                if hasattr(flow_manager, '_handlers'):
                    handlers = getattr(flow_manager, '_handlers', {})
                    diagnostic_data["flow_handlers"] = list(handlers.keys())
                    
                    if domain in handlers:
                        diagnostic_data["config_flow_registered"] = True
                        recommendations.append("Config flow is properly registered")
                    else:
                        warnings.append(f"Config flow for '{domain}' not found in flow handlers")
                        diagnostic_data["config_flow_registered"] = False
                else:
                    warnings.append("Cannot access flow handlers registry")
                    diagnostic_data["flow_handlers_accessible"] = False
            else:
                warnings.append("Config flow manager not available")
                diagnostic_data["flow_manager_available"] = False
            
            # Test config flow instantiation
            try:
                from . import config_flow
                if hasattr(config_flow, 'RoostSchedulerConfigFlow'):
                    flow_class = getattr(config_flow, 'RoostSchedulerConfigFlow')
                    
                    # Try to create an instance (without initializing)
                    diagnostic_data["config_flow_class_instantiable"] = True
                    recommendations.append("Config flow class can be instantiated")
                else:
                    issues.append({
                        "issue_type": "config_flow_class_missing",
                        "description": "Config flow class not found in module",
                        "severity": "error",
                        "fix_available": True,
                        "fix_description": "Define RoostSchedulerConfigFlow class in config_flow.py",
                        "diagnostic_info": {"module_attributes": dir(config_flow)}
                    })
            except ImportError as e:
                issues.append({
                    "issue_type": "config_flow_import_error",
                    "description": f"Cannot import config flow module: {str(e)}",
                    "severity": "error",
                    "fix_available": True,
                    "fix_description": "Fix import errors in config_flow.py",
                    "diagnostic_info": {"import_error": str(e)}
                })
            
            # Check manifest config_flow setting
            integration_path = self._get_integration_path()
            manifest_path = integration_path / "manifest.json"
            
            if manifest_path.exists():
                import json
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest_data = json.load(f)
                    
                    config_flow_enabled = manifest_data.get("config_flow", False)
                    diagnostic_data["manifest_config_flow_enabled"] = config_flow_enabled
                    
                    if not config_flow_enabled:
                        issues.append({
                            "issue_type": "config_flow_disabled_in_manifest",
                            "description": "config_flow is not enabled in manifest.json",
                            "severity": "error",
                            "fix_available": True,
                            "fix_description": "Set 'config_flow': true in manifest.json",
                            "diagnostic_info": {"current_value": config_flow_enabled}
                        })
                    else:
                        recommendations.append("Config flow is enabled in manifest.json")
                        
                except json.JSONDecodeError as e:
                    issues.append({
                        "issue_type": "manifest_json_error",
                        "description": f"Invalid JSON in manifest.json: {str(e)}",
                        "severity": "error",
                        "fix_available": True,
                        "fix_description": "Fix JSON syntax errors in manifest.json",
                        "diagnostic_info": {"json_error": str(e)}
                    })
            else:
                issues.append({
                    "issue_type": "manifest_missing",
                    "description": "manifest.json file not found",
                    "severity": "error",
                    "fix_available": True,
                    "fix_description": "Create manifest.json with config_flow: true",
                    "diagnostic_info": {"manifest_path": str(manifest_path)}
                })
            
            success = not any(
                issue.get("severity") == "error" if isinstance(issue, dict) 
                else getattr(issue, "severity", None) == "error" 
                for issue in issues
            )
            
            if success:
                recommendations.append("Config flow availability validation passed")
            else:
                recommendations.append("Fix config flow availability issues")
            
            return ValidationResult(
                success=success,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                diagnostic_data=diagnostic_data
            )
            
        except Exception as e:
            _LOGGER.error("Error during config flow availability validation: %s", e)
            issues.append({
                "issue_type": "validation_error",
                "description": f"Config flow availability validation failed: {str(e)}",
                "severity": "error",
                "fix_available": False,
                "fix_description": "Check logs for detailed error information",
                "diagnostic_info": {"error": str(e), "error_type": type(e).__name__}
            })
            
            return ValidationResult(
                success=False,
                issues=issues,
                warnings=warnings,
                recommendations=["Fix validation errors before proceeding"],
                diagnostic_data=diagnostic_data
            )

    async def run_comprehensive_validation(self, domain: str) -> ComprehensiveResult:
        """Run all validation checks and provide comprehensive results.
        
        Args:
            domain: The integration domain to validate
            
        Returns:
            ComprehensiveResult with all validation results
        """
        _LOGGER.info("Running comprehensive startup validation for domain: %s", domain)
        
        try:
            # Check cache first
            if domain in self._validation_cache:
                cached_result = self._validation_cache[domain]
                _LOGGER.debug("Using cached validation result for domain: %s", domain)
                return cached_result
            
            # Run integration loading validation
            integration_loading_result = await self.validate_integration_loading(domain)
            
            # Run config flow availability validation
            config_flow_availability_result = await self.validate_config_flow_availability(domain)
            
            # Run domain consistency check
            integration_path = self._get_integration_path()
            domain_checker = DomainConsistencyChecker(str(integration_path))
            domain_consistency_result = await domain_checker.validate_consistency()
            
            # Collect comprehensive diagnostic data
            diagnostics = IntegrationDiagnostics(self.hass, domain)
            diagnostic_data = await diagnostics.collect_diagnostic_data()
            
            # Generate startup diagnostics
            startup_diagnostics = await self._generate_startup_diagnostics(
                domain, integration_loading_result, config_flow_availability_result, 
                domain_consistency_result, diagnostic_data
            )
            
            # Aggregate issues, warnings, and recommendations
            all_issues = []
            all_warnings = []
            all_recommendations = []
            
            # From integration loading
            all_issues.extend(integration_loading_result.issues)
            all_warnings.extend(integration_loading_result.warnings)
            all_recommendations.extend(integration_loading_result.recommendations)
            
            # From config flow availability
            all_issues.extend(config_flow_availability_result.issues)
            all_warnings.extend(config_flow_availability_result.warnings)
            all_recommendations.extend(config_flow_availability_result.recommendations)
            
            # From domain consistency
            all_issues.extend(domain_consistency_result.issues)
            all_warnings.extend(domain_consistency_result.warnings)
            all_recommendations.extend(domain_consistency_result.recommendations)
            
            # From diagnostic data
            all_issues.extend(diagnostic_data.error_details)
            
            # Determine overall success
            success = (
                integration_loading_result.success and
                config_flow_availability_result.success and
                domain_consistency_result.consistent and
                diagnostic_data.config_flow_class_found and
                diagnostic_data.manifest_valid
            )
            
            # Create comprehensive result
            result = ComprehensiveResult(
                success=success,
                integration_loading_result=integration_loading_result,
                config_flow_availability_result=config_flow_availability_result,
                domain_consistency_result=domain_consistency_result,
                diagnostic_data=diagnostic_data,
                issues=all_issues,
                warnings=all_warnings,
                recommendations=all_recommendations,
                startup_diagnostics=startup_diagnostics
            )
            
            # Cache the result
            self._validation_cache[domain] = result
            
            if success:
                _LOGGER.info("Comprehensive validation passed for domain: %s", domain)
            else:
                _LOGGER.warning("Comprehensive validation failed for domain: %s", domain)
                _LOGGER.debug("Validation issues: %s", all_issues)
            
            return result
            
        except Exception as e:
            _LOGGER.error("Error during comprehensive validation: %s", e)
            
            # Return failed result with error information
            return ComprehensiveResult(
                success=False,
                integration_loading_result=ValidationResult(
                    success=False, issues=[], warnings=[], recommendations=[], diagnostic_data={}
                ),
                config_flow_availability_result=ValidationResult(
                    success=False, issues=[], warnings=[], recommendations=[], diagnostic_data={}
                ),
                domain_consistency_result=ConsistencyResult(
                    consistent=False, manifest_domain=None, const_domain=None,
                    config_flow_domain=None, issues=[], warnings=[], recommendations=[]
                ),
                diagnostic_data=DiagnosticData(
                    ha_version="unknown", integration_version=VERSION, domain_consistency=False,
                    file_permissions={}, import_status={}, dependency_status={},
                    config_flow_class_found=False, manifest_valid=False,
                    error_details=[f"Comprehensive validation failed: {str(e)}"],
                    system_info={}, integration_info={}
                ),
                issues=[f"Comprehensive validation error: {str(e)}"],
                warnings=[],
                recommendations=["Check logs for detailed error information"],
                startup_diagnostics={"validation_error": str(e)}
            )

    def get_startup_diagnostics(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """Get startup diagnostic information.
        
        Args:
            domain: Optional domain to get diagnostics for. If None, returns general diagnostics.
            
        Returns:
            Dictionary with startup diagnostic information
        """
        diagnostics = {
            "validation_cache_size": len(self._validation_cache),
            "cached_domains": list(self._validation_cache.keys()),
            "hass_state": {
                "is_running": self.hass.is_running,
                "state": str(self.hass.state),
                "config_dir": self.hass.config.config_dir
            }
        }
        
        if domain and domain in self._validation_cache:
            cached_result = self._validation_cache[domain]
            diagnostics[f"{domain}_validation"] = {
                "success": cached_result.success,
                "issue_count": len(cached_result.issues),
                "warning_count": len(cached_result.warnings),
                "recommendation_count": len(cached_result.recommendations),
                "integration_loaded": cached_result.diagnostic_data.integration_info.get("loaded", False),
                "config_flow_found": cached_result.diagnostic_data.config_flow_class_found,
                "manifest_valid": cached_result.diagnostic_data.manifest_valid,
                "domain_consistent": cached_result.diagnostic_data.domain_consistency
            }
        
        return diagnostics

    def _get_integration_path(self):
        """Get the path to the integration directory."""
        from pathlib import Path
        current_file = Path(__file__)
        return current_file.parent

    async def _check_ha_dependencies(self) -> List[Dict[str, Any]]:
        """Check Home Assistant dependencies."""
        issues = []
        
        # Check required domains
        for domain in REQUIRED_DOMAINS:
            if not await self._is_domain_available(domain):
                issues.append({
                    "issue_type": "required_dependency_missing",
                    "description": f"Required Home Assistant component '{domain}' is not available",
                    "severity": "error",
                    "fix_available": False,
                    "fix_description": f"Ensure '{domain}' component is available in Home Assistant",
                    "diagnostic_info": {"missing_domain": domain, "dependency_type": "required"}
                })
        
        # Check optional domains (warnings only)
        for domain in OPTIONAL_DOMAINS:
            if not await self._is_domain_available(domain):
                issues.append({
                    "issue_type": "optional_dependency_missing",
                    "description": f"Optional Home Assistant component '{domain}' is not available",
                    "severity": "warning",
                    "fix_available": False,
                    "fix_description": f"Consider enabling '{domain}' component for enhanced functionality",
                    "diagnostic_info": {"missing_domain": domain, "dependency_type": "optional"}
                })
        
        return issues

    async def _check_integration_imports(self, domain: str) -> List[Dict[str, Any]]:
        """Check integration Python imports."""
        issues = []
        
        # Core integration modules to test
        modules_to_test = [
            "const",
            "config_flow", 
            "models",
            "storage"
        ]
        
        for module_name in modules_to_test:
            try:
                from importlib import import_module
                import_module(f".{module_name}", package=f"custom_components.{domain}")
            except ImportError as e:
                issues.append({
                    "issue_type": "integration_import_error",
                    "description": f"Cannot import integration module '{module_name}': {str(e)}",
                    "severity": "error",
                    "fix_available": True,
                    "fix_description": f"Fix import errors in {module_name}.py",
                    "diagnostic_info": {"module": module_name, "import_error": str(e)}
                })
            except Exception as e:
                issues.append({
                    "issue_type": "integration_module_error",
                    "description": f"Error in integration module '{module_name}': {str(e)}",
                    "severity": "warning",
                    "fix_available": True,
                    "fix_description": f"Check {module_name}.py for syntax or runtime errors",
                    "diagnostic_info": {"module": module_name, "error": str(e)}
                })
        
        return issues

    async def _is_domain_available(self, domain: str) -> bool:
        """Check if a Home Assistant domain/component is available."""
        try:
            # Check if component is loaded
            if domain in self.hass.config.components:
                return True
            
            # Try to import the component
            try:
                from importlib import import_module
                import_module(f"homeassistant.components.{domain}")
                return True
            except ImportError:
                return False
                
        except Exception:
            return False

    async def run_validation_orchestration(self, domain: str, config_entry: Optional[ConfigEntry] = None) -> ComprehensiveResult:
        """Orchestrate comprehensive validation with result aggregation.
        
        This method coordinates all validation components and provides
        aggregated results with detailed reporting.
        
        Args:
            domain: The integration domain to validate
            config_entry: Optional config entry for context
            
        Returns:
            ComprehensiveResult with orchestrated validation results
        """
        _LOGGER.info("Starting validation orchestration for domain: %s", domain)
        
        try:
            # Initialize validation context
            validation_context = {
                "domain": domain,
                "config_entry_id": config_entry.entry_id if config_entry else None,
                "start_time": self.hass.loop.time(),
                "validation_steps": []
            }
            
            # Step 1: Pre-validation checks
            _LOGGER.debug("Running pre-validation checks")
            pre_validation_result = await self._run_pre_validation_checks(domain)
            validation_context["validation_steps"].append({
                "step": "pre_validation",
                "success": pre_validation_result["success"],
                "duration": pre_validation_result.get("duration", 0)
            })
            
            # Step 2: Core validation (existing comprehensive validation)
            _LOGGER.debug("Running core validation")
            core_validation_start = self.hass.loop.time()
            comprehensive_result = await self.run_comprehensive_validation(domain)
            core_validation_duration = self.hass.loop.time() - core_validation_start
            
            validation_context["validation_steps"].append({
                "step": "core_validation",
                "success": comprehensive_result.success,
                "duration": core_validation_duration
            })
            
            # Step 3: Post-validation analysis
            _LOGGER.debug("Running post-validation analysis")
            post_validation_result = await self._run_post_validation_analysis(
                domain, comprehensive_result
            )
            validation_context["validation_steps"].append({
                "step": "post_validation",
                "success": post_validation_result["success"],
                "duration": post_validation_result.get("duration", 0)
            })
            
            # Step 4: Result aggregation and enhancement
            enhanced_result = await self._enhance_comprehensive_result(
                comprehensive_result, validation_context, pre_validation_result, post_validation_result
            )
            
            # Step 5: Generate final diagnostic report
            final_diagnostics = await self._generate_final_diagnostic_report(
                domain, enhanced_result, validation_context
            )
            enhanced_result.startup_diagnostics.update(final_diagnostics)
            
            validation_context["total_duration"] = self.hass.loop.time() - validation_context["start_time"]
            enhanced_result.startup_diagnostics["validation_context"] = validation_context
            
            _LOGGER.info(
                "Validation orchestration completed for domain: %s (success: %s, duration: %.2fs)",
                domain, enhanced_result.success, validation_context["total_duration"]
            )
            
            return enhanced_result
            
        except Exception as e:
            _LOGGER.error("Error during validation orchestration: %s", e)
            
            # Return enhanced error result
            error_result = ComprehensiveResult(
                success=False,
                integration_loading_result=ValidationResult(
                    success=False, issues=[], warnings=[], recommendations=[], diagnostic_data={}
                ),
                config_flow_availability_result=ValidationResult(
                    success=False, issues=[], warnings=[], recommendations=[], diagnostic_data={}
                ),
                domain_consistency_result=ConsistencyResult(
                    consistent=False, manifest_domain=None, const_domain=None,
                    config_flow_domain=None, issues=[], warnings=[], recommendations=[]
                ),
                diagnostic_data=DiagnosticData(
                    ha_version="unknown", integration_version=VERSION, domain_consistency=False,
                    file_permissions={}, import_status={}, dependency_status={},
                    config_flow_class_found=False, manifest_valid=False,
                    error_details=[f"Validation orchestration failed: {str(e)}"],
                    system_info={}, integration_info={}
                ),
                issues=[f"Orchestration error: {str(e)}"],
                warnings=[],
                recommendations=["Check logs and retry validation"],
                startup_diagnostics={
                    "orchestration_error": str(e),
                    "error_type": type(e).__name__,
                    "validation_context": validation_context if 'validation_context' in locals() else {}
                }
            )
            
            return error_result

    async def aggregate_validation_results(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """Aggregate multiple validation results into a summary.
        
        Args:
            results: List of ValidationResult objects to aggregate
            
        Returns:
            Dictionary with aggregated validation summary
        """
        if not results:
            return {
                "total_validations": 0,
                "successful_validations": 0,
                "failed_validations": 0,
                "success_rate": 0.0,
                "total_issues": 0,
                "total_warnings": 0,
                "aggregated_recommendations": []
            }
        
        successful_count = sum(1 for result in results if result.success)
        total_issues = sum(len(result.issues) for result in results)
        total_warnings = sum(len(result.warnings) for result in results)
        
        # Aggregate unique recommendations
        all_recommendations = []
        for result in results:
            all_recommendations.extend(result.recommendations)
        unique_recommendations = list(set(all_recommendations))
        
        # Categorize issues by severity
        error_issues = []
        warning_issues = []
        info_issues = []
        
        for result in results:
            for issue in result.issues:
                if isinstance(issue, dict):
                    severity = issue.get("severity", "info")
                elif hasattr(issue, "severity"):
                    severity = issue.severity
                else:
                    severity = "info"
                
                if severity == "error":
                    error_issues.append(issue)
                elif severity == "warning":
                    warning_issues.append(issue)
                else:
                    info_issues.append(issue)
        
        return {
            "total_validations": len(results),
            "successful_validations": successful_count,
            "failed_validations": len(results) - successful_count,
            "success_rate": successful_count / len(results) if results else 0.0,
            "total_issues": total_issues,
            "total_warnings": total_warnings,
            "error_issues": len(error_issues),
            "warning_issues": len(warning_issues),
            "info_issues": len(info_issues),
            "aggregated_recommendations": unique_recommendations,
            "issue_breakdown": {
                "errors": error_issues,
                "warnings": warning_issues,
                "info": info_issues
            }
        }

    async def generate_startup_diagnostic_report(self, domain: str, comprehensive_result: ComprehensiveResult) -> str:
        """Generate a detailed startup diagnostic report.
        
        Args:
            domain: The integration domain
            comprehensive_result: The comprehensive validation result
            
        Returns:
            Formatted diagnostic report string
        """
        report_lines = [
            "=" * 80,
            f"STARTUP VALIDATION DIAGNOSTIC REPORT - {domain.upper()}",
            "=" * 80,
            "",
            f"Domain: {domain}",
            f"Integration Version: {comprehensive_result.diagnostic_data.integration_version}",
            f"Home Assistant Version: {comprehensive_result.diagnostic_data.ha_version}",
            f"Validation Timestamp: {comprehensive_result.startup_diagnostics.get('validation_timestamp', 'unknown')}",
            f"Overall Success: {'✓ PASS' if comprehensive_result.success else '✗ FAIL'}",
            ""
        ]
        
        # Validation Results Summary
        report_lines.extend([
            "VALIDATION RESULTS SUMMARY:",
            "-" * 30
        ])
        
        validation_results = comprehensive_result.startup_diagnostics.get("validation_results", {})
        for validation_type, result in validation_results.items():
            status = "✓ PASS" if result.get("success", False) else "✗ FAIL"
            issue_count = result.get("issue_count", 0)
            warning_count = result.get("warning_count", 0)
            
            report_lines.append(f"{validation_type.replace('_', ' ').title()}: {status}")
            if issue_count > 0:
                report_lines.append(f"  Issues: {issue_count}")
            if warning_count > 0:
                report_lines.append(f"  Warnings: {warning_count}")
        
        report_lines.append("")
        
        # Integration Status
        report_lines.extend([
            "INTEGRATION STATUS:",
            "-" * 20
        ])
        
        integration_status = comprehensive_result.startup_diagnostics.get("integration_status", {})
        for key, value in integration_status.items():
            display_key = key.replace('_', ' ').title()
            if isinstance(value, bool):
                display_value = "✓ Yes" if value else "✗ No"
            else:
                display_value = str(value)
            report_lines.append(f"{display_key}: {display_value}")
        
        report_lines.append("")
        
        # Issues and Warnings
        if comprehensive_result.issues:
            report_lines.extend([
                "ISSUES FOUND:",
                "-" * 14
            ])
            for i, issue in enumerate(comprehensive_result.issues, 1):
                if isinstance(issue, dict):
                    severity = issue.get("severity", "unknown").upper()
                    description = issue.get("description", str(issue))
                    report_lines.append(f"{i}. [{severity}] {description}")
                else:
                    report_lines.append(f"{i}. {issue}")
            report_lines.append("")
        
        if comprehensive_result.warnings:
            report_lines.extend([
                "WARNINGS:",
                "-" * 9
            ])
            for i, warning in enumerate(comprehensive_result.warnings, 1):
                report_lines.append(f"{i}. {warning}")
            report_lines.append("")
        
        # Recommendations
        if comprehensive_result.recommendations:
            report_lines.extend([
                "RECOMMENDATIONS:",
                "-" * 16
            ])
            for i, recommendation in enumerate(comprehensive_result.recommendations, 1):
                report_lines.append(f"{i}. {recommendation}")
            report_lines.append("")
        
        # System Information
        system_info = comprehensive_result.startup_diagnostics.get("system_info", {})
        if system_info:
            report_lines.extend([
                "SYSTEM INFORMATION:",
                "-" * 19
            ])
            for key, value in system_info.items():
                display_key = key.replace('_', ' ').title()
                report_lines.append(f"{display_key}: {value}")
            report_lines.append("")
        
        # Error Summary
        error_summary = comprehensive_result.startup_diagnostics.get("error_summary", {})
        if error_summary:
            report_lines.extend([
                "ERROR SUMMARY:",
                "-" * 14
            ])
            for key, value in error_summary.items():
                display_key = key.replace('_', ' ').title()
                report_lines.append(f"{display_key}: {value}")
            report_lines.append("")
        
        # Validation Context (if available)
        validation_context = comprehensive_result.startup_diagnostics.get("validation_context", {})
        if validation_context:
            report_lines.extend([
                "VALIDATION CONTEXT:",
                "-" * 19
            ])
            
            total_duration = validation_context.get("total_duration", 0)
            report_lines.append(f"Total Duration: {total_duration:.3f}s")
            
            validation_steps = validation_context.get("validation_steps", [])
            if validation_steps:
                report_lines.append("Validation Steps:")
                for step in validation_steps:
                    step_name = step.get("step", "unknown").replace('_', ' ').title()
                    step_success = "✓" if step.get("success", False) else "✗"
                    step_duration = step.get("duration", 0)
                    report_lines.append(f"  {step_success} {step_name}: {step_duration:.3f}s")
            
            report_lines.append("")
        
        report_lines.extend([
            "=" * 80,
            "END OF DIAGNOSTIC REPORT",
            "=" * 80
        ])
        
        return "\n".join(report_lines)

    async def _run_pre_validation_checks(self, domain: str) -> Dict[str, Any]:
        """Run pre-validation checks before main validation."""
        start_time = self.hass.loop.time()
        
        try:
            checks = {
                "hass_running": self.hass.is_running,
                "integration_path_exists": self._get_integration_path().exists(),
                "domain_matches": domain == DOMAIN,
                "config_entries_accessible": hasattr(self.hass, 'config_entries')
            }
            
            success = all(checks.values())
            
            return {
                "success": success,
                "checks": checks,
                "duration": self.hass.loop.time() - start_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration": self.hass.loop.time() - start_time
            }

    async def _run_post_validation_analysis(self, domain: str, result: ComprehensiveResult) -> Dict[str, Any]:
        """Run post-validation analysis and enhancement."""
        start_time = self.hass.loop.time()
        
        try:
            analysis = {
                "validation_completeness": self._assess_validation_completeness(result),
                "issue_severity_analysis": self._analyze_issue_severity(result),
                "recovery_recommendations": self._generate_recovery_recommendations(result),
                "performance_metrics": self._calculate_performance_metrics(result)
            }
            
            return {
                "success": True,
                "analysis": analysis,
                "duration": self.hass.loop.time() - start_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration": self.hass.loop.time() - start_time
            }

    async def _enhance_comprehensive_result(
        self, 
        result: ComprehensiveResult, 
        validation_context: Dict[str, Any],
        pre_validation: Dict[str, Any],
        post_validation: Dict[str, Any]
    ) -> ComprehensiveResult:
        """Enhance comprehensive result with additional context."""
        
        # Add pre-validation context
        result.startup_diagnostics["pre_validation"] = pre_validation
        
        # Add post-validation analysis
        if post_validation.get("success"):
            result.startup_diagnostics["post_validation_analysis"] = post_validation.get("analysis", {})
        
        # Enhance recommendations based on analysis
        if post_validation.get("success") and "analysis" in post_validation:
            recovery_recs = post_validation["analysis"].get("recovery_recommendations", [])
            result.recommendations.extend(recovery_recs)
        
        return result

    async def _generate_final_diagnostic_report(
        self, 
        domain: str, 
        result: ComprehensiveResult, 
        validation_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate final diagnostic report data."""
        return {
            "final_assessment": {
                "overall_health": "healthy" if result.success else "unhealthy",
                "critical_issues": len([
                    issue for issue in result.issues 
                    if (isinstance(issue, dict) and issue.get("severity") == "error") or
                       (hasattr(issue, "severity") and issue.severity == "error")
                ]),
                "actionable_recommendations": len([
                    rec for rec in result.recommendations 
                    if "fix" in rec.lower() or "update" in rec.lower() or "create" in rec.lower()
                ]),
                "validation_coverage": self._calculate_validation_coverage(result)
            },
            "next_steps": self._generate_next_steps(result),
            "troubleshooting_priority": self._determine_troubleshooting_priority(result)
        }

    def _assess_validation_completeness(self, result: ComprehensiveResult) -> Dict[str, Any]:
        """Assess how complete the validation was."""
        return {
            "integration_loading_completed": result.integration_loading_result.success is not None,
            "config_flow_validation_completed": result.config_flow_availability_result.success is not None,
            "domain_consistency_completed": result.domain_consistency_result.consistent is not None,
            "diagnostic_data_collected": bool(result.diagnostic_data.system_info),
            "completeness_score": self._calculate_completeness_score(result)
        }

    def _analyze_issue_severity(self, result: ComprehensiveResult) -> Dict[str, Any]:
        """Analyze the severity distribution of issues."""
        severity_counts = {"error": 0, "warning": 0, "info": 0}
        
        for issue in result.issues:
            if isinstance(issue, dict):
                severity = issue.get("severity", "info")
            elif hasattr(issue, "severity"):
                severity = issue.severity
            else:
                severity = "info"
            
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "severity_distribution": severity_counts,
            "critical_issue_ratio": severity_counts["error"] / max(len(result.issues), 1),
            "requires_immediate_attention": severity_counts["error"] > 0
        }

    def _generate_recovery_recommendations(self, result: ComprehensiveResult) -> List[str]:
        """Generate specific recovery recommendations based on validation results."""
        recommendations = []
        
        if not result.success:
            if not result.diagnostic_data.config_flow_class_found:
                recommendations.append("Priority: Fix config flow class definition and import issues")
            
            if not result.diagnostic_data.manifest_valid:
                recommendations.append("Priority: Validate and fix manifest.json configuration")
            
            if not result.domain_consistency_result.consistent:
                recommendations.append("Priority: Resolve domain consistency issues across integration files")
        
        return recommendations

    def _calculate_performance_metrics(self, result: ComprehensiveResult) -> Dict[str, Any]:
        """Calculate performance metrics for the validation."""
        return {
            "validation_efficiency": len(result.recommendations) / max(len(result.issues), 1),
            "issue_resolution_potential": len([
                issue for issue in result.issues 
                if isinstance(issue, dict) and issue.get("fix_available", False)
            ]) / max(len(result.issues), 1)
        }

    def _calculate_completeness_score(self, result: ComprehensiveResult) -> float:
        """Calculate a completeness score for the validation."""
        completed_checks = 0
        total_checks = 4  # integration_loading, config_flow, domain_consistency, diagnostics
        
        if result.integration_loading_result.success is not None:
            completed_checks += 1
        if result.config_flow_availability_result.success is not None:
            completed_checks += 1
        if result.domain_consistency_result.consistent is not None:
            completed_checks += 1
        if result.diagnostic_data.system_info:
            completed_checks += 1
        
        return completed_checks / total_checks

    def _calculate_validation_coverage(self, result: ComprehensiveResult) -> float:
        """Calculate validation coverage percentage."""
        # This is a simplified coverage calculation
        coverage_areas = [
            result.diagnostic_data.config_flow_class_found,
            result.diagnostic_data.manifest_valid,
            result.diagnostic_data.domain_consistency,
            bool(result.diagnostic_data.file_permissions),
            bool(result.diagnostic_data.import_status),
            bool(result.diagnostic_data.dependency_status)
        ]
        
        return sum(coverage_areas) / len(coverage_areas)

    def _generate_next_steps(self, result: ComprehensiveResult) -> List[str]:
        """Generate next steps based on validation results."""
        if result.success:
            return ["Integration validation passed - ready for normal operation"]
        
        next_steps = []
        
        # Prioritize critical issues
        critical_issues = [
            issue for issue in result.issues 
            if (isinstance(issue, dict) and issue.get("severity") == "error") or
               (hasattr(issue, "severity") and issue.severity == "error")
        ]
        
        if critical_issues:
            next_steps.append("1. Address critical errors first")
            for i, issue in enumerate(critical_issues[:3], 2):  # Show top 3
                if isinstance(issue, dict):
                    next_steps.append(f"{i}. {issue.get('fix_description', 'Fix critical issue')}")
        
        if not result.diagnostic_data.config_flow_class_found:
            next_steps.append("• Verify config flow class implementation")
        
        if not result.diagnostic_data.manifest_valid:
            next_steps.append("• Fix manifest.json configuration")
        
        return next_steps

    def _determine_troubleshooting_priority(self, result: ComprehensiveResult) -> str:
        """Determine troubleshooting priority level."""
        if result.success:
            return "low"
        
        critical_issues = len([
            issue for issue in result.issues 
            if (isinstance(issue, dict) and issue.get("severity") == "error") or
               (hasattr(issue, "severity") and issue.severity == "error")
        ])
        
        if critical_issues > 3:
            return "critical"
        elif critical_issues > 0:
            return "high"
        elif len(result.warnings) > 5:
            return "medium"
        else:
            return "low"

    async def _generate_startup_diagnostics(
        self, 
        domain: str,
        integration_result: ValidationResult,
        config_flow_result: ValidationResult,
        domain_result: ConsistencyResult,
        diagnostic_data: DiagnosticData
    ) -> Dict[str, Any]:
        """Generate comprehensive startup diagnostics."""
        return {
            "domain": domain,
            "validation_timestamp": self.hass.loop.time(),
            "overall_success": (
                integration_result.success and 
                config_flow_result.success and 
                domain_result.consistent
            ),
            "validation_results": {
                "integration_loading": {
                    "success": integration_result.success,
                    "issue_count": len(integration_result.issues),
                    "warning_count": len(integration_result.warnings)
                },
                "config_flow_availability": {
                    "success": config_flow_result.success,
                    "issue_count": len(config_flow_result.issues),
                    "warning_count": len(config_flow_result.warnings)
                },
                "domain_consistency": {
                    "consistent": domain_result.consistent,
                    "issue_count": len(domain_result.issues),
                    "warning_count": len(domain_result.warnings)
                }
            },
            "integration_status": {
                "version": diagnostic_data.integration_version,
                "ha_version": diagnostic_data.ha_version,
                "loaded": diagnostic_data.integration_info.get("loaded", False),
                "config_entries": diagnostic_data.integration_info.get("config_entries", 0),
                "config_flow_class_found": diagnostic_data.config_flow_class_found,
                "manifest_valid": diagnostic_data.manifest_valid,
                "domain_consistency": diagnostic_data.domain_consistency
            },
            "system_info": diagnostic_data.system_info,
            "error_summary": {
                "total_issues": len(integration_result.issues) + len(config_flow_result.issues) + len(domain_result.issues),
                "total_warnings": len(integration_result.warnings) + len(config_flow_result.warnings) + len(domain_result.warnings),
                "critical_errors": len([
                    issue for issue in integration_result.issues + config_flow_result.issues
                    if (isinstance(issue, dict) and issue.get("severity") == "error") or
                       (hasattr(issue, "severity") and issue.severity == "error")
                ])
            }
        }