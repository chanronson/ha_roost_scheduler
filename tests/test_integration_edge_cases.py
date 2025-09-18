"""Integration tests for edge cases and complex scenarios."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, time, timedelta
import json

from homeassistant.core import HomeAssistant, ServiceCall, Context
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.exceptions import ServiceValidationError

from custom_components.roost_scheduler import async_setup_entry
from custom_components.roost_scheduler.const import DOMAIN
from custom_components.roost_scheduler.models import ScheduleData


@pytest.fixture
def mock_hass_with_complex_entities():
    """Create mock Home Assistant with complex entity scenarios."""
    hass = MagicMock(spec=HomeAssistant)
    
    # Create config mock
    config_mock = MagicMock()
    config_mock.config_dir = "/config"
    hass.config = config_mock
    
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.services.async_call = AsyncMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.data = {}
    
    # Mock entity states with various scenarios
    mock_states = {}
    
    # Climate entities with different configurations
    climate1 = MagicMock()
    climate1.state = "heat"
    climate1.attributes = {
        "temperature": 20.0,
        "target_temp_high": None,
        "target_temp_low": None,
        "hvac_modes": ["heat", "cool", "auto", "off"],
        "min_temp": 5.0,
        "max_temp": 35.0
    }
    mock_states["climate.living_room"] = climate1
    
    # Climate with dual setpoint
    climate2 = MagicMock()
    climate2.state = "auto"
    climate2.attributes = {
        "temperature": 22.0,
        "target_temp_high": 24.0,
        "target_temp_low": 18.0,
        "hvac_modes": ["heat", "cool", "auto", "off"],
        "min_temp": 10.0,
        "max_temp": 30.0
    }
    mock_states["climate.bedroom"] = climate2
    
    # Unavailable climate
    climate3 = MagicMock()
    climate3.state = STATE_UNAVAILABLE
    climate3.attributes = {}
    mock_states["climate.unavailable"] = climate3
    
    # Various presence entities
    phone = MagicMock()
    phone.state = STATE_HOME
    phone.last_updated = datetime.now()
    mock_states["device_tracker.phone"] = phone
    
    person = MagicMock()
    person.state = STATE_HOME
    person.last_updated = datetime.now()
    mock_states["person.user"] = person
    
    # Stale presence entity
    stale_tracker = MagicMock()
    stale_tracker.state = STATE_HOME
    stale_tracker.last_updated = datetime.now() - timedelta(minutes=20)
    mock_states["device_tracker.stale"] = stale_tracker
    
    # Override entities
    force_home = MagicMock()
    force_home.state = "off"
    mock_states["input_boolean.roost_force_home"] = force_home
    
    force_away = MagicMock()
    force_away.state = "off"
    mock_states["input_boolean.roost_force_away"] = force_away
    
    def mock_get_state(entity_id):
        return mock_states.get(entity_id)
    
    def mock_set_state(entity_id, state):
        mock_states[entity_id] = state
    
    # Create states mock
    states_mock = MagicMock()
    states_mock.get = mock_get_state
    states_mock._mock_set_state = mock_set_state
    states_mock._mock_states = mock_states
    hass.states = states_mock
    
    return hass


@pytest.fixture
def complex_schedule_data():
    """Create complex schedule data with edge cases."""
    return {
        "version": "0.3.0",
        "entities_tracked": ["climate.living_room", "climate.bedroom", "climate.unavailable"],
        "presence_entities": ["device_tracker.phone", "person.user", "device_tracker.stale"],
        "presence_rule": "anyone_home",
        "presence_timeout_seconds": 600,
        "buffer": {
            "global": {
                "time_minutes": 15,
                "value_delta": 2.0,
                "apply_to": "climate"
            }
        },
        "ui": {
            "resolution_minutes": 15,  # High resolution
            "auto_add_card": False
        },
        "schedules": {
            "home": {
                "monday": [
                    # Overlapping slots (edge case)
                    {
                        "start_time": "06:00",
                        "end_time": "08:30",
                        "target": {"temperature": 20.0},
                        "buffer_override": None
                    },
                    {
                        "start_time": "08:00",  # Overlaps with previous
                        "end_time": "10:00",
                        "target": {"temperature": 21.0},
                        "buffer_override": {"time_minutes": 5, "value_delta": 0.5}
                    },
                    # Midnight crossing slot
                    {
                        "start_time": "23:30",
                        "end_time": "01:00",  # Next day
                        "target": {"temperature": 18.0},
                        "buffer_override": None
                    }
                ],
                "sunday": [
                    # Dual setpoint schedule
                    {
                        "start_time": "08:00",
                        "end_time": "22:00",
                        "target": {"target_temp_high": 24.0, "target_temp_low": 18.0},
                        "buffer_override": None
                    }
                ]
            },
            "away": {
                "monday": [
                    # All-day slot
                    {
                        "start_time": "00:00",
                        "end_time": "23:59",
                        "target": {"temperature": 16.0},
                        "buffer_override": None
                    }
                ]
            }
        },
        "metadata": {
            "created_by": "edge_case_test",
            "created_at": "2025-09-17T10:00:00Z",
            "last_modified": "2025-09-17T10:00:00Z"
        }
    }


class TestComplexScheduleScenarios:
    """Test complex scheduling scenarios and edge cases."""
    
    @pytest.mark.asyncio
    async def test_overlapping_schedule_slots(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test handling of overlapping schedule slots."""
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test at 08:15 Monday (in overlap zone)
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 8, 15)  # Monday 08:15
                mock_datetime.strptime = datetime.strptime
                
                # Should use the later/more specific slot (21.0°C)
                current_slot = await schedule_manager.evaluate_current_slot("climate.living_room", "home")
                assert current_slot is not None
                assert current_slot.target_value == 21.0
    
    @pytest.mark.asyncio
    async def test_midnight_crossing_schedule(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test schedule slots that cross midnight."""
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test at 00:30 Tuesday (should match Monday's midnight-crossing slot)
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 23, 0, 30)  # Tuesday 00:30
                mock_datetime.strptime = datetime.strptime
                
                current_slot = await schedule_manager.evaluate_current_slot("climate.living_room", "home")
                assert current_slot is not None
                assert current_slot.target_value == 18.0
    
    @pytest.mark.asyncio
    async def test_dual_setpoint_climate_control(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test controlling climate entities with dual setpoints."""
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry for bedroom (dual setpoint)
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.bedroom"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test dual setpoint application on Sunday
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 21, 10, 0)  # Sunday 10:00
                mock_datetime.strptime = datetime.strptime
                
                result = await schedule_manager.apply_schedule("climate.bedroom", force=True)
                assert result is True
                
                # Should call service with both high and low temps
                mock_hass.services.async_call.assert_called_with(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": "climate.bedroom",
                        "target_temp_high": 24.0,
                        "target_temp_low": 18.0
                    },
                    blocking=True
                )
    
    @pytest.mark.asyncio
    async def test_high_resolution_schedule_precision(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test high resolution (15-minute) schedule precision."""
        mock_hass = mock_hass_with_complex_entities
        
        # Add high-resolution schedule data
        complex_schedule_data["schedules"]["home"]["tuesday"] = [
            {
                "start_time": "08:00",
                "end_time": "08:15",
                "target": {"temperature": 19.0},
                "buffer_override": None
            },
            {
                "start_time": "08:15",
                "end_time": "08:30",
                "target": {"temperature": 20.0},
                "buffer_override": None
            },
            {
                "start_time": "08:30",
                "end_time": "08:45",
                "target": {"temperature": 21.0},
                "buffer_override": None
            }
        ]
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test precise timing at 08:20 Tuesday
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 23, 8, 20)  # Tuesday 08:20
                mock_datetime.strptime = datetime.strptime
                
                current_slot = await schedule_manager.evaluate_current_slot("climate.living_room", "home")
                assert current_slot is not None
                assert current_slot.target_value == 20.0  # Should be in 08:15-08:30 slot


class TestPresenceComplexScenarios:
    """Test complex presence detection scenarios."""
    
    @pytest.mark.asyncio
    async def test_mixed_presence_entity_states(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test presence detection with mixed entity states."""
        mock_hass = mock_hass_with_complex_entities
        
        # Set mixed presence states
        mock_hass.states._mock_states["device_tracker.phone"].state = STATE_HOME
        mock_hass.states._mock_states["person.user"].state = STATE_NOT_HOME
        mock_hass.states._mock_states["device_tracker.stale"].state = STATE_HOME  # But stale
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone", "person.user", "device_tracker.stale"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get presence manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Should be home because phone is home (stale tracker ignored)
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "home"
    
    @pytest.mark.asyncio
    async def test_everyone_home_rule(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test everyone_home presence rule."""
        mock_hass = mock_hass_with_complex_entities
        
        # Modify schedule data for everyone_home rule
        complex_schedule_data["presence_rule"] = "everyone_home"
        
        # Set presence states - one home, one away
        mock_hass.states._mock_states["device_tracker.phone"].state = STATE_HOME
        mock_hass.states._mock_states["person.user"].state = STATE_NOT_HOME
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone", "person.user"],
            "presence_rule": "everyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get presence manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Should be away because not everyone is home
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "away"
            
            # Set both home
            mock_hass.states._mock_states["person.user"].state = STATE_HOME
            
            # Should now be home
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "home"
    
    @pytest.mark.asyncio
    async def test_presence_override_priority(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test presence override priority when both are set."""
        mock_hass = mock_hass_with_complex_entities
        
        # Set both overrides (edge case)
        mock_hass.states._mock_states["input_boolean.roost_force_home"].state = "on"
        mock_hass.states._mock_states["input_boolean.roost_force_away"].state = "on"
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get presence manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Force away should take priority over force home
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "away"


class TestBufferComplexScenarios:
    """Test complex buffer system scenarios."""
    
    @pytest.mark.asyncio
    async def test_rapid_schedule_changes_with_buffer(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test buffer behavior with rapid schedule changes."""
        mock_hass = mock_hass_with_complex_entities
        
        # Set current temperature
        mock_hass.states._mock_states["climate.living_room"].attributes["temperature"] = 19.0
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get managers
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            buffer_manager = integration_data["buffer_manager"]
            
            # Simulate rapid manual changes
            buffer_manager.update_manual_change("climate.living_room", 19.5)
            
            # Immediate schedule application should be suppressed
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 8, 15)  # Monday 08:15
                mock_datetime.strptime = datetime.strptime
                
                # Update current temp to manual value
                mock_hass.states._mock_states["climate.living_room"].attributes["temperature"] = 19.5
                
                result = await schedule_manager.apply_schedule("climate.living_room", force=False)
                
                # Should be suppressed due to recent manual change
                mock_hass.services.async_call.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_buffer_with_temperature_limits(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test buffer behavior with climate entity temperature limits."""
        mock_hass = mock_hass_with_complex_entities
        
        # Set target outside entity limits
        complex_schedule_data["schedules"]["home"]["monday"][0]["target"]["temperature"] = 40.0  # Above max_temp (35.0)
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test schedule application with out-of-range target
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 7, 0)  # Monday 07:00
                mock_datetime.strptime = datetime.strptime
                
                result = await schedule_manager.apply_schedule("climate.living_room", force=True)
                assert result is True
                
                # Should clamp to max_temp
                mock_hass.services.async_call.assert_called_with(
                    "climate",
                    "set_temperature",
                    {"entity_id": "climate.living_room", "temperature": 35.0},
                    blocking=True
                )
    
    @pytest.mark.asyncio
    async def test_buffer_per_entity_tracking(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test buffer tracking per entity independently."""
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry with multiple entities
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room", "climate.bedroom"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get buffer manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            buffer_manager = integration_data["buffer_manager"]
            
            # Manual change on living room only
            buffer_manager.update_manual_change("climate.living_room", 19.0)
            
            # Test suppression for living room
            should_suppress_lr = buffer_manager.should_suppress_change(
                entity_id="climate.living_room",
                target_value=20.0,
                slot_config={}
            )
            
            # Test suppression for bedroom (no manual change)
            should_suppress_br = buffer_manager.should_suppress_change(
                entity_id="climate.bedroom",
                target_value=20.0,
                slot_config={}
            )
            
            # Living room should be suppressed, bedroom should not
            assert should_suppress_lr is True
            assert should_suppress_br is False


class TestServiceIntegrationEdgeCases:
    """Test service integration edge cases."""
    
    @pytest.mark.asyncio
    async def test_service_call_with_invalid_time_format(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test service calls with invalid time formats."""
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test with invalid time format
            service_call = ServiceCall(
                domain=DOMAIN,
                service="apply_slot",
                data={
                    "entity_id": "climate.living_room",
                    "day": "monday",
                    "time": "invalid-time-format",
                    "force": False
                },
                context=Context()
            )
            
            # Should raise ValueError for invalid time format
            with pytest.raises(ValueError, match="Invalid time format"):
                await schedule_manager.apply_slot_service(service_call)
    
    @pytest.mark.asyncio
    async def test_service_call_with_nonexistent_entity(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test service calls with non-existent entities."""
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test with non-existent entity
            service_call = ServiceCall(
                domain=DOMAIN,
                service="apply_grid_now",
                data={
                    "entity_id": "climate.nonexistent",
                    "force": False
                },
                context=Context()
            )
            
            # Should raise ValueError for non-existent entity
            with pytest.raises(ValueError, match="Entity climate.nonexistent not found"):
                await schedule_manager.apply_grid_now_service(service_call)
    
    @pytest.mark.asyncio
    async def test_concurrent_service_calls(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test handling of concurrent service calls."""
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Create multiple concurrent service calls
            service_call1 = ServiceCall(
                domain=DOMAIN,
                service="apply_slot",
                data={
                    "entity_id": "climate.living_room",
                    "day": "monday",
                    "time": "06:00-08:00",
                    "force": True
                },
                context=Context()
            )
            
            service_call2 = ServiceCall(
                domain=DOMAIN,
                service="apply_grid_now",
                data={
                    "entity_id": "climate.living_room",
                    "force": True
                },
                context=Context()
            )
            
            # Execute concurrently
            import asyncio
            results = await asyncio.gather(
                schedule_manager.apply_slot_service(service_call1),
                schedule_manager.apply_grid_now_service(service_call2),
                return_exceptions=True
            )
            
            # Both should complete without exceptions
            assert len(results) == 2
            for result in results:
                assert not isinstance(result, Exception)


class TestDataConsistencyAndValidation:
    """Test data consistency and validation scenarios."""
    
    @pytest.mark.asyncio
    async def test_schedule_data_validation_on_load(self, mock_hass_with_complex_entities):
        """Test schedule data validation during load."""
        # Create invalid schedule data
        invalid_data = {
            "version": "0.3.0",
            "entities_tracked": "not_a_list",  # Should be list
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "invalid_rule",  # Invalid rule
            "presence_timeout_seconds": "not_a_number",  # Should be number
            "schedules": {
                "home": {
                    "monday": [
                        {
                            "start_time": "25:00",  # Invalid time
                            "end_time": "08:00",
                            "target": {"temperature": "not_a_number"},  # Should be number
                            "buffer_override": None
                        }
                    ]
                }
            }
        }
        
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage with invalid data
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = invalid_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Should handle invalid data gracefully by creating defaults
            result = await async_setup_entry(mock_hass, config_entry)
            assert result is True
            
            # Should have saved corrected/default data
            mock_store.async_save.assert_called()
    
    @pytest.mark.asyncio
    async def test_schedule_modification_validation(self, mock_hass_with_complex_entities, complex_schedule_data):
        """Test validation during schedule modifications."""
        mock_hass = mock_hass_with_complex_entities
        
        # Mock config entry
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        config_entry.data = {
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600
        }
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = complex_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test invalid slot modification
            with pytest.raises(ValueError):
                await schedule_manager.update_slot(
                    entity_id="climate.living_room",
                    mode="home",
                    day="invalid_day",  # Invalid day
                    time_slot="06:00-08:00",
                    target={"temperature": 20.0}
                )
            
            # Test invalid time slot format
            with pytest.raises(ValueError):
                await schedule_manager.update_slot(
                    entity_id="climate.living_room",
                    mode="home",
                    day="monday",
                    time_slot="invalid-format",  # Invalid format
                    target={"temperature": 20.0}
                )
            
            # Test invalid target value
            with pytest.raises(ValueError):
                await schedule_manager.update_slot(
                    entity_id="climate.living_room",
                    mode="home",
                    day="monday",
                    time_slot="06:00-08:00",
                    target={"temperature": "not_a_number"}  # Invalid type
                )