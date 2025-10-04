"""Unit tests for domain consistency checking functionality."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch
import pytest

from custom_components.roost_scheduler.domain_consistency_checker import (
    DomainConsistencyChecker,
    ConsistencyResult,
    FixResult
)


class TestDomainConsistencyChecker:
    """Test cases for DomainConsistencyChecker."""

    @pytest.fixture
    def temp_integration_path(self):
        """Create a temporary integration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            integration_path = Path(temp_dir) / "test_integration"
            integration_path.mkdir()
            yield integration_path

    @pytest.fixture
    def checker(self, temp_integration_path):
        """Create a DomainConsistencyChecker instance."""
        return DomainConsistencyChecker(str(temp_integration_path))

    @pytest.fixture
    def mock_checker(self):
        """Create a DomainConsistencyChecker with mocked paths."""
        with patch.object(Path, 'exists'):
            return DomainConsistencyChecker("/mock/path")

    # Domain extraction method tests
    @pytest.mark.asyncio
    async def test_check_manifest_domain_success(self, mock_checker):
        """Test successful domain extraction from manifest.json."""
        manifest_data = {
            "domain": "test_domain",
            "name": "Test Integration",
            "version": "1.0.0"
        }
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(manifest_data))):
                domain = await mock_checker.check_manifest_domain()

        assert domain == "test_domain"

    @pytest.mark.asyncio
    async def test_check_manifest_domain_missing_file(self, mock_checker):
        """Test domain extraction when manifest.json is missing."""
        with patch.object(Path, "exists", return_value=False):
            domain = await mock_checker.check_manifest_domain()

        assert domain is None

    @pytest.mark.asyncio
    async def test_check_manifest_domain_missing_domain_field(self, mock_checker):
        """Test domain extraction when domain field is missing."""
        manifest_data = {
            "name": "Test Integration",
            "version": "1.0.0"
            # Missing domain field
        }
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(manifest_data))):
                domain = await mock_checker.check_manifest_domain()

        assert domain is None

    @pytest.mark.asyncio
    async def test_check_manifest_domain_empty_domain(self, mock_checker):
        """Test domain extraction when domain field is empty."""
        manifest_data = {
            "domain": "",
            "name": "Test Integration",
            "version": "1.0.0"
        }
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(manifest_data))):
                domain = await mock_checker.check_manifest_domain()

        assert domain is None

    @pytest.mark.asyncio
    async def test_check_manifest_domain_invalid_json(self, mock_checker):
        """Test domain extraction with invalid JSON."""
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="invalid json")):
                domain = await mock_checker.check_manifest_domain()

        assert domain is None

    @pytest.mark.asyncio
    async def test_check_const_domain_success(self, mock_checker):
        """Test successful domain extraction from const.py."""
        const_content = '''"""Constants for test integration."""
DOMAIN = "test_domain"
VERSION = "1.0.0"
'''
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=const_content)):
                domain = await mock_checker.check_const_domain()

        assert domain == "test_domain"

    @pytest.mark.asyncio
    async def test_check_const_domain_single_quotes(self, mock_checker):
        """Test domain extraction with single quotes."""
        const_content = "DOMAIN = 'test_domain'"
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=const_content)):
                domain = await mock_checker.check_const_domain()

        assert domain == "test_domain"

    @pytest.mark.asyncio
    async def test_check_const_domain_missing_file(self, mock_checker):
        """Test domain extraction when const.py is missing."""
        with patch.object(Path, "exists", return_value=False):
            domain = await mock_checker.check_const_domain()

        assert domain is None

    @pytest.mark.asyncio
    async def test_check_const_domain_missing_constant(self, mock_checker):
        """Test domain extraction when DOMAIN constant is missing."""
        const_content = '''"""Constants for test integration."""
VERSION = "1.0.0"
NAME = "Test Integration"
'''
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=const_content)):
                domain = await mock_checker.check_const_domain()

        assert domain is None

    @pytest.mark.asyncio
    async def test_check_const_domain_variable_assignment(self, mock_checker):
        """Test domain extraction with variable assignment."""
        const_content = '''"""Constants for test integration."""
DOMAIN_NAME = "test_domain"
DOMAIN = DOMAIN_NAME
'''
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=const_content)):
                domain = await mock_checker.check_const_domain()

        assert domain == "DOMAIN_NAME"  # Returns the variable name, not resolved value

    @pytest.mark.asyncio
    async def test_check_config_flow_domain_success(self, mock_checker):
        """Test successful domain extraction from config_flow.py."""
        config_flow_content = '''"""Config flow for test integration."""
from homeassistant import config_entries
from .const import DOMAIN

class TestConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""
    pass
'''
        
        # Mock const domain check to return the expected domain
        mock_checker.check_const_domain = AsyncMock(return_value="test_domain")
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=config_flow_content)):
                domain = await mock_checker.check_config_flow_domain()

        assert domain == "test_domain"

    @pytest.mark.asyncio
    async def test_check_config_flow_domain_direct_string(self, mock_checker):
        """Test domain extraction with direct string in config flow."""
        config_flow_content = '''"""Config flow for test integration."""
from homeassistant import config_entries

class TestConfigFlow(config_entries.ConfigFlow, domain="test_domain"):
    """Handle a config flow."""
    pass
'''
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=config_flow_content)):
                domain = await mock_checker.check_config_flow_domain()

        assert domain == "test_domain"

    @pytest.mark.asyncio
    async def test_check_config_flow_domain_missing_file(self, mock_checker):
        """Test domain extraction when config_flow.py is missing."""
        with patch.object(Path, "exists", return_value=False):
            domain = await mock_checker.check_config_flow_domain()

        assert domain is None

    @pytest.mark.asyncio
    async def test_check_config_flow_domain_no_domain_config(self, mock_checker):
        """Test domain extraction when no domain configuration is found."""
        config_flow_content = '''"""Config flow for test integration."""
from homeassistant import config_entries

class TestConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow."""
    pass
'''
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=config_flow_content)):
                domain = await mock_checker.check_config_flow_domain()

        assert domain is None

    # Consistency validation tests
    @pytest.mark.asyncio
    async def test_validate_consistency_all_consistent(self, mock_checker):
        """Test consistency validation when all domains match."""
        mock_checker.check_manifest_domain = AsyncMock(return_value="test_domain")
        mock_checker.check_const_domain = AsyncMock(return_value="test_domain")
        mock_checker.check_config_flow_domain = AsyncMock(return_value="test_domain")

        result = await mock_checker.validate_consistency()

        assert isinstance(result, ConsistencyResult)
        assert result.consistent is True
        assert result.manifest_domain == "test_domain"
        assert result.const_domain == "test_domain"
        assert result.config_flow_domain == "test_domain"
        assert len(result.issues) == 0
        assert "Domain configuration is consistent across all files" in result.recommendations

    @pytest.mark.asyncio
    async def test_validate_consistency_domain_mismatch(self, mock_checker):
        """Test consistency validation with domain mismatch."""
        mock_checker.check_manifest_domain = AsyncMock(return_value="domain1")
        mock_checker.check_const_domain = AsyncMock(return_value="domain2")
        mock_checker.check_config_flow_domain = AsyncMock(return_value="domain3")

        result = await mock_checker.validate_consistency()

        assert isinstance(result, ConsistencyResult)
        assert result.consistent is False
        assert result.manifest_domain == "domain1"
        assert result.const_domain == "domain2"
        assert result.config_flow_domain == "domain3"
        assert len(result.issues) >= 1
        assert any("Domain mismatch detected" in issue for issue in result.issues)
        assert any("Manifest domain 'domain1' does not match const domain 'domain2'" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_consistency_missing_domains(self, mock_checker):
        """Test consistency validation with missing domains."""
        mock_checker.check_manifest_domain = AsyncMock(return_value=None)
        mock_checker.check_const_domain = AsyncMock(return_value=None)
        mock_checker.check_config_flow_domain = AsyncMock(return_value=None)

        result = await mock_checker.validate_consistency()

        assert isinstance(result, ConsistencyResult)
        assert result.consistent is False
        assert result.manifest_domain is None
        assert result.const_domain is None
        assert result.config_flow_domain is None
        assert len(result.issues) >= 1
        assert any("No domain configuration found" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_consistency_partial_missing(self, mock_checker):
        """Test consistency validation with some missing domains."""
        mock_checker.check_manifest_domain = AsyncMock(return_value="test_domain")
        mock_checker.check_const_domain = AsyncMock(return_value=None)
        mock_checker.check_config_flow_domain = AsyncMock(return_value="test_domain")

        result = await mock_checker.validate_consistency()

        assert isinstance(result, ConsistencyResult)
        assert result.consistent is False
        assert result.manifest_domain == "test_domain"
        assert result.const_domain is None
        assert result.config_flow_domain == "test_domain"
        assert any("DOMAIN constant not found in const.py" in issue for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_consistency_invalid_domain_format(self, mock_checker):
        """Test consistency validation with invalid domain format."""
        mock_checker.check_manifest_domain = AsyncMock(return_value="Invalid-Domain!")
        mock_checker.check_const_domain = AsyncMock(return_value="Invalid-Domain!")
        mock_checker.check_config_flow_domain = AsyncMock(return_value="Invalid-Domain!")

        result = await mock_checker.validate_consistency()

        assert isinstance(result, ConsistencyResult)
        assert result.consistent is False
        assert len(result.issues) >= 3  # One for each file with invalid format
        assert any("Invalid domain format" in issue for issue in result.issues)
        assert any("Domain should contain only lowercase letters" in rec for rec in result.recommendations)

    # Automatic fixing tests
    @pytest.mark.asyncio
    async def test_fix_inconsistencies_already_consistent(self, mock_checker):
        """Test fixing when domains are already consistent."""
        consistency_result = ConsistencyResult(
            consistent=True,
            manifest_domain="test_domain",
            const_domain="test_domain",
            config_flow_domain="test_domain",
            issues=[],
            warnings=[],
            recommendations=[]
        )
        mock_checker.validate_consistency = AsyncMock(return_value=consistency_result)

        result = await mock_checker.fix_inconsistencies()

        assert isinstance(result, FixResult)
        assert result.success is True
        assert "No fixes needed" in result.fixes_applied[0]
        assert len(result.errors) == 0
        assert result.backup_created is False

    @pytest.mark.asyncio
    async def test_fix_inconsistencies_successful_fix(self, mock_checker):
        """Test successful fixing of domain inconsistencies."""
        # Initial inconsistent state
        initial_consistency = ConsistencyResult(
            consistent=False,
            manifest_domain="domain1",
            const_domain="domain2",
            config_flow_domain="domain1",
            issues=["Domain mismatch"],
            warnings=[],
            recommendations=[]
        )
        
        # Final consistent state after fixing
        final_consistency = ConsistencyResult(
            consistent=True,
            manifest_domain="domain1",
            const_domain="domain1",
            config_flow_domain="domain1",
            issues=[],
            warnings=[],
            recommendations=[]
        )
        
        mock_checker.validate_consistency = AsyncMock(side_effect=[initial_consistency, final_consistency])
        mock_checker._create_backup = AsyncMock()
        mock_checker._determine_correct_domain = MagicMock(return_value="domain1")
        mock_checker._fix_manifest_domain = AsyncMock()
        mock_checker._fix_const_domain = AsyncMock()

        result = await mock_checker.fix_inconsistencies()

        assert isinstance(result, FixResult)
        assert result.success is True
        assert result.backup_created is True
        assert "Created backup" in result.fixes_applied[0]
        assert "Updated const.py DOMAIN to 'domain1'" in result.fixes_applied
        assert "Domain consistency successfully restored" in result.fixes_applied
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_fix_inconsistencies_backup_failure(self, mock_checker):
        """Test fixing when backup creation fails."""
        consistency_result = ConsistencyResult(
            consistent=False,
            manifest_domain="domain1",
            const_domain="domain2",
            config_flow_domain="domain1",
            issues=["Domain mismatch"],
            warnings=[],
            recommendations=[]
        )
        
        mock_checker.validate_consistency = AsyncMock(return_value=consistency_result)
        mock_checker._create_backup = AsyncMock(side_effect=Exception("Backup failed"))
        mock_checker._determine_correct_domain = MagicMock(return_value="domain1")

        result = await mock_checker.fix_inconsistencies()

        assert isinstance(result, FixResult)
        assert result.backup_created is False
        assert "Could not create backup: Backup failed" in result.warnings

    @pytest.mark.asyncio
    async def test_fix_inconsistencies_no_correct_domain(self, mock_checker):
        """Test fixing when correct domain cannot be determined."""
        consistency_result = ConsistencyResult(
            consistent=False,
            manifest_domain=None,
            const_domain=None,
            config_flow_domain=None,
            issues=["No domains found"],
            warnings=[],
            recommendations=[]
        )
        
        mock_checker.validate_consistency = AsyncMock(return_value=consistency_result)
        mock_checker._create_backup = AsyncMock()
        mock_checker._determine_correct_domain = MagicMock(return_value=None)

        result = await mock_checker.fix_inconsistencies()

        assert isinstance(result, FixResult)
        assert result.success is False
        assert "Could not determine correct domain" in result.errors[0]

    @pytest.mark.asyncio
    async def test_fix_inconsistencies_fix_failure(self, mock_checker):
        """Test fixing when individual fix operations fail."""
        consistency_result = ConsistencyResult(
            consistent=False,
            manifest_domain="domain1",
            const_domain="domain2",
            config_flow_domain="domain1",
            issues=["Domain mismatch"],
            warnings=[],
            recommendations=[]
        )
        
        mock_checker.validate_consistency = AsyncMock(return_value=consistency_result)
        mock_checker._create_backup = AsyncMock()
        mock_checker._determine_correct_domain = MagicMock(return_value="domain1")
        mock_checker._fix_manifest_domain = AsyncMock()
        mock_checker._fix_const_domain = AsyncMock(side_effect=Exception("Fix failed"))

        result = await mock_checker.fix_inconsistencies()

        assert isinstance(result, FixResult)
        assert result.success is False
        assert "Failed to fix const.py: Fix failed" in result.errors

    # Helper method tests
    def test_is_valid_domain_format_valid_domains(self, mock_checker):
        """Test domain format validation with valid domains."""
        valid_domains = [
            "test_domain",
            "my_integration",
            "simple",
            "domain123",
            "test_domain_v2"
        ]
        
        for domain in valid_domains:
            assert mock_checker._is_valid_domain_format(domain) is True

    def test_is_valid_domain_format_invalid_domains(self, mock_checker):
        """Test domain format validation with invalid domains."""
        invalid_domains = [
            "Test-Domain",  # Contains dash
            "UPPERCASE",    # Contains uppercase
            "123domain",    # Starts with number
            "_domain",      # Starts with underscore
            "domain!",      # Contains special character
            "",             # Empty string
            None,           # None value
            "domain space", # Contains space
        ]
        
        for domain in invalid_domains:
            assert mock_checker._is_valid_domain_format(domain) is False

    def test_determine_correct_domain_priority_order(self, mock_checker):
        """Test correct domain determination follows priority order."""
        # Test manifest priority
        consistency_result = ConsistencyResult(
            consistent=False,
            manifest_domain="manifest_domain",
            const_domain="const_domain",
            config_flow_domain="config_domain",
            issues=[],
            warnings=[],
            recommendations=[]
        )
        
        correct_domain = mock_checker._determine_correct_domain(consistency_result)
        assert correct_domain == "manifest_domain"

    def test_determine_correct_domain_fallback_to_const(self, mock_checker):
        """Test correct domain determination falls back to const when manifest is None."""
        consistency_result = ConsistencyResult(
            consistent=False,
            manifest_domain=None,
            const_domain="const_domain",
            config_flow_domain="config_domain",
            issues=[],
            warnings=[],
            recommendations=[]
        )
        
        correct_domain = mock_checker._determine_correct_domain(consistency_result)
        assert correct_domain == "const_domain"

    def test_determine_correct_domain_fallback_to_config_flow(self, mock_checker):
        """Test correct domain determination falls back to config flow when others are None."""
        consistency_result = ConsistencyResult(
            consistent=False,
            manifest_domain=None,
            const_domain=None,
            config_flow_domain="config_domain",
            issues=[],
            warnings=[],
            recommendations=[]
        )
        
        correct_domain = mock_checker._determine_correct_domain(consistency_result)
        assert correct_domain == "config_domain"

    def test_determine_correct_domain_no_domains(self, mock_checker):
        """Test correct domain determination when no domains are found."""
        consistency_result = ConsistencyResult(
            consistent=False,
            manifest_domain=None,
            const_domain=None,
            config_flow_domain=None,
            issues=[],
            warnings=[],
            recommendations=[]
        )
        
        correct_domain = mock_checker._determine_correct_domain(consistency_result)
        assert correct_domain is None

    def test_determine_correct_domain_invalid_format_fallback(self, mock_checker):
        """Test correct domain determination with invalid format domains."""
        consistency_result = ConsistencyResult(
            consistent=False,
            manifest_domain="Invalid-Domain!",
            const_domain="valid_domain",
            config_flow_domain="Another-Invalid!",
            issues=[],
            warnings=[],
            recommendations=[]
        )
        
        correct_domain = mock_checker._determine_correct_domain(consistency_result)
        assert correct_domain == "valid_domain"

    # File operation tests
    @pytest.mark.asyncio
    async def test_create_backup_success(self, mock_checker):
        """Test successful backup creation."""
        with patch('shutil.copy2') as mock_copy:
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'mkdir'):
                    await mock_checker._create_backup()
                    
                    # Should attempt to copy all three files
                    assert mock_copy.call_count == 3

    @pytest.mark.asyncio
    async def test_fix_manifest_domain_success(self, mock_checker):
        """Test successful manifest domain fixing."""
        original_manifest = {
            "domain": "old_domain",
            "name": "Test Integration",
            "version": "1.0.0"
        }
        
        expected_manifest = {
            "domain": "new_domain",
            "name": "Test Integration",
            "version": "1.0.0"
        }
        
        mock_open_obj = mock_open(read_data=json.dumps(original_manifest))
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open_obj):
                await mock_checker._fix_manifest_domain("new_domain")
                
                # Check that file was written with updated domain
                handle = mock_open_obj()
                written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
                written_manifest = json.loads(written_data)
                assert written_manifest["domain"] == "new_domain"

    @pytest.mark.asyncio
    async def test_fix_manifest_domain_missing_file(self, mock_checker):
        """Test manifest domain fixing with missing file."""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                await mock_checker._fix_manifest_domain("new_domain")

    @pytest.mark.asyncio
    async def test_fix_const_domain_success(self, mock_checker):
        """Test successful const domain fixing."""
        original_content = '''"""Constants for test integration."""
DOMAIN = "old_domain"
VERSION = "1.0.0"
'''
        
        mock_open_obj = mock_open(read_data=original_content)
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open_obj):
                await mock_checker._fix_const_domain("new_domain")
                
                # Check that file was written with updated domain
                handle = mock_open_obj()
                written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
                assert 'DOMAIN = "new_domain"' in written_content

    @pytest.mark.asyncio
    async def test_fix_const_domain_add_missing_constant(self, mock_checker):
        """Test const domain fixing when DOMAIN constant is missing."""
        original_content = '''"""Constants for test integration."""
VERSION = "1.0.0"
NAME = "Test Integration"
'''
        
        mock_open_obj = mock_open(read_data=original_content)
        
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", mock_open_obj):
                await mock_checker._fix_const_domain("new_domain")
                
                # Check that DOMAIN constant was added
                handle = mock_open_obj()
                written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
                assert 'DOMAIN = "new_domain"' in written_content

    @pytest.mark.asyncio
    async def test_fix_const_domain_missing_file(self, mock_checker):
        """Test const domain fixing with missing file."""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                await mock_checker._fix_const_domain("new_domain")

    # Integration tests with real file operations
    @pytest.mark.asyncio
    async def test_real_file_operations(self, temp_integration_path):
        """Test domain consistency checker with real file operations."""
        checker = DomainConsistencyChecker(str(temp_integration_path))
        
        # Create test files
        manifest_data = {
            "domain": "test_domain",
            "name": "Test Integration",
            "version": "1.0.0",
            "config_flow": True
        }
        
        const_content = '''"""Constants for test integration."""
DOMAIN = "test_domain"
VERSION = "1.0.0"
'''
        
        config_flow_content = '''"""Config flow for test integration."""
from homeassistant import config_entries
from .const import DOMAIN

class TestConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""
    pass
'''
        
        # Write test files
        (temp_integration_path / "manifest.json").write_text(json.dumps(manifest_data))
        (temp_integration_path / "const.py").write_text(const_content)
        (temp_integration_path / "config_flow.py").write_text(config_flow_content)
        
        # Test domain extraction
        manifest_domain = await checker.check_manifest_domain()
        const_domain = await checker.check_const_domain()
        config_flow_domain = await checker.check_config_flow_domain()
        
        assert manifest_domain == "test_domain"
        assert const_domain == "test_domain"
        assert config_flow_domain == "test_domain"
        
        # Test consistency validation
        result = await checker.validate_consistency()
        assert result.consistent is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_real_file_operations_with_inconsistency(self, temp_integration_path):
        """Test domain consistency checker with real inconsistent files."""
        checker = DomainConsistencyChecker(str(temp_integration_path))
        
        # Create inconsistent test files
        manifest_data = {
            "domain": "manifest_domain",
            "name": "Test Integration",
            "version": "1.0.0",
            "config_flow": True
        }
        
        const_content = '''"""Constants for test integration."""
DOMAIN = "const_domain"
VERSION = "1.0.0"
'''
        
        # Write test files
        (temp_integration_path / "manifest.json").write_text(json.dumps(manifest_data))
        (temp_integration_path / "const.py").write_text(const_content)
        
        # Test consistency validation
        result = await checker.validate_consistency()
        assert result.consistent is False
        assert len(result.issues) >= 1
        assert any("Domain mismatch" in issue or "does not match" in issue for issue in result.issues)
        
        # Test fixing
        fix_result = await checker.fix_inconsistencies()
        assert fix_result.success is True
        assert fix_result.backup_created is True
        
        # Verify fix was applied
        updated_const_content = (temp_integration_path / "const.py").read_text()
        assert 'DOMAIN = "manifest_domain"' in updated_const_content
        
        # Verify consistency after fix
        final_result = await checker.validate_consistency()
        assert final_result.consistent is True