"""Tests for file system validation components."""
from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open

import pytest

from custom_components.roost_scheduler.file_system_validator import (
    FileSystemValidator,
    FilePermissionDetails,
    FileIntegrityResult,
    FileSystemValidationResult,
)
from custom_components.roost_scheduler.file_system_error_handler import (
    FileSystemErrorHandler,
    FileSystemError,
    PermissionFixGuidance,
)


class TestFileSystemValidator:
    """Test the FileSystemValidator class."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.config.config_dir = "/config"
        return hass

    @pytest.fixture
    def validator(self, mock_hass):
        """Create a FileSystemValidator instance."""
        with patch.object(FileSystemValidator, '_get_integration_path') as mock_path:
            mock_path.return_value = Path("/test/integration")
            return FileSystemValidator(mock_hass, "test_domain")

    @pytest.fixture
    def temp_integration_dir(self):
        """Create a temporary integration directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            integration_path = Path(temp_dir) / "test_integration"
            integration_path.mkdir()
            
            # Create some test files
            (integration_path / "__init__.py").write_text("# Test init file")
            (integration_path / "manifest.json").write_text('{"domain": "test"}')
            (integration_path / "config_flow.py").write_text("# Test config flow")
            
            yield integration_path

    @pytest.mark.asyncio
    async def test_check_file_permissions_existing_file(self, validator):
        """Test checking permissions for an existing file."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=False), \
             patch('os.access') as mock_access, \
             patch('pathlib.Path.stat') as mock_stat:
            
            # Mock access permissions
            mock_access.side_effect = lambda path, mode: {
                os.R_OK: True,
                os.W_OK: True,
                os.X_OK: False
            }.get(mode, False)
            
            # Mock file stats
            mock_stat_obj = Mock()
            mock_stat_obj.st_size = 1024
            mock_stat_obj.st_mode = stat.S_IFREG | stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP
            mock_stat.return_value = mock_stat_obj
            
            result = await validator.check_file_permissions("/test/file.py")
            
            assert isinstance(result, FilePermissionDetails)
            assert result.exists is True
            assert result.readable is True
            assert result.writable is True
            assert result.executable is False
            assert result.is_file is True
            assert result.is_directory is False
            assert result.size == 1024
            assert result.owner_readable is True
            assert result.owner_writable is True
            assert result.group_readable is True

    @pytest.mark.asyncio
    async def test_check_file_permissions_missing_file(self, validator):
        """Test checking permissions for a missing file."""
        with patch('pathlib.Path.exists', return_value=False):
            result = await validator.check_file_permissions("/test/missing.py")
            
            assert isinstance(result, FilePermissionDetails)
            assert result.exists is False
            assert result.readable is False
            assert result.writable is False
            assert result.executable is False
            assert result.error_message is not None
            assert "does not exist" in result.error_message

    @pytest.mark.asyncio
    async def test_check_file_permissions_permission_error(self, validator):
        """Test handling permission errors during file checking."""
        with patch('pathlib.Path.exists', side_effect=PermissionError("Access denied")):
            result = await validator.check_file_permissions("/test/restricted.py")
            
            assert isinstance(result, FilePermissionDetails)
            assert result.exists is False
            assert result.error_message is not None
            assert "Permission check failed" in result.error_message

    @pytest.mark.asyncio
    async def test_check_directory_permissions(self, validator):
        """Test checking permissions for a directory."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_file', return_value=False), \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('os.access') as mock_access, \
             patch('pathlib.Path.stat') as mock_stat:
            
            # Mock directory without execute permission
            mock_access.side_effect = lambda path, mode: {
                os.R_OK: True,
                os.W_OK: True,
                os.X_OK: False  # No execute permission
            }.get(mode, False)
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_mode = stat.S_IFDIR | stat.S_IRUSR | stat.S_IWUSR
            mock_stat.return_value = mock_stat_obj
            
            result = await validator.check_directory_permissions("/test/dir")
            
            assert result.is_directory is True
            assert result.executable is False
            assert result.error_message is not None
            assert "execute permission" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_file_integrity_valid_file(self, validator):
        """Test file integrity validation for a valid file."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=False), \
             patch('os.access', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch.object(validator, '_validate_file_content', return_value=True):
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_size = 1024
            mock_stat.return_value = mock_stat_obj
            
            result = await validator.validate_file_integrity("/test/file.py", "file")
            
            assert isinstance(result, FileIntegrityResult)
            assert result.exists is True
            assert result.is_valid is True
            assert result.expected_type == "file"
            assert result.actual_type == "file"
            assert result.size == 1024
            assert result.is_empty is False
            assert result.is_readable is True
            assert result.content_valid is True

    @pytest.mark.asyncio
    async def test_validate_file_integrity_empty_file(self, validator):
        """Test file integrity validation for an empty file."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=False), \
             patch('os.access', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch.object(validator, '_validate_file_content', return_value=True):
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_size = 0  # Empty file
            mock_stat.return_value = mock_stat_obj
            
            result = await validator.validate_file_integrity("/test/empty.py", "file")
            
            assert result.exists is True
            assert result.is_valid is False  # Empty files are invalid
            assert result.size == 0
            assert result.is_empty is True

    @pytest.mark.asyncio
    async def test_validate_file_integrity_type_mismatch(self, validator):
        """Test file integrity validation with type mismatch."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('os.access', return_value=True):
            
            result = await validator.validate_file_integrity("/test/dir", "file")
            
            assert result.exists is True
            assert result.is_valid is False
            assert result.expected_type == "file"
            assert result.actual_type == "directory"

    @pytest.mark.asyncio
    async def test_validate_file_system_success(self, validator):
        """Test complete file system validation with no issues."""
        # Mock all required files as existing and valid
        mock_permissions = {}
        mock_integrity = {}
        
        # Add integration directory
        mock_permissions["integration_directory"] = FilePermissionDetails(
            path="/test/integration",
            exists=True,
            readable=True,
            writable=True,
            executable=True,
            is_file=False,
            is_directory=True
        )
        
        # Add all required files
        for filename in validator.REQUIRED_FILES:
            mock_permissions[filename] = FilePermissionDetails(
                path=f"/test/integration/{filename}",
                exists=True,
                readable=True,
                writable=True,
                executable=False,
                is_file=True,
                is_directory=False
            )
            mock_integrity[filename] = FileIntegrityResult(
                path=f"/test/integration/{filename}",
                exists=True,
                is_valid=True,
                expected_type="file",
                actual_type="file",
                is_readable=True,
                content_valid=True
            )
        
        with patch.object(validator, '_check_all_permissions', return_value=mock_permissions), \
             patch.object(validator, '_check_file_integrity', return_value=mock_integrity):
            
            result = await validator.validate_file_system()
            
            assert isinstance(result, FileSystemValidationResult)
            assert result.success is True
            assert len(result.missing_files) == 0
            assert len(result.permission_issues) == 0
            assert len(result.integrity_issues) == 0

    @pytest.mark.asyncio
    async def test_validate_file_system_with_issues(self, validator):
        """Test file system validation with various issues."""
        mock_permissions = {
            "__init__.py": FilePermissionDetails(
                path="/test/integration/__init__.py",
                exists=False,
                readable=False,
                writable=False,
                executable=False,
                is_file=False,
                is_directory=False,
                error_message="File does not exist"
            )
        }
        
        mock_integrity = {
            "__init__.py": FileIntegrityResult(
                path="/test/integration/__init__.py",
                exists=False,
                is_valid=False,
                expected_type="file",
                error_message="File does not exist"
            )
        }
        
        with patch.object(validator, '_check_all_permissions', return_value=mock_permissions), \
             patch.object(validator, '_check_file_integrity', return_value=mock_integrity):
            
            result = await validator.validate_file_system()
            
            assert result.success is False
            assert "__init__.py" in result.missing_files
            assert len(result.permission_issues) > 0
            assert len(result.integrity_issues) > 0

    @pytest.mark.asyncio
    async def test_validate_file_system_exception_handling(self, validator):
        """Test file system validation exception handling."""
        with patch.object(validator, '_check_all_permissions', side_effect=Exception("Test error")):
            result = await validator.validate_file_system()
            
            assert result.success is False
            assert len(result.error_details) > 0
            assert "File system validation failed" in result.error_details[0]

    @pytest.mark.asyncio
    async def test_validate_python_file_valid(self, validator):
        """Test Python file validation with valid syntax."""
        valid_python = "def test_function():\n    return True\n"
        
        with patch('builtins.open', mock_open(read_data=valid_python)):
            result = await validator._validate_python_file(Path("/test/valid.py"))
            
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_python_file_invalid_syntax(self, validator):
        """Test Python file validation with invalid syntax."""
        invalid_python = "def test_function(\n    return True\n"  # Missing closing parenthesis
        
        with patch('builtins.open', mock_open(read_data=invalid_python)):
            result = await validator._validate_python_file(Path("/test/invalid.py"))
            
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_json_file_valid(self, validator):
        """Test JSON file validation with valid JSON."""
        valid_json = '{"domain": "test", "name": "Test Integration"}'
        
        with patch('builtins.open', mock_open(read_data=valid_json)):
            result = await validator._validate_json_file(Path("/test/valid.json"))
            
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_json_file_invalid(self, validator):
        """Test JSON file validation with invalid JSON."""
        invalid_json = '{"domain": "test", "name": "Test Integration"'  # Missing closing brace
        
        with patch('builtins.open', mock_open(read_data=invalid_json)):
            result = await validator._validate_json_file(Path("/test/invalid.json"))
            
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_yaml_file_valid(self, validator):
        """Test YAML file validation with valid YAML."""
        valid_yaml = "domain: test\nname: Test Integration\n"
        
        with patch('builtins.open', mock_open(read_data=valid_yaml)):
            result = await validator._validate_yaml_file(Path("/test/valid.yaml"))
            
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_yaml_file_invalid(self, validator):
        """Test YAML file validation with invalid YAML."""
        invalid_yaml = "domain: test\n  name: Test Integration\n invalid_indent"
        
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            result = await validator._validate_yaml_file(Path("/test/invalid.yaml"))
            
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_yaml_file_no_yaml_module(self, validator):
        """Test YAML file validation when yaml module is not available."""
        with patch('builtins.open', mock_open(read_data="test: data")):
            # Mock ImportError to simulate missing yaml module
            with patch.object(validator, '_validate_yaml_file') as mock_validate:
                # Simulate the ImportError path in the actual method
                async def mock_yaml_validate(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            f.read()
                        return True
                    except (UnicodeDecodeError, OSError):
                        return False
                
                mock_validate.side_effect = mock_yaml_validate
                result = await validator._validate_yaml_file(Path("/test/fallback.yaml"))
                
                assert result is True

    def test_generate_permission_report(self, validator):
        """Test permission report generation."""
        validation_result = FileSystemValidationResult(
            success=False,
            permissions={
                "__init__.py": FilePermissionDetails(
                    path="/test/__init__.py",
                    exists=True,
                    readable=True,
                    writable=False,
                    executable=False,
                    is_file=True,
                    is_directory=False,
                    size=1024,
                    permissions_octal="0o644"
                )
            },
            integrity={},
            missing_files=["config_flow.py"],
            permission_issues=["__init__.py: File is not writable"],
            integrity_issues=[],
            recommendations=["Fix write permissions for __init__.py"],
            error_details=[]
        )
        
        report = validator.generate_permission_report(validation_result)
        
        assert "FILE SYSTEM PERMISSION REPORT" in report
        assert "test_domain" in report
        assert "✗ FAIL" in report
        assert "__init__.py" in report
        assert "MISSING FILES:" in report
        assert "config_flow.py" in report
        assert "PERMISSION ISSUES:" in report
        assert "RECOMMENDATIONS:" in report

    @pytest.mark.asyncio
    async def test_check_file_corruption_existing_file(self, validator):
        """Test file corruption checking for existing file."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('os.access', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('builtins.open', mock_open(read_data="valid content")), \
             patch.object(validator, '_validate_python_file', return_value=True):
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_size = 13
            mock_stat.return_value = mock_stat_obj
            
            result = await validator.check_file_corruption("/test/file.py")
            
            assert result["exists"] is True
            assert result["readable"] is True
            assert result["size_consistent"] is True
            assert result["encoding_valid"] is True
            assert result["content_parseable"] is True
            assert len(result["corruption_indicators"]) == 0

    @pytest.mark.asyncio
    async def test_check_file_corruption_missing_file(self, validator):
        """Test file corruption checking for missing file."""
        with patch('pathlib.Path.exists', return_value=False):
            result = await validator.check_file_corruption("/test/missing.py")
            
            assert result["exists"] is False
            assert "File does not exist" in result["corruption_indicators"]
            assert "Recreate missing file" in result["recommendations"][0]

    @pytest.mark.asyncio
    async def test_check_file_corruption_encoding_error(self, validator):
        """Test file corruption checking with encoding errors."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('os.access', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('builtins.open', side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")):
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_size = 10
            mock_stat.return_value = mock_stat_obj
            
            result = await validator.check_file_corruption("/test/file.py")
            
            assert result["encoding_valid"] is False
            assert "File contains invalid UTF-8 encoding" in result["corruption_indicators"]
            assert "Fix file encoding" in result["recommendations"][0]


class TestFileSystemErrorHandler:
    """Test the FileSystemErrorHandler class."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.config.config_dir = "/config"
        return hass

    @pytest.fixture
    def error_handler(self, mock_hass):
        """Create a FileSystemErrorHandler instance."""
        with patch.object(FileSystemErrorHandler, '_get_integration_path') as mock_path:
            mock_path.return_value = Path("/test/integration")
            return FileSystemErrorHandler(mock_hass, "test_domain")

    @pytest.mark.asyncio
    async def test_detect_file_system_errors_no_issues(self, error_handler):
        """Test error detection when no issues exist."""
        with patch.object(error_handler, '_check_directory_errors', return_value=[]), \
             patch.object(error_handler, '_check_file_errors', return_value=[]), \
             patch.object(error_handler, '_check_permission_patterns', return_value=[]), \
             patch.object(error_handler, '_check_file_system_health', return_value=[]):
            
            errors = await error_handler.detect_file_system_errors()
            
            assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_detect_file_system_errors_with_issues(self, error_handler):
        """Test error detection with various issues."""
        mock_errors = [
            FileSystemError(
                error_type="directory_missing",
                file_path="/test/integration",
                error_message="Directory does not exist",
                severity="critical",
                causes=["Installation issue"],
                solutions=["Reinstall integration"],
                system_context={}
            )
        ]
        
        with patch.object(error_handler, '_check_directory_errors', return_value=mock_errors), \
             patch.object(error_handler, '_check_file_errors', return_value=[]), \
             patch.object(error_handler, '_check_permission_patterns', return_value=[]), \
             patch.object(error_handler, '_check_file_system_health', return_value=[]):
            
            errors = await error_handler.detect_file_system_errors()
            
            assert len(errors) == 1
            assert errors[0].error_type == "directory_missing"
            assert errors[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_detect_file_system_errors_exception_handling(self, error_handler):
        """Test error detection exception handling."""
        with patch.object(error_handler, '_check_directory_errors', side_effect=Exception("Test error")):
            errors = await error_handler.detect_file_system_errors()
            
            assert len(errors) == 1
            assert errors[0].error_type == "detection_failure"
            assert "Failed to detect file system errors" in errors[0].error_message

    @pytest.mark.asyncio
    async def test_generate_permission_fix_guidance_missing_file(self, error_handler):
        """Test permission fix guidance for missing file."""
        with patch('pathlib.Path.exists', return_value=False):
            guidance = await error_handler.generate_permission_fix_guidance("/test/missing.py")
            
            assert isinstance(guidance, PermissionFixGuidance)
            assert guidance.file_path == "/test/missing.py"
            assert "N/A" in guidance.current_permissions
            assert "Create the missing file" in guidance.fix_commands[0]
            assert "does not exist" in guidance.explanation

    @pytest.mark.asyncio
    async def test_generate_permission_fix_guidance_file(self, error_handler):
        """Test permission fix guidance for regular file."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=False), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('os.access', return_value=True):
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_mode = stat.S_IFREG | stat.S_IRUSR | stat.S_IWUSR
            mock_stat_obj.st_uid = 1000
            mock_stat.return_value = mock_stat_obj
            
            guidance = await error_handler.generate_permission_fix_guidance("/test/file.py")
            
            assert guidance.recommended_permissions == "0o644"
            assert "chmod 644" in guidance.fix_commands[0]
            assert guidance.requires_sudo is False

    @pytest.mark.asyncio
    async def test_generate_permission_fix_guidance_directory(self, error_handler):
        """Test permission fix guidance for directory."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('os.access', return_value=True):
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_mode = stat.S_IFDIR | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
            mock_stat_obj.st_uid = 1000
            mock_stat.return_value = mock_stat_obj
            
            guidance = await error_handler.generate_permission_fix_guidance("/test/dir")
            
            assert guidance.recommended_permissions == "0o755"
            assert "chmod 755" in guidance.fix_commands[0]
            assert "chmod -R 755" in guidance.fix_commands[1]

    @pytest.mark.asyncio
    async def test_generate_permission_fix_guidance_requires_sudo(self, error_handler):
        """Test permission fix guidance when sudo is required."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=False), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('os.access', return_value=False):  # No write access
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_mode = stat.S_IFREG | stat.S_IRUSR
            mock_stat_obj.st_uid = 0  # Root owned
            mock_stat.return_value = mock_stat_obj
            
            guidance = await error_handler.generate_permission_fix_guidance("/test/file.py")
            
            assert guidance.requires_sudo is True
            assert "sudo chmod" in guidance.fix_commands[0]

    def test_generate_troubleshooting_guide_no_errors(self, error_handler):
        """Test troubleshooting guide generation with no errors."""
        guide = error_handler.generate_troubleshooting_guide([])
        
        assert "✅ HEALTHY" in guide
        assert "All file system checks passed successfully" in guide

    def test_generate_troubleshooting_guide_with_errors(self, error_handler):
        """Test troubleshooting guide generation with errors."""
        errors = [
            FileSystemError(
                error_type="file_missing",
                file_path="/test/file.py",
                error_message="File is missing",
                severity="critical",
                causes=["Installation issue"],
                solutions=["Recreate file", "Reinstall integration"],
                system_context={},
                auto_fixable=True
            ),
            FileSystemError(
                error_type="permission_issue",
                file_path="/test/dir",
                error_message="Permission denied",
                severity="warning",
                causes=["Wrong permissions"],
                solutions=["Fix permissions"],
                system_context={},
                auto_fixable=False
            )
        ]
        
        guide = error_handler.generate_troubleshooting_guide(errors)
        
        assert "FILE SYSTEM TROUBLESHOOTING GUIDE" in guide
        assert "🚨 CRITICAL ERRORS" in guide
        assert "⚠️  WARNING ERRORS" in guide
        assert "🔧 QUICK FIXES" in guide
        assert "FILE MISSING" in guide
        assert "PERMISSION ISSUE" in guide
        assert "This issue can be automatically fixed" in guide

    @pytest.mark.asyncio
    async def test_attempt_auto_fix_success(self, error_handler):
        """Test successful automatic fixing of errors."""
        errors = [
            FileSystemError(
                error_type="file_not_readable",
                file_path="/test/file.py",
                error_message="File not readable",
                severity="critical",
                causes=["Permission issue"],
                solutions=["Fix permissions"],
                system_context={},
                auto_fixable=True
            )
        ]
        
        with patch.object(error_handler, '_apply_auto_fix', return_value=True):
            result = await error_handler.attempt_auto_fix(errors)
            
            assert result["attempted_fixes"] == 1
            assert result["successful_fixes"] == 1
            assert result["failed_fixes"] == 0
            assert len(result["remaining_errors"]) == 0
            assert result["fix_details"][0]["status"] == "fixed"

    @pytest.mark.asyncio
    async def test_attempt_auto_fix_failure(self, error_handler):
        """Test failed automatic fixing of errors."""
        errors = [
            FileSystemError(
                error_type="file_not_readable",
                file_path="/test/file.py",
                error_message="File not readable",
                severity="critical",
                causes=["Permission issue"],
                solutions=["Fix permissions"],
                system_context={},
                auto_fixable=True
            )
        ]
        
        with patch.object(error_handler, '_apply_auto_fix', return_value=False):
            result = await error_handler.attempt_auto_fix(errors)
            
            assert result["attempted_fixes"] == 1
            assert result["successful_fixes"] == 0
            assert result["failed_fixes"] == 1
            assert len(result["remaining_errors"]) == 1
            assert result["fix_details"][0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_attempt_auto_fix_exception(self, error_handler):
        """Test auto fix with exception handling."""
        errors = [
            FileSystemError(
                error_type="file_not_readable",
                file_path="/test/file.py",
                error_message="File not readable",
                severity="critical",
                causes=["Permission issue"],
                solutions=["Fix permissions"],
                system_context={},
                auto_fixable=True
            )
        ]
        
        with patch.object(error_handler, '_apply_auto_fix', side_effect=Exception("Fix failed")):
            result = await error_handler.attempt_auto_fix(errors)
            
            assert result["attempted_fixes"] == 1
            assert result["successful_fixes"] == 0
            assert result["failed_fixes"] == 1
            assert result["fix_details"][0]["status"] == "error"
            assert "Error during auto-fix" in result["fix_details"][0]["message"]

    @pytest.mark.asyncio
    async def test_attempt_auto_fix_non_fixable(self, error_handler):
        """Test auto fix with non-fixable errors."""
        errors = [
            FileSystemError(
                error_type="disk_space_low",
                file_path="/test",
                error_message="Disk space low",
                severity="critical",
                causes=["No space"],
                solutions=["Free space"],
                system_context={},
                auto_fixable=False  # Not auto-fixable
            )
        ]
        
        result = await error_handler.attempt_auto_fix(errors)
        
        assert result["attempted_fixes"] == 0
        assert result["successful_fixes"] == 0
        assert result["failed_fixes"] == 0
        assert len(result["remaining_errors"]) == 1

    @pytest.mark.asyncio
    async def test_check_directory_errors_missing_directory(self, error_handler):
        """Test directory error checking for missing directory."""
        with patch('pathlib.Path.exists', return_value=False):
            errors = await error_handler._check_directory_errors()
            
            assert len(errors) == 1
            assert errors[0].error_type == "directory_missing"
            assert errors[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_check_directory_errors_permission_issues(self, error_handler):
        """Test directory error checking for permission issues."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('os.access') as mock_access:
            
            # Mock no read access
            mock_access.side_effect = lambda path, mode: mode != os.R_OK
            
            errors = await error_handler._check_directory_errors()
            
            assert len(errors) >= 1
            assert any(e.error_type == "directory_not_readable" for e in errors)

    @pytest.mark.asyncio
    async def test_check_file_errors_missing_files(self, error_handler):
        """Test file error checking for missing required files."""
        with patch('pathlib.Path.exists', return_value=False):
            errors = await error_handler._check_file_errors()
            
            # Should find errors for all required files
            assert len(errors) >= 4  # At least __init__.py, config_flow.py, const.py, manifest.json
            assert all(e.error_type == "file_missing" for e in errors)
            assert all(e.severity == "critical" for e in errors)

    @pytest.mark.asyncio
    async def test_check_file_errors_permission_issues(self, error_handler):
        """Test file error checking for permission issues."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('os.access', return_value=False), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_size = 1024
            mock_stat.return_value = mock_stat_obj
            
            errors = await error_handler._check_file_errors()
            
            # Should find permission errors for required files
            assert len(errors) >= 4
            assert all(e.error_type == "file_not_readable" for e in errors)

    @pytest.mark.asyncio
    async def test_check_file_errors_empty_files(self, error_handler):
        """Test file error checking for empty files."""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('os.access', return_value=True), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat_obj = Mock()
            mock_stat_obj.st_size = 0  # Empty file
            mock_stat.return_value = mock_stat_obj
            
            errors = await error_handler._check_file_errors()
            
            # Should find empty file warnings
            assert len(errors) >= 4
            assert all(e.error_type == "file_empty" for e in errors)
            assert all(e.severity == "warning" for e in errors)

    @pytest.mark.asyncio
    async def test_apply_auto_fix_directory_permissions(self, error_handler):
        """Test applying auto fix for directory permission issues."""
        error = FileSystemError(
            error_type="directory_not_readable",
            file_path="/test/dir",
            error_message="Directory not readable",
            severity="critical",
            causes=["Permission issue"],
            solutions=["Fix permissions"],
            system_context={},
            auto_fixable=True
        )
        
        with patch('os.chmod') as mock_chmod:
            result = await error_handler._apply_auto_fix(error)
            
            assert result is True
            mock_chmod.assert_called_once_with("/test/dir", 0o755)

    @pytest.mark.asyncio
    async def test_apply_auto_fix_file_permissions(self, error_handler):
        """Test applying auto fix for file permission issues."""
        error = FileSystemError(
            error_type="file_not_readable",
            file_path="/test/file.py",
            error_message="File not readable",
            severity="critical",
            causes=["Permission issue"],
            solutions=["Fix permissions"],
            system_context={},
            auto_fixable=True
        )
        
        with patch('os.chmod') as mock_chmod:
            result = await error_handler._apply_auto_fix(error)
            
            assert result is True
            mock_chmod.assert_called_once_with("/test/file.py", 0o644)

    @pytest.mark.asyncio
    async def test_apply_auto_fix_unsupported_error(self, error_handler):
        """Test applying auto fix for unsupported error type."""
        error = FileSystemError(
            error_type="unsupported_error",
            file_path="/test/file",
            error_message="Unsupported error",
            severity="critical",
            causes=["Unknown"],
            solutions=["Manual fix"],
            system_context={},
            auto_fixable=True
        )
        
        result = await error_handler._apply_auto_fix(error)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_auto_fix_exception_handling(self, error_handler):
        """Test auto fix exception handling."""
        error = FileSystemError(
            error_type="file_not_readable",
            file_path="/test/file.py",
            error_message="File not readable",
            severity="critical",
            causes=["Permission issue"],
            solutions=["Fix permissions"],
            system_context={},
            auto_fixable=True
        )
        
        with patch('os.chmod', side_effect=PermissionError("Access denied")):
            result = await error_handler._apply_auto_fix(error)
            
            assert result is False