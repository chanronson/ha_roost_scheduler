"""Troubleshooting utilities for Roost Scheduler."""
from __future__ import annotations

import logging
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

from homeassistant.core import HomeAssistant
from homeassistant.const import __version__ as HA_VERSION

from .const import DOMAIN, VERSION
from .integration_diagnostics import IntegrationDiagnostics, DiagnosticData
from .config_flow_validator import ConfigFlowValidator
from .domain_consistency_checker import DomainConsistencyChecker
from .startup_validation_system import StartupValidationSystem
from .file_system_validator import FileSystemValidator
from .file_system_error_handler import FileSystemErrorHandler

_LOGGER = logging.getLogger(__name__)


@dataclass
class TroubleshootingContext:
    """Context information for troubleshooting."""
    timestamp: str
    ha_version: str
    integration_version: str
    entry_id: Optional[str]
    error_context: Optional[str]
    user_action: Optional[str]
    system_state: Dict[str, Any]


@dataclass
class TroubleshootingReport:
    """Comprehensive troubleshooting report."""
    context: TroubleshootingContext
    diagnostic_data: DiagnosticData
    validation_results: Dict[str, Any]
    component_health: Dict[str, Any]
    error_analysis: Dict[str, Any]
    recommendations: List[str]
    step_by_step_guide: List[str]
    common_solutions: Dict[str, List[str]]
    formatted_report: str


