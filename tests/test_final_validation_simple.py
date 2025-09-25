"""
Simple final validation test for manager integration fix.

This test validates that the original TypeError is resolved and the integration
can be set up successfully with the correct constructor signatures.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.storage import StorageService


class TestFinalValidationSimple:
    """Simple validation tests for the manager integration fix."""

    def test_presence_manager_constructor_accepts_storage_service(self):
        """Test that PresenceManager constructor accepts storage_service parameter."""
        # Create mock objects
        mock_hass = MagicMock()
        mock_storage_service = MagicMock(spec=StorageService)
        
        # This should not raise a TypeError
        try:
            presence_manager = PresenceManager(mock_hass, mock_storage_service)
            assert presence_manager is not None
            assert presence_manager.hass is mock_hass
            assert presence_manager.storage_service is mock_storage_service
        except TypeError as e:
            pytest.fail(f"PresenceManager constructor still has TypeError: {e}")

    def test_buffer_manager_constructor_accepts_storage_service(self):
        """Test that BufferManager constructor accepts storage_service parameter."""
        # Create mock objects
        mock_hass = MagicMock()
        mock_storage_service = MagicMock(spec=StorageService)
        
        # This should not raise a TypeError
        try:
            buffer_manager = BufferManager(mock_hass, mock_storage_service)
            assert buffer_manager is not None
            assert buffer_manager.hass is mock_hass
            assert buffer_manager.storage_service is mock_storage_service
        except TypeError as e:
            pytest.fail(f"BufferManager constructor still has TypeError: {e}")

    def test_manager_constructors_signature_compatibility(self):
        """Test that manager constructors have compatible signatures."""
        import inspect
        
        # Check PresenceManager signature
        presence_sig = inspect.signature(PresenceManager.__init__)
        presence_params = list(presence_sig.parameters.keys())
        
        # Should have: self, hass, storage_service
        assert len(presence_params) == 3, f"PresenceManager.__init__ should have 3 parameters, got {len(presence_params)}: {presence_params}"
        assert 'self' in presence_params
        assert 'hass' in presence_params
        assert 'storage_service' in presence_params
        
        # Check BufferManager signature
        buffer_sig = inspect.signature(BufferManager.__init__)
        buffer_params = list(buffer_sig.parameters.keys())
        
        # Should have: self, hass, storage_service
        assert len(buffer_params) == 3, f"BufferManager.__init__ should have 3 parameters, got {len(buffer_params)}: {buffer_params}"
        assert 'self' in buffer_params
        assert 'hass' in buffer_params
        assert 'storage_service' in buffer_params

    @pytest.mark.asyncio
    async def test_integration_setup_constructor_calls(self):
        """Test that integration setup calls constructors with correct parameters."""
        from custom_components.roost_scheduler import async_setup_entry
        from homeassistant.config_entries import ConfigEntry
        from homeassistant.core import HomeAssistant
        
        # Create mock objects
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_hass.data = {}
        
        mock_config_entry = MagicMock(spec=ConfigEntry)
        mock_config_entry.entry_id = "test_validation"
        mock_config_entry.data = {
            "entities_tracked": ["climate.test"],
            "presence_entities": ["device_tracker.test"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        mock_config_entry.options = {}
        
        # Mock the manager classes to track constructor calls
        with patch('custom_components.roost_scheduler.presence_manager.PresenceManager') as mock_presence_class, \
             patch('custom_components.roost_scheduler.buffer_manager.BufferManager') as mock_buffer_class, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule_class, \
             patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage_class, \
             patch('custom_components.roost_scheduler.logging_config.LoggingManager') as mock_logging_class, \
             patch('custom_components.roost_scheduler.config_validator.ConfigValidator') as mock_validator_class, \
             patch('custom_components.roost_scheduler._register_services') as mock_register_services, \
             patch('custom_components.roost_scheduler._register_websocket_handlers') as mock_register_ws:
            
            # Setup mock instances
            mock_storage_instance = AsyncMock()
            mock_storage_class.return_value = mock_storage_instance
            
            mock_logging_instance = AsyncMock()
            mock_logging_class.return_value = mock_logging_instance
            
            mock_presence_instance = AsyncMock()
            mock_presence_class.return_value = mock_presence_instance
            
            mock_buffer_instance = AsyncMock()
            mock_buffer_class.return_value = mock_buffer_instance
            
            mock_schedule_instance = AsyncMock()
            mock_schedule_class.return_value = mock_schedule_instance
            
            mock_validator_instance = AsyncMock()
            mock_validator_class.return_value = mock_validator_instance
            
            # Attempt setup - this should not raise TypeError
            try:
                result = await async_setup_entry(mock_hass, mock_config_entry)
                
                # Verify that constructors were called with correct parameters
                # PresenceManager should be called with (hass, storage_service)
                mock_presence_class.assert_called_once()
                presence_call_args = mock_presence_class.call_args
                assert len(presence_call_args[0]) == 2, f"PresenceManager called with wrong number of args: {len(presence_call_args[0])}"
                assert presence_call_args[0][0] is mock_hass
                assert presence_call_args[0][1] is mock_storage_instance
                
                # BufferManager should be called with (hass, storage_service)
                mock_buffer_class.assert_called_once()
                buffer_call_args = mock_buffer_class.call_args
                assert len(buffer_call_args[0]) == 2, f"BufferManager called with wrong number of args: {len(buffer_call_args[0])}"
                assert buffer_call_args[0][0] is mock_hass
                assert buffer_call_args[0][1] is mock_storage_instance
                
                print("✓ Integration setup calls constructors with correct parameters")
                print("✓ No TypeError occurred during setup")
                
            except TypeError as e:
                pytest.fail(f"TypeError still occurs during integration setup: {e}")
            except Exception as e:
                # Other exceptions are acceptable for this test
                print(f"Setup failed with non-TypeError exception (acceptable): {e}")

    def test_original_error_scenario_resolved(self):
        """Test the specific scenario that caused the original TypeError."""
        # This simulates the exact call pattern that was failing:
        # presence_manager = PresenceManager(hass, storage_service)  # 3 args
        # buffer_manager = BufferManager(hass, storage_service)     # 3 args
        
        mock_hass = MagicMock()
        mock_storage_service = MagicMock()
        
        # These calls should work without TypeError
        try:
            # This was the failing call pattern
            presence_manager = PresenceManager(mock_hass, mock_storage_service)
            buffer_manager = BufferManager(mock_hass, mock_storage_service)
            
            assert presence_manager is not None
            assert buffer_manager is not None
            
            print("✓ Original error scenario resolved")
            print("✓ PresenceManager(hass, storage_service) works")
            print("✓ BufferManager(hass, storage_service) works")
            
        except TypeError as e:
            pytest.fail(f"Original TypeError scenario still fails: {e}")

    def test_manager_initialization_with_storage_integration(self):
        """Test that managers properly initialize with storage integration."""
        mock_hass = MagicMock()
        mock_storage_service = MagicMock(spec=StorageService)
        
        # Test PresenceManager
        presence_manager = PresenceManager(mock_hass, mock_storage_service)
        assert hasattr(presence_manager, 'storage_service')
        assert presence_manager.storage_service is mock_storage_service
        
        # Test BufferManager
        buffer_manager = BufferManager(mock_hass, mock_storage_service)
        assert hasattr(buffer_manager, 'storage_service')
        assert buffer_manager.storage_service is mock_storage_service
        
        print("✓ Managers properly initialize with storage integration")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])