"""Test the Frontend Resource Manager."""
import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.components import frontend

from custom_components.roost_scheduler.frontend_manager import (
    FrontendResourceManager,
    FrontendResourceConfig,
    ResourceRegistrationResult,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.config_dir = "/config"
    hass.config.components = {"frontend"}
    return hass


@pytest.fixture
def frontend_manager(mock_hass):
    """Create a frontend resource manager instance."""
    return FrontendResourceManager(mock_hass)


@pytest.fixture
def mock_resource_config():
    """Create a mock resource configuration."""
    return FrontendResourceConfig(
        card_js_path="/hacsfiles/roost-scheduler-card/roost-scheduler-card.js",
        card_css_path="/hacsfiles/roost-scheduler-card/roost-scheduler-card.css",
        resource_version="1.0.0",
        fallback_enabled=True,
        retry_attempts=2,
        retry_delay=0.1
    )


class TestFrontendResourceManager:
    """Test the FrontendResourceManager class."""

    def test_initialization(self, mock_hass):
        """Test frontend resource manager initialization."""
        manager = FrontendResourceManager(mock_hass)
        
        assert manager.hass == mock_hass
        assert manager._registered_resources == []
        assert manager._registration_results == []
        assert manager._config.card_js_path == "/hacsfiles/roost-scheduler-card/roost-scheduler-card.js"
        assert manager._config.resource_version == "0.3.0"
        assert manager._config.fallback_enabled is True
        assert manager._config.retry_attempts == 3

    @pytest.mark.asyncio
    @patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url')
    @patch('os.path.isfile')
    @pytest.mark.asyncio
    async def test_successful_resource_registration(self, mock_isfile, mock_add_js, frontend_manager):
        """Test successful frontend resource registration."""
        # Mock file existence
        mock_isfile.return_value = True
        
        # Mock file size
        with patch('os.path.getsize', return_value=1024):
            result = await frontend_manager.register_frontend_resources()
        
        assert result["success"] is True
        assert len(result["resources_registered"]) == 1
        assert result["resources_registered"][0]["resource"] == "/hacsfiles/roost-scheduler-card/roost-scheduler-card.js"
        assert len(result["resources_failed"]) == 0
        assert result["frontend_available"] is True
        
        # Verify frontend.add_extra_js_url was called
        mock_add_js.assert_called_once_with(
            frontend_manager.hass, 
            "/hacsfiles/roost-scheduler-card/roost-scheduler-card.js"
        )

    @pytest.mark.asyncio
    @patch('os.path.isfile')
    @pytest.mark.asyncio
    async def test_missing_js_file_registration(self, mock_isfile, frontend_manager):
        """Test registration when JavaScript file is missing."""
        # Mock file doesn't exist
        mock_isfile.return_value = False
        
        result = await frontend_manager.register_frontend_resources()
        
        assert result["success"] is False
        assert len(result["resources_registered"]) == 0
        assert len(result["resources_failed"]) >= 1
        assert any("JavaScript resource not found" in failure["error"] 
                  for failure in result["resources_failed"])

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_frontend_not_available(self, frontend_manager):
        """Test registration when frontend component is not available."""
        # Mock frontend not available
        frontend_manager.hass.config.components = set()
        
        result = await frontend_manager.register_frontend_resources()
        
        assert result["success"] is False
        assert result["frontend_available"] is False
        assert len(result["resources_failed"]) >= 1
        assert any("frontend component not available" in failure["error"] 
                  for failure in result["resources_failed"])

    @patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url')
    @patch('os.path.isfile')
    @pytest.mark.asyncio
    async def test_registration_with_retry_logic(self, mock_isfile, mock_add_js, frontend_manager):
        """Test resource registration with retry logic."""
        # Mock file exists
        mock_isfile.return_value = True
        
        # Mock first call fails, second succeeds
        mock_add_js.side_effect = [Exception("Network error"), None]
        
        with patch('os.path.getsize', return_value=1024):
            with patch('asyncio.sleep'):  # Speed up test
                result = await frontend_manager.register_frontend_resources()
        
        assert result["success"] is True
        assert len(result["resources_registered"]) == 1
        assert result["resources_registered"][0]["retry_count"] == 1
        assert mock_add_js.call_count == 2

    @patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url')
    @patch('os.path.isfile')
    @pytest.mark.asyncio
    async def test_registration_retry_exhausted(self, mock_isfile, mock_add_js, frontend_manager):
        """Test registration when all retry attempts are exhausted."""
        # Mock file exists
        mock_isfile.return_value = True
        
        # Mock all calls fail
        mock_add_js.side_effect = Exception("Persistent error")
        
        with patch('os.path.getsize', return_value=1024):
            with patch('asyncio.sleep'):  # Speed up test
                result = await frontend_manager.register_frontend_resources()
        
        assert result["success"] is False
        assert len(result["resources_failed"]) >= 1
        assert mock_add_js.call_count == 3  # Default retry attempts

    @patch('os.path.isfile')
    @pytest.mark.asyncio
    async def test_fallback_resource_registration(self, mock_isfile, frontend_manager):
        """Test fallback resource registration when primary fails."""
        # Mock primary file doesn't exist, but fallback does
        def mock_file_exists(path):
            # Convert to full path for checking
            if "/config/www/community/roost-scheduler-card" in path:
                return False  # Primary HACS path doesn't exist
            elif "/config/www/roost-scheduler-card" in path:
                return True   # Fallback local path exists
            elif "/config/www/community/roost_scheduler" in path:
                return False  # Another fallback doesn't exist
            elif "/config/www/community/roost-scheduler-card/dist" in path:
                return False  # Dist fallback doesn't exist
            return False
        
        mock_isfile.side_effect = mock_file_exists
        
        with patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url') as mock_add_js:
            with patch('os.path.getsize', return_value=1024):
                result = await frontend_manager.register_frontend_resources()
        
        assert result["success"] is True
        # Should have both fallback and original registration attempts
        assert len(result["resources_registered"]) >= 1
        # Check that at least one used fallback
        fallback_used = any(r.get("fallback_used", False) for r in result["resources_registered"])
        assert fallback_used is True
        assert len(result["warnings"]) >= 1

    @patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url')
    @patch('os.path.isfile')
    @pytest.mark.asyncio
    async def test_css_resource_registration(self, mock_isfile, mock_add_js, frontend_manager):
        """Test CSS resource registration when configured."""
        # Configure CSS resource
        frontend_manager._config.card_css_path = "/hacsfiles/roost-scheduler-card/styles.css"
        
        # Mock files exist
        mock_isfile.return_value = True
        
        # Mock CSS registration function exists
        with patch('custom_components.roost_scheduler.frontend_manager.frontend') as mock_frontend:
            mock_frontend.add_extra_js_url = mock_add_js
            mock_frontend.add_extra_css_url = MagicMock()
            
            with patch('os.path.getsize', return_value=1024):
                result = await frontend_manager.register_frontend_resources()
        
        assert result["success"] is True
        assert len(result["resources_registered"]) == 2  # JS + CSS
        
        # Verify both resources were registered
        mock_add_js.assert_called_once()
        mock_frontend.add_extra_css_url.assert_called_once()

    @patch('os.path.isfile')
    @pytest.mark.asyncio
    async def test_css_registration_not_supported(self, mock_isfile, frontend_manager):
        """Test CSS registration when not supported by HA version."""
        # Configure CSS resource
        frontend_manager._config.card_css_path = "/hacsfiles/roost-scheduler-card/styles.css"
        
        # Mock files exist
        mock_isfile.return_value = True
        
        with patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url'):
            with patch('os.path.getsize', return_value=1024):
                # Mock CSS registration not available
                with patch('custom_components.roost_scheduler.frontend_manager.frontend', spec=['add_extra_js_url']):
                    result = await frontend_manager.register_frontend_resources()
        
        assert result["success"] is True  # JS still succeeds
        assert len(result["resources_registered"]) == 1  # Only JS
        assert len(result["warnings"]) >= 1  # CSS warning

    @pytest.mark.asyncio
    async def test_verify_resource_availability_success(self, frontend_manager):
        """Test resource availability verification when files exist."""
        with patch('os.path.isfile', return_value=True):
            with patch('os.path.getsize', return_value=2048):
                result = await frontend_manager.verify_resource_availability()
        
        assert result["js_available"] is True
        assert result["css_available"] is True  # No CSS configured, so considered available
        assert result["js_size"] == 2048
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_verify_resource_availability_missing_files(self, frontend_manager):
        """Test resource availability verification when files are missing."""
        with patch('os.path.isfile', return_value=False):
            result = await frontend_manager.verify_resource_availability()
        
        assert result["js_available"] is False
        assert result["css_available"] is True  # No CSS configured
        assert len(result["errors"]) >= 1
        assert any("JavaScript resource not found" in error for error in result["errors"])

    @pytest.mark.asyncio
    async def test_verify_resource_availability_with_css(self, frontend_manager):
        """Test resource availability verification with CSS configured."""
        # Configure CSS resource
        frontend_manager._config.card_css_path = "/hacsfiles/roost-scheduler-card/styles.css"
        
        def mock_file_exists(path):
            return "roost-scheduler-card.js" in path  # Only JS exists
        
        with patch('os.path.isfile', side_effect=mock_file_exists):
            with patch('os.path.getsize', return_value=1024):
                result = await frontend_manager.verify_resource_availability()
        
        assert result["js_available"] is True
        assert result["css_available"] is False
        assert len(result["errors"]) >= 1
        assert any("CSS resource not found" in error for error in result["errors"])

    @pytest.mark.asyncio
    async def test_handle_resource_loading_errors_with_recovery(self, frontend_manager):
        """Test resource loading error handling with successful recovery."""
        error_info = {"error": "Resource not found", "resource": "main"}
        
        # Mock successful fallback
        with patch('os.path.isfile') as mock_isfile:
            # First path fails, second succeeds
            mock_isfile.side_effect = [False, True]
            
            with patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url'):
                result = await frontend_manager.handle_resource_loading_errors(error_info)
        
        assert result["recovery_attempted"] is True
        assert result["recovery_successful"] is True
        assert result["fallback_used"] is True
        assert len(result["actions_taken"]) >= 1

    @pytest.mark.asyncio
    async def test_handle_resource_loading_errors_no_recovery(self, frontend_manager):
        """Test resource loading error handling when recovery fails."""
        error_info = {"error": "Resource not found", "resource": "main"}
        
        # Mock all paths fail
        with patch('os.path.isfile', return_value=False):
            result = await frontend_manager.handle_resource_loading_errors(error_info)
        
        assert result["recovery_attempted"] is True
        assert result["recovery_successful"] is False
        assert len(result["manual_steps_required"]) >= 1
        assert any("Verify that the Roost Scheduler card files" in step 
                  for step in result["manual_steps_required"])

    def test_get_registration_status(self, frontend_manager):
        """Test getting registration status and diagnostics."""
        # Add some mock registration results
        frontend_manager._registered_resources = ["/test/resource.js"]
        frontend_manager._registration_results = [
            ResourceRegistrationResult(
                success=True,
                resource_path="/test/resource.js",
                retry_count=1
            )
        ]
        
        status = frontend_manager.get_registration_status()
        
        assert status["registered_resources"] == ["/test/resource.js"]
        assert len(status["registration_results"]) == 1
        assert status["registration_results"][0]["success"] is True
        assert status["registration_results"][0]["retry_count"] == 1
        assert status["frontend_available"] is True
        assert "config" in status
        assert status["config"]["card_js_path"] == "/hacsfiles/roost-scheduler-card/roost-scheduler-card.js"

    def test_is_frontend_available_true(self, frontend_manager):
        """Test frontend availability check when frontend is available."""
        frontend_manager.hass.config.components = {"frontend", "other_component"}
        
        assert frontend_manager._is_frontend_available() is True

    def test_is_frontend_available_false(self, frontend_manager):
        """Test frontend availability check when frontend is not available."""
        frontend_manager.hass.config.components = {"other_component"}
        
        assert frontend_manager._is_frontend_available() is False

    def test_is_frontend_available_exception(self, frontend_manager):
        """Test frontend availability check when exception occurs."""
        frontend_manager.hass.config.components = None  # Will cause AttributeError
        
        assert frontend_manager._is_frontend_available() is False

    def test_get_full_resource_path_hacsfiles(self, frontend_manager):
        """Test converting HACS resource path to full filesystem path."""
        resource_path = "/hacsfiles/roost-scheduler-card/roost-scheduler-card.js"
        
        result = frontend_manager._get_full_resource_path(resource_path)
        
        expected = "/config/www/community/roost-scheduler-card/roost-scheduler-card.js"
        assert result == expected

    def test_get_full_resource_path_local(self, frontend_manager):
        """Test converting local resource path to full filesystem path."""
        resource_path = "/local/roost-scheduler-card/roost-scheduler-card.js"
        
        result = frontend_manager._get_full_resource_path(resource_path)
        
        expected = "/config/www/roost-scheduler-card/roost-scheduler-card.js"
        assert result == expected

    def test_get_full_resource_path_unknown(self, frontend_manager):
        """Test converting unknown resource path format."""
        resource_path = "/unknown/path/resource.js"
        
        result = frontend_manager._get_full_resource_path(resource_path)
        
        assert result is None

    def test_get_full_resource_path_exception(self, frontend_manager):
        """Test resource path conversion when exception occurs."""
        # Mock config_dir to cause an exception
        frontend_manager.hass.config.config_dir = None
        
        resource_path = "/hacsfiles/test/resource.js"
        result = frontend_manager._get_full_resource_path(resource_path)
        
        assert result is None


class TestFrontendResourceConfig:
    """Test the FrontendResourceConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = FrontendResourceConfig(card_js_path="/test/path.js")
        
        assert config.card_js_path == "/test/path.js"
        assert config.card_css_path is None
        assert config.resource_version == "1.0.0"
        assert config.fallback_enabled is True
        assert config.retry_attempts == 3
        assert config.retry_delay == 1.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = FrontendResourceConfig(
            card_js_path="/custom/path.js",
            card_css_path="/custom/styles.css",
            resource_version="2.0.0",
            fallback_enabled=False,
            retry_attempts=5,
            retry_delay=0.5
        )
        
        assert config.card_js_path == "/custom/path.js"
        assert config.card_css_path == "/custom/styles.css"
        assert config.resource_version == "2.0.0"
        assert config.fallback_enabled is False
        assert config.retry_attempts == 5
        assert config.retry_delay == 0.5


class TestResourceRegistrationResult:
    """Test the ResourceRegistrationResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = ResourceRegistrationResult(
            success=True,
            resource_path="/test/resource.js"
        )
        
        assert result.success is True
        assert result.resource_path == "/test/resource.js"
        assert result.error_message is None
        assert result.retry_count == 0
        assert result.fallback_used is False

    def test_custom_values(self):
        """Test custom result values."""
        result = ResourceRegistrationResult(
            success=False,
            resource_path="/test/resource.js",
            error_message="Registration failed",
            retry_count=2,
            fallback_used=True
        )
        
        assert result.success is False
        assert result.resource_path == "/test/resource.js"
        assert result.error_message == "Registration failed"
        assert result.retry_count == 2
        assert result.fallback_used is True


class TestVersionCompatibility:
    """Test version compatibility scenarios."""

    @patch('custom_components.roost_scheduler.frontend_manager.ha_version', '2023.1.0')
    @pytest.mark.asyncio
    async def test_old_ha_version_compatibility(self, frontend_manager):
        """Test compatibility with older Home Assistant versions."""
        status = frontend_manager.get_registration_status()
        
        assert status["ha_version"] == '2023.1.0'
        # Should still work with basic functionality

    @patch('custom_components.roost_scheduler.frontend_manager.ha_version', '2024.1.0')
    @pytest.mark.asyncio
    async def test_new_ha_version_compatibility(self, frontend_manager):
        """Test compatibility with newer Home Assistant versions."""
        status = frontend_manager.get_registration_status()
        
        assert status["ha_version"] == '2024.1.0'
        # Should work with all features

    @pytest.mark.asyncio
    async def test_frontend_api_changes(self, frontend_manager):
        """Test handling of frontend API changes."""
        # Mock scenario where add_extra_js_url doesn't exist
        with patch('custom_components.roost_scheduler.frontend_manager.frontend', spec=[]):
            with patch('os.path.isfile', return_value=True):
                with patch('os.path.getsize', return_value=1024):
                    result = await frontend_manager.register_frontend_resources()
        
        # Should handle gracefully
        assert result["success"] is False
        assert len(result["resources_failed"]) >= 1


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_registrations(self, frontend_manager):
        """Test handling of concurrent registration attempts."""
        with patch('os.path.isfile', return_value=True):
            with patch('os.path.getsize', return_value=1024):
                with patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url'):
                    # Start multiple registrations concurrently
                    tasks = [
                        frontend_manager.register_frontend_resources()
                        for _ in range(3)
                    ]
                    results = await asyncio.gather(*tasks)
        
        # All should succeed
        for result in results:
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_very_large_file(self, frontend_manager):
        """Test handling of very large resource files."""
        with patch('os.path.isfile', return_value=True):
            with patch('os.path.getsize', return_value=100_000_000):  # 100MB
                with patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url'):
                    result = await frontend_manager.verify_resource_availability()
        
        assert result["js_available"] is True
        assert result["js_size"] == 100_000_000

    @pytest.mark.asyncio
    async def test_zero_size_file(self, frontend_manager):
        """Test handling of zero-size resource files."""
        with patch('os.path.isfile', return_value=True):
            with patch('os.path.getsize', return_value=0):
                result = await frontend_manager.verify_resource_availability()
        
        assert result["js_available"] is True
        assert result["js_size"] == 0

    @pytest.mark.asyncio
    async def test_permission_denied_error(self, frontend_manager):
        """Test handling of permission denied errors."""
        with patch('os.path.isfile', side_effect=PermissionError("Permission denied")):
            result = await frontend_manager.verify_resource_availability()
        
        assert result["js_available"] is False
        assert len(result["errors"]) >= 1

    @pytest.mark.asyncio
    async def test_filesystem_error(self, frontend_manager):
        """Test handling of filesystem errors."""
        with patch('os.path.isfile', side_effect=OSError("Filesystem error")):
            result = await frontend_manager.verify_resource_availability()
        
        assert result["js_available"] is False
        assert len(result["errors"]) >= 1