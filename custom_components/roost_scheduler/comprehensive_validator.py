"""Comprehensive validation system integrating manifest, dependency, and version compatibility validation."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .manifest_validator import ManifestValidator, ManifestValidationResult
from .dependency_validator import DependencyValidator, DependencyValidationResult
from .version_compatibility_validator import VersionCompatibilityValidator, VersionCompatibilityResult

_LOGGER = logging.getLogger(__name__)


@dataclass
class ComprehensiveValidationResult:
    """Result of comprehensive validation."""
    valid: bool
    overall_status: str  # "valid", "warnings", "errors"
    manifest_result: ManifestValidationResult
    dependency_result: DependencyValidationResult
    version_result: VersionCompatibilityResult
    summary: Dict[str, Any]
    recommendations: List[str]


class ComprehensiveValidator:
    """Comprehensive validator that integrates all validation systems."""

    def __init__(self, hass: HomeAssistant, integration_path: Optional[Path] = None) -> None:
        """Initialize the comprehensive validator."""
        self.hass = hass
        self.integration_path = integration_path or self._get_integration_path()
        
        # Initialize individual validators
        self.manifest_validator = ManifestValidator(hass, self.integration_path)
        self.dependency_validator = DependencyValidator(hass, self.integration_path)
        self.version_validator = VersionCompatibilityValidator(hass, self.integration_path)

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        current_file = Path(__file__)
        return current_file.parent

    async def validate_all(self) -> ComprehensiveValidationResult:
        """Run all validation checks and provide comprehensive results."""
        _LOGGER.info("Starting comprehensive validation for %s", DOMAIN)
        
        try:
            # Run all validations
            manifest_result = await self.manifest_validator.validate_manifest()
            dependency_result = await self.dependency_validator.validate_dependencies()
            version_result = await self.version_validator.validate_version_compatibility()

            # Analyze overall status
            overall_status, valid = self._analyze_overall_status(
                manifest_result, dependency_result, version_result
            )

            # Generate summary
            summary = self._generate_summary(manifest_result, dependency_result, version_result)

            # Generate comprehensive recommendations
            recommendations = self._generate_comprehensive_recommendations(
                manifest_result, dependency_result, version_result
            )

            return ComprehensiveValidationResult(
                valid=valid,
                overall_status=overall_status,
                manifest_result=manifest_result,
                dependency_result=dependency_result,
                version_result=version_result,
                summary=summary,
                recommendations=recommendations
            )

        except Exception as e:
            _LOGGER.error("Comprehensive validation failed: %s", e)
            
            # Return error result
            return ComprehensiveValidationResult(
                valid=False,
                overall_status="errors",
                manifest_result=ManifestValidationResult(valid=False, issues=[], warnings=[f"Validation failed: {str(e)}"]),
                dependency_result=DependencyValidationResult(valid=False, dependencies={}, imports={}, conflicts=[], warnings=[f"Validation failed: {str(e)}"], recommendations=[]),
                version_result=VersionCompatibilityResult(compatible=False, overall_compatibility_level="incompatible", home_assistant=None, integration=None, dependencies={}, issues=[], warnings=[f"Validation failed: {str(e)}"], recommendations=[]),
                summary={"error": str(e)},
                recommendations=[f"Fix validation error: {str(e)}"]
            )

    def _analyze_overall_status(
        self, 
        manifest_result: ManifestValidationResult,
        dependency_result: DependencyValidationResult,
        version_result: VersionCompatibilityResult
    ) -> tuple[str, bool]:
        """Analyze overall validation status."""
        # Check for critical errors
        has_critical_errors = (
            not manifest_result.valid or
            not dependency_result.valid or
            not version_result.compatible
        )

        if has_critical_errors:
            return "errors", False

        # Check for warnings
        has_warnings = (
            bool(manifest_result.warnings) or
            bool(dependency_result.warnings) or
            bool(version_result.warnings) or
            any(issue.severity == "warning" for issue in manifest_result.issues) or
            any(issue.severity == "warning" for issue in version_result.issues)
        )

        if has_warnings:
            return "warnings", True

        return "valid", True

    def _generate_summary(
        self,
        manifest_result: ManifestValidationResult,
        dependency_result: DependencyValidationResult,
        version_result: VersionCompatibilityResult
    ) -> Dict[str, Any]:
        """Generate a comprehensive summary."""
        return {
            "manifest": {
                "valid": manifest_result.valid,
                "issues_count": len(manifest_result.issues),
                "warnings_count": len(manifest_result.warnings),
                "domain": manifest_result.manifest_data.get("domain") if manifest_result.manifest_data else None,
                "version": manifest_result.manifest_data.get("version") if manifest_result.manifest_data else None,
                "config_flow_enabled": manifest_result.manifest_data.get("config_flow") if manifest_result.manifest_data else None
            },
            "dependencies": {
                "valid": dependency_result.valid,
                "total_dependencies": len(dependency_result.dependencies),
                "available_dependencies": sum(1 for dep in dependency_result.dependencies.values() if dep.available),
                "failed_imports": sum(1 for imp in dependency_result.imports.values() if not imp.importable),
                "conflicts_count": len(dependency_result.conflicts)
            },
            "version_compatibility": {
                "compatible": version_result.compatible,
                "compatibility_level": version_result.overall_compatibility_level,
                "ha_version": version_result.home_assistant.current_version if version_result.home_assistant else None,
                "integration_version": version_result.integration.current_version if version_result.integration else None,
                "issues_count": len(version_result.issues)
            },
            "overall": {
                "validation_passed": self._analyze_overall_status(manifest_result, dependency_result, version_result)[1],
                "total_issues": len(manifest_result.issues) + len(version_result.issues),
                "total_warnings": len(manifest_result.warnings) + len(dependency_result.warnings) + len(version_result.warnings)
            }
        }

    def _generate_comprehensive_recommendations(
        self,
        manifest_result: ManifestValidationResult,
        dependency_result: DependencyValidationResult,
        version_result: VersionCompatibilityResult
    ) -> List[str]:
        """Generate comprehensive recommendations based on all validation results."""
        recommendations = []

        # Manifest recommendations
        for issue in manifest_result.issues:
            if issue.fix_suggestion:
                recommendations.append(f"Manifest: {issue.fix_suggestion}")

        # Dependency recommendations
        recommendations.extend([f"Dependencies: {rec}" for rec in dependency_result.recommendations])

        # Version compatibility recommendations
        recommendations.extend([f"Version: {rec}" for rec in version_result.recommendations])

        # Cross-cutting recommendations
        if not manifest_result.valid and not dependency_result.valid:
            recommendations.append("Fix manifest issues first, then re-validate dependencies")

        if not version_result.compatible:
            recommendations.append("Address version compatibility issues before proceeding with other fixes")

        # Priority recommendations
        priority_recommendations = []
        
        # Critical issues first
        if not manifest_result.valid:
            priority_recommendations.append("CRITICAL: Fix manifest.json validation errors")
        
        if not dependency_result.valid:
            priority_recommendations.append("CRITICAL: Resolve missing required dependencies")
        
        if not version_result.compatible:
            priority_recommendations.append("CRITICAL: Address version compatibility issues")

        return priority_recommendations + recommendations

    def get_comprehensive_report(self, result: ComprehensiveValidationResult) -> str:
        """Generate a comprehensive validation report."""
        lines = [
            "=" * 80,
            "COMPREHENSIVE INTEGRATION VALIDATION REPORT",
            "=" * 80,
            f"Integration: {DOMAIN}",
            f"Overall Status: {'✓ VALID' if result.valid else '✗ INVALID'} ({result.overall_status.upper()})",
            f"Validation Date: {self._get_current_timestamp()}",
            "",
            "SUMMARY:",
            "-" * 8
        ]

        # Add summary information
        summary = result.summary
        lines.extend([
            f"Manifest Valid: {'✓' if summary['manifest']['valid'] else '✗'}",
            f"Dependencies Valid: {'✓' if summary['dependencies']['valid'] else '✗'}",
            f"Version Compatible: {'✓' if summary['version_compatibility']['compatible'] else '✗'}",
            f"Total Issues: {summary['overall']['total_issues']}",
            f"Total Warnings: {summary['overall']['total_warnings']}",
            ""
        ])

        # Manifest section
        lines.extend([
            "MANIFEST VALIDATION:",
            "-" * 20,
            self.manifest_validator.get_validation_summary(result.manifest_result),
            ""
        ])

        # Dependencies section
        lines.extend([
            "DEPENDENCY VALIDATION:",
            "-" * 21,
            self.dependency_validator.get_validation_summary(result.dependency_result),
            ""
        ])

        # Version compatibility section
        lines.extend([
            "VERSION COMPATIBILITY:",
            "-" * 22,
            self.version_validator.get_compatibility_summary(result.version_result),
            ""
        ])

        # Recommendations section
        if result.recommendations:
            lines.extend([
                "COMPREHENSIVE RECOMMENDATIONS:",
                "-" * 30
            ])
            for i, rec in enumerate(result.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        # Next steps
        lines.extend([
            "NEXT STEPS:",
            "-" * 11
        ])
        
        if result.valid:
            lines.extend([
                "✓ All validations passed successfully",
                "✓ Integration should work correctly",
                "• Consider addressing any warnings for optimal performance"
            ])
        else:
            lines.extend([
                "1. Address critical issues first (marked as CRITICAL above)",
                "2. Fix manifest validation errors",
                "3. Resolve dependency issues",
                "4. Address version compatibility problems",
                "5. Re-run validation to verify fixes"
            ])

        lines.extend([
            "",
            "=" * 80,
            "END OF COMPREHENSIVE VALIDATION REPORT",
            "=" * 80
        ])

        return "\n".join(lines)

    def _get_current_timestamp(self) -> str:
        """Get current timestamp for reporting."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def quick_validation(self) -> bool:
        """Run a quick validation check for basic functionality."""
        try:
            # Quick manifest check
            manifest_path = self.integration_path / "manifest.json"
            if not manifest_path.exists():
                return False

            # Quick dependency check
            from .const import REQUIRED_DOMAINS
            for dep in REQUIRED_DOMAINS:
                try:
                    await self.hass.async_add_executor_job(
                        __import__, f"homeassistant.components.{dep}"
                    )
                except ImportError:
                    return False

            # Quick version check
            from homeassistant.const import __version__ as HA_VERSION
            from .const import MIN_HA_VERSION
            if self._compare_versions(HA_VERSION, MIN_HA_VERSION) < 0:
                return False

            return True

        except Exception as e:
            _LOGGER.debug("Quick validation failed: %s", e)
            return False

    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1."""
        try:
            def parse_version(v):
                return tuple(map(int, v.split('.')))
            
            v1 = parse_version(version1)
            v2 = parse_version(version2)
            
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            else:
                return 0
                
        except Exception:
            return 0  # Assume equal if parsing fails