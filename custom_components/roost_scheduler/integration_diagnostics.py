"""Integration Diagnostics collector for Roost Scheduler integration."""
from __future__ import annotations

import json
import logging
import os
import platform
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.storage import Store

from .const import DOMAIN, VERSION, REQUIRED_DOMAINS, OPTIONAL_DOMAINS
from .file_system_validator import FileSystemValidator, FileSystemValidationResult
from .file_system_error_handler import FileSystemErrorHandler, FileSystemError

_LOGGER = logging.getLogger(__name__)


@dataclass
class PermissionStatus:
    """File permission status."""
    readable: bool
    writable: bool
    executable: bool
    exists: bool
    error_message: Optional[str] = None


@dataclass
class DependencyStatus:
    """Dependency availability status."""
    available: bool
    version: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ImportStatus:
    """Import status for Python modules."""
    importable: bool
    error_message: Optional[str] = None
    module_path: Optional[str] = None


@dataclass
class DiagnosticData:
    """Comprehensive diagnostic data."""
    ha_version: str
    integration_version: str
    domain_consistency: bool
    file_permissions: Dict[str, PermissionStatus]
    import_status: Dict[str, ImportStatus]
    dependency_status: Dict[str, DependencyStatus]
    config_flow_class_found: bool
    manifest_valid: bool
    error_details: List[str]
    system_info: Dict[str, Any]
    integration_info: Dict[str, Any]