class TroubleshootingReportGenerator:
    """Generates comprehensive troubleshooting reports with diagnostic data and user-friendly guidance."""
    
    def __init__(self, hass: HomeAssistant, domain: str = DOMAIN) -> None:
        """Initialize the troubleshooting report generator."""
        self.hass = hass
        self.domain = domain
        self.diagnostics = IntegrationDiagnostics(hass, domain)
        
    async def generate_comprehensive_report(
        self, 
        entry_id: Optional[str] = None,
        error_context: Optional[str] = None,
        user_action: Optional[str] = None
    ) -> TroubleshootingReport:
        """Generate a comprehensive troubleshooting report."""
        _LOGGER.info("Generating comprehensive troubleshooting report")
        
        try:
            # Create troubleshooting context
            context = TroubleshootingContext(
                timestamp=datetime.now().isoformat(),
                ha_version=HA_VERSION,
                integration_version=VERSION,
                entry_id=entry_id,
                error_context=error_context,
                user_action=user_action,
                system_state=await self._collect_system_state()
            )
            
            # Collect diagnostic data
            diagnostic_data = await self.diagnostics.collect_diagnostic_data()
            
            # Run validation checks
            validation_results = await self._run_comprehensive_validation()
            
            # Analyze component health
            component_health = await self._analyze_component_health(entry_id)
            
            # Perform error analysis
            error_analysis = await self._perform_error_analysis(diagnostic_data, validation_results)
            
            # Generate recommendations
            recommendations = await self._generate_comprehensive_recommendations(
                diagnostic_data, validation_results, error_analysis
            )
            
            # Create step-by-step troubleshooting guide
            step_by_step_guide = await self._create_step_by_step_guide(
                error_analysis, recommendations
            )
            
            # Get common solutions database
            common_solutions = self._get_enhanced_common_solutions()
            
            # Generate formatted report
            formatted_report = await self._format_comprehensive_report(
                context, diagnostic_data, validation_results, component_health,
                error_analysis, recommendations, step_by_step_guide, common_solutions
            )
            
            return TroubleshootingReport(
                context=context,
                diagnostic_data=diagnostic_data,
                validation_results=validation_results,
                component_health=component_health,
                error_analysis=error_analysis,
                recommendations=recommendations,
                step_by_step_guide=step_by_step_guide,
                common_solutions=common_solutions,
                formatted_report=formatted_report
            )
            
        except Exception as e:
            _LOGGER.error("Error generating troubleshooting report: %s", e, exc_info=True)
            # Return minimal report with error information
            return await self._create_error_report(e, entry_id, error_context)
    
    async def _collect_system_state(self) -> Dict[str, Any]:
        """Collect current system state information."""
        try:
            return {
                "integration_loaded": self.domain in self.hass.config.components,
                "config_entries_count": len(self.hass.config_entries.async_entries(self.domain)),
                "active_entities": len([
                    entity for entity in self.hass.states.async_all()
                    if entity.entity_id.startswith(f"{self.domain}.")
                ]),
                "hass_state": self.hass.state.name,
                "startup_complete": self.hass.is_running,
                "config_dir_writable": self.hass.config.config_dir is not None
            }
        except Exception as e:
            _LOGGER.debug("Error collecting system state: %s", e)
            return {"error": f"Failed to collect system state: {str(e)}"}
    
    async def _run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation checks."""
        validation_results = {}
        
        try:
            # Config flow validation
            config_validator = ConfigFlowValidator(self.hass, self.domain)
            validation_results["config_flow"] = await config_validator.validate_config_flow_registration()
            validation_results["domain_consistency"] = await config_validator.validate_domain_consistency()
            validation_results["manifest"] = await config_validator.validate_manifest_configuration()
            
            # Domain consistency check
            domain_checker = DomainConsistencyChecker(str(self.diagnostics._integration_path))
            validation_results["domain_files"] = await domain_checker.validate_consistency()
            
            # Startup validation
            startup_validator = StartupValidationSystem(self.hass)
            validation_results["startup"] = await startup_validator.validate_integration_loading(self.domain)
            validation_results["config_flow_availability"] = await startup_validator.validate_config_flow_availability(self.domain)
            
            # File system validation
            fs_validator = FileSystemValidator(self.hass, self.domain)
            validation_results["file_system"] = await fs_validator.validate_file_system()
            
        except Exception as e:
            _LOGGER.error("Error during validation: %s", e)
            validation_results["error"] = f"Validation failed: {str(e)}"
        
        return validation_results
    
    async def _analyze_component_health(self, entry_id: Optional[str]) -> Dict[str, Any]:
        """Analyze health of integration components."""
        if not entry_id:
            return {"status": "no_entry", "message": "No config entry provided for analysis"}
        
        try:
            # Use existing troubleshooting manager for component analysis
            legacy_manager = TroubleshootingManager(self.hass)
            component_diagnostics = await legacy_manager.run_comprehensive_diagnostics(entry_id)
            
            return {
                "overall_health": component_diagnostics.get("overall_health", "unknown"),
                "components": component_diagnostics.get("components", {}),
                "health_summary": component_diagnostics.get("health_summary", {}),
                "performance_summary": component_diagnostics.get("performance_summary", {})
            }
            
        except Exception as e:
            _LOGGER.error("Error analyzing component health: %s", e)
            return {"status": "error", "message": f"Component analysis failed: {str(e)}"}
    
    async def _perform_error_analysis(
        self, 
        diagnostic_data: DiagnosticData, 
        validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive error analysis."""
        error_analysis = {
            "critical_errors": [],
            "warnings": [],
            "configuration_issues": [],
            "dependency_issues": [],
            "file_system_issues": [],
            "import_issues": [],
            "error_categories": {},
            "severity_assessment": "unknown"
        }
        
        try:
            # Analyze diagnostic data errors
            for error in diagnostic_data.error_details:
                if any(keyword in error.lower() for keyword in ["critical", "fatal", "failed to load"]):
                    error_analysis["critical_errors"].append(error)
                else:
                    error_analysis["warnings"].append(error)
            
            # Analyze validation results
            for validation_type, result in validation_results.items():
                if isinstance(result, dict) and not result.get("success", True):
                    issues = result.get("issues", [])
                    for issue in issues:
                        if validation_type == "config_flow":
                            error_analysis["configuration_issues"].append(f"Config Flow: {issue}")
                        elif validation_type == "file_system":
                            error_analysis["file_system_issues"].append(f"File System: {issue}")
            
            # Analyze dependencies
            for dep_name, dep_status in diagnostic_data.dependency_status.items():
                if not dep_status.available:
                    error_analysis["dependency_issues"].append(
                        f"{dep_name}: {dep_status.error_message or 'Not available'}"
                    )
            
            # Analyze imports
            for import_name, import_status in diagnostic_data.import_status.items():
                if not import_status.importable:
                    error_analysis["import_issues"].append(
                        f"{import_name}: {import_status.error_message or 'Import failed'}"
                    )
            
            # Categorize errors
            error_analysis["error_categories"] = self._categorize_errors(error_analysis)
            
            # Assess severity
            error_analysis["severity_assessment"] = self._assess_error_severity(error_analysis)
            
        except Exception as e:
            _LOGGER.error("Error during error analysis: %s", e)
            error_analysis["critical_errors"].append(f"Error analysis failed: {str(e)}")
        
        return error_analysis
    
    def _categorize_errors(self, error_analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """Categorize errors by type and cause."""
        categories = {
            "installation_issues": [],
            "configuration_issues": [],
            "permission_issues": [],
            "dependency_issues": [],
            "code_issues": [],
            "system_issues": []
        }
        
        all_errors = (
            error_analysis["critical_errors"] + 
            error_analysis["warnings"] + 
            error_analysis["configuration_issues"] +
            error_analysis["dependency_issues"] +
            error_analysis["file_system_issues"] +
            error_analysis["import_issues"]
        )
        
        for error in all_errors:
            error_lower = error.lower()
            
            if any(keyword in error_lower for keyword in ["permission", "access", "readable", "writable"]):
                categories["permission_issues"].append(error)
            elif any(keyword in error_lower for keyword in ["dependency", "import", "module"]):
                categories["dependency_issues"].append(error)
            elif any(keyword in error_lower for keyword in ["config", "manifest", "domain"]):
                categories["configuration_issues"].append(error)
            elif any(keyword in error_lower for keyword in ["file", "directory", "path"]):
                categories["installation_issues"].append(error)
            elif any(keyword in error_lower for keyword in ["class", "method", "attribute"]):
                categories["code_issues"].append(error)
            else:
                categories["system_issues"].append(error)
        
        return categories
    
    def _assess_error_severity(self, error_analysis: Dict[str, Any]) -> str:
        """Assess overall error severity."""
        critical_count = len(error_analysis["critical_errors"])
        warning_count = len(error_analysis["warnings"])
        config_issues = len(error_analysis["configuration_issues"])
        dependency_issues = len(error_analysis["dependency_issues"])
        
        if critical_count > 0 or dependency_issues > 2:
            return "critical"
        elif config_issues > 2 or warning_count > 5:
            return "high"
        elif config_issues > 0 or warning_count > 2:
            return "medium"
        elif warning_count > 0:
            return "low"
        else:
            return "none"
    
    async def _generate_comprehensive_recommendations(
        self,
        diagnostic_data: DiagnosticData,
        validation_results: Dict[str, Any],
        error_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate comprehensive recommendations based on all analysis."""
        recommendations = []
        
        try:
            # Priority recommendations based on severity
            severity = error_analysis.get("severity_assessment", "unknown")
            
            if severity == "critical":
                recommendations.extend([
                    "🚨 CRITICAL: Integration has critical errors that prevent normal operation",
                    "Stop using the integration until issues are resolved",
                    "Check Home Assistant logs for detailed error messages",
                    "Consider backing up configuration before making changes"
                ])
            
            # Domain consistency recommendations
            if not diagnostic_data.domain_consistency:
                recommendations.extend([
                    "🔧 Fix domain consistency across integration files",
                    "Ensure manifest.json, const.py, and config_flow.py use the same domain",
                    "Use the domain consistency checker to identify mismatches"
                ])
            
            # Config flow recommendations
            if not diagnostic_data.config_flow_class_found:
                recommendations.extend([
                    "🔧 Fix config flow class implementation",
                    "Ensure ConfigFlow class exists in config_flow.py",
                    "Verify class inherits from config_entries.ConfigFlow",
                    "Check that required methods are implemented"
                ])
            
            # Manifest recommendations
            if not diagnostic_data.manifest_valid:
                recommendations.extend([
                    "🔧 Fix manifest.json configuration",
                    "Ensure 'config_flow': true is set in manifest.json",
                    "Verify all required fields are present",
                    "Check JSON syntax is valid"
                ])
            
            # File system recommendations
            file_issues = error_analysis.get("file_system_issues", [])
            if file_issues:
                recommendations.extend([
                    "🔧 Fix file system issues:",
                    "Check file and directory permissions",
                    "Ensure integration files are readable by Home Assistant",
                    "Verify integration directory structure is correct"
                ])
            
            # Dependency recommendations
            dependency_issues = error_analysis.get("dependency_issues", [])
            if dependency_issues:
                recommendations.extend([
                    "🔧 Resolve dependency issues:",
                    "Install missing Home Assistant components",
                    "Check component compatibility with your HA version",
                    "Restart Home Assistant after installing dependencies"
                ])
            
            # Import recommendations
            import_issues = error_analysis.get("import_issues", [])
            if import_issues:
                recommendations.extend([
                    "🔧 Fix import errors:",
                    "Check for missing or corrupted integration files",
                    "Verify Python syntax in integration modules",
                    "Ensure all required modules are present"
                ])
            
            # Category-specific recommendations
            error_categories = error_analysis.get("error_categories", {})
            
            if error_categories.get("permission_issues"):
                recommendations.extend([
                    "🔐 Permission Issues Detected:",
                    "Check Home Assistant process has read access to integration files",
                    "Verify directory permissions allow traversal",
                    "Consider reinstalling integration if permissions are corrupted"
                ])
            
            if error_categories.get("installation_issues"):
                recommendations.extend([
                    "📦 Installation Issues Detected:",
                    "Reinstall the integration through HACS or manually",
                    "Verify all integration files are present",
                    "Check integration directory structure matches expected layout"
                ])
            
            # Performance recommendations
            if severity in ["medium", "high"]:
                recommendations.extend([
                    "⚡ Performance Optimization:",
                    "Enable debug logging temporarily to identify bottlenecks",
                    "Monitor entity update frequencies",
                    "Consider reducing tracked entities if performance is poor"
                ])
            
            # General maintenance recommendations
            if not recommendations or severity == "none":
                recommendations.extend([
                    "✅ Integration appears healthy",
                    "Consider enabling performance monitoring for ongoing health checks",
                    "Regular diagnostic checks can help identify issues early",
                    "Keep integration updated to latest version"
                ])
            
        except Exception as e:
            _LOGGER.error("Error generating recommendations: %s", e)
            recommendations.append(f"⚠️ Error generating recommendations: {str(e)}")
        
        return recommendations
    
    async def _format_comprehensive_report(
        self,
        context: TroubleshootingContext,
        diagnostic_data: DiagnosticData,
        validation_results: Dict[str, Any],
        component_health: Dict[str, Any],
        error_analysis: Dict[str, Any],
        recommendations: List[str],
        step_by_step_guide: List[str],
        common_solutions: Dict[str, List[str]]
    ) -> str:
        """Format comprehensive troubleshooting report."""
        report_lines = []
        
        try:
            # Header
            report_lines.extend([
                "=" * 80,
                "🔧 ROOST SCHEDULER COMPREHENSIVE TROUBLESHOOTING REPORT",
                "=" * 80,
                "",
                f"📅 Generated: {context.timestamp}",
                f"🏠 Home Assistant Version: {context.ha_version}",
                f"🔌 Integration Version: {context.integration_version}",
                f"🆔 Entry ID: {context.entry_id or 'N/A'}",
                f"⚠️  Error Context: {context.error_context or 'General diagnostics'}",
                f"👤 User Action: {context.user_action or 'Automatic check'}",
                ""
            ])
            
            # Executive Summary
            severity = error_analysis.get("severity_assessment", "unknown")
            severity_emoji = {
                "critical": "🚨", "high": "⚠️", "medium": "⚡", "low": "ℹ️", "none": "✅"
            }.get(severity, "❓")
            
            report_lines.extend([
                "📊 EXECUTIVE SUMMARY",
                "-" * 20,
                f"{severity_emoji} Overall Severity: {severity.upper()}",
                f"🏥 Integration Health: {component_health.get('overall_health', 'unknown').upper()}",
                f"🔧 Domain Consistency: {'✅' if diagnostic_data.domain_consistency else '❌'}",
                f"🌊 Config Flow Available: {'✅' if diagnostic_data.config_flow_class_found else '❌'}",
                f"📋 Manifest Valid: {'✅' if diagnostic_data.manifest_valid else '❌'}",
                ""
            ])
            
            # System Information
            report_lines.extend([
                "💻 SYSTEM INFORMATION",
                "-" * 20
            ])
            
            for key, value in diagnostic_data.system_info.items():
                report_lines.append(f"{key}: {value}")
            
            system_state = context.system_state
            report_lines.extend([
                f"Integration Loaded: {'✅' if system_state.get('integration_loaded') else '❌'}",
                f"Config Entries: {system_state.get('config_entries_count', 0)}",
                f"Active Entities: {system_state.get('active_entities', 0)}",
                f"Home Assistant Running: {'✅' if system_state.get('startup_complete') else '❌'}",
                ""
            ])
            
            # Error Analysis
            if error_analysis.get("critical_errors") or error_analysis.get("warnings"):
                report_lines.extend([
                    "🚨 ERROR ANALYSIS",
                    "-" * 15
                ])
                
                critical_errors = error_analysis.get("critical_errors", [])
                if critical_errors:
                    report_lines.append("Critical Errors:")
                    for error in critical_errors:
                        report_lines.append(f"  🚨 {error}")
                    report_lines.append("")
                
                warnings = error_analysis.get("warnings", [])
                if warnings:
                    report_lines.append("Warnings:")
                    for warning in warnings:
                        report_lines.append(f"  ⚠️  {warning}")
                    report_lines.append("")
                
                # Error categories
                error_categories = error_analysis.get("error_categories", {})
                if any(error_categories.values()):
                    report_lines.append("Error Categories:")
                    for category, errors in error_categories.items():
                        if errors:
                            report_lines.append(f"  📂 {category.replace('_', ' ').title()}: {len(errors)} issues")
                    report_lines.append("")
            
            # Component Health
            if component_health.get("components"):
                report_lines.extend([
                    "🏥 COMPONENT HEALTH",
                    "-" * 18
                ])
                
                health_summary = component_health.get("health_summary", {})
                if health_summary:
                    report_lines.extend([
                        f"Total Components: {health_summary.get('total_components', 0)}",
                        f"Healthy: {health_summary.get('healthy', 0)} ✅",
                        f"Issues: {health_summary.get('issues', 0)} ⚠️",
                        f"Errors: {health_summary.get('errors', 0)} ❌",
                        f"Missing: {health_summary.get('missing', 0)} ❓",
                        f"Health Percentage: {health_summary.get('health_percentage', 0):.1f}%",
                        ""
                    ])
                
                components = component_health.get("components", {})
                for component_name, component_info in components.items():
                    status_emoji = {"healthy": "✅", "issues": "⚠️", "error": "❌", "missing": "❓"}.get(
                        component_info.get("status", "unknown"), "❓"
                    )
                    report_lines.append(f"{status_emoji} {component_name}: {component_info.get('status', 'unknown')}")
                    
                    if component_info.get("health_score"):
                        report_lines.append(f"    Health Score: {component_info['health_score']}")
                    
                    issues = component_info.get("issues", [])
                    if issues:
                        for issue in issues[:3]:  # Limit to first 3 issues
                            report_lines.append(f"    • {issue}")
                        if len(issues) > 3:
                            report_lines.append(f"    ... and {len(issues) - 3} more issues")
                
                report_lines.append("")
            
            # Validation Results Summary
            report_lines.extend([
                "🔍 VALIDATION RESULTS",
                "-" * 19
            ])
            
            for validation_type, result in validation_results.items():
                if isinstance(result, dict):
                    success = result.get("success", True)
                    status_emoji = "✅" if success else "❌"
                    report_lines.append(f"{status_emoji} {validation_type.replace('_', ' ').title()}: {'PASS' if success else 'FAIL'}")
                    
                    if not success and result.get("issues"):
                        for issue in result["issues"][:2]:  # Limit to first 2 issues
                            report_lines.append(f"    • {issue}")
                        if len(result["issues"]) > 2:
                            report_lines.append(f"    ... and {len(result['issues']) - 2} more issues")
            
            report_lines.append("")
            
            # File System Status
            if diagnostic_data.file_permissions:
                report_lines.extend([
                    "📁 FILE SYSTEM STATUS",
                    "-" * 20
                ])
                
                for file_path, perm in diagnostic_data.file_permissions.items():
                    status_emoji = "✅" if perm.exists and perm.readable else "❌"
                    report_lines.append(f"{status_emoji} {file_path}")
                    if perm.error_message:
                        report_lines.append(f"    Error: {perm.error_message}")
                
                report_lines.append("")
            
            # Recommendations
            if recommendations:
                report_lines.extend([
                    "💡 RECOMMENDATIONS",
                    "-" * 17
                ])
                
                for rec in recommendations:
                    report_lines.append(f"{rec}")
                
                report_lines.append("")
            
            # Step-by-Step Guide
            if step_by_step_guide:
                report_lines.extend([
                    "📋 STEP-BY-STEP TROUBLESHOOTING GUIDE",
                    "-" * 37
                ])
                
                for step in step_by_step_guide:
                    report_lines.append(step)
                
                report_lines.append("")
            
            # Common Solutions Quick Reference
            report_lines.extend([
                "🔧 COMMON SOLUTIONS QUICK REFERENCE",
                "-" * 35,
                ""
            ])
            
            # Show relevant solutions based on error categories
            error_categories = error_analysis.get("error_categories", {})
            relevant_solutions = []
            
            if error_categories.get("configuration_issues"):
                relevant_solutions.extend(["config_flow_not_loading", "invalid_handler_specified"])
            if error_categories.get("installation_issues"):
                relevant_solutions.append("integration_not_loading")
            if error_categories.get("permission_issues"):
                relevant_solutions.append("permission_denied")
            if error_categories.get("dependency_issues"):
                relevant_solutions.append("import_errors")
            
            # If no specific categories, show general solutions
            if not relevant_solutions:
                relevant_solutions = ["config_flow_not_loading", "integration_not_loading", "storage_issues"]
            
            for solution_key in relevant_solutions[:5]:  # Limit to 5 most relevant
                if solution_key in common_solutions:
                    report_lines.append(f"🔧 {solution_key.replace('_', ' ').title()}:")
                    for solution in common_solutions[solution_key]:
                        report_lines.append(f"  • {solution}")
                    report_lines.append("")
            
            # Footer
            report_lines.extend([
                "=" * 80,
                "📞 ADDITIONAL HELP",
                "=" * 80,
                "",
                "If this report doesn't resolve your issue:",
                "• Check the integration's documentation",
                "• Search for similar issues in the community forums",
                "• Generate a fresh report after making changes",
                "• Consider reporting the issue with this diagnostic data",
                "",
                "Report generated by Roost Scheduler Troubleshooting System",
                f"Timestamp: {context.timestamp}",
                "=" * 80
            ])
            
        except Exception as e:
            _LOGGER.error("Error formatting report: %s", e)
            report_lines.extend([
                "❌ ERROR FORMATTING REPORT",
                f"An error occurred while formatting the report: {str(e)}",
                "Raw diagnostic data is available in the TroubleshootingReport object."
            ])
        
        return "\n".join(report_lines)
    
    async def _create_error_report(
        self, 
        error: Exception, 
        entry_id: Optional[str], 
        error_context: Optional[str]
    ) -> TroubleshootingReport:
        """Create minimal error report when main report generation fails."""
        context = TroubleshootingContext(
            timestamp=datetime.now().isoformat(),
            ha_version=HA_VERSION,
            integration_version=VERSION,
            entry_id=entry_id,
            error_context=error_context,
            user_action="Error during report generation",
            system_state={}
        )
        
        # Create minimal diagnostic data
        diagnostic_data = DiagnosticData(
            ha_version=HA_VERSION,
            integration_version=VERSION,
            domain_consistency=False,
            file_permissions={},
            import_status={},
            dependency_status={},
            config_flow_class_found=False,
            manifest_valid=False,
            error_details=[f"Report generation failed: {str(error)}"],
            system_info={},
            integration_info={}
        )
        
        error_report = f"""
🚨 TROUBLESHOOTING REPORT GENERATION FAILED
==========================================

An error occurred while generating the comprehensive troubleshooting report.

Error: {str(error)}
Timestamp: {context.timestamp}
Entry ID: {entry_id or 'N/A'}
Context: {error_context or 'N/A'}

IMMEDIATE ACTIONS:
• Check Home Assistant logs for detailed error messages
• Ensure the integration is properly installed
• Try restarting Home Assistant
• Consider reinstalling the integration

If the problem persists, please report this issue with the error details above.
"""
        
        return TroubleshootingReport(
            context=context,
            diagnostic_data=diagnostic_data,
            validation_results={},
            component_health={},
            error_analysis={"severity_assessment": "critical"},
            recommendations=["Check logs", "Restart Home Assistant", "Reinstall integration"],
            step_by_step_guide=["Check error details above"],
            common_solutions={},
            formatted_report=error_report
        )


class TroubleshootingManager:
    """Legacy troubleshooting manager for backward compatibility."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the troubleshooting manager."""
        self.hass = hass
    
    async def _create_step_by_step_guide(
        self,
        error_analysis: Dict[str, Any],
        recommendations: List[str]
    ) -> List[str]:
        """Create step-by-step troubleshooting guide."""
        guide_steps = []
        
        try:
            severity = error_analysis.get("severity_assessment", "unknown")
            error_categories = error_analysis.get("error_categories", {})
            
            # Step 1: Initial assessment
            guide_steps.extend([
                "📋 STEP 1: Initial Assessment",
                "• Review the troubleshooting report above",
                "• Note the overall severity level",
                "• Identify the primary error categories",
                "• Back up your current configuration if making changes",
                ""
            ])
            
            # Step 2: Critical issues first
            if severity == "critical":
                guide_steps.extend([
                    "🚨 STEP 2: Address Critical Issues (PRIORITY)",
                    "• Stop using the integration immediately",
                    "• Check Home Assistant logs for detailed errors",
                    "• Note any recent changes to your system",
                    "• Prepare to reinstall if necessary",
                    ""
                ])
            
            # Step 3: Domain and configuration issues
            if error_categories.get("configuration_issues"):
                guide_steps.extend([
                    "🔧 STEP 3: Fix Configuration Issues",
                    "• Open the integration's manifest.json file",
                    "• Verify 'config_flow': true is present",
                    "• Check domain consistency across files",
                    "• Validate JSON syntax",
                    "• Restart Home Assistant after changes",
                    ""
                ])
            
            # Step 4: Permission and file system issues
            if error_categories.get("permission_issues") or error_categories.get("installation_issues"):
                guide_steps.extend([
                    "🔐 STEP 4: Fix File System and Permission Issues",
                    "• Check integration directory exists and is readable",
                    "• Verify Home Assistant process can access files",
                    "• Fix any permission issues found",
                    "• Reinstall integration if files are corrupted",
                    "• Restart Home Assistant",
                    ""
                ])
            
            # Step 5: Dependencies
            if error_categories.get("dependency_issues"):
                guide_steps.extend([
                    "📦 STEP 5: Resolve Dependency Issues",
                    "• Check which dependencies are missing",
                    "• Install missing Home Assistant components",
                    "• Verify component versions are compatible",
                    "• Restart Home Assistant after installing dependencies",
                    ""
                ])
            
            # Step 6: Code and import issues
            if error_categories.get("code_issues"):
                guide_steps.extend([
                    "💻 STEP 6: Fix Code and Import Issues",
                    "• Check for syntax errors in integration files",
                    "• Verify all required modules are present",
                    "• Reinstall integration if code is corrupted",
                    "• Check integration version compatibility",
                    ""
                ])
            
            # Step 7: Testing and verification
            guide_steps.extend([
                "✅ STEP 7: Test and Verify",
                "• Restart Home Assistant completely",
                "• Try adding the integration through the UI",
                "• Check logs for any remaining errors",
                "• Run diagnostics again to verify fixes",
                "• Test basic integration functionality",
                ""
            ])
            
            # Step 8: Additional help
            guide_steps.extend([
                "🆘 STEP 8: If Issues Persist",
                "• Generate a new troubleshooting report",
                "• Check the integration's documentation",
                "• Search for similar issues in the community",
                "• Consider reporting the issue with diagnostic data",
                "• Try a clean reinstall as last resort",
                ""
            ])
            
        except Exception as e:
            _LOGGER.error("Error creating step-by-step guide: %s", e)
            guide_steps.append(f"⚠️ Error creating guide: {str(e)}")
        
        return guide_steps
    
    def _get_enhanced_common_solutions(self) -> Dict[str, List[str]]:
        """Get enhanced common solutions database."""
        return {
            "config_flow_not_loading": [
                "Check manifest.json has 'config_flow': true",
                "Verify ConfigFlow class exists in config_flow.py",
                "Ensure domain consistency across all files",
                "Check config_flow.py imports are correct",
                "Restart Home Assistant after fixes"
            ],
            "invalid_handler_specified": [
                "Fix domain mismatch between manifest.json and const.py",
                "Ensure ConfigFlow class inherits from config_entries.ConfigFlow",
                "Check that async_step_user method is implemented",
                "Verify integration is properly installed",
                "Clear browser cache and try again"
            ],
            "integration_not_loading": [
                "Check Home Assistant logs for specific error messages",
                "Verify all required files are present and readable",
                "Ensure dependencies are installed and available",
                "Check for Python syntax errors in integration files",
                "Restart Home Assistant and check startup logs"
            ],
            "entities_not_found": [
                "Verify referenced entities exist in Home Assistant",
                "Check entity naming and domains are correct",
                "Remove references to deleted or renamed entities",
                "Ensure entities are properly configured and available",
                "Check entity states are updating regularly"
            ],
            "storage_issues": [
                "Check Home Assistant has write permissions to config directory",
                "Ensure sufficient disk space is available",
                "Verify storage files are not corrupted",
                "Check for file system errors",
                "Restart Home Assistant to reset storage connections"
            ],
            "presence_detection_issues": [
                "Verify presence entities are updating regularly",
                "Check presence entity states and last_updated times",
                "Adjust presence timeout if entities update infrequently",
                "Ensure presence entities are of appropriate types",
                "Check for network connectivity issues"
            ],
            "buffer_not_working": [
                "Check buffer configuration values are valid",
                "Ensure buffer is enabled in integration settings",
                "Verify entity states are being tracked properly",
                "Check for manual changes that override buffer logic",
                "Review buffer timeout and delta settings"
            ],
            "performance_issues": [
                "Enable performance monitoring to identify bottlenecks",
                "Check for excessive debug logging",
                "Review number of tracked entities",
                "Consider reducing update frequency for non-critical entities",
                "Monitor system resource usage"
            ],
            "permission_denied": [
                "Check Home Assistant process user permissions",
                "Verify integration directory is readable",
                "Fix file ownership if necessary",
                "Check SELinux or AppArmor policies if applicable",
                "Reinstall integration with correct permissions"
            ],
            "import_errors": [
                "Check for missing integration files",
                "Verify Python syntax in all modules",
                "Ensure all dependencies are installed",
                "Check for circular import issues",
                "Reinstall integration if files are corrupted"
            ],
            "manifest_errors": [
                "Validate JSON syntax in manifest.json",
                "Ensure all required fields are present",
                "Check domain matches integration directory name",
                "Verify version format is correct",
                "Ensure dependencies list is valid"
            ]
        }

    async def run_comprehensive_diagnostics(self, entry_id: str) -> Dict[str, Any]:
        """Run comprehensive diagnostics for a specific config entry."""
        _LOGGER.info("Running comprehensive diagnostics for entry %s", entry_id)
        
        diagnostics = {
            "entry_id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "overall_health": "unknown",
            "components": {},
            "common_issues": [],
            "recommendations": [],
            "performance_summary": {},
            "configuration_issues": [],
            "entity_issues": []
        }
        
        try:
            # Get entry data
            entry_data = self.hass.data.get(DOMAIN, {}).get(entry_id)
            if not entry_data:
                diagnostics["overall_health"] = "critical"
                diagnostics["common_issues"].append("Entry data not found - integration may not be properly initialized")
                diagnostics["recommendations"].append("Restart Home Assistant and check logs for initialization errors")
                return diagnostics
            
            # Test each component
            await self._diagnose_presence_manager(entry_data, diagnostics)
            await self._diagnose_buffer_manager(entry_data, diagnostics)
            await self._diagnose_schedule_manager(entry_data, diagnostics)
            await self._diagnose_storage_service(entry_data, diagnostics)
            await self._diagnose_logging_manager(entry_data, diagnostics)
            
            # Analyze overall health
            self._analyze_overall_health(diagnostics)
            
            # Generate summary recommendations
            self._generate_summary_recommendations(diagnostics)
            
            _LOGGER.info("Comprehensive diagnostics completed for entry %s", entry_id)
            
        except Exception as e:
            _LOGGER.error("Error during comprehensive diagnostics: %s", e, exc_info=True)
            diagnostics["overall_health"] = "error"
            diagnostics["common_issues"].append(f"Diagnostic process failed: {str(e)}")
        
        return diagnostics
    
    async def _diagnose_presence_manager(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose presence manager issues."""
        presence_manager = entry_data.get("presence_manager")
        if not presence_manager:
            diagnostics["components"]["presence_manager"] = {
                "status": "missing",
                "issues": ["PresenceManager not found in entry data"]
            }
            return
        
        try:
            # Run presence manager diagnostics
            pm_diagnostics = await presence_manager.run_diagnostics()
            
            # Extract key information
            component_info = {
                "status": "healthy" if pm_diagnostics.get("troubleshooting", {}).get("health_score", 0) > 70 else "issues",
                "health_score": pm_diagnostics.get("troubleshooting", {}).get("health_score", 0),
                "entities_configured": len(pm_diagnostics.get("configuration", {}).get("presence_entities", [])),
                "current_mode": pm_diagnostics.get("configuration", {}).get("current_mode", "unknown"),
                "issues": pm_diagnostics.get("troubleshooting", {}).get("common_issues", []),
                "performance": pm_diagnostics.get("performance_metrics", {})
            }
            
            diagnostics["components"]["presence_manager"] = component_info
            
            # Add to overall issues
            diagnostics["common_issues"].extend(component_info["issues"])
            
        except Exception as e:
            diagnostics["components"]["presence_manager"] = {
                "status": "error",
                "issues": [f"Failed to diagnose presence manager: {str(e)}"]
            }
    
    async def _diagnose_buffer_manager(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose buffer manager issues."""
        buffer_manager = entry_data.get("buffer_manager")
        if not buffer_manager:
            diagnostics["components"]["buffer_manager"] = {
                "status": "missing",
                "issues": ["BufferManager not found in entry data"]
            }
            return
        
        try:
            # Run buffer manager diagnostics
            bm_diagnostics = await buffer_manager.run_diagnostics()
            
            # Extract key information
            component_info = {
                "status": "healthy" if bm_diagnostics.get("troubleshooting", {}).get("health_score", 0) > 70 else "issues",
                "health_score": bm_diagnostics.get("troubleshooting", {}).get("health_score", 0),
                "entities_tracked": bm_diagnostics.get("manager_status", {}).get("entities_tracked", 0),
                "global_buffer_enabled": bm_diagnostics.get("manager_status", {}).get("global_buffer_enabled", False),
                "issues": bm_diagnostics.get("troubleshooting", {}).get("common_issues", []),
                "performance": bm_diagnostics.get("performance_metrics", {})
            }
            
            diagnostics["components"]["buffer_manager"] = component_info
            
            # Add to overall issues
            diagnostics["common_issues"].extend(component_info["issues"])
            
        except Exception as e:
            diagnostics["components"]["buffer_manager"] = {
                "status": "error",
                "issues": [f"Failed to diagnose buffer manager: {str(e)}"]
            }
    
    async def _diagnose_schedule_manager(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose schedule manager issues."""
        schedule_manager = entry_data.get("schedule_manager")
        if not schedule_manager:
            diagnostics["components"]["schedule_manager"] = {
                "status": "missing",
                "issues": ["ScheduleManager not found in entry data"]
            }
            return
        
        try:
            # Test basic schedule manager functionality
            component_info = {
                "status": "healthy",
                "issues": []
            }
            
            # Test schedule loading
            try:
                # This is a basic test - in a real implementation you might have more specific tests
                if hasattr(schedule_manager, 'get_tracked_entities'):
                    tracked_entities = schedule_manager.get_tracked_entities()
                    component_info["entities_tracked"] = len(tracked_entities)
                else:
                    component_info["entities_tracked"] = 0
            except Exception as e:
                component_info["issues"].append(f"Failed to get tracked entities: {str(e)}")
                component_info["status"] = "issues"
            
            diagnostics["components"]["schedule_manager"] = component_info
            diagnostics["common_issues"].extend(component_info["issues"])
            
        except Exception as e:
            diagnostics["components"]["schedule_manager"] = {
                "status": "error",
                "issues": [f"Failed to diagnose schedule manager: {str(e)}"]
            }
    
    async def _diagnose_storage_service(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose storage service issues."""
        storage_service = entry_data.get("storage_service")
        if not storage_service:
            diagnostics["components"]["storage_service"] = {
                "status": "missing",
                "issues": ["StorageService not found in entry data"]
            }
            return
        
        try:
            component_info = {
                "status": "healthy",
                "issues": []
            }
            
            # Test storage loading
            try:
                schedule_data = await storage_service.load_schedules()
                component_info["has_data"] = schedule_data is not None
                if schedule_data:
                    component_info["data_version"] = getattr(schedule_data, 'version', 'unknown')
                    component_info["entities_in_data"] = len(getattr(schedule_data, 'entities_tracked', []))
            except Exception as e:
                component_info["issues"].append(f"Failed to load schedules: {str(e)}")
                component_info["status"] = "issues"
            
            # Test storage saving (with a dummy save to test permissions)
            try:
                if hasattr(storage_service, '_store'):
                    # Just test that we can access the store
                    store = storage_service._store
                    component_info["store_available"] = store is not None
                else:
                    component_info["store_available"] = False
            except Exception as e:
                component_info["issues"].append(f"Storage access test failed: {str(e)}")
                component_info["status"] = "issues"
            
            diagnostics["components"]["storage_service"] = component_info
            diagnostics["common_issues"].extend(component_info["issues"])
            
        except Exception as e:
            diagnostics["components"]["storage_service"] = {
                "status": "error",
                "issues": [f"Failed to diagnose storage service: {str(e)}"]
            }
    
    async def _diagnose_logging_manager(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose logging manager issues."""
        logging_manager = entry_data.get("logging_manager")
        if not logging_manager:
            diagnostics["components"]["logging_manager"] = {
                "status": "missing",
                "issues": ["LoggingManager not found - enhanced logging unavailable"]
            }
            return
        
        try:
            component_info = {
                "status": "healthy",
                "issues": []
            }
            
            # Get logging status
            debug_status = logging_manager.get_debug_status()
            component_info["logging_level"] = debug_status.get("logging_level", "unknown")
            component_info["debug_enabled"] = any(debug_status.get("debug_flags", {}).values())
            component_info["performance_monitoring"] = debug_status.get("performance_monitoring", False)
            component_info["file_logging"] = debug_status.get("file_logging", False)
            
            diagnostics["components"]["logging_manager"] = component_info
            
        except Exception as e:
            diagnostics["components"]["logging_manager"] = {
                "status": "error",
                "issues": [f"Failed to diagnose logging manager: {str(e)}"]
            }
    
    def _analyze_overall_health(self, diagnostics: Dict[str, Any]) -> None:
        """Analyze overall system health based on component diagnostics."""
        components = diagnostics.get("components", {})
        
        # Count component statuses
        healthy_count = sum(1 for comp in components.values() if comp.get("status") == "healthy")
        issues_count = sum(1 for comp in components.values() if comp.get("status") == "issues")
        error_count = sum(1 for comp in components.values() if comp.get("status") == "error")
        missing_count = sum(1 for comp in components.values() if comp.get("status") == "missing")
        
        total_components = len(components)
        
        # Determine overall health
        if error_count > 0 or missing_count > 2:  # Allow some missing components
            diagnostics["overall_health"] = "critical"
        elif issues_count > total_components // 2:
            diagnostics["overall_health"] = "poor"
        elif issues_count > 0:
            diagnostics["overall_health"] = "fair"
        else:
            diagnostics["overall_health"] = "good"
        
        # Add health summary
        diagnostics["health_summary"] = {
            "total_components": total_components,
            "healthy": healthy_count,
            "issues": issues_count,
            "errors": error_count,
            "missing": missing_count,
            "health_percentage": (healthy_count / max(total_components, 1)) * 100
        }
    
    def _generate_summary_recommendations(self, diagnostics: Dict[str, Any]) -> None:
        """Generate summary recommendations based on all diagnostic results."""
        recommendations = []
        overall_health = diagnostics.get("overall_health", "unknown")
        
        if overall_health == "critical":
            recommendations.extend([
                "Critical issues detected - integration may not function properly",
                "Check Home Assistant logs for detailed error messages",
                "Consider removing and re-adding the integration",
                "Ensure Home Assistant has sufficient disk space and permissions"
            ])
        elif overall_health == "poor":
            recommendations.extend([
                "Multiple issues detected - some features may not work correctly",
                "Review component-specific issues and address configuration problems",
                "Check entity configurations and ensure all referenced entities exist"
            ])
        elif overall_health == "fair":
            recommendations.extend([
                "Minor issues detected - integration should work but may have limitations",
                "Review and fix configuration validation errors",
                "Consider enabling debug logging to monitor for additional issues"
            ])
        else:
            recommendations.extend([
                "Integration appears to be functioning normally",
                "Consider enabling performance monitoring if experiencing slowdowns",
                "Regular diagnostic checks can help identify issues early"
            ])
        
        # Add specific recommendations based on common issues
        common_issues = diagnostics.get("common_issues", [])
        
        if any("storage" in issue.lower() for issue in common_issues):
            recommendations.append("Check Home Assistant storage permissions and available disk space")
        
        if any("entity" in issue.lower() and "not found" in issue.lower() for issue in common_issues):
            recommendations.append("Review entity configurations and remove references to non-existent entities")
        
        if any("timeout" in issue.lower() or "stale" in issue.lower() for issue in common_issues):
            recommendations.append("Check network connectivity and entity update frequencies")
        
        # Remove duplicates and add to diagnostics
        diagnostics["recommendations"] = list(set(recommendations))
    
    def generate_troubleshooting_report(self, diagnostics: Dict[str, Any]) -> str:
        """Generate a human-readable troubleshooting report."""
        report_lines = []
        
        # Header
        report_lines.append("=== Roost Scheduler Troubleshooting Report ===")
        report_lines.append(f"Generated: {diagnostics.get('timestamp', 'unknown')}")
        report_lines.append(f"Entry ID: {diagnostics.get('entry_id', 'unknown')}")
        report_lines.append(f"Overall Health: {diagnostics.get('overall_health', 'unknown').upper()}")
        report_lines.append("")
        
        # Health Summary
        health_summary = diagnostics.get("health_summary", {})
        if health_summary:
            report_lines.append("Health Summary:")
            report_lines.append(f"  Total Components: {health_summary.get('total_components', 0)}")
            report_lines.append(f"  Healthy: {health_summary.get('healthy', 0)}")
            report_lines.append(f"  With Issues: {health_summary.get('issues', 0)}")
            report_lines.append(f"  Errors: {health_summary.get('errors', 0)}")
            report_lines.append(f"  Missing: {health_summary.get('missing', 0)}")
            report_lines.append(f"  Health Percentage: {health_summary.get('health_percentage', 0):.1f}%")
            report_lines.append("")
        
        # Component Status
        components = diagnostics.get("components", {})
        if components:
            report_lines.append("Component Status:")
            for component_name, component_info in components.items():
                status = component_info.get("status", "unknown").upper()
                report_lines.append(f"  {component_name}: {status}")
                
                # Add component-specific details
                if "health_score" in component_info:
                    report_lines.append(f"    Health Score: {component_info['health_score']}")
                
                if "entities_configured" in component_info:
                    report_lines.append(f"    Entities Configured: {component_info['entities_configured']}")
                
                if "entities_tracked" in component_info:
                    report_lines.append(f"    Entities Tracked: {component_info['entities_tracked']}")
                
                # Add issues
                issues = component_info.get("issues", [])
                if issues:
                    report_lines.append("    Issues:")
                    for issue in issues:
                        report_lines.append(f"      - {issue}")
            
            report_lines.append("")
        
        # Common Issues
        common_issues = diagnostics.get("common_issues", [])
        if common_issues:
            report_lines.append("Common Issues Found:")
            for issue in common_issues:
                report_lines.append(f"  - {issue}")
            report_lines.append("")
        
        # Recommendations
        recommendations = diagnostics.get("recommendations", [])
        if recommendations:
            report_lines.append("Recommendations:")
            for recommendation in recommendations:
                report_lines.append(f"  - {recommendation}")
            report_lines.append("")
        
        # Performance Summary
        performance_summary = diagnostics.get("performance_summary", {})
        if performance_summary:
            report_lines.append("Performance Summary:")
            for metric, value in performance_summary.items():
                report_lines.append(f"  {metric}: {value}")
            report_lines.append("")
        
        report_lines.append("=== End of Report ===")
        
        return "\n".join(report_lines)
    
    async def quick_health_check(self, entry_id: str) -> Tuple[str, List[str]]:
        """Perform a quick health check and return status and critical issues."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(entry_id)
            if not entry_data:
                return "critical", ["Integration not properly initialized"]
            
            critical_issues = []
            
            # Check critical components
            required_components = ["storage_service", "schedule_manager", "presence_manager", "buffer_manager"]
            for component in required_components:
                if component not in entry_data or entry_data[component] is None:
                    critical_issues.append(f"Missing {component}")
            
            # Quick storage test
            storage_service = entry_data.get("storage_service")
            if storage_service:
                try:
                    await storage_service.load_schedules()
                except Exception as e:
                    critical_issues.append(f"Storage access failed: {str(e)}")
            
            # Determine status
            if len(critical_issues) > 2:
                return "critical", critical_issues
            elif len(critical_issues) > 0:
                return "issues", critical_issues
            else:
                return "healthy", []
                
        except Exception as e:
            return "error", [f"Health check failed: {str(e)}"]
    
    def get_common_solutions(self) -> Dict[str, List[str]]:
        """Get common solutions for typical issues."""
        return {
            "integration_not_loading": [
                "Check Home Assistant logs for specific error messages",
                "Ensure all required dependencies are installed",
                "Restart Home Assistant",
                "Check available disk space and permissions"
            ],
            "entities_not_found": [
                "Verify that referenced entities exist in Home Assistant",
                "Check entity naming and domains",
                "Remove references to deleted entities",
                "Ensure entities are properly configured and available"
            ],
            "storage_issues": [
                "Check Home Assistant storage permissions",
                "Ensure sufficient disk space is available",
                "Check for file system errors",
                "Restart Home Assistant to reset storage connections"
            ],
            "presence_detection_issues": [
                "Verify presence entities are updating regularly",
                "Check presence entity states and last_updated times",
                "Adjust presence timeout if entities update infrequently",
                "Ensure presence entities are of appropriate types (device_tracker, person, etc.)"
            ],
            "buffer_not_working": [
                "Check buffer configuration values (time and delta)",
                "Ensure buffer is enabled in configuration",
                "Verify entity states are being tracked properly",
                "Check for manual changes that might affect buffer logic"
            ],
            "performance_issues": [
                "Enable performance monitoring to identify bottlenecks",
                "Check for excessive debug logging",
                "Review entity count and complexity",
                "Consider reducing update frequency for non-critical entities"
            ]
        }