"""Manifest validation for Roost Scheduler integration."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from homeassistant.core import HomeAssistant
from homeassistant.const import __version__ as HA_VERSION

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ManifestValidationIssue:
    """Represents a manifest validation issue."""
    field: str
    issue_type: str
    message: str
    severity: str  # "error", "warning", "info"
    fix_suggestion: Optional[str] = None


@dataclass
class ManifestValidationResult:
    """Result of manifest validation."""
    valid: bool
    issues: List[ManifestValidationIssue]
    warnings: List[str]
    manifest_data: Optional[Dict[str, Any]] = None


class ManifestValidator:
    """Validates manifest.json configuration for Home Assistant integrations."""

    # Required fields for all integrations
    REQUIRED_FIELDS = {
        "domain": str,
        "name": str,
        "version": str,
        "documentation": str,
        "issue_tracker": str,
        "dependencies": list,
        "codeowners": list,
        "config_flow": bool,
        "iot_class": str,
        "integration_type": str
    }

    # Optional fields that are commonly used
    OPTIONAL_FIELDS = {
        "requirements": list,
        "after_dependencies": list,
        "loggers": list,
        "quality_scale": str,
        "homekit": dict,
        "zeroconf": list,
        "ssdp": list,
        "mqtt": list,
        "dhcp": list,
        "usb": list,
        "bluetooth": list
    }

    # Valid values for specific fields
    VALID_IOT_CLASSES = {
        "assumed_state", "cloud_polling", "cloud_push", "local_polling", 
        "local_push", "calculated"
    }

    VALID_INTEGRATION_TYPES = {
        "device", "entity", "hub", "service", "system", "helper"
    }

    VALID_QUALITY_SCALES = {
        "gold", "silver", "bronze", "internal"
    }

    def __init__(self, hass: HomeAssistant, integration_path: Optional[Path] = None) -> None:
        """Initialize the manifest validator."""
        self.hass = hass
        self.integration_path = integration_path or self._get_integration_path()
        self.manifest_path = self.integration_path / "manifest.json"

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        current_file = Path(__file__)
        return current_file.parent

    async def validate_manifest(self) -> ManifestValidationResult:
        """Validate the manifest.json file comprehensively."""
        _LOGGER.debug("Starting manifest validation for %s", self.integration_path)
        
        issues = []
        warnings = []
        manifest_data = None

        try:
            # Check if manifest file exists
            if not self.manifest_path.exists():
                issues.append(ManifestValidationIssue(
                    field="file",
                    issue_type="missing_file",
                    message="manifest.json file does not exist",
                    severity="error",
                    fix_suggestion="Create a manifest.json file in the integration directory"
                ))
                return ManifestValidationResult(valid=False, issues=issues, warnings=warnings)

            # Parse manifest JSON
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
            except json.JSONDecodeError as e:
                issues.append(ManifestValidationIssue(
                    field="file",
                    issue_type="invalid_json",
                    message=f"Invalid JSON syntax: {str(e)}",
                    severity="error",
                    fix_suggestion="Fix JSON syntax errors in manifest.json"
                ))
                return ManifestValidationResult(valid=False, issues=issues, warnings=warnings)

            # Validate required fields
            await self._validate_required_fields(manifest_data, issues)

            # Validate field types
            await self._validate_field_types(manifest_data, issues)

            # Validate field values
            await self._validate_field_values(manifest_data, issues, warnings)

            # Validate config flow specific requirements
            await self._validate_config_flow_requirements(manifest_data, issues, warnings)

            # Validate dependencies
            await self._validate_dependencies(manifest_data, issues, warnings)

            # Validate domain consistency
            await self._validate_domain_consistency(manifest_data, issues, warnings)

            # Check for deprecated fields
            await self._check_deprecated_fields(manifest_data, warnings)

            # Validate version format
            await self._validate_version_format(manifest_data, issues, warnings)

            # Validate URLs
            await self._validate_urls(manifest_data, issues, warnings)

            # Check for unknown fields
            await self._check_unknown_fields(manifest_data, warnings)

        except Exception as e:
            _LOGGER.error("Unexpected error during manifest validation: %s", e)
            issues.append(ManifestValidationIssue(
                field="validation",
                issue_type="validation_error",
                message=f"Validation failed with error: {str(e)}",
                severity="error"
            ))

        # Determine if validation passed
        has_errors = any(issue.severity == "error" for issue in issues)
        valid = not has_errors

        return ManifestValidationResult(
            valid=valid,
            issues=issues,
            warnings=warnings,
            manifest_data=manifest_data
        )

    async def _validate_required_fields(self, manifest_data: Dict[str, Any], issues: List[ManifestValidationIssue]) -> None:
        """Validate that all required fields are present."""
        for field, expected_type in self.REQUIRED_FIELDS.items():
            if field not in manifest_data:
                issues.append(ManifestValidationIssue(
                    field=field,
                    issue_type="missing_required_field",
                    message=f"Required field '{field}' is missing",
                    severity="error",
                    fix_suggestion=f"Add '{field}' field to manifest.json"
                ))

    async def _validate_field_types(self, manifest_data: Dict[str, Any], issues: List[ManifestValidationIssue]) -> None:
        """Validate that fields have the correct types."""
        all_fields = {**self.REQUIRED_FIELDS, **self.OPTIONAL_FIELDS}
        
        for field, expected_type in all_fields.items():
            if field in manifest_data:
                value = manifest_data[field]
                if not isinstance(value, expected_type):
                    issues.append(ManifestValidationIssue(
                        field=field,
                        issue_type="invalid_type",
                        message=f"Field '{field}' should be {expected_type.__name__}, got {type(value).__name__}",
                        severity="error",
                        fix_suggestion=f"Change '{field}' to be of type {expected_type.__name__}"
                    ))

    async def _validate_field_values(self, manifest_data: Dict[str, Any], issues: List[ManifestValidationIssue], warnings: List[str]) -> None:
        """Validate specific field values."""
        # Validate iot_class
        if "iot_class" in manifest_data:
            iot_class = manifest_data["iot_class"]
            if iot_class not in self.VALID_IOT_CLASSES:
                issues.append(ManifestValidationIssue(
                    field="iot_class",
                    issue_type="invalid_value",
                    message=f"Invalid iot_class '{iot_class}'. Valid values: {', '.join(self.VALID_IOT_CLASSES)}",
                    severity="error",
                    fix_suggestion=f"Use one of: {', '.join(self.VALID_IOT_CLASSES)}"
                ))

        # Validate integration_type
        if "integration_type" in manifest_data:
            integration_type = manifest_data["integration_type"]
            if integration_type not in self.VALID_INTEGRATION_TYPES:
                issues.append(ManifestValidationIssue(
                    field="integration_type",
                    issue_type="invalid_value",
                    message=f"Invalid integration_type '{integration_type}'. Valid values: {', '.join(self.VALID_INTEGRATION_TYPES)}",
                    severity="error",
                    fix_suggestion=f"Use one of: {', '.join(self.VALID_INTEGRATION_TYPES)}"
                ))

        # Validate quality_scale
        if "quality_scale" in manifest_data:
            quality_scale = manifest_data["quality_scale"]
            if quality_scale not in self.VALID_QUALITY_SCALES:
                warnings.append(f"Quality scale '{quality_scale}' is not standard. Consider using: {', '.join(self.VALID_QUALITY_SCALES)}")

        # Validate domain format
        if "domain" in manifest_data:
            domain = manifest_data["domain"]
            if not re.match(r'^[a-z][a-z0-9_]*$', domain):
                issues.append(ManifestValidationIssue(
                    field="domain",
                    issue_type="invalid_format",
                    message=f"Domain '{domain}' contains invalid characters. Must start with letter and contain only lowercase letters, numbers, and underscores",
                    severity="error",
                    fix_suggestion="Use only lowercase letters, numbers, and underscores for domain"
                ))

    async def _validate_config_flow_requirements(self, manifest_data: Dict[str, Any], issues: List[ManifestValidationIssue], warnings: List[str]) -> None:
        """Validate config flow specific requirements."""
        config_flow = manifest_data.get("config_flow", False)
        
        if config_flow:
            # Config flow integrations should have certain characteristics
            if "config_flow" not in manifest_data:
                issues.append(ManifestValidationIssue(
                    field="config_flow",
                    issue_type="missing_config_flow",
                    message="config_flow field is required for config flow integrations",
                    severity="error",
                    fix_suggestion="Add 'config_flow': true to manifest.json"
                ))
            elif manifest_data["config_flow"] is not True:
                issues.append(ManifestValidationIssue(
                    field="config_flow",
                    issue_type="invalid_config_flow_value",
                    message="config_flow must be true for config flow integrations",
                    severity="error",
                    fix_suggestion="Set 'config_flow': true in manifest.json"
                ))

            # Check if config_flow.py exists
            config_flow_path = self.integration_path / "config_flow.py"
            if not config_flow_path.exists():
                issues.append(ManifestValidationIssue(
                    field="config_flow",
                    issue_type="missing_config_flow_file",
                    message="config_flow.py file is missing but config_flow is enabled",
                    severity="error",
                    fix_suggestion="Create config_flow.py file or set config_flow to false"
                ))

    async def _validate_dependencies(self, manifest_data: Dict[str, Any], issues: List[ManifestValidationIssue], warnings: List[str]) -> None:
        """Validate dependencies and after_dependencies."""
        dependencies = manifest_data.get("dependencies", [])
        after_dependencies = manifest_data.get("after_dependencies", [])

        # Check for common required dependencies for config flow integrations
        if manifest_data.get("config_flow", False):
            recommended_deps = ["frontend"]
            for dep in recommended_deps:
                if dep not in dependencies:
                    warnings.append(f"Config flow integrations typically require '{dep}' dependency")

        # Check for circular dependencies
        common_deps = set(dependencies) & set(after_dependencies)
        if common_deps:
            warnings.append(f"Dependencies appear in both dependencies and after_dependencies: {', '.join(common_deps)}")

        # Validate dependency names
        for dep in dependencies + after_dependencies:
            if not isinstance(dep, str):
                issues.append(ManifestValidationIssue(
                    field="dependencies",
                    issue_type="invalid_dependency_type",
                    message=f"Dependency '{dep}' must be a string",
                    severity="error",
                    fix_suggestion="Ensure all dependencies are strings"
                ))
            elif not re.match(r'^[a-z][a-z0-9_]*$', dep):
                warnings.append(f"Dependency '{dep}' has unusual format - ensure it's a valid Home Assistant component")

    async def _validate_domain_consistency(self, manifest_data: Dict[str, Any], issues: List[ManifestValidationIssue], warnings: List[str]) -> None:
        """Validate domain consistency with const.py."""
        manifest_domain = manifest_data.get("domain")
        
        if manifest_domain != DOMAIN:
            issues.append(ManifestValidationIssue(
                field="domain",
                issue_type="domain_mismatch",
                message=f"Domain in manifest.json ('{manifest_domain}') doesn't match DOMAIN in const.py ('{DOMAIN}')",
                severity="error",
                fix_suggestion=f"Update domain in manifest.json to '{DOMAIN}' or update DOMAIN in const.py"
            ))

    async def _check_deprecated_fields(self, manifest_data: Dict[str, Any], warnings: List[str]) -> None:
        """Check for deprecated fields."""
        deprecated_fields = {
            "requirements": "Use dependencies instead of requirements where possible"
        }

        for field, message in deprecated_fields.items():
            if field in manifest_data:
                warnings.append(f"Field '{field}' is deprecated: {message}")

    async def _validate_version_format(self, manifest_data: Dict[str, Any], issues: List[ManifestValidationIssue], warnings: List[str]) -> None:
        """Validate version format."""
        version = manifest_data.get("version")
        if version:
            # Check semantic versioning format
            if not re.match(r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$', version):
                warnings.append(f"Version '{version}' doesn't follow semantic versioning (x.y.z)")

    async def _validate_urls(self, manifest_data: Dict[str, Any], issues: List[ManifestValidationIssue], warnings: List[str]) -> None:
        """Validate URL fields."""
        url_fields = ["documentation", "issue_tracker"]
        
        for field in url_fields:
            if field in manifest_data:
                url = manifest_data[field]
                if not isinstance(url, str):
                    continue
                    
                # Basic URL validation
                if not url.startswith(("http://", "https://")):
                    warnings.append(f"Field '{field}' should be a valid HTTP/HTTPS URL")
                elif "github.com/user/" in url or "example.com" in url:
                    warnings.append(f"Field '{field}' appears to contain placeholder URL")

    async def _check_unknown_fields(self, manifest_data: Dict[str, Any], warnings: List[str]) -> None:
        """Check for unknown fields."""
        known_fields = set(self.REQUIRED_FIELDS.keys()) | set(self.OPTIONAL_FIELDS.keys())
        manifest_fields = set(manifest_data.keys())
        unknown_fields = manifest_fields - known_fields

        if unknown_fields:
            warnings.append(f"Unknown fields in manifest: {', '.join(unknown_fields)}")

    def get_validation_summary(self, result: ManifestValidationResult) -> str:
        """Generate a human-readable validation summary."""
        lines = [
            "=" * 50,
            "MANIFEST VALIDATION SUMMARY",
            "=" * 50,
            f"Status: {'✓ VALID' if result.valid else '✗ INVALID'}",
            f"Issues: {len(result.issues)}",
            f"Warnings: {len(result.warnings)}",
            ""
        ]

        if result.issues:
            lines.extend([
                "ISSUES:",
                "-" * 8
            ])
            for issue in result.issues:
                severity_symbol = "🔴" if issue.severity == "error" else "🟡" if issue.severity == "warning" else "🔵"
                lines.append(f"{severity_symbol} {issue.field}: {issue.message}")
                if issue.fix_suggestion:
                    lines.append(f"   Fix: {issue.fix_suggestion}")
            lines.append("")

        if result.warnings:
            lines.extend([
                "WARNINGS:",
                "-" * 9
            ])
            for warning in result.warnings:
                lines.append(f"⚠️  {warning}")
            lines.append("")

        if result.manifest_data:
            lines.extend([
                "MANIFEST INFO:",
                "-" * 14,
                f"Domain: {result.manifest_data.get('domain', 'N/A')}",
                f"Name: {result.manifest_data.get('name', 'N/A')}",
                f"Version: {result.manifest_data.get('version', 'N/A')}",
                f"Config Flow: {result.manifest_data.get('config_flow', False)}",
                f"Integration Type: {result.manifest_data.get('integration_type', 'N/A')}",
                f"IoT Class: {result.manifest_data.get('iot_class', 'N/A')}",
                ""
            ])

        lines.extend([
            "=" * 50,
            "END OF VALIDATION SUMMARY",
            "=" * 50
        ])

        return "\n".join(lines)