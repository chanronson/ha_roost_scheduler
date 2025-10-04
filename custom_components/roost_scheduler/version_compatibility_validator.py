"""Version compatibility validation for Roost Scheduler integration."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.loader import async_get_integration

from .const import DOMAIN, MIN_HA_VERSION, RECOMMENDED_HA_VERSION
from .version import VERSION, MIN_SUPPORTED_VERSION, VERSION_HISTORY

_LOGGER = logging.getLogger(__name__)


@dataclass
class VersionInfo:
    """Version information for a component."""
    name: str
    current_version: Optional[str]
    required_version: Optional[str]
    recommended_version: Optional[str]
    compatible: bool
    compatibility_level: str  # "full", "partial", "incompatible"
    issues: List[str]
    warnings: List[str]


@dataclass
class CompatibilityIssue:
    """Represents a version compatibility issue."""
    component: str
    issue_type: str
    severity: str  # "error", "warning", "info"
    message: str
    current_version: Optional[str] = None
    required_version: Optional[str] = None
    fix_suggestion: Optional[str] = None


@dataclass
class VersionCompatibilityResult:
    """Result of version compatibility validation."""
    compatible: bool
    overall_compatibility_level: str
    home_assistant: VersionInfo
    integration: VersionInfo
    dependencies: Dict[str, VersionInfo]
    issues: List[CompatibilityIssue]
    warnings: List[str]
    recommendations: List[str]


class VersionCompatibilityValidator:
    """Validates version compatibility across the integration ecosystem."""

    # Known Home Assistant version compatibility matrix
    HA_COMPATIBILITY_MATRIX = {
        "2023.1.0": {"status": "minimum", "notes": "Minimum supported version"},
        "2023.6.0": {"status": "stable", "notes": "Stable support"},
        "2023.12.0": {"status": "stable", "notes": "Stable support"},
        "2024.1.0": {"status": "recommended", "notes": "Recommended version"},
        "2024.6.0": {"status": "latest", "notes": "Latest stable"},
        "2024.12.0": {"status": "beta", "notes": "Beta support"}
    }

    # Known breaking changes in Home Assistant versions
    BREAKING_CHANGES = {
        "2023.2.0": ["Config flow API changes"],
        "2023.7.0": ["Entity registry changes"],
        "2024.1.0": ["Storage API updates"],
        "2024.6.0": ["WebSocket API changes"]
    }

    # Deprecated features by version
    DEPRECATED_FEATURES = {
        "2023.12.0": ["Legacy config flow methods"],
        "2024.1.0": ["Old storage format"],
        "2024.6.0": ["Legacy entity attributes"]
    }

    def __init__(self, hass: HomeAssistant, integration_path: Optional[Path] = None) -> None:
        """Initialize the version compatibility validator."""
        self.hass = hass
        self.integration_path = integration_path or self._get_integration_path()

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        current_file = Path(__file__)
        return current_file.parent

    async def validate_version_compatibility(self) -> VersionCompatibilityResult:
        """Validate version compatibility comprehensively."""
        _LOGGER.debug("Starting version compatibility validation")
        
        issues = []
        warnings = []
        recommendations = []
        dependencies = {}

        try:
            # Validate Home Assistant version compatibility
            ha_info = await self._validate_home_assistant_version(issues, warnings, recommendations)

            # Validate integration version consistency
            integration_info = await self._validate_integration_version(issues, warnings)

            # Validate dependency versions
            await self._validate_dependency_versions(dependencies, issues, warnings)

            # Check for breaking changes
            await self._check_breaking_changes(issues, warnings)

            # Check for deprecated features
            await self._check_deprecated_features(warnings, recommendations)

            # Validate version format compliance
            await self._validate_version_formats(issues, warnings)

            # Check upgrade/downgrade compatibility
            await self._check_upgrade_compatibility(issues, warnings, recommendations)

        except Exception as e:
            _LOGGER.error("Unexpected error during version compatibility validation: %s", e)
            issues.append(CompatibilityIssue(
                component="validator",
                issue_type="validation_error",
                severity="error",
                message=f"Version compatibility validation failed: {str(e)}"
            ))

        # Determine overall compatibility
        has_errors = any(issue.severity == "error" for issue in issues)
        has_warnings = any(issue.severity == "warning" for issue in issues) or bool(warnings)
        
        if has_errors:
            overall_compatibility = "incompatible"
            compatible = False
        elif has_warnings:
            overall_compatibility = "partial"
            compatible = True
        else:
            overall_compatibility = "full"
            compatible = True

        return VersionCompatibilityResult(
            compatible=compatible,
            overall_compatibility_level=overall_compatibility,
            home_assistant=ha_info,
            integration=integration_info,
            dependencies=dependencies,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations
        )

    async def _validate_home_assistant_version(self, issues: List[CompatibilityIssue], warnings: List[str], recommendations: List[str]) -> VersionInfo:
        """Validate Home Assistant version compatibility."""
        current_ha_version = HA_VERSION
        ha_issues = []
        ha_warnings = []
        
        try:
            # Check minimum version requirement
            if self._compare_versions(current_ha_version, MIN_HA_VERSION) < 0:
                issues.append(CompatibilityIssue(
                    component="home_assistant",
                    issue_type="version_too_old",
                    severity="error",
                    message=f"Home Assistant version {current_ha_version} is below minimum required version {MIN_HA_VERSION}",
                    current_version=current_ha_version,
                    required_version=MIN_HA_VERSION,
                    fix_suggestion=f"Upgrade Home Assistant to version {MIN_HA_VERSION} or later"
                ))
                compatibility_level = "incompatible"
                compatible = False
            else:
                compatible = True
                
                # Check recommended version
                if self._compare_versions(current_ha_version, RECOMMENDED_HA_VERSION) < 0:
                    ha_warnings.append(f"Home Assistant version {current_ha_version} is below recommended version {RECOMMENDED_HA_VERSION}")
                    recommendations.append(f"Consider upgrading to Home Assistant {RECOMMENDED_HA_VERSION} for optimal compatibility")
                    compatibility_level = "partial"
                else:
                    compatibility_level = "full"

            # Check for known compatibility issues
            await self._check_ha_version_specific_issues(current_ha_version, issues, warnings)

        except Exception as e:
            ha_issues.append(f"Error validating Home Assistant version: {str(e)}")
            compatible = False
            compatibility_level = "incompatible"

        return VersionInfo(
            name="Home Assistant",
            current_version=current_ha_version,
            required_version=MIN_HA_VERSION,
            recommended_version=RECOMMENDED_HA_VERSION,
            compatible=compatible,
            compatibility_level=compatibility_level,
            issues=ha_issues,
            warnings=ha_warnings
        )

    async def _validate_integration_version(self, issues: List[CompatibilityIssue], warnings: List[str]) -> VersionInfo:
        """Validate integration version consistency."""
        integration_issues = []
        integration_warnings = []
        
        try:
            # Get version from code
            code_version = VERSION
            
            # Get version from manifest
            manifest_version = await self._get_manifest_version()
            
            # Check version consistency
            if manifest_version and manifest_version != code_version:
                issues.append(CompatibilityIssue(
                    component="integration",
                    issue_type="version_mismatch",
                    severity="error",
                    message=f"Version mismatch: code version ({code_version}) != manifest version ({manifest_version})",
                    current_version=code_version,
                    required_version=manifest_version,
                    fix_suggestion="Update version in const.py or manifest.json to match"
                ))
                compatible = False
                compatibility_level = "incompatible"
            else:
                compatible = True
                compatibility_level = "full"

            # Validate version format
            if not self._is_valid_semantic_version(code_version):
                integration_warnings.append(f"Integration version '{code_version}' doesn't follow semantic versioning")

        except Exception as e:
            integration_issues.append(f"Error validating integration version: {str(e)}")
            compatible = False
            compatibility_level = "incompatible"

        return VersionInfo(
            name="Roost Scheduler",
            current_version=VERSION,
            required_version=None,
            recommended_version=None,
            compatible=compatible,
            compatibility_level=compatibility_level,
            issues=integration_issues,
            warnings=integration_warnings
        )

    async def _validate_dependency_versions(self, dependencies: Dict[str, VersionInfo], issues: List[CompatibilityIssue], warnings: List[str]) -> None:
        """Validate dependency version compatibility."""
        try:
            # Check manifest dependencies
            manifest_path = self.integration_path / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)

                # Check Home Assistant component dependencies
                for dep in manifest_data.get("dependencies", []):
                    dep_info = await self._check_dependency_version(dep)
                    dependencies[dep] = dep_info
                    
                    if not dep_info.compatible:
                        issues.append(CompatibilityIssue(
                            component=dep,
                            issue_type="dependency_incompatible",
                            severity="error",
                            message=f"Dependency '{dep}' is not compatible",
                            fix_suggestion=f"Check {dep} component availability and version"
                        ))

                # Check Python requirements
                for req in manifest_data.get("requirements", []):
                    req_info = await self._check_python_requirement_version(req)
                    dependencies[f"python_{req}"] = req_info

        except Exception as e:
            warnings.append(f"Error validating dependency versions: {str(e)}")

    async def _check_dependency_version(self, dependency: str) -> VersionInfo:
        """Check version compatibility of a Home Assistant dependency."""
        try:
            integration = await async_get_integration(self.hass, dependency)
            
            return VersionInfo(
                name=dependency,
                current_version=getattr(integration, 'version', None),
                required_version=None,
                recommended_version=None,
                compatible=True,
                compatibility_level="full",
                issues=[],
                warnings=[]
            )
            
        except Exception as e:
            return VersionInfo(
                name=dependency,
                current_version=None,
                required_version=None,
                recommended_version=None,
                compatible=False,
                compatibility_level="incompatible",
                issues=[f"Dependency not available: {str(e)}"],
                warnings=[]
            )

    async def _check_python_requirement_version(self, requirement: str) -> VersionInfo:
        """Check version compatibility of a Python requirement."""
        try:
            # Parse requirement (e.g., "voluptuous>=0.11.0")
            import re
            match = re.match(r'^([a-zA-Z0-9_-]+)([><=!]+)?([\d.]+)?', requirement)
            if not match:
                return VersionInfo(
                    name=requirement,
                    current_version=None,
                    required_version=None,
                    recommended_version=None,
                    compatible=False,
                    compatibility_level="incompatible",
                    issues=[f"Invalid requirement format: {requirement}"],
                    warnings=[]
                )

            package_name = match.group(1)
            operator = match.group(2) or ""
            required_version = match.group(3)

            # Try to import and get version
            try:
                module = __import__(package_name)
                current_version = getattr(module, '__version__', None)
                
                # Simple version compatibility check
                compatible = True
                compatibility_level = "full"
                if required_version and current_version:
                    if operator.startswith('>=') and self._compare_versions(current_version, required_version) < 0:
                        compatible = False
                        compatibility_level = "incompatible"
                    elif operator.startswith('==') and current_version != required_version:
                        compatible = False
                        compatibility_level = "incompatible"

                return VersionInfo(
                    name=package_name,
                    current_version=current_version,
                    required_version=required_version,
                    recommended_version=None,
                    compatible=compatible,
                    compatibility_level=compatibility_level,
                    issues=[],
                    warnings=[]
                )

            except ImportError:
                return VersionInfo(
                    name=package_name,
                    current_version=None,
                    required_version=required_version,
                    recommended_version=None,
                    compatible=False,
                    compatibility_level="incompatible",
                    issues=[f"Package {package_name} not installed"],
                    warnings=[]
                )

        except Exception as e:
            return VersionInfo(
                name=requirement,
                current_version=None,
                required_version=None,
                recommended_version=None,
                compatible=False,
                compatibility_level="incompatible",
                issues=[f"Error checking requirement: {str(e)}"],
                warnings=[]
            )

    async def _check_ha_version_specific_issues(self, ha_version: str, issues: List[CompatibilityIssue], warnings: List[str]) -> None:
        """Check for Home Assistant version-specific compatibility issues."""
        # Check for breaking changes
        for version, changes in self.BREAKING_CHANGES.items():
            if self._compare_versions(ha_version, version) >= 0:
                for change in changes:
                    warnings.append(f"Breaking change in HA {version}: {change}")

        # Check for deprecated features
        for version, features in self.DEPRECATED_FEATURES.items():
            if self._compare_versions(ha_version, version) >= 0:
                for feature in features:
                    warnings.append(f"Deprecated in HA {version}: {feature}")

    async def _check_breaking_changes(self, issues: List[CompatibilityIssue], warnings: List[str]) -> None:
        """Check for breaking changes that might affect the integration."""
        current_ha_version = HA_VERSION
        
        # Check if current HA version has breaking changes that affect us
        for version, changes in self.BREAKING_CHANGES.items():
            if self._compare_versions(current_ha_version, version) >= 0:
                for change in changes:
                    # Check if this breaking change affects our integration
                    if self._affects_integration(change):
                        issues.append(CompatibilityIssue(
                            component="home_assistant",
                            issue_type="breaking_change",
                            severity="warning",
                            message=f"Breaking change in HA {version} may affect integration: {change}",
                            current_version=current_ha_version,
                            fix_suggestion="Review integration code for compatibility with this change"
                        ))

    async def _check_deprecated_features(self, warnings: List[str], recommendations: List[str]) -> None:
        """Check for deprecated features that the integration might be using."""
        current_ha_version = HA_VERSION
        
        for version, features in self.DEPRECATED_FEATURES.items():
            if self._compare_versions(current_ha_version, version) >= 0:
                for feature in features:
                    if self._uses_deprecated_feature(feature):
                        warnings.append(f"Integration uses deprecated feature: {feature}")
                        recommendations.append(f"Update integration to avoid deprecated feature: {feature}")

    async def _validate_version_formats(self, issues: List[CompatibilityIssue], warnings: List[str]) -> None:
        """Validate that versions follow proper formatting."""
        # Check integration version format
        if not self._is_valid_semantic_version(VERSION):
            warnings.append(f"Integration version '{VERSION}' doesn't follow semantic versioning")

        # Check manifest version format
        manifest_version = await self._get_manifest_version()
        if manifest_version and not self._is_valid_semantic_version(manifest_version):
            warnings.append(f"Manifest version '{manifest_version}' doesn't follow semantic versioning")

    async def _check_upgrade_compatibility(self, issues: List[CompatibilityIssue], warnings: List[str], recommendations: List[str]) -> None:
        """Check upgrade/downgrade compatibility."""
        try:
            # Check if current version is in supported range
            current_version = VERSION
            
            # Check if we can migrate from minimum supported version
            if self._compare_versions(current_version, MIN_SUPPORTED_VERSION) < 0:
                issues.append(CompatibilityIssue(
                    component="integration",
                    issue_type="version_too_old",
                    severity="error",
                    message=f"Current version {current_version} is below minimum supported version {MIN_SUPPORTED_VERSION}",
                    current_version=current_version,
                    required_version=MIN_SUPPORTED_VERSION,
                    fix_suggestion="Upgrade to a supported version"
                ))

            # Check version history consistency
            if current_version not in VERSION_HISTORY:
                warnings.append(f"Current version {current_version} not found in version history")
                recommendations.append("Add current version to VERSION_HISTORY for proper migration support")

        except Exception as e:
            warnings.append(f"Error checking upgrade compatibility: {str(e)}")

    async def _get_manifest_version(self) -> Optional[str]:
        """Get version from manifest.json."""
        try:
            manifest_path = self.integration_path / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                return manifest_data.get("version")
        except Exception as e:
            _LOGGER.debug("Error reading manifest version: %s", e)
        return None

    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1."""
        try:
            def parse_version(v):
                # Handle pre-release versions (e.g., "1.0.0-beta.1")
                base_version = v.split('-')[0].split('+')[0]
                return tuple(map(int, base_version.split('.')))
            
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

    def _is_valid_semantic_version(self, version: str) -> bool:
        """Check if version follows semantic versioning."""
        pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$'
        return bool(re.match(pattern, version))

    def _affects_integration(self, breaking_change: str) -> bool:
        """Check if a breaking change affects this integration."""
        # Simple keyword matching - in a real implementation, this would be more sophisticated
        integration_keywords = ["config_flow", "entity", "storage", "websocket"]
        return any(keyword in breaking_change.lower() for keyword in integration_keywords)

    def _uses_deprecated_feature(self, feature: str) -> bool:
        """Check if the integration uses a deprecated feature."""
        # Simple keyword matching - in a real implementation, this would analyze the code
        deprecated_keywords = ["legacy", "old", "deprecated"]
        return any(keyword in feature.lower() for keyword in deprecated_keywords)

    def get_compatibility_summary(self, result: VersionCompatibilityResult) -> str:
        """Generate a human-readable compatibility summary."""
        lines = [
            "=" * 70,
            "VERSION COMPATIBILITY SUMMARY",
            "=" * 70,
            f"Overall Status: {'✓ COMPATIBLE' if result.compatible else '✗ INCOMPATIBLE'}",
            f"Compatibility Level: {result.overall_compatibility_level.upper()}",
            f"Issues: {len(result.issues)}",
            f"Warnings: {len(result.warnings)}",
            ""
        ]

        # Home Assistant compatibility
        ha_info = result.home_assistant
        lines.extend([
            "HOME ASSISTANT:",
            "-" * 16,
            f"Current Version: {ha_info.current_version}",
            f"Required Version: {ha_info.required_version}",
            f"Recommended Version: {ha_info.recommended_version}",
            f"Compatibility: {'✓' if ha_info.compatible else '✗'} ({ha_info.compatibility_level})",
            ""
        ])

        # Integration compatibility
        int_info = result.integration
        lines.extend([
            "INTEGRATION:",
            "-" * 12,
            f"Current Version: {int_info.current_version}",
            f"Compatibility: {'✓' if int_info.compatible else '✗'} ({int_info.compatibility_level})",
            ""
        ])

        # Dependencies
        if result.dependencies:
            lines.extend([
                "DEPENDENCIES:",
                "-" * 13
            ])
            for name, dep_info in result.dependencies.items():
                status = "✓" if dep_info.compatible else "✗"
                version_info = f" (v{dep_info.current_version})" if dep_info.current_version else ""
                lines.append(f"{status} {dep_info.name}{version_info} - {dep_info.compatibility_level}")
            lines.append("")

        # Issues
        if result.issues:
            lines.extend([
                "ISSUES:",
                "-" * 7
            ])
            for issue in result.issues:
                severity_symbol = "🔴" if issue.severity == "error" else "🟡" if issue.severity == "warning" else "🔵"
                lines.append(f"{severity_symbol} {issue.component}: {issue.message}")
                if issue.fix_suggestion:
                    lines.append(f"   Fix: {issue.fix_suggestion}")
            lines.append("")

        # Warnings
        if result.warnings:
            lines.extend([
                "WARNINGS:",
                "-" * 9
            ])
            for warning in result.warnings:
                lines.append(f"⚠️  {warning}")
            lines.append("")

        # Recommendations
        if result.recommendations:
            lines.extend([
                "RECOMMENDATIONS:",
                "-" * 16
            ])
            for rec in result.recommendations:
                lines.append(f"💡 {rec}")
            lines.append("")

        lines.extend([
            "=" * 70,
            "END OF COMPATIBILITY SUMMARY",
            "=" * 70
        ])

        return "\n".join(lines)