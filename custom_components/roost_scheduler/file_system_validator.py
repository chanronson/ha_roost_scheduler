"""File system and permission validation for Roost Scheduler integration."""
from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FilePermissionDetails:
    """Detailed file permission information."""
    path: str
    exists: bool
    readable: bool
    writable: bool
    executable: bool
    is_file: bool
    is_directory: bool
    size: Optional[int] = None
    permissions_octal: Optional[str] = None
    owner_readable: bool = False
    owner_writable: bool = False
    owner_executable: bool = False
    group_readable: bool = False
    group_writable: bool = False
    group_executable: bool = False
    other_readable: bool = False
    other_writable: bool = False
    other_executable: bool = False
    error_message: Optional[str] = None


@dataclass
class FileIntegrityResult:
    """File integrity validation result."""
    path: str
    exists: bool
    is_valid: bool
    expected_type: str  # 'file' or 'directory'
    actual_type: Optional[str] = None
    size: Optional[int] = None
    is_empty: Optional[bool] = None
    is_readable: bool = False
    content_valid: bool = False
    error_message: Optional[str] = None


@dataclass
class FileSystemValidationResult:
    """Complete file system validation result."""
    success: bool
    permissions: Dict[str, FilePermissionDetails]
    integrity: Dict[str, FileIntegrityResult]
    missing_files: List[str]
    permission_issues: List[str]
    integrity_issues: List[str]
    recommendations: List[str]
    error_details: List[str]


