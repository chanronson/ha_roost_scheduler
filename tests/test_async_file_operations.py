"""Tests for async file operations in migration system."""
import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from aiofiles import open as aiofiles_open

from custom_components.roost_scheduler.migration import (
    async_read_json_file,
    async_write_json_file,
    async_copy_file,
    async_file_exists,
    async_ensure_directory,
)


class TestAsyncReadJsonFile:
    """Test async_read_json_file function."""
    
    @pytest.mark.asyncio
    async def test_read_valid_json_file(self):
        """Test reading a valid JSON file."""
        test_data = {"version": "0.4.0", "test": "data"}
        json_content = json.dumps(test_data)
        
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value=json_content)
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=None)
        
        test_path = Path("/test/file.json")
        
        with patch('aiofiles.open', return_value=mock_file):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = len(json_content)
                        
                        result = await async_read_json_file(test_path)
                        
                        assert result == test_data
                        mock_file.read.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading a file that doesn't exist returns empty dict."""
        test_path = Path("/test/nonexistent.json")
        
        with patch('pathlib.Path.exists', return_value=False):
            result = await async_read_json_file(test_path)
            assert result == {}
    
    @pytest.mark.asyncio
    async def test_read_empty_file(self):
        """Test reading an empty file returns empty dict."""
        test_path = Path("/test/empty.json")
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_file', return_value=True):
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 0
                    
                    result = await async_read_json_file(test_path)
                    assert result == {}
    
    @pytest.mark.asyncio
    async def test_read_invalid_json(self):
        """Test reading invalid JSON raises JSONDecodeError."""
        invalid_json = '{"invalid": json content}'
        
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value=invalid_json)
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=None)
        
        test_path = Path("/test/invalid.json")
        
        with patch('aiofiles.open', return_value=mock_file):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = len(invalid_json)
                        
                        with pytest.raises(json.JSONDecodeError):
                            await async_read_json_file(test_path)
    
    @pytest.mark.asyncio
    async def test_read_permission_error(self):
        """Test handling permission errors."""
        test_path = Path("/test/protected.json")
        
        with patch('aiofiles.open', side_effect=PermissionError("Access denied")):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = 100
                        
                        with pytest.raises(PermissionError):
                            await async_read_json_file(test_path)
    
    @pytest.mark.asyncio
    async def test_read_unicode_decode_error(self):
        """Test handling unicode decode errors."""
        test_path = Path("/test/binary.json")
        
        with patch('aiofiles.open', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid start byte')):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = 100
                        
                        with pytest.raises(UnicodeDecodeError):
                            await async_read_json_file(test_path)
    
    @pytest.mark.asyncio
    async def test_read_directory_instead_of_file(self):
        """Test error when path is a directory."""
        test_path = Path("/test/directory")
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_file', return_value=False):
                with patch('pathlib.Path.is_dir', return_value=True):
                    
                    with pytest.raises(OSError, match="Path is not a regular file"):
                        await async_read_json_file(test_path)


class TestAsyncWriteJsonFile:
    """Test async_write_json_file function."""
    
    @pytest.mark.asyncio
    async def test_write_valid_json_file(self):
        """Test writing valid JSON data to file."""
        test_data = {"version": "0.4.0", "test": "data"}
        test_path = Path("/test/output.json")
        
        mock_file = AsyncMock()
        mock_file.write = AsyncMock()
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiofiles.open', return_value=mock_file):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.stat') as mock_stat:
                    mock_stat.return_value.st_size = 100
                    
                    await async_write_json_file(test_path, test_data)
                    
                    mock_file.write.assert_called_once()
                    written_content = mock_file.write.call_args[0][0]
                    assert json.loads(written_content) == test_data
    
    @pytest.mark.asyncio
    async def test_write_creates_parent_directory(self):
        """Test that parent directory is created if it doesn't exist."""
        test_data = {"test": "data"}
        test_path = Path("/test/new_dir/output.json")
        
        mock_file = AsyncMock()
        mock_file.write = AsyncMock()
        mock_file.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiofiles.open', return_value=mock_file):
            with patch('pathlib.Path.exists', return_value=False):
                with patch('pathlib.Path.mkdir') as mock_mkdir:
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = 100
                        
                        await async_write_json_file(test_path, test_data)
                        
                        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
                        mock_file.write.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_write_invalid_data_type(self):
        """Test error when data is not a dictionary."""
        test_path = Path("/test/output.json")
        invalid_data = "not a dictionary"
        
        with pytest.raises(TypeError, match="Data must be a dictionary"):
            await async_write_json_file(test_path, invalid_data)
    
    @pytest.mark.asyncio
    async def test_write_permission_error(self):
        """Test handling permission errors during write."""
        test_data = {"test": "data"}
        test_path = Path("/test/protected.json")
        
        with patch('aiofiles.open', side_effect=PermissionError("Access denied")):
            with patch('pathlib.Path.exists', return_value=True):
                
                with pytest.raises(PermissionError):
                    await async_write_json_file(test_path, test_data)
    
    @pytest.mark.asyncio
    async def test_write_json_serialization_error(self):
        """Test handling JSON serialization errors."""
        test_path = Path("/test/output.json")
        
        # Create data that can't be serialized to JSON even with default=str
        # Use a circular reference which will cause a ValueError
        circular_data = {}
        circular_data["self"] = circular_data
        
        # This should fail during JSON serialization, before file operations
        with pytest.raises((TypeError, ValueError)):
            await async_write_json_file(test_path, circular_data)
    
    @pytest.mark.asyncio
    async def test_write_directory_creation_error(self):
        """Test handling errors when creating parent directory."""
        test_data = {"test": "data"}
        test_path = Path("/test/new_dir/output.json")
        
        with patch('pathlib.Path.exists', return_value=False):
            with patch('pathlib.Path.mkdir', side_effect=OSError("Cannot create directory")):
                
                with pytest.raises(OSError, match="Cannot create directory"):
                    await async_write_json_file(test_path, test_data)


