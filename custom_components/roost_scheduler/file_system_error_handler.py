"""File system error handling and troubleshooting for Roost Scheduler integration."""
from __future__ import annotations

import logging
import os
import platform
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class FileSystemError:
    """Represents a file system error with context and solutions."""
    error_type: str
    file_path: str
    error_message: str
    severity: str  # 'critical', 'warning', 'info'
    causes: List[str]
    solutions: List[str]
    system_context: Dict[str, Any]
    auto_fixable: bool = False


@dataclass
class PermissionFixGuidance:
    """Guidance for fixing permission issues."""
    file_path: str
    current_permissions: str
    recommended_permissions: str
    fix_commands: List[str]
    explanation: str
    requires_sudo: bool = False


class FileSystemErrorHandler:
    """Handles file system errors and provides troubleshooting guidance."""

    def __init__(self, hass: HomeAssistant, domain: str = DOMAIN) -> None:
        """Initialize the error handler."""
        self.hass = hass
        self.domain = domain
        self._integration_path = self._get_integration_path()
        self._system_info = self._collect_system_info()

    def _get_integration_path(self) -> Path:
        """Get the path to the integration directory."""
        current_file = Path(__file__)
        return current_file.parent

    def _collect_system_info(self) -> Dict[str, Any]:
        """Collect system information for error context."""
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0],
            "user": os.getenv("USER", "unknown"),
            "home_assistant_config_dir": self.hass.config.config_dir if self.hass else "unknown"
        }

    async def detect_file_system_errors(self) -> List[FileSystemError]:
        """Detect and categorize file system errors."""
        errors = []
        
        try:
            # Check integration directory
            dir_errors = await self._check_directory_errors()
            errors.extend(dir_errors)
            
            # Check individual files
            file_errors = await self._check_file_errors()
            errors.extend(file_errors)
            
            # Check permission patterns
            permission_errors = await self._check_permission_patterns()
            errors.extend(permission_errors)
            
            # Check disk space and file system health
            fs_health_errors = await self._check_file_system_health()
            errors.extend(fs_health_errors)
            
        except Exception as e:
            _LOGGER.error("Error during file system error detection: %s", e)
            errors.append(FileSystemError(
                error_type="detection_failure",
                file_path=str(self._integration_path),
                error_message=f"Failed to detect file system errors: {str(e)}",
                severity="critical",
                causes=["System error during error detection"],
                solutions=["Check system logs", "Restart Home Assistant"],
                system_context=self._system_info
            ))
        
        return errors

    async def generate_permission_fix_guidance(self, file_path: str) -> PermissionFixGuidance:
        """Generate specific guidance for fixing permission issues."""
        path = Path(file_path)
        
        try:
            if not path.exists():
                return PermissionFixGuidance(
                    file_path=file_path,
                    current_permissions="N/A (file does not exist)",
                    recommended_permissions="N/A",
                    fix_commands=[f"Create the missing file: {file_path}"],
                    explanation="File does not exist and needs to be created",
                    requires_sudo=False
                )
            
            # Get current permissions
            file_stat = path.stat()
            current_perms = oct(stat.S_IMODE(file_stat.st_mode))
            
            # Determine recommended permissions
            if path.is_dir():
                recommended_perms = "0o755"  # rwxr-xr-x for directories
                recommended_octal = "755"
            else:
                recommended_perms = "0o644"  # rw-r--r-- for files
                recommended_octal = "644"
            
            # Generate fix commands
            fix_commands = []
            explanation_parts = []
            requires_sudo = False
            
            # Check if we can write to the file/directory
            parent_writable = os.access(path.parent, os.W_OK)
            file_writable = os.access(path, os.W_OK) if path.exists() else parent_writable
            
            if not file_writable:
                requires_sudo = True
                fix_commands.append(f"sudo chmod {recommended_octal} {file_path}")
                explanation_parts.append("Requires sudo due to insufficient permissions")
            else:
                fix_commands.append(f"chmod {recommended_octal} {file_path}")
            
            # Add ownership fix if needed
            try:
                import pwd
                current_user = pwd.getpwuid(os.getuid()).pw_name
                file_owner = pwd.getpwuid(file_stat.st_uid).pw_name
                
                if file_owner != current_user:
                    if requires_sudo:
                        fix_commands.append(f"sudo chown {current_user}:{current_user} {file_path}")
                    else:
                        fix_commands.append(f"chown {current_user}:{current_user} {file_path}")
                    explanation_parts.append(f"File owned by {file_owner}, should be owned by {current_user}")
            except (ImportError, KeyError, OSError):
                # pwd module not available or other error
                pass
            
            # Add recursive fix for directories if needed
            if path.is_dir():
                if requires_sudo:
                    fix_commands.append(f"sudo chmod -R {recommended_octal} {file_path}")
                else:
                    fix_commands.append(f"chmod -R {recommended_octal} {file_path}")
                explanation_parts.append("Applied recursively to directory contents")
            
            explanation = "; ".join(explanation_parts) if explanation_parts else f"Set standard permissions ({recommended_octal})"
            
            return PermissionFixGuidance(
                file_path=file_path,
                current_permissions=current_perms,
                recommended_permissions=recommended_perms,
                fix_commands=fix_commands,
                explanation=explanation,
                requires_sudo=requires_sudo
            )
            
        except Exception as e:
            return PermissionFixGuidance(
                file_path=file_path,
                current_permissions="unknown",
                recommended_permissions="unknown",
                fix_commands=[f"# Error generating fix commands: {str(e)}"],
                explanation=f"Could not analyze permissions: {str(e)}",
                requires_sudo=False
            )

    def generate_troubleshooting_guide(self, errors: List[FileSystemError]) -> str:
        """Generate a comprehensive troubleshooting guide."""
        if not errors:
            return self._generate_success_guide()
        
        guide_lines = [
            "=" * 70,
            "FILE SYSTEM TROUBLESHOOTING GUIDE",
            "=" * 70,
            "",
            f"Integration: {self.domain}",
            f"Path: {self._integration_path}",
            f"System: {self._system_info['platform']} {self._system_info['architecture']}",
            f"User: {self._system_info['user']}",
            "",
            f"Found {len(errors)} file system issue(s):",
            ""
        ]
        
        # Group errors by severity
        critical_errors = [e for e in errors if e.severity == "critical"]
        warning_errors = [e for e in errors if e.severity == "warning"]
        info_errors = [e for e in errors if e.severity == "info"]
        
        # Critical errors first
        if critical_errors:
            guide_lines.extend([
                "🚨 CRITICAL ERRORS (Must be fixed):",
                "-" * 40
            ])
            for i, error in enumerate(critical_errors, 1):
                guide_lines.extend(self._format_error_section(i, error))
            guide_lines.append("")
        
        # Warning errors
        if warning_errors:
            guide_lines.extend([
                "⚠️  WARNING ERRORS (Should be fixed):",
                "-" * 40
            ])
            for i, error in enumerate(warning_errors, len(critical_errors) + 1):
                guide_lines.extend(self._format_error_section(i, error))
            guide_lines.append("")
        
        # Info errors
        if info_errors:
            guide_lines.extend([
                "ℹ️  INFORMATIONAL (Optional fixes):",
                "-" * 40
            ])
            for i, error in enumerate(info_errors, len(critical_errors) + len(warning_errors) + 1):
                guide_lines.extend(self._format_error_section(i, error))
            guide_lines.append("")
        
        # Quick fix section
        auto_fixable = [e for e in errors if e.auto_fixable]
        if auto_fixable:
            guide_lines.extend([
                "🔧 QUICK FIXES:",
                "-" * 15,
                "The following issues can be automatically resolved:",
                ""
            ])
            for error in auto_fixable:
                guide_lines.append(f"• {error.file_path}: {error.error_message}")
                for solution in error.solutions[:2]:  # Show first 2 solutions
                    guide_lines.append(f"  → {solution}")
                guide_lines.append("")
        
        # General recommendations
        guide_lines.extend([
            "📋 GENERAL RECOMMENDATIONS:",
            "-" * 28,
            "1. Fix critical errors first, then warnings",
            "2. Restart Home Assistant after making file system changes",
            "3. Check file permissions match your system's requirements",
            "4. Ensure integration files are not corrupted",
            "5. Verify sufficient disk space is available",
            "",
            "💡 GETTING HELP:",
            "-" * 16,
            "If issues persist after following this guide:",
            "• Check Home Assistant logs for additional errors",
            "• Verify your installation method (HACS, manual, etc.)",
            "• Consider reinstalling the integration",
            "• Report persistent issues with this troubleshooting output",
            "",
            "=" * 70,
            "END OF TROUBLESHOOTING GUIDE",
            "=" * 70
        ])
        
        return "\n".join(guide_lines)

    async def attempt_auto_fix(self, errors: List[FileSystemError]) -> Dict[str, Any]:
        """Attempt to automatically fix file system errors where possible."""
        fix_results = {
            "attempted_fixes": 0,
            "successful_fixes": 0,
            "failed_fixes": 0,
            "fix_details": [],
            "remaining_errors": []
        }
        
        for error in errors:
            if not error.auto_fixable:
                fix_results["remaining_errors"].append(error)
                continue
            
            fix_results["attempted_fixes"] += 1
            
            try:
                success = await self._apply_auto_fix(error)
                
                if success:
                    fix_results["successful_fixes"] += 1
                    fix_results["fix_details"].append({
                        "file_path": error.file_path,
                        "error_type": error.error_type,
                        "status": "fixed",
                        "message": f"Successfully fixed {error.error_type}"
                    })
                else:
                    fix_results["failed_fixes"] += 1
                    fix_results["remaining_errors"].append(error)
                    fix_results["fix_details"].append({
                        "file_path": error.file_path,
                        "error_type": error.error_type,
                        "status": "failed",
                        "message": f"Could not automatically fix {error.error_type}"
                    })
                    
            except Exception as e:
                fix_results["failed_fixes"] += 1
                fix_results["remaining_errors"].append(error)
                fix_results["fix_details"].append({
                    "file_path": error.file_path,
                    "error_type": error.error_type,
                    "status": "error",
                    "message": f"Error during auto-fix: {str(e)}"
                })
        
        return fix_results

    def _generate_success_guide(self) -> str:
        """Generate a guide when no errors are found."""
        return "\n".join([
            "=" * 50,
            "FILE SYSTEM STATUS: ✅ HEALTHY",
            "=" * 50,
            "",
            f"Integration: {self.domain}",
            f"Path: {self._integration_path}",
            "",
            "All file system checks passed successfully!",
            "",
            "✅ File permissions are correct",
            "✅ All required files are present",
            "✅ Files are readable and not corrupted",
            "✅ Directory structure is valid",
            "",
            "Your integration should be working correctly.",
            "If you're still experiencing issues, they may be",
            "related to configuration or other system components.",
            "",
            "=" * 50
        ])

    def _format_error_section(self, index: int, error: FileSystemError) -> List[str]:
        """Format an error section for the troubleshooting guide."""
        lines = [
            f"{index}. {error.error_type.upper().replace('_', ' ')}",
            f"   File: {error.file_path}",
            f"   Error: {error.error_message}",
            ""
        ]
        
        if error.causes:
            lines.append("   Possible Causes:")
            for cause in error.causes:
                lines.append(f"   • {cause}")
            lines.append("")
        
        if error.solutions:
            lines.append("   Solutions:")
            for solution in error.solutions:
                lines.append(f"   → {solution}")
            lines.append("")
        
        if error.auto_fixable:
            lines.append("   ✨ This issue can be automatically fixed")
            lines.append("")
        
        return lines

    async def _check_directory_errors(self) -> List[FileSystemError]:
        """Check for directory-related errors."""
        errors = []
        
        try:
            if not self._integration_path.exists():
                errors.append(FileSystemError(
                    error_type="directory_missing",
                    file_path=str(self._integration_path),
                    error_message="Integration directory does not exist",
                    severity="critical",
                    causes=[
                        "Integration not properly installed",
                        "Directory was deleted",
                        "Installation path is incorrect"
                    ],
                    solutions=[
                        "Reinstall the integration",
                        "Check installation method (HACS, manual)",
                        "Verify Home Assistant configuration directory"
                    ],
                    system_context=self._system_info
                ))
                return errors
            
            if not os.access(self._integration_path, os.R_OK):
                errors.append(FileSystemError(
                    error_type="directory_not_readable",
                    file_path=str(self._integration_path),
                    error_message="Integration directory is not readable",
                    severity="critical",
                    causes=[
                        "Insufficient permissions",
                        "Directory ownership issues",
                        "File system corruption"
                    ],
                    solutions=[
                        f"chmod +r {self._integration_path}",
                        f"chown -R {os.getenv('USER', 'homeassistant')} {self._integration_path}",
                        "Check file system integrity"
                    ],
                    system_context=self._system_info,
                    auto_fixable=True
                ))
            
            if not os.access(self._integration_path, os.X_OK):
                errors.append(FileSystemError(
                    error_type="directory_not_accessible",
                    file_path=str(self._integration_path),
                    error_message="Integration directory is not accessible",
                    severity="critical",
                    causes=[
                        "Missing execute permission",
                        "Directory ownership issues"
                    ],
                    solutions=[
                        f"chmod +x {self._integration_path}",
                        f"chmod 755 {self._integration_path}"
                    ],
                    system_context=self._system_info,
                    auto_fixable=True
                ))
                
        except Exception as e:
            errors.append(FileSystemError(
                error_type="directory_check_failed",
                file_path=str(self._integration_path),
                error_message=f"Failed to check directory: {str(e)}",
                severity="warning",
                causes=["System error", "Permission issues"],
                solutions=["Check system logs", "Verify file system health"],
                system_context=self._system_info
            ))
        
        return errors

    async def _check_file_errors(self) -> List[FileSystemError]:
        """Check for individual file errors."""
        errors = []
        
        required_files = [
            "__init__.py",
            "config_flow.py",
            "const.py",
            "manifest.json"
        ]
        
        for filename in required_files:
            file_path = self._integration_path / filename
            
            try:
                if not file_path.exists():
                    errors.append(FileSystemError(
                        error_type="file_missing",
                        file_path=str(file_path),
                        error_message=f"Required file {filename} is missing",
                        severity="critical",
                        causes=[
                            "Incomplete installation",
                            "File was deleted",
                            "Installation corruption"
                        ],
                        solutions=[
                            f"Recreate {filename}",
                            "Reinstall the integration",
                            "Check installation integrity"
                        ],
                        system_context=self._system_info
                    ))
                    continue
                
                if not os.access(file_path, os.R_OK):
                    errors.append(FileSystemError(
                        error_type="file_not_readable",
                        file_path=str(file_path),
                        error_message=f"File {filename} is not readable",
                        severity="critical",
                        causes=[
                            "Insufficient read permissions",
                            "File ownership issues"
                        ],
                        solutions=[
                            f"chmod +r {file_path}",
                            f"chmod 644 {file_path}"
                        ],
                        system_context=self._system_info,
                        auto_fixable=True
                    ))
                
                # Check file size (empty files might indicate corruption)
                if file_path.stat().st_size == 0:
                    errors.append(FileSystemError(
                        error_type="file_empty",
                        file_path=str(file_path),
                        error_message=f"File {filename} is empty",
                        severity="warning",
                        causes=[
                            "File corruption",
                            "Incomplete write operation",
                            "Installation error"
                        ],
                        solutions=[
                            f"Restore {filename} from backup",
                            "Reinstall the integration",
                            "Check for file system errors"
                        ],
                        system_context=self._system_info
                    ))
                    
            except Exception as e:
                errors.append(FileSystemError(
                    error_type="file_check_failed",
                    file_path=str(file_path),
                    error_message=f"Failed to check {filename}: {str(e)}",
                    severity="warning",
                    causes=["System error", "File system issues"],
                    solutions=["Check system logs", "Verify file system health"],
                    system_context=self._system_info
                ))
        
        return errors

    async def _check_permission_patterns(self) -> List[FileSystemError]:
        """Check for common permission patterns and issues."""
        errors = []
        
        try:
            # Check if running as root (common issue)
            if os.getuid() == 0:
                errors.append(FileSystemError(
                    error_type="running_as_root",
                    file_path=str(self._integration_path),
                    error_message="Home Assistant is running as root",
                    severity="warning",
                    causes=[
                        "Improper installation",
                        "Security misconfiguration"
                    ],
                    solutions=[
                        "Run Home Assistant as non-root user",
                        "Check installation documentation",
                        "Review security best practices"
                    ],
                    system_context=self._system_info
                ))
            
            # Check for overly restrictive permissions
            if self._integration_path.exists():
                dir_stat = self._integration_path.stat()
                dir_mode = stat.S_IMODE(dir_stat.st_mode)
                
                # Directory should be at least readable and executable
                if not (dir_mode & stat.S_IRUSR and dir_mode & stat.S_IXUSR):
                    errors.append(FileSystemError(
                        error_type="restrictive_permissions",
                        file_path=str(self._integration_path),
                        error_message="Directory has overly restrictive permissions",
                        severity="critical",
                        causes=[
                            "Incorrect chmod command",
                            "Security policy too strict"
                        ],
                        solutions=[
                            f"chmod 755 {self._integration_path}",
                            "Review permission requirements"
                        ],
                        system_context=self._system_info,
                        auto_fixable=True
                    ))
                    
        except (OSError, AttributeError):
            # getuid() not available on Windows, or other OS errors
            pass
        except Exception as e:
            errors.append(FileSystemError(
                error_type="permission_check_failed",
                file_path=str(self._integration_path),
                error_message=f"Failed to check permission patterns: {str(e)}",
                severity="info",
                causes=["System compatibility", "OS-specific issues"],
                solutions=["Check OS-specific documentation"],
                system_context=self._system_info
            ))
        
        return errors

    async def _check_file_system_health(self) -> List[FileSystemError]:
        """Check overall file system health."""
        errors = []
        
        try:
            # Check disk space
            if self._integration_path.exists():
                statvfs = os.statvfs(self._integration_path)
                free_space = statvfs.f_frsize * statvfs.f_bavail
                total_space = statvfs.f_frsize * statvfs.f_blocks
                usage_percent = ((total_space - free_space) / total_space) * 100
                
                if usage_percent > 95:
                    errors.append(FileSystemError(
                        error_type="disk_space_low",
                        file_path=str(self._integration_path),
                        error_message=f"Disk space critically low ({usage_percent:.1f}% used)",
                        severity="critical",
                        causes=[
                            "Insufficient disk space",
                            "Log files consuming space",
                            "Temporary files not cleaned"
                        ],
                        solutions=[
                            "Free up disk space",
                            "Clean temporary files",
                            "Check log file sizes"
                        ],
                        system_context=self._system_info
                    ))
                elif usage_percent > 85:
                    errors.append(FileSystemError(
                        error_type="disk_space_warning",
                        file_path=str(self._integration_path),
                        error_message=f"Disk space running low ({usage_percent:.1f}% used)",
                        severity="warning",
                        causes=["Disk space getting low"],
                        solutions=["Monitor disk usage", "Plan for cleanup"],
                        system_context=self._system_info
                    ))
                    
        except (OSError, AttributeError):
            # statvfs not available on all systems
            pass
        except Exception as e:
            errors.append(FileSystemError(
                error_type="health_check_failed",
                file_path=str(self._integration_path),
                error_message=f"Failed to check file system health: {str(e)}",
                severity="info",
                causes=["System compatibility issues"],
                solutions=["Manual disk space check"],
                system_context=self._system_info
            ))
        
        return errors

    async def _apply_auto_fix(self, error: FileSystemError) -> bool:
        """Apply automatic fix for an error."""
        try:
            if error.error_type == "directory_not_readable":
                os.chmod(error.file_path, 0o755)
                return True
            elif error.error_type == "directory_not_accessible":
                os.chmod(error.file_path, 0o755)
                return True
            elif error.error_type == "file_not_readable":
                os.chmod(error.file_path, 0o644)
                return True
            elif error.error_type == "restrictive_permissions":
                if Path(error.file_path).is_dir():
                    os.chmod(error.file_path, 0o755)
                else:
                    os.chmod(error.file_path, 0o644)
                return True
            
            return False
            
        except Exception as e:
            _LOGGER.debug("Auto-fix failed for %s: %s", error.file_path, e)
            return False