class IntegrationDiagnostics:
    """Provides comprehensive diagnostic information for troubleshooting."""

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize the diagnostics collector."""
        self.hass = hass
        self.domain = domain
        self._integration_path = self._get_integration_path()

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        current_file = Path(__file__)
        return current_file.parent

    async def collect_diagnostic_data(self) -> DiagnosticData:
        """Collect comprehensive diagnostic data."""
        _LOGGER.debug("Collecting diagnostic data for domain: %s", self.domain)
        
        try:
            # Collect system information
            system_info = await self._collect_system_info()
            
            # Collect integration information
            integration_info = await self._collect_integration_info()
            
            # Check file permissions
            file_permissions = await self._check_all_file_permissions()
            
            # Verify dependencies
            dependency_status = await self._verify_all_dependencies()
            
            # Validate imports
            import_status = await self._validate_all_imports()
            
            # Check domain consistency
            domain_consistency = await self._check_domain_consistency()
            
            # Check config flow class
            config_flow_class_found = await self._check_config_flow_class()
            
            # Validate manifest
            manifest_valid = await self._validate_manifest()
            
            # Collect error details
            error_details = await self._collect_error_details()
            
            return DiagnosticData(
                ha_version=HA_VERSION,
                integration_version=VERSION,
                domain_consistency=domain_consistency,
                file_permissions=file_permissions,
                import_status=import_status,
                dependency_status=dependency_status,
                config_flow_class_found=config_flow_class_found,
                manifest_valid=manifest_valid,
                error_details=error_details,
                system_info=system_info,
                integration_info=integration_info
            )
            
        except Exception as e:
            _LOGGER.error("Error collecting diagnostic data: %s", e)
            # Return minimal diagnostic data with error
            return DiagnosticData(
                ha_version=HA_VERSION,
                integration_version=VERSION,
                domain_consistency=False,
                file_permissions={},
                import_status={},
                dependency_status={},
                config_flow_class_found=False,
                manifest_valid=False,
                error_details=[f"Diagnostic collection failed: {str(e)}"],
                system_info={},
                integration_info={}
            )

    async def check_file_permissions(self, file_path: Optional[str] = None) -> PermissionStatus:
        """Check file system permissions for integration files."""
        # Use the new file system validator for enhanced permission checking
        fs_validator = FileSystemValidator(self.hass, self.domain)
        
        if file_path:
            path = file_path
        else:
            path = str(self._integration_path)
        
        try:
            perm_details = await fs_validator.check_file_permissions(path)
            
            return PermissionStatus(
                readable=perm_details.readable,
                writable=perm_details.writable,
                executable=perm_details.executable,
                exists=perm_details.exists,
                error_message=perm_details.error_message
            )
            
        except Exception as e:
            return PermissionStatus(
                readable=False,
                writable=False,
                executable=False,
                exists=False,
                error_message=f"Permission check failed: {str(e)}"
            )

    async def verify_dependencies(self) -> Dict[str, DependencyStatus]:
        """Verify all integration dependencies."""
        dependency_status = {}
        
        # Check required dependencies
        for dep in REQUIRED_DOMAINS:
            status = await self._check_single_dependency(dep)
            dependency_status[f"required_{dep}"] = status
        
        # Check optional dependencies
        for dep in OPTIONAL_DOMAINS:
            status = await self._check_single_dependency(dep)
            dependency_status[f"optional_{dep}"] = status
        
        # Check Python dependencies
        python_deps = ["voluptuous", "aiohttp"]
        for dep in python_deps:
            status = await self._check_python_dependency(dep)
            dependency_status[f"python_{dep}"] = status
        
        return dependency_status

    async def validate_imports(self) -> Dict[str, ImportStatus]:
        """Validate all Python imports used by the integration."""
        import_status = {}
        
        # Core integration modules
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
            status = await self._check_module_import(f".{module}")
            import_status[f"integration_{module}"] = status
        
        # Home Assistant imports
        ha_imports = [
            "homeassistant.core",
            "homeassistant.config_entries",
            "homeassistant.helpers.storage",
            "homeassistant.components.frontend",
            "homeassistant.components.websocket_api"
        ]
        
        for module in ha_imports:
            status = await self._check_module_import(module)
            import_status[f"ha_{module.split('.')[-1]}"] = status
        
        return import_status

    async def get_file_system_validation(self) -> FileSystemValidationResult:
        """Get comprehensive file system validation results."""
        fs_validator = FileSystemValidator(self.hass, self.domain)
        return await fs_validator.validate_file_system()

    async def validate_integration_files(self) -> Dict[str, Any]:
        """Validate integration-specific file requirements and content."""
        fs_validator = FileSystemValidator(self.hass, self.domain)
        return await fs_validator.validate_integration_files()

    async def check_file_corruption(self, file_path: str) -> Dict[str, Any]:
        """Check for file corruption indicators."""
        fs_validator = FileSystemValidator(self.hass, self.domain)
        return await fs_validator.check_file_corruption(file_path)

    async def detect_file_system_errors(self) -> List[FileSystemError]:
        """Detect file system errors and issues."""
        error_handler = FileSystemErrorHandler(self.hass, self.domain)
        return await error_handler.detect_file_system_errors()

    async def generate_file_system_troubleshooting_guide(self) -> str:
        """Generate comprehensive file system troubleshooting guide."""
        error_handler = FileSystemErrorHandler(self.hass, self.domain)
        errors = await error_handler.detect_file_system_errors()
        return error_handler.generate_troubleshooting_guide(errors)

    async def attempt_file_system_auto_fix(self) -> Dict[str, Any]:
        """Attempt to automatically fix file system issues."""
        error_handler = FileSystemErrorHandler(self.hass, self.domain)
        errors = await error_handler.detect_file_system_errors()
        return await error_handler.attempt_auto_fix(errors)

    def generate_troubleshooting_report(self, diagnostic_data: Optional[DiagnosticData] = None) -> str:
        """Generate a comprehensive troubleshooting report."""
        if diagnostic_data is None:
            # This would normally be async, but for report generation we'll use cached data
            diagnostic_data = DiagnosticData(
                ha_version=HA_VERSION,
                integration_version=VERSION,
                domain_consistency=False,
                file_permissions={},
                import_status={},
                dependency_status={},
                config_flow_class_found=False,
                manifest_valid=False,
                error_details=["No diagnostic data available"],
                system_info={},
                integration_info={}
            )
        
        report_lines = [
            "=" * 60,
            "ROOST SCHEDULER INTEGRATION TROUBLESHOOTING REPORT",
            "=" * 60,
            "",
            f"Integration Version: {diagnostic_data.integration_version}",
            f"Home Assistant Version: {diagnostic_data.ha_version}",
            f"Domain: {self.domain}",
            f"Integration Path: {self._integration_path}",
            "",
            "SYSTEM INFORMATION:",
            "-" * 20
        ]
        
        # Add system info
        for key, value in diagnostic_data.system_info.items():
            report_lines.append(f"{key}: {value}")
        
        report_lines.extend([
            "",
            "VALIDATION STATUS:",
            "-" * 18,
            f"Domain Consistency: {'✓' if diagnostic_data.domain_consistency else '✗'}",
            f"Config Flow Class Found: {'✓' if diagnostic_data.config_flow_class_found else '✗'}",
            f"Manifest Valid: {'✓' if diagnostic_data.manifest_valid else '✗'}",
            ""
        ])
        
        # Add file permissions
        if diagnostic_data.file_permissions:
            report_lines.extend([
                "FILE PERMISSIONS:",
                "-" * 17
            ])
            for file_path, perm in diagnostic_data.file_permissions.items():
                status = "✓" if perm.readable and perm.exists else "✗"
                report_lines.append(f"{status} {file_path}: R:{perm.readable} W:{perm.writable} E:{perm.exists}")
                if perm.error_message:
                    report_lines.append(f"    Error: {perm.error_message}")
            report_lines.append("")
        
        # Add dependency status
        if diagnostic_data.dependency_status:
            report_lines.extend([
                "DEPENDENCY STATUS:",
                "-" * 18
            ])
            for dep_name, dep_status in diagnostic_data.dependency_status.items():
                status = "✓" if dep_status.available else "✗"
                version_info = f" (v{dep_status.version})" if dep_status.version else ""
                report_lines.append(f"{status} {dep_name}{version_info}")
                if dep_status.error_message:
                    report_lines.append(f"    Error: {dep_status.error_message}")
            report_lines.append("")
        
        # Add import status
        if diagnostic_data.import_status:
            report_lines.extend([
                "IMPORT STATUS:",
                "-" * 14
            ])
            for module_name, import_stat in diagnostic_data.import_status.items():
                status = "✓" if import_stat.importable else "✗"
                report_lines.append(f"{status} {module_name}")
                if import_stat.error_message:
                    report_lines.append(f"    Error: {import_stat.error_message}")
            report_lines.append("")
        
        # Add error details
        if diagnostic_data.error_details:
            report_lines.extend([
                "ERROR DETAILS:",
                "-" * 14
            ])
            for error in diagnostic_data.error_details:
                report_lines.append(f"• {error}")
            report_lines.append("")
        
        # Add recommendations
        report_lines.extend([
            "RECOMMENDATIONS:",
            "-" * 16
        ])
        
        recommendations = self._generate_recommendations(diagnostic_data)
        for rec in recommendations:
            report_lines.append(f"• {rec}")
        
        # Add file system troubleshooting section
        report_lines.extend([
            "",
            "FILE SYSTEM TROUBLESHOOTING:",
            "-" * 28,
            "For detailed file system analysis and fixes, use:",
            "• await diagnostics.generate_file_system_troubleshooting_guide()",
            "• await diagnostics.attempt_file_system_auto_fix()",
            ""
        ])
        
        report_lines.extend([
            "",
            "=" * 60,
            "END OF TROUBLESHOOTING REPORT",
            "=" * 60
        ])
        
        return "\n".join(report_lines)

    async def _collect_system_info(self) -> Dict[str, Any]:
        """Collect system information."""
        return {
            "platform": platform.platform(),
            "python_version": sys.version,
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "home_assistant_version": HA_VERSION,
            "integration_domain": self.domain,
            "integration_path": str(self._integration_path)
        }

    async def _collect_integration_info(self) -> Dict[str, Any]:
        """Collect integration-specific information."""
        info = {
            "domain": self.domain,
            "version": VERSION,
            "integration_path": str(self._integration_path)
        }
        
        # Check if integration is loaded
        if self.domain in self.hass.config.components:
            info["loaded"] = True
            info["config_entries"] = len(self.hass.config_entries.async_entries(self.domain))
        else:
            info["loaded"] = False
            info["config_entries"] = 0
        
        return info

    async def _check_all_file_permissions(self) -> Dict[str, PermissionStatus]:
        """Check permissions for all integration files."""
        # Use the new file system validator for comprehensive permission checking
        fs_validator = FileSystemValidator(self.hass, self.domain)
        fs_result = await fs_validator.validate_file_system()
        
        file_permissions = {}
        
        # Convert FilePermissionDetails to PermissionStatus for compatibility
        for filename, perm_details in fs_result.permissions.items():
            file_permissions[filename] = PermissionStatus(
                readable=perm_details.readable,
                writable=perm_details.writable,
                executable=perm_details.executable,
                exists=perm_details.exists,
                error_message=perm_details.error_message
            )
        
        return file_permissions

    async def _verify_all_dependencies(self) -> Dict[str, DependencyStatus]:
        """Verify all dependencies."""
        return await self.verify_dependencies()

    async def _validate_all_imports(self) -> Dict[str, ImportStatus]:
        """Validate all imports."""
        return await self.validate_imports()

    async def _check_domain_consistency(self) -> bool:
        """Check if domain is consistent across files."""
        try:
            # Check manifest domain
            manifest_path = self._integration_path / "manifest.json"
            manifest_domain = None
            if manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                manifest_domain = manifest_data.get("domain")
            
            # Check const domain
            const_path = self._integration_path / "const.py"
            const_domain = None
            if const_path.exists():
                with open(const_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                import re
                match = re.search(r'DOMAIN\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    const_domain = match.group(1)
            
            # Check consistency
            domains = [manifest_domain, const_domain, self.domain]
            unique_domains = set(filter(None, domains))
            
            return len(unique_domains) <= 1
            
        except Exception as e:
            _LOGGER.debug("Error checking domain consistency: %s", e)
            return False

    async def _check_config_flow_class(self) -> bool:
        """Check if config flow class exists and is importable."""
        try:
            config_flow_path = self._integration_path / "config_flow.py"
            if not config_flow_path.exists():
                return False
            
            # Try to import the config flow module
            from . import config_flow
            return hasattr(config_flow, 'RoostSchedulerConfigFlow')
            
        except Exception as e:
            _LOGGER.debug("Error checking config flow class: %s", e)
            return False

    async def _validate_manifest(self) -> bool:
        """Validate manifest.json file."""
        try:
            manifest_path = self._integration_path / "manifest.json"
            if not manifest_path.exists():
                return False
            
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
            
            # Check required fields
            required_fields = ["domain", "name", "version", "config_flow"]
            for field in required_fields:
                if field not in manifest_data:
                    return False
            
            # Check config_flow is enabled
            if manifest_data.get("config_flow") is not True:
                return False
            
            return True
            
        except Exception as e:
            _LOGGER.debug("Error validating manifest: %s", e)
            return False

    async def _collect_error_details(self) -> List[str]:
        """Collect detailed error information."""
        errors = []
        
        # Check for common issues
        try:
            # Check if integration directory exists
            if not self._integration_path.exists():
                errors.append(f"Integration directory not found: {self._integration_path}")
            
            # Check for manifest issues
            manifest_path = self._integration_path / "manifest.json"
            if not manifest_path.exists():
                errors.append("manifest.json file missing")
            else:
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    errors.append(f"Invalid JSON in manifest.json: {str(e)}")
            
            # Check for config flow issues
            config_flow_path = self._integration_path / "config_flow.py"
            if not config_flow_path.exists():
                errors.append("config_flow.py file missing")
            
        except Exception as e:
            errors.append(f"Error collecting error details: {str(e)}")
        
        return errors

    async def _check_single_dependency(self, dependency: str) -> DependencyStatus:
        """Check if a single dependency is available."""
        try:
            # Check if it's a Home Assistant component
            if hasattr(self.hass.components, dependency):
                return DependencyStatus(available=True)
            
            # Try to import it
            try:
                module = __import__(f"homeassistant.components.{dependency}")
                version = getattr(module, '__version__', None)
                return DependencyStatus(available=True, version=version)
            except ImportError as e:
                return DependencyStatus(available=False, error_message=str(e))
            
        except Exception as e:
            return DependencyStatus(available=False, error_message=str(e))

    async def _check_python_dependency(self, dependency: str) -> DependencyStatus:
        """Check if a Python dependency is available."""
        try:
            module = __import__(dependency)
            version = getattr(module, '__version__', None)
            return DependencyStatus(available=True, version=version)
        except ImportError as e:
            return DependencyStatus(available=False, error_message=str(e))
        except Exception as e:
            return DependencyStatus(available=False, error_message=str(e))

    async def _check_module_import(self, module_name: str) -> ImportStatus:
        """Check if a module can be imported."""
        try:
            if module_name.startswith('.'):
                # Relative import
                from importlib import import_module
                module = import_module(module_name, package=__package__)
            else:
                # Absolute import
                module = __import__(module_name)
            
            module_path = getattr(module, '__file__', None)
            return ImportStatus(importable=True, module_path=module_path)
            
        except ImportError as e:
            return ImportStatus(importable=False, error_message=str(e))
        except Exception as e:
            return ImportStatus(importable=False, error_message=str(e))

    def _generate_recommendations(self, diagnostic_data: DiagnosticData) -> List[str]:
        """Generate recommendations based on diagnostic data."""
        recommendations = []
        
        if not diagnostic_data.domain_consistency:
            recommendations.append("Fix domain consistency across manifest.json, const.py, and config_flow.py")
        
        if not diagnostic_data.config_flow_class_found:
            recommendations.append("Ensure ConfigFlow class is properly defined in config_flow.py")
        
        if not diagnostic_data.manifest_valid:
            recommendations.append("Fix manifest.json configuration and ensure config_flow is set to true")
        
        # Check file permissions
        for file_path, perm in diagnostic_data.file_permissions.items():
            if not perm.exists:
                recommendations.append(f"Create missing file: {file_path}")
            elif not perm.readable:
                recommendations.append(f"Fix read permissions for: {file_path}")
        
        # Check dependencies
        for dep_name, dep_status in diagnostic_data.dependency_status.items():
            if not dep_status.available and dep_name.startswith("required_"):
                dep_clean_name = dep_name.replace("required_", "")
                recommendations.append(f"Install or enable required dependency: {dep_clean_name}")
        
        # Check imports
        failed_imports = [name for name, status in diagnostic_data.import_status.items() if not status.importable]
        if failed_imports:
            recommendations.append("Fix import errors for: " + ", ".join(failed_imports))
        
        if diagnostic_data.error_details:
            recommendations.append("Review error details above and fix identified issues")
        
        if not recommendations:
            recommendations.append("All checks passed - integration should be working correctly")
        
        return recommendations