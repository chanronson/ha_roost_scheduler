"""Comprehensive integration tests for Roost Scheduler workflows."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, time, timedelta
import json

from homeassistant.core import HomeAssistant, ServiceCall, Context
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.helpers.storage import Store

from custom_components.roost_scheduler import async_setup_entry, async_unload_entry
from custom_components.roost_scheduler.const import DOMAIN
from custom_components.roost_scheduler.models import ScheduleData, ScheduleSlot
from custom_components.roost_scheduler.schedule_manager import ScheduleManager
from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.buffer_manager import BufferManager
from custom_components.roost_scheduler.storage import StorageService


@pytest.fixture
def mock_hass():
    """Create a comprehensive mock Home Assistant instance."""
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
    
    # Mock entity states
    mock_states = {}
    
    def mock_get_state(entity_id):
        return mock_states.get(entity_id)
    
    def mock_set_state(entity_id, state):
        mock_states[entity_id] = state
    
    # Create states mock
    states_mock = MagicMock()
    states_mock.get = mock_get_state
    states_mock._mock_set_state = mock_set_state
    hass.states = states_mock
    
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "entities_tracked": ["climate.living_room", "climate.bedroom"],
        "presence_entities": ["device_tracker.phone", "person.user"],
        "presence_rule": "anyone_home",
        "presence_timeout_seconds": 600
    }
    entry.options = {}
    return entry


@pytest.fixture
def sample_schedule_data():
    """Create sample schedule data for testing."""
    return {
        "version": "0.3.0",
        "entities_tracked": ["climate.living_room", "climate.bedroom"],
        "presence_entities": ["device_tracker.phone", "person.user"],
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
            "resolution_minutes": 30,
            "auto_add_card": False
        },
        "schedules": {
            "home": {
                "monday": [
                    {
                        "start_time": "06:00",
                        "end_time": "08:00",
                        "target": {"temperature": 20.0},
                        "buffer_override": None
                    },
                    {
                        "start_time": "18:00",
                        "end_time": "22:00",
                        "target": {"temperature": 21.0},
                        "buffer_override": None
                    }
                ],
                "tuesday": [
                    {
                        "start_time": "07:00",
                        "end_time": "09:00",
                        "target": {"temperature": 19.5},
                        "buffer_override": {"time_minutes": 10, "value_delta": 1.0}
                    }
                ]
            },
            "away": {
                "monday": [
                    {
                        "start_time": "08:00",
                        "end_time": "18:00",
                        "target": {"temperature": 16.0},
                        "buffer_override": None
                    }
                ],
                "tuesday": [
                    {
                        "start_time": "09:00",
                        "end_time": "17:00",
                        "target": {"temperature": 15.5},
                        "buffer_override": None
                    }
                ]
            }
        },
        "metadata": {
            "created_by": "integration_test",
            "created_at": "2025-09-17T10:00:00Z",
            "last_modified": "2025-09-17T10:00:00Z"
        }
    }


class TestCompleteUserWorkflows:
    """Test complete user workflows from start to finish."""
    
    @pytest.mark.asyncio
    async def test_fresh_installation_workflow(self, mock_hass, mock_config_entry):
        """Test complete fresh installation workflow."""
        # Mock storage to return None (fresh install)
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = None
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            result = await async_setup_entry(mock_hass, mock_config_entry)
            assert result is True
            
            # Verify integration data was created
            assert DOMAIN in mock_hass.data
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
            
            # Verify services were registered
            assert mock_hass.services.async_register.call_count == 2
            
            # Verify storage was initialized with default data
            mock_store.async_save.assert_called_once()
            saved_data = mock_store.async_save.call_args[0][0]
            assert saved_data["version"] == "0.3.0"
            assert saved_data["entities_tracked"] == ["climate.living_room", "climate.bedroom"]
    
    @pytest.mark.asyncio
    async def test_schedule_creation_and_application_workflow(self, mock_hass, mock_config_entry, sample_schedule_data):
        """Test creating schedules and applying them."""
        # Setup entity states
        climate_state = MagicMock()
        climate_state.state = "heat"
        climate_state.attributes = {"temperature": 18.0, "target_temp_high": None, "target_temp_low": None}
        mock_hass.states._mock_set_state("climate.living_room", climate_state)
        
        presence_state = MagicMock()
        presence_state.state = STATE_HOME
        presence_state.last_updated = datetime.now()
        mock_hass.states._mock_set_state("device_tracker.phone", presence_state)
        
        # Mock storage with sample data
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get the schedule manager
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test schedule application at 07:00 on Monday (home mode)
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 7, 0)  # Monday 07:00
                mock_datetime.strptime = datetime.strptime
                
                # Apply schedule
                result = await schedule_manager.apply_schedule("climate.living_room")
                assert result is True
                
                # Verify service call was made
                mock_hass.services.async_call.assert_called_with(
                    "climate",
                    "set_temperature",
                    {"entity_id": "climate.living_room", "temperature": 20.0},
                    blocking=True
                )
    
    @pytest.mark.asyncio
    async def test_schedule_modification_workflow(self, mock_hass, mock_config_entry, sample_schedule_data):
        """Test modifying existing schedules."""
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get the schedule manager
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Modify a schedule slot
            result = await schedule_manager.update_slot(
                entity_id="climate.living_room",
                mode="home",
                day="monday",
                time_slot="06:00-08:00",
                target={"temperature": 22.0}
            )
            assert result is True
            
            # Verify storage was updated
            mock_store.async_save.assert_called()
            
            # Verify event was emitted
            mock_hass.bus.async_fire.assert_called_with(
                "roost_scheduler_schedule_updated",
                {
                    "entity_id": "climate.living_room",
                    "mode": "home",
                    "day": "monday",
                    "time_slot": "06:00-08:00",
                    "target_value": 22.0,
                    "changes": [{"day": "monday", "time": "06:00-08:00", "value": 22.0}]
                }
            )
    
    @pytest.mark.asyncio
    async def test_service_call_workflow(self, mock_hass, mock_config_entry, sample_schedule_data):
        """Test using services to control schedules."""
        # Setup entity state
        climate_state = MagicMock()
        climate_state.state = "heat"
        climate_state.attributes = {"temperature": 18.0}
        mock_hass.states._mock_set_state("climate.living_room", climate_state)
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get the schedule manager
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test apply_slot service
            service_call = ServiceCall(
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
            
            await schedule_manager.apply_slot_service(service_call)
            
            # Verify climate service was called
            mock_hass.services.async_call.assert_called_with(
                "climate",
                "set_temperature",
                {"entity_id": "climate.living_room", "temperature": 20.0},
                blocking=True
            )
    
    @pytest.mark.asyncio
    async def test_uninstallation_workflow(self, mock_hass, mock_config_entry, sample_schedule_data):
        """Test complete uninstallation workflow."""
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Verify setup completed
            assert DOMAIN in mock_hass.data
            assert mock_config_entry.entry_id in mock_hass.data[DOMAIN]
            
            # Unload integration
            result = await async_unload_entry(mock_hass, mock_config_entry)
            assert result is True
            
            # Verify cleanup
            assert mock_config_entry.entry_id not in mock_hass.data.get(DOMAIN, {})


class TestPresenceBasedModeSwitch:
    """Test presence-based mode switching scenarios."""
    
    @pytest.fixture
    def setup_presence_test(self, mock_hass, mock_config_entry, sample_schedule_data):
        """Setup for presence testing."""
        # Setup entity states
        climate_state = MagicMock()
        climate_state.state = "heat"
        climate_state.attributes = {"temperature": 18.0}
        mock_hass.states._mock_set_state("climate.living_room", climate_state)
        
        # Setup presence entities
        phone_state = MagicMock()
        phone_state.last_updated = datetime.now()
        mock_hass.states._mock_set_state("device_tracker.phone", phone_state)
        
        person_state = MagicMock()
        person_state.last_updated = datetime.now()
        mock_hass.states._mock_set_state("person.user", person_state)
        
        return mock_hass, mock_config_entry, sample_schedule_data
    
    @pytest.mark.asyncio
    async def test_home_to_away_mode_switch(self, setup_presence_test):
        """Test switching from home to away mode."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_presence_test
        
        # Start with home presence
        mock_hass.states.get("device_tracker.phone").state = STATE_HOME
        mock_hass.states.get("person.user").state = STATE_HOME
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get managers
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            schedule_manager = integration_data["schedule_manager"]
            
            # Verify initial home mode
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "home"
            
            # Change presence to away
            mock_hass.states.get("device_tracker.phone").state = STATE_NOT_HOME
            mock_hass.states.get("person.user").state = STATE_NOT_HOME
            
            # Verify mode changed to away
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "away"
            
            # Test schedule application in away mode at 09:00 Monday
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 9, 0)  # Monday 09:00
                mock_datetime.strptime = datetime.strptime
                
                result = await schedule_manager.apply_schedule("climate.living_room")
                assert result is True
                
                # Should apply away schedule (16.0°C)
                mock_hass.services.async_call.assert_called_with(
                    "climate",
                    "set_temperature",
                    {"entity_id": "climate.living_room", "temperature": 16.0},
                    blocking=True
                )
    
    @pytest.mark.asyncio
    async def test_anyone_home_rule(self, setup_presence_test):
        """Test anyone_home presence rule."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_presence_test
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get presence manager
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Test: one person home, one away -> should be home
            mock_hass.states.get("device_tracker.phone").state = STATE_HOME
            mock_hass.states.get("person.user").state = STATE_NOT_HOME
            
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "home"
            
            # Test: both away -> should be away
            mock_hass.states.get("device_tracker.phone").state = STATE_NOT_HOME
            mock_hass.states.get("person.user").state = STATE_NOT_HOME
            
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "away"
    
    @pytest.mark.asyncio
    async def test_presence_timeout_handling(self, setup_presence_test):
        """Test presence timeout handling for stale entities."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_presence_test
        
        # Set stale timestamps (older than timeout)
        stale_time = datetime.now() - timedelta(minutes=15)  # Older than 10 minute timeout
        mock_hass.states.get("device_tracker.phone").last_updated = stale_time
        mock_hass.states.get("device_tracker.phone").state = STATE_HOME
        mock_hass.states.get("person.user").state = STATE_HOME
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get presence manager
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Should treat stale entity as away
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "away"  # Only person.user is valid and home
    
    @pytest.mark.asyncio
    async def test_presence_override_functionality(self, setup_presence_test):
        """Test presence override with boolean helpers."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_presence_test
        
        # Setup override entities
        force_home_state = MagicMock()
        force_home_state.state = "off"
        mock_hass.states._mock_set_state("input_boolean.roost_force_home", force_home_state)
        
        force_away_state = MagicMock()
        force_away_state.state = "off"
        mock_hass.states._mock_set_state("input_boolean.roost_force_away", force_away_state)
        
        # Set normal presence to away
        mock_hass.states.get("device_tracker.phone").state = STATE_NOT_HOME
        mock_hass.states.get("person.user").state = STATE_NOT_HOME
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get presence manager
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            presence_manager = integration_data["presence_manager"]
            
            # Normal mode should be away
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "away"
            
            # Enable force home override
            mock_hass.states.get("input_boolean.roost_force_home").state = "on"
            
            # Should now be home despite presence entities
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "home"
            
            # Disable force home, enable force away
            mock_hass.states.get("input_boolean.roost_force_home").state = "off"
            mock_hass.states.get("input_boolean.roost_force_away").state = "on"
            
            # Set presence to home but should still be away due to override
            mock_hass.states.get("device_tracker.phone").state = STATE_HOME
            mock_hass.states.get("person.user").state = STATE_HOME
            
            current_mode = await presence_manager.get_current_mode()
            assert current_mode == "away"


class TestBufferSystemBehavior:
    """Test buffer system behavior under various conditions."""
    
    @pytest.fixture
    def setup_buffer_test(self, mock_hass, mock_config_entry, sample_schedule_data):
        """Setup for buffer testing."""
        # Setup climate entity with current temperature
        climate_state = MagicMock()
        climate_state.state = "heat"
        climate_state.attributes = {"temperature": 19.0}  # Current temp
        mock_hass.states._mock_set_state("climate.living_room", climate_state)
        
        return mock_hass, mock_config_entry, sample_schedule_data
    
    @pytest.mark.asyncio
    async def test_buffer_suppression_within_tolerance(self, setup_buffer_test):
        """Test buffer suppression when current value is within tolerance."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_buffer_test
        
        # Set current temperature close to target (within 2.0°C tolerance)
        mock_hass.states.get("climate.living_room").attributes["temperature"] = 19.5  # Target is 20.0
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get managers
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            buffer_manager = integration_data["buffer_manager"]
            
            # Test suppression logic
            should_suppress = buffer_manager.should_suppress_change(
                entity_id="climate.living_room",
                target_value=20.0,
                slot_config={}
            )
            
            # Should suppress because 19.5 is within 2.0°C of 20.0
            assert should_suppress is True
    
    @pytest.mark.asyncio
    async def test_buffer_suppression_outside_tolerance(self, setup_buffer_test):
        """Test buffer allows change when current value is outside tolerance."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_buffer_test
        
        # Set current temperature far from target (outside 2.0°C tolerance)
        mock_hass.states.get("climate.living_room").attributes["temperature"] = 17.0  # Target is 20.0
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get managers
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            buffer_manager = integration_data["buffer_manager"]
            
            # Test suppression logic
            should_suppress = buffer_manager.should_suppress_change(
                entity_id="climate.living_room",
                target_value=20.0,
                slot_config={}
            )
            
            # Should not suppress because 17.0 is outside 2.0°C tolerance of 20.0
            assert should_suppress is False
    
    @pytest.mark.asyncio
    async def test_buffer_suppression_after_manual_change(self, setup_buffer_test):
        """Test buffer suppression after recent manual change."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_buffer_test
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get managers
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            buffer_manager = integration_data["buffer_manager"]
            
            # Simulate recent manual change
            buffer_manager.update_manual_change("climate.living_room", 18.5)
            
            # Set current temperature to manual value
            mock_hass.states.get("climate.living_room").attributes["temperature"] = 18.5
            
            # Test suppression with target different from manual value
            should_suppress = buffer_manager.should_suppress_change(
                entity_id="climate.living_room",
                target_value=20.0,
                slot_config={}
            )
            
            # Should suppress because manual change is recent and current value matches manual value
            assert should_suppress is True
    
    @pytest.mark.asyncio
    async def test_buffer_per_slot_override(self, setup_buffer_test):
        """Test per-slot buffer override functionality."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_buffer_test
        
        # Set current temperature
        mock_hass.states.get("climate.living_room").attributes["temperature"] = 18.8  # Close to 19.5 target
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get managers
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            buffer_manager = integration_data["buffer_manager"]
            
            # Test with slot-specific override (tighter tolerance: 1.0°C)
            slot_config = {
                "buffer_override": {
                    "time_minutes": 10,
                    "value_delta": 1.0  # Tighter than global 2.0
                }
            }
            
            should_suppress = buffer_manager.should_suppress_change(
                entity_id="climate.living_room",
                target_value=19.5,
                slot_config=slot_config
            )
            
            # Should not suppress because 18.8 is outside 1.0°C tolerance of 19.5
            assert should_suppress is False
            
            # Test with looser slot override
            slot_config["buffer_override"]["value_delta"] = 3.0
            
            should_suppress = buffer_manager.should_suppress_change(
                entity_id="climate.living_room",
                target_value=19.5,
                slot_config=slot_config
            )
            
            # Should suppress because 18.8 is within 3.0°C tolerance of 19.5
            assert should_suppress is True
    
    @pytest.mark.asyncio
    async def test_buffer_force_apply_bypass(self, setup_buffer_test):
        """Test force apply bypasses buffer logic."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_buffer_test
        
        # Set current temperature within tolerance
        mock_hass.states.get("climate.living_room").attributes["temperature"] = 19.8  # Close to 20.0
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get managers
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test normal application (should be suppressed)
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 7, 0)  # Monday 07:00
                mock_datetime.strptime = datetime.strptime
                
                result = await schedule_manager.apply_schedule("climate.living_room", force=False)
                
                # Should not call service due to buffer suppression
                mock_hass.services.async_call.assert_not_called()
            
            # Reset mock
            mock_hass.services.async_call.reset_mock()
            
            # Test force application (should bypass buffer)
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 7, 0)  # Monday 07:00
                mock_datetime.strptime = datetime.strptime
                
                result = await schedule_manager.apply_schedule("climate.living_room", force=True)
                
                # Should call service despite buffer suppression
                mock_hass.services.async_call.assert_called_with(
                    "climate",
                    "set_temperature",
                    {"entity_id": "climate.living_room", "temperature": 20.0},
                    blocking=True
                )
    
    @pytest.mark.asyncio
    async def test_buffer_time_expiration(self, setup_buffer_test):
        """Test buffer time expiration allows changes."""
        mock_hass, mock_config_entry, sample_schedule_data = setup_buffer_test
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get managers
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            buffer_manager = integration_data["buffer_manager"]
            
            # Simulate old manual change (beyond buffer time)
            old_time = datetime.now() - timedelta(minutes=20)  # Older than 15 minute buffer
            with patch('custom_components.roost_scheduler.buffer_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = old_time
                buffer_manager.update_manual_change("climate.living_room", 18.5)
            
            # Set current temperature to manual value
            mock_hass.states.get("climate.living_room").attributes["temperature"] = 18.5
            
            # Test suppression with expired buffer time
            should_suppress = buffer_manager.should_suppress_change(
                entity_id="climate.living_room",
                target_value=20.0,
                slot_config={}
            )
            
            # Should not suppress because buffer time has expired
            assert should_suppress is False


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_unavailable_entity_handling(self, mock_hass, mock_config_entry, sample_schedule_data):
        """Test handling of unavailable entities."""
        # Setup unavailable entity
        climate_state = MagicMock()
        climate_state.state = "unavailable"
        climate_state.attributes = {}
        mock_hass.states._mock_set_state("climate.living_room", climate_state)
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test schedule application with unavailable entity
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 7, 0)  # Monday 07:00
                mock_datetime.strptime = datetime.strptime
                
                result = await schedule_manager.apply_schedule("climate.living_room")
                
                # Should return False and not call service
                assert result is False
                mock_hass.services.async_call.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_service_call_failure_handling(self, mock_hass, mock_config_entry, sample_schedule_data):
        """Test handling of service call failures."""
        # Setup entity
        climate_state = MagicMock()
        climate_state.state = "heat"
        climate_state.attributes = {"temperature": 18.0}
        mock_hass.states._mock_set_state("climate.living_room", climate_state)
        
        # Mock service call to fail
        mock_hass.services.async_call.side_effect = Exception("Service call failed")
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = sample_schedule_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Setup integration
            await async_setup_entry(mock_hass, mock_config_entry)
            
            # Get schedule manager
            integration_data = mock_hass.data[DOMAIN][mock_config_entry.entry_id]
            schedule_manager = integration_data["schedule_manager"]
            
            # Test schedule application with service failure
            with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_datetime:
                mock_datetime.now.return_value = datetime(2025, 9, 22, 7, 0)  # Monday 07:00
                mock_datetime.strptime = datetime.strptime
                
                result = await schedule_manager.apply_schedule("climate.living_room", force=True)
                
                # Should return False due to service failure
                assert result is False
    
    @pytest.mark.asyncio
    async def test_storage_corruption_recovery(self, mock_hass, mock_config_entry):
        """Test recovery from storage corruption."""
        # Mock corrupted storage data
        corrupted_data = {"invalid": "data", "version": "corrupted"}
        
        # Mock storage
        with patch('custom_components.roost_scheduler.storage.Store') as mock_store_class:
            mock_store = MagicMock()
            mock_store.async_load.return_value = corrupted_data
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Mock recovery mechanism
            with patch('custom_components.roost_scheduler.storage.StorageService._attempt_recovery') as mock_recovery:
                mock_recovery.return_value = None  # Recovery fails
                
                # Setup integration should handle corruption gracefully
                result = await async_setup_entry(mock_hass, mock_config_entry)
                
                # Should still succeed by creating default data
                assert result is True
                
                # Should have attempted recovery
                mock_recovery.assert_called_once()