class TestAsyncCopyFile:
    """Test async_copy_file function."""
    
    @pytest.mark.asyncio
    async def test_copy_nonexistent_source(self):
        """Test error when source file doesn't exist."""
        src_path = Path("/test/nonexistent.json")
        dst_path = Path("/test/destination.json")
        
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="Source file not found"):
                await async_copy_file(src_path, dst_path)
    
    @pytest.mark.asyncio
    async def test_copy_source_is_directory(self):
        """Test error when source is a directory."""
        src_path = Path("/test/directory")
        dst_path = Path("/test/destination.json")
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_file', return_value=False):
                with pytest.raises(OSError, match="Source is not a regular file"):
                    await async_copy_file(src_path, dst_path)
    
    @pytest.mark.asyncio
    async def test_copy_permission_error(self):
        """Test handling permission errors during copy."""
        src_path = Path("/test/source.json")
        dst_path = Path("/test/destination.json")
        
        with patch('aiofiles.open', side_effect=PermissionError("Access denied")):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = 100
                        
                        with pytest.raises(PermissionError):
                            await async_copy_file(src_path, dst_path)
    
    @pytest.mark.asyncio
    async def test_copy_unicode_decode_error(self):
        """Test handling unicode decode errors during copy."""
        src_path = Path("/test/binary.json")
        dst_path = Path("/test/destination.json")
        
        with patch('aiofiles.open', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid start byte')):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = 100
                        
                        with pytest.raises(UnicodeDecodeError):
                            await async_copy_file(src_path, dst_path)


class TestAsyncFileExists:
    """Test async_file_exists function."""
    
    @pytest.mark.asyncio
    async def test_file_exists_and_is_file(self):
        """Test when file exists and is a regular file."""
        test_path = Path("/test/file.json")
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_file', return_value=True):
                result = await async_file_exists(test_path)
                assert result is True
    
    @pytest.mark.asyncio
    async def test_file_does_not_exist(self):
        """Test when file doesn't exist."""
        test_path = Path("/test/nonexistent.json")
        
        with patch('pathlib.Path.exists', return_value=False):
            result = await async_file_exists(test_path)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_path_is_directory(self):
        """Test when path exists but is a directory."""
        test_path = Path("/test/directory")
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.is_file', return_value=False):
                result = await async_file_exists(test_path)
                assert result is False
    
    @pytest.mark.asyncio
    async def test_file_exists_error_handling(self):
        """Test error handling in file existence check."""
        test_path = Path("/test/file.json")
        
        with patch('pathlib.Path.exists', side_effect=OSError("Access denied")):
            result = await async_file_exists(test_path)
            assert result is False


class TestAsyncEnsureDirectory:
    """Test async_ensure_directory function."""
    
    @pytest.mark.asyncio
    async def test_create_new_directory(self):
        """Test creating a new directory."""
        test_path = Path("/test/new_directory")
        
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            await async_ensure_directory(test_path)
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    
    @pytest.mark.asyncio
    async def test_directory_already_exists(self):
        """Test when directory already exists."""
        test_path = Path("/test/existing_directory")
        
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            # mkdir with exist_ok=True should not raise error
            await async_ensure_directory(test_path)
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    
    @pytest.mark.asyncio
    async def test_directory_creation_error(self):
        """Test handling errors during directory creation."""
        test_path = Path("/test/protected_directory")
        
        with patch('pathlib.Path.mkdir', side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError):
                await async_ensure_directory(test_path)


class TestAsyncFileOperationsIntegration:
    """Integration tests for async file operations."""
    
    @pytest.mark.asyncio
    async def test_write_then_read_json_file(self):
        """Test writing and then reading a JSON file."""
        test_data = {
            "version": "0.4.0",
            "entities_tracked": ["climate.test"],
            "schedules": {"home": [], "away": []}
        }
        test_path = Path("/test/integration.json")
        json_content = json.dumps(test_data, indent=2, default=str)
        
        # Mock write operation
        mock_write_file = AsyncMock()
        mock_write_file.write = AsyncMock()
        mock_write_file.__aenter__ = AsyncMock(return_value=mock_write_file)
        mock_write_file.__aexit__ = AsyncMock(return_value=None)
        
        # Mock read operation
        mock_read_file = AsyncMock()
        mock_read_file.read = AsyncMock(return_value=json_content)
        mock_read_file.__aenter__ = AsyncMock(return_value=mock_read_file)
        mock_read_file.__aexit__ = AsyncMock(return_value=None)
        
        def mock_aiofiles_open(path, mode='r', **kwargs):
            if 'w' in mode:
                return mock_write_file
            else:
                return mock_read_file
        
        with patch('aiofiles.open', side_effect=mock_aiofiles_open):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = len(json_content)
                        
                        # Write the file
                        await async_write_json_file(test_path, test_data)
                        
                        # Verify write was called
                        mock_write_file.write.assert_called_once()
                        
                        # Now read it back
                        result = await async_read_json_file(test_path)
                        
                        assert result == test_data
                        mock_read_file.read.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self):
        """Test various error recovery scenarios."""
        test_path = Path("/test/error_test.json")
        
        # Test sequence: permission error, then success
        call_count = 0
        def mock_aiofiles_open_with_retry(path, mode='r', **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise PermissionError("First attempt fails")
            else:
                # Second attempt succeeds
                mock_file = AsyncMock()
                mock_file.read = AsyncMock(return_value='{"recovered": true}')
                mock_file.__aenter__ = AsyncMock(return_value=mock_file)
                mock_file.__aexit__ = AsyncMock(return_value=None)
                return mock_file
        
        with patch('aiofiles.open', side_effect=mock_aiofiles_open_with_retry):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.is_file', return_value=True):
                    with patch('pathlib.Path.stat') as mock_stat:
                        mock_stat.return_value.st_size = 100
                        
                        # First call should fail
                        with pytest.raises(PermissionError):
                            await async_read_json_file(test_path)
                        
                        # Second call should succeed
                        result = await async_read_json_file(test_path)
                        assert result == {"recovered": True}