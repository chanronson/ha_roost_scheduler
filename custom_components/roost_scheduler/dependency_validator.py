"""Dependency validation for Roost Scheduler integration."""
from __future__ import annotations

import importlib
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.loader import Integration, async_get_integration

from .const import DOMAIN, REQUIRED_DOMAINS, OPTIONAL_DOMAINS

_LOGGER = logging.getLogger(__name__)


@dataclass
class DependencyInfo:
    """Information about a dependency."""
    name: str
    available: bool
    version: Optional[str] = None
    error_message: Optional[str] = None
    is_required: bool = True
    integration_info: Optional[Dict[str, Any]] = None


@dataclass
class ImportInfo:
    """Information about a Python import."""
    module_name: str
    importable: bool
    error_message: Optional[str] = None
    module_path: Optional[str] = None
    version: Optional[str] = None


@dataclass
class ConflictInfo:
    """Information about a dependency conflict."""
    dependency1: str
    dependency2: str
    conflict_type: str
    description: str
    severity: str  # "error", "warning", "info"


@dataclass
class DependencyValidationResult:
    """Result of dependency validation."""
    valid: bool
    dependencies: Dict[str, DependencyInfo]
    imports: Dict[str, ImportInfo]
    conflicts: List[ConflictInfo]
    warnings: List[str]
    recommendations: List[str]