class FileSystemValidator:
    """Validates file system permissions and integrity for the integration."""

    # Required files for the integration
    REQUIRED_FILES = {
        "__init__.py": "file",
        "config_flow.py": "file", 
        "const.py": "file",
        "manifest.json": "file",
        "models.py": "file",
        "storage.py": "file",
        "strings.json": "file",
        "services.yaml": "file"
    }

    # Optional files that should be checked if present
    OPTIONAL_FILES = {
        "schedule_manager.py": "file",
        "presence_manager.py": "file",
        "buffer_manager.py": "file",
        "dashboard_service.py": "file",
        "frontend_manager.py": "file",
        "troubleshooting.py": "file",
        "logging_config.py": "file"
    }

    def __init__(self, hass: HomeAssistant, domain: str = DOMAIN) -> None:
        """Initialize the file system validator."""
        self.hass = hass
        self.domain = domain
        self._integration_path = self._get_integration_path()

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        current_file = Path(__file__)
        return current_file.parent

    async def validate_file_system(self) -> FileSystemValidationResult:
        """Perform comprehensive file system validation."""
        _LOGGER.debug("Starting file system validation for domain: %s", self.domain)
        
        try:
            # Check file permissions
            permissions = await self._check_all_permissions()
            
            # Check file integrity
            integrity = await self._check_file_integrity()
            
            # Identify issues
            missing_files = self._identify_missing_files(permissions, integrity)
            permission_issues = self._identify_permission_issues(permissions)
            integrity_issues = self._identify_integrity_issues(integrity)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                permissions, integrity, missing_files, permission_issues, integrity_issues
            )
            
            # Determine overall success
            success = (
                len(missing_files) == 0 and
                len(permission_issues) == 0 and
                len(integrity_issues) == 0
            )
            
            return FileSystemValidationResult(
                success=success,
                permissions=permissions,
                integrity=integrity,
                missing_files=missing_files,
                permission_issues=permission_issues,
                integrity_issues=integrity_issues,
                recommendations=recommendations,
                error_details=[]
            )
            
        except Exception as e:
            error_msg = f"File system validation failed: {str(e)}"
            _LOGGER.error(error_msg)
            
            return FileSystemValidationResult(
                success=False,
                permissions={},
                integrity={},
                missing_files=[],
                permission_issues=[],
                integrity_issues=[],
                recommendations=[],
                error_details=[error_msg]
            )

    async def check_file_permissions(self, file_path: str) -> FilePermissionDetails:
        """Check detailed permissions for a specific file or directory."""
        path = Path(file_path)
        
        try:
            exists = path.exists()
            
            if not exists:
                return FilePermissionDetails(
                    path=str(path),
                    exists=False,
                    readable=False,
                    writable=False,
                    executable=False,
                    is_file=False,
                    is_directory=False,
                    error_message=f"Path does not exist: {path}"
                )
            
            # Basic permission checks
            readable = os.access(path, os.R_OK)
            writable = os.access(path, os.W_OK)
            executable = os.access(path, os.X_OK)
            is_file = path.is_file()
            is_directory = path.is_dir()
            
            # Get file size
            size = None
            if is_file:
                try:
                    size = path.stat().st_size
                except OSError:
                    size = None
            
            # Get detailed permission information
            permissions_octal = None
            owner_readable = owner_writable = owner_executable = False
            group_readable = group_writable = group_executable = False
            other_readable = other_writable = other_executable = False
            
            try:
                file_stat = path.stat()
                mode = file_stat.st_mode
                permissions_octal = oct(stat.S_IMODE(mode))
                
                # Owner permissions
                owner_readable = bool(mode & stat.S_IRUSR)
                owner_writable = bool(mode & stat.S_IWUSR)
                owner_executable = bool(mode & stat.S_IXUSR)
                
                # Group permissions
                group_readable = bool(mode & stat.S_IRGRP)
                group_writable = bool(mode & stat.S_IWGRP)
                group_executable = bool(mode & stat.S_IXGRP)
                
                # Other permissions
                other_readable = bool(mode & stat.S_IROTH)
                other_writable = bool(mode & stat.S_IWOTH)
                other_executable = bool(mode & stat.S_IXOTH)
                
            except OSError as e:
                _LOGGER.debug("Could not get detailed permissions for %s: %s", path, e)
            
            return FilePermissionDetails(
                path=str(path),
                exists=exists,
                readable=readable,
                writable=writable,
                executable=executable,
                is_file=is_file,
                is_directory=is_directory,
                size=size,
                permissions_octal=permissions_octal,
                owner_readable=owner_readable,
                owner_writable=owner_writable,
                owner_executable=owner_executable,
                group_readable=group_readable,
                group_writable=group_writable,
                group_executable=group_executable,
                other_readable=other_readable,
                other_writable=other_writable,
                other_executable=other_executable
            )
            
        except Exception as e:
            return FilePermissionDetails(
                path=str(path),
                exists=False,
                readable=False,
                writable=False,
                executable=False,
                is_file=False,
                is_directory=False,
                error_message=f"Permission check failed: {str(e)}"
            )

    async def check_directory_permissions(self, directory_path: str) -> FilePermissionDetails:
        """Check permissions for a directory with directory-specific validation."""
        perm_details = await self.check_file_permissions(directory_path)
        
        if perm_details.exists and perm_details.is_directory:
            # For directories, executable permission is needed to access contents
            if not perm_details.executable:
                if not perm_details.error_message:
                    perm_details.error_message = "Directory lacks execute permission for access"
                else:
                    perm_details.error_message += "; Directory lacks execute permission"
        
        return perm_details

    async def validate_file_integrity(self, file_path: str, expected_type: str = "file") -> FileIntegrityResult:
        """Validate the integrity of a specific file."""
        path = Path(file_path)
        
        try:
            exists = path.exists()
            
            if not exists:
                return FileIntegrityResult(
                    path=str(path),
                    exists=False,
                    is_valid=False,
                    expected_type=expected_type,
                    error_message=f"File does not exist: {path}"
                )
            
            # Check if type matches expectation
            actual_type = "directory" if path.is_dir() else "file"
            type_matches = actual_type == expected_type
            
            # Check readability
            is_readable = os.access(path, os.R_OK)
            
            # Get file size and check if empty
            size = None
            is_empty = None
            if path.is_file():
                try:
                    size = path.stat().st_size
                    is_empty = size == 0
                except OSError:
                    size = None
                    is_empty = None
            
            # Validate content based on file type
            content_valid = await self._validate_file_content(path, expected_type)
            
            # Determine overall validity
            is_valid = (
                exists and
                type_matches and
                is_readable and
                content_valid and
                (is_empty is False if expected_type == "file" else True)
            )
            
            return FileIntegrityResult(
                path=str(path),
                exists=exists,
                is_valid=is_valid,
                expected_type=expected_type,
                actual_type=actual_type,
                size=size,
                is_empty=is_empty,
                is_readable=is_readable,
                content_valid=content_valid
            )
            
        except Exception as e:
            return FileIntegrityResult(
                path=str(path),
                exists=False,
                is_valid=False,
                expected_type=expected_type,
                error_message=f"Integrity check failed: {str(e)}"
            )

    def generate_permission_report(self, validation_result: FileSystemValidationResult) -> str:
        """Generate a detailed permission report."""
        report_lines = [
            "=" * 60,
            "FILE SYSTEM PERMISSION REPORT",
            "=" * 60,
            "",
            f"Integration: {self.domain}",
            f"Path: {self._integration_path}",
            f"Overall Status: {'✓ PASS' if validation_result.success else '✗ FAIL'}",
            ""
        ]
        
        # Permission details
        if validation_result.permissions:
            report_lines.extend([
                "FILE PERMISSIONS:",
                "-" * 17
            ])
            
            for file_path, perm in validation_result.permissions.items():
                status = "✓" if perm.exists and perm.readable else "✗"
                file_type = "DIR" if perm.is_directory else "FILE"
                size_info = f" ({perm.size} bytes)" if perm.size is not None else ""
                
                report_lines.append(f"{status} {file_type} {file_path}{size_info}")
                
                if perm.permissions_octal:
                    report_lines.append(f"    Permissions: {perm.permissions_octal}")
                
                perm_details = []
                if perm.owner_readable: perm_details.append("owner:r")
                if perm.owner_writable: perm_details.append("owner:w")
                if perm.owner_executable: perm_details.append("owner:x")
                if perm.group_readable: perm_details.append("group:r")
                if perm.group_writable: perm_details.append("group:w")
                if perm.group_executable: perm_details.append("group:x")
                if perm.other_readable: perm_details.append("other:r")
                if perm.other_writable: perm_details.append("other:w")
                if perm.other_executable: perm_details.append("other:x")
                
                if perm_details:
                    report_lines.append(f"    Details: {', '.join(perm_details)}")
                
                if perm.error_message:
                    report_lines.append(f"    Error: {perm.error_message}")
                
                report_lines.append("")
        
        # Issues
        if validation_result.missing_files:
            report_lines.extend([
                "MISSING FILES:",
                "-" * 14
            ])
            for missing_file in validation_result.missing_files:
                report_lines.append(f"✗ {missing_file}")
            report_lines.append("")
        
        if validation_result.permission_issues:
            report_lines.extend([
                "PERMISSION ISSUES:",
                "-" * 18
            ])
            for issue in validation_result.permission_issues:
                report_lines.append(f"• {issue}")
            report_lines.append("")
        
        if validation_result.integrity_issues:
            report_lines.extend([
                "INTEGRITY ISSUES:",
                "-" * 17
            ])
            for issue in validation_result.integrity_issues:
                report_lines.append(f"• {issue}")
            report_lines.append("")
        
        # Recommendations
        if validation_result.recommendations:
            report_lines.extend([
                "RECOMMENDATIONS:",
                "-" * 16
            ])
            for rec in validation_result.recommendations:
                report_lines.append(f"• {rec}")
            report_lines.append("")
        
        report_lines.extend([
            "=" * 60,
            "END OF PERMISSION REPORT",
            "=" * 60
        ])
        
        return "\n".join(report_lines)

    async def _check_all_permissions(self) -> Dict[str, FilePermissionDetails]:
        """Check permissions for all integration files."""
        permissions = {}
        
        # Check integration directory
        dir_perms = await self.check_directory_permissions(str(self._integration_path))
        permissions["integration_directory"] = dir_perms
        
        # Check required files
        for filename, file_type in self.REQUIRED_FILES.items():
            file_path = self._integration_path / filename
            if file_type == "directory":
                perms = await self.check_directory_permissions(str(file_path))
            else:
                perms = await self.check_file_permissions(str(file_path))
            permissions[filename] = perms
        
        # Check optional files if they exist
        for filename, file_type in self.OPTIONAL_FILES.items():
            file_path = self._integration_path / filename
            if file_path.exists():
                if file_type == "directory":
                    perms = await self.check_directory_permissions(str(file_path))
                else:
                    perms = await self.check_file_permissions(str(file_path))
                permissions[filename] = perms
        
        return permissions

    async def _check_file_integrity(self) -> Dict[str, FileIntegrityResult]:
        """Check integrity for all integration files."""
        integrity = {}
        
        # Check required files
        for filename, file_type in self.REQUIRED_FILES.items():
            file_path = self._integration_path / filename
            result = await self.validate_file_integrity(str(file_path), file_type)
            integrity[filename] = result
        
        # Check optional files if they exist
        for filename, file_type in self.OPTIONAL_FILES.items():
            file_path = self._integration_path / filename
            if file_path.exists():
                result = await self.validate_file_integrity(str(file_path), file_type)
                integrity[filename] = result
        
        return integrity

    async def _validate_file_content(self, path: Path, expected_type: str) -> bool:
        """Validate file content based on file type."""
        if not path.exists() or not path.is_file():
            return False
        
        try:
            # Basic validation - check if file is readable and not corrupted
            if not os.access(path, os.R_OK):
                return False
            
            # File-specific validation
            if path.suffix == ".py":
                return await self._validate_python_file(path)
            elif path.suffix == ".json":
                return await self._validate_json_file(path)
            elif path.suffix == ".yaml" or path.suffix == ".yml":
                return await self._validate_yaml_file(path)
            else:
                # For other files, just check if they're readable and not empty
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read(1)  # Read just one character to test
                        return len(content) > 0 or path.stat().st_size == 0
                except (UnicodeDecodeError, OSError):
                    # Try binary read for non-text files
                    try:
                        with open(path, 'rb') as f:
                            content = f.read(1)
                            return True  # If we can read it, it's valid
                    except OSError:
                        return False
            
        except Exception as e:
            _LOGGER.debug("Content validation failed for %s: %s", path, e)
            return False

    async def _validate_python_file(self, path: Path) -> bool:
        """Validate Python file syntax."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to compile the Python code
            compile(content, str(path), 'exec')
            return True
            
        except (SyntaxError, UnicodeDecodeError, OSError):
            return False
        except Exception:
            # Other compilation errors might still be valid Python
            return True

    async def _validate_json_file(self, path: Path) -> bool:
        """Validate JSON file syntax."""
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                json.load(f)
            return True
            
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return False

    async def _validate_yaml_file(self, path: Path) -> bool:
        """Validate YAML file syntax."""
        try:
            import yaml
            with open(path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            return True
            
        except (yaml.YAMLError, UnicodeDecodeError, OSError):
            return False
        except ImportError:
            # If yaml is not available, just check if file is readable
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    f.read()
                return True
            except (UnicodeDecodeError, OSError):
                return False

    def _identify_missing_files(
        self, 
        permissions: Dict[str, FilePermissionDetails],
        integrity: Dict[str, FileIntegrityResult]
    ) -> List[str]:
        """Identify missing required files."""
        missing_files = []
        
        for filename in self.REQUIRED_FILES:
            if filename not in permissions or not permissions[filename].exists:
                missing_files.append(filename)
            elif filename in integrity and not integrity[filename].exists:
                missing_files.append(filename)
        
        return missing_files

    def _identify_permission_issues(self, permissions: Dict[str, FilePermissionDetails]) -> List[str]:
        """Identify permission-related issues."""
        issues = []
        
        for filename, perm in permissions.items():
            if perm.error_message:
                issues.append(f"{filename}: {perm.error_message}")
            elif perm.exists:
                if not perm.readable:
                    issues.append(f"{filename}: File is not readable")
                if perm.is_directory and not perm.executable:
                    issues.append(f"{filename}: Directory is not accessible (no execute permission)")
        
        return issues

    def _identify_integrity_issues(self, integrity: Dict[str, FileIntegrityResult]) -> List[str]:
        """Identify file integrity issues."""
        issues = []
        
        for filename, result in integrity.items():
            if result.error_message:
                issues.append(f"{filename}: {result.error_message}")
            elif not result.is_valid:
                if not result.exists:
                    issues.append(f"{filename}: File does not exist")
                elif result.actual_type != result.expected_type:
                    issues.append(f"{filename}: Expected {result.expected_type}, found {result.actual_type}")
                elif not result.is_readable:
                    issues.append(f"{filename}: File is not readable")
                elif not result.content_valid:
                    issues.append(f"{filename}: File content is invalid or corrupted")
                elif result.is_empty:
                    issues.append(f"{filename}: File is empty")
        
        return issues

    def _generate_recommendations(
        self,
        permissions: Dict[str, FilePermissionDetails],
        integrity: Dict[str, FileIntegrityResult],
        missing_files: List[str],
        permission_issues: List[str],
        integrity_issues: List[str]
    ) -> List[str]:
        """Generate recommendations for fixing issues."""
        recommendations = []
        
        if missing_files:
            recommendations.append(f"Create missing required files: {', '.join(missing_files)}")
        
        # Permission-specific recommendations
        for filename, perm in permissions.items():
            if perm.exists and not perm.readable:
                recommendations.append(f"Fix read permissions for {filename}: chmod +r {perm.path}")
            if perm.is_directory and perm.exists and not perm.executable:
                recommendations.append(f"Fix directory access for {filename}: chmod +x {perm.path}")
        
        # Integrity-specific recommendations
        for filename, result in integrity.items():
            if result.exists and not result.content_valid:
                if filename.endswith('.py'):
                    recommendations.append(f"Fix Python syntax errors in {filename}")
                elif filename.endswith('.json'):
                    recommendations.append(f"Fix JSON syntax errors in {filename}")
                elif filename.endswith(('.yaml', '.yml')):
                    recommendations.append(f"Fix YAML syntax errors in {filename}")
                else:
                    recommendations.append(f"Fix file corruption in {filename}")
        
        # General recommendations
        if permission_issues or integrity_issues:
            recommendations.append("Check file system permissions and ensure Home Assistant has proper access")
            recommendations.append("Verify integration was installed correctly and files are not corrupted")
        
        if not missing_files and not permission_issues and not integrity_issues:
            recommendations.append("All file system checks passed - no issues detected")
        
        return recommendations