class DependencyValidator:
    """Validates integration dependencies and imports."""

    # Core Python modules that should always be available
    CORE_PYTHON_MODULES = {
        "json", "logging", "os", "sys", "pathlib", "typing", "dataclasses",
        "asyncio", "datetime", "re", "uuid", "functools", "collections"
    }

    # Home Assistant modules commonly used by integrations
    COMMON_HA_MODULES = {
        "homeassistant.core": "HomeAssistant core functionality",
        "homeassistant.config_entries": "Configuration entries system",
        "homeassistant.helpers.storage": "Storage helpers",
        "homeassistant.helpers.entity": "Entity base classes",
        "homeassistant.helpers.entity_platform": "Entity platform helpers",
        "homeassistant.helpers.event": "Event helpers",
        "homeassistant.helpers.service": "Service helpers",
        "homeassistant.const": "Home Assistant constants",
        "homeassistant.exceptions": "Home Assistant exceptions"
    }

    # Third-party Python packages that might be used
    THIRD_PARTY_MODULES = {
        "voluptuous": "Schema validation",
        "aiohttp": "Async HTTP client",
        "async_timeout": "Async timeout utilities",
        "yarl": "URL parsing"
    }

    def __init__(self, hass: HomeAssistant, integration_path: Optional[Path] = None) -> None:
        """Initialize the dependency validator."""
        self.hass = hass
        self.integration_path = integration_path or self._get_integration_path()

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        current_file = Path(__file__)
        return current_file.parent

    async def validate_dependencies(self) -> DependencyValidationResult:
        """Validate all dependencies comprehensively."""
        _LOGGER.debug("Starting dependency validation for %s", DOMAIN)
        
        dependencies = {}
        imports = {}
        conflicts = []
        warnings = []
        recommendations = []

        try:
            # Validate Home Assistant component dependencies
            await self._validate_ha_dependencies(dependencies, warnings)

            # Validate Python imports
            await self._validate_python_imports(imports, warnings)

            # Check for dependency conflicts
            await self._check_dependency_conflicts(dependencies, conflicts, warnings)

            # Validate integration-specific imports
            await self._validate_integration_imports(imports, warnings)

            # Check for missing recommended dependencies
            await self._check_recommended_dependencies(dependencies, recommendations)

            # Validate version compatibility
            await self._validate_version_compatibility(dependencies, warnings)

        except Exception as e:
            _LOGGER.error("Unexpected error during dependency validation: %s", e)
            warnings.append(f"Dependency validation failed with error: {str(e)}")

        # Determine if validation passed
        has_critical_failures = (
            any(not dep.available and dep.is_required for dep in dependencies.values()) or
            any(not imp.importable for name, imp in imports.items() if name.startswith("critical_"))
        )
        valid = not has_critical_failures

        return DependencyValidationResult(
            valid=valid,
            dependencies=dependencies,
            imports=imports,
            conflicts=conflicts,
            warnings=warnings,
            recommendations=recommendations
        )

    async def _validate_ha_dependencies(self, dependencies: Dict[str, DependencyInfo], warnings: List[str]) -> None:
        """Validate Home Assistant component dependencies."""
        # Check required dependencies
        for dep in REQUIRED_DOMAINS:
            dep_info = await self._check_ha_component(dep, is_required=True)
            dependencies[f"ha_required_{dep}"] = dep_info
            
            if not dep_info.available:
                warnings.append(f"Required Home Assistant component '{dep}' is not available: {dep_info.error_message}")

        # Check optional dependencies
        for dep in OPTIONAL_DOMAINS:
            dep_info = await self._check_ha_component(dep, is_required=False)
            dependencies[f"ha_optional_{dep}"] = dep_info
            
            if not dep_info.available:
                _LOGGER.debug("Optional Home Assistant component '%s' is not available: %s", dep, dep_info.error_message)

        # Check manifest dependencies
        await self._validate_manifest_dependencies(dependencies, warnings)

    async def _check_ha_component(self, component_name: str, is_required: bool = True) -> DependencyInfo:
        """Check if a Home Assistant component is available."""
        try:
            # Try to get the integration
            integration = await async_get_integration(self.hass, component_name)
            
            # Get integration info
            integration_info = {
                "domain": integration.domain,
                "name": integration.name,
                "version": getattr(integration, 'version', None),
                "documentation": getattr(integration, 'documentation', None),
                "requirements": getattr(integration, 'requirements', []),
                "dependencies": getattr(integration, 'dependencies', [])
            }
            
            return DependencyInfo(
                name=component_name,
                available=True,
                is_required=is_required,
                integration_info=integration_info
            )
            
        except Exception as e:
            return DependencyInfo(
                name=component_name,
                available=False,
                error_message=str(e),
                is_required=is_required
            )

    async def _validate_manifest_dependencies(self, dependencies: Dict[str, DependencyInfo], warnings: List[str]) -> None:
        """Validate dependencies listed in manifest.json."""
        try:
            manifest_path = self.integration_path / "manifest.json"
            if not manifest_path.exists():
                warnings.append("manifest.json not found - cannot validate manifest dependencies")
                return

            import json
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)

            manifest_deps = manifest_data.get("dependencies", [])
            after_deps = manifest_data.get("after_dependencies", [])

            # Validate each manifest dependency
            for dep in manifest_deps:
                if f"ha_required_{dep}" not in dependencies and f"ha_optional_{dep}" not in dependencies:
                    dep_info = await self._check_ha_component(dep, is_required=True)
                    dependencies[f"manifest_{dep}"] = dep_info
                    
                    if not dep_info.available:
                        warnings.append(f"Manifest dependency '{dep}' is not available: {dep_info.error_message}")

            # Validate after_dependencies
            for dep in after_deps:
                if f"ha_required_{dep}" not in dependencies and f"ha_optional_{dep}" not in dependencies:
                    dep_info = await self._check_ha_component(dep, is_required=False)
                    dependencies[f"after_{dep}"] = dep_info

        except Exception as e:
            warnings.append(f"Error validating manifest dependencies: {str(e)}")

    async def _validate_python_imports(self, imports: Dict[str, ImportInfo], warnings: List[str]) -> None:
        """Validate Python module imports."""
        # Check core Python modules
        for module in self.CORE_PYTHON_MODULES:
            import_info = await self._check_python_import(module)
            imports[f"python_core_{module}"] = import_info

        # Check common Home Assistant modules
        for module, description in self.COMMON_HA_MODULES.items():
            import_info = await self._check_python_import(module)
            imports[f"ha_module_{module.split('.')[-1]}"] = import_info
            
            if not import_info.importable:
                warnings.append(f"Home Assistant module '{module}' ({description}) is not importable: {import_info.error_message}")

        # Check third-party modules
        for module, description in self.THIRD_PARTY_MODULES.items():
            import_info = await self._check_python_import(module)
            imports[f"third_party_{module}"] = import_info

    async def _check_python_import(self, module_name: str) -> ImportInfo:
        """Check if a Python module can be imported."""
        try:
            if module_name.startswith('.'):
                # Relative import
                module = importlib.import_module(module_name, package=__package__)
            else:
                # Absolute import
                module = importlib.import_module(module_name)
            
            # Get module info
            module_path = getattr(module, '__file__', None)
            version = getattr(module, '__version__', None)
            
            return ImportInfo(
                module_name=module_name,
                importable=True,
                module_path=module_path,
                version=version
            )
            
        except ImportError as e:
            return ImportInfo(
                module_name=module_name,
                importable=False,
                error_message=str(e)
            )
        except Exception as e:
            return ImportInfo(
                module_name=module_name,
                importable=False,
                error_message=f"Unexpected error: {str(e)}"
            )

    async def _validate_integration_imports(self, imports: Dict[str, ImportInfo], warnings: List[str]) -> None:
        """Validate integration-specific imports."""
        # Integration modules that should be importable
        integration_modules = [
            "const",
            "config_flow", 
            "models",
            "storage",
            "schedule_manager",
            "presence_manager",
            "buffer_manager"
        ]

        for module in integration_modules:
            try:
                import_info = await self._check_python_import(f".{module}")
                imports[f"integration_{module}"] = import_info
                
                if not import_info.importable:
                    warnings.append(f"Integration module '{module}' is not importable: {import_info.error_message}")
                    
            except Exception as e:
                imports[f"integration_{module}"] = ImportInfo(
                    module_name=module,
                    importable=False,
                    error_message=str(e)
                )
                warnings.append(f"Error checking integration module '{module}': {str(e)}")

    async def _check_dependency_conflicts(self, dependencies: Dict[str, DependencyInfo], conflicts: List[ConflictInfo], warnings: List[str]) -> None:
        """Check for dependency conflicts."""
        # Check for version conflicts
        await self._check_version_conflicts(dependencies, conflicts)
        
        # Check for circular dependencies
        await self._check_circular_dependencies(dependencies, conflicts)
        
        # Check for incompatible dependencies
        await self._check_incompatible_dependencies(dependencies, conflicts)

    async def _check_version_conflicts(self, dependencies: Dict[str, DependencyInfo], conflicts: List[ConflictInfo]) -> None:
        """Check for version conflicts between dependencies."""
        # This is a placeholder for more sophisticated version conflict detection
        # In a real implementation, you would check for known incompatible versions
        pass

    async def _check_circular_dependencies(self, dependencies: Dict[str, DependencyInfo], conflicts: List[ConflictInfo]) -> None:
        """Check for circular dependency issues."""
        try:
            manifest_path = self.integration_path / "manifest.json"
            if not manifest_path.exists():
                return

            import json
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)

            deps = set(manifest_data.get("dependencies", []))
            after_deps = set(manifest_data.get("after_dependencies", []))

            # Check for dependencies that appear in both lists
            common_deps = deps & after_deps
            if common_deps:
                for dep in common_deps:
                    conflicts.append(ConflictInfo(
                        dependency1=dep,
                        dependency2=dep,
                        conflict_type="circular_dependency",
                        description=f"Dependency '{dep}' appears in both dependencies and after_dependencies",
                        severity="warning"
                    ))

        except Exception as e:
            _LOGGER.debug("Error checking circular dependencies: %s", e)

    async def _check_incompatible_dependencies(self, dependencies: Dict[str, DependencyInfo], conflicts: List[ConflictInfo]) -> None:
        """Check for known incompatible dependencies."""
        # This is a placeholder for checking known incompatible dependency combinations
        # In a real implementation, you would maintain a database of known conflicts
        pass

    async def _check_recommended_dependencies(self, dependencies: Dict[str, DependencyInfo], recommendations: List[str]) -> None:
        """Check for missing recommended dependencies."""
        # For config flow integrations, recommend certain dependencies
        recommended_for_config_flow = ["frontend", "websocket_api"]
        
        for dep in recommended_for_config_flow:
            dep_key = f"ha_required_{dep}"
            if dep_key not in dependencies or not dependencies[dep_key].available:
                recommendations.append(f"Consider adding '{dep}' dependency for better config flow support")

    async def _validate_version_compatibility(self, dependencies: Dict[str, DependencyInfo], warnings: List[str]) -> None:
        """Validate version compatibility with Home Assistant."""
        try:
            # Parse current HA version
            current_version = HA_VERSION
            
            # Check if we have minimum version requirements
            from .const import MIN_HA_VERSION, RECOMMENDED_HA_VERSION
            
            if self._compare_versions(current_version, MIN_HA_VERSION) < 0:
                warnings.append(f"Home Assistant version {current_version} is below minimum required version {MIN_HA_VERSION}")
            
            if self._compare_versions(current_version, RECOMMENDED_HA_VERSION) < 0:
                warnings.append(f"Home Assistant version {current_version} is below recommended version {RECOMMENDED_HA_VERSION}")
                
        except Exception as e:
            warnings.append(f"Error validating version compatibility: {str(e)}")

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

    def get_validation_summary(self, result: DependencyValidationResult) -> str:
        """Generate a human-readable validation summary."""
        lines = [
            "=" * 60,
            "DEPENDENCY VALIDATION SUMMARY",
            "=" * 60,
            f"Status: {'✓ VALID' if result.valid else '✗ INVALID'}",
            f"Dependencies Checked: {len(result.dependencies)}",
            f"Imports Checked: {len(result.imports)}",
            f"Conflicts Found: {len(result.conflicts)}",
            f"Warnings: {len(result.warnings)}",
            ""
        ]

        # Dependencies summary
        if result.dependencies:
            lines.extend([
                "DEPENDENCIES:",
                "-" * 13
            ])
            
            required_deps = {k: v for k, v in result.dependencies.items() if v.is_required}
            optional_deps = {k: v for k, v in result.dependencies.items() if not v.is_required}
            
            if required_deps:
                lines.append("Required:")
                for name, dep in required_deps.items():
                    status = "✓" if dep.available else "✗"
                    version_info = f" (v{dep.version})" if dep.version else ""
                    lines.append(f"  {status} {dep.name}{version_info}")
                    if not dep.available and dep.error_message:
                        lines.append(f"      Error: {dep.error_message}")
                lines.append("")
            
            if optional_deps:
                lines.append("Optional:")
                for name, dep in optional_deps.items():
                    status = "✓" if dep.available else "○"
                    version_info = f" (v{dep.version})" if dep.version else ""
                    lines.append(f"  {status} {dep.name}{version_info}")
                lines.append("")

        # Imports summary
        if result.imports:
            lines.extend([
                "IMPORTS:",
                "-" * 8
            ])
            
            failed_imports = {k: v for k, v in result.imports.items() if not v.importable}
            if failed_imports:
                lines.append("Failed:")
                for name, imp in failed_imports.items():
                    lines.append(f"  ✗ {imp.module_name}")
                    if imp.error_message:
                        lines.append(f"      Error: {imp.error_message}")
                lines.append("")

        # Conflicts
        if result.conflicts:
            lines.extend([
                "CONFLICTS:",
                "-" * 10
            ])
            for conflict in result.conflicts:
                severity_symbol = "🔴" if conflict.severity == "error" else "🟡"
                lines.append(f"{severity_symbol} {conflict.conflict_type}: {conflict.description}")
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
            "=" * 60,
            "END OF DEPENDENCY VALIDATION",
            "=" * 60
        ])

        return "\n".join(lines)