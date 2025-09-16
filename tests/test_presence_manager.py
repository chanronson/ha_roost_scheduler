"""Tests for the PresenceManager class."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from homeassistant.core import HomeAssistant, State, Event
from homeassistant.const import STATE_HOME, STATE_NOT_HOME

from custom_components.roost_scheduler.presence_manager import PresenceManager
from custom_components.roost_scheduler.const import MODE_HOME, MODE_AWAY


@pytest.fixture
def hass():
    """Create a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.states = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def presence_manager(hass):
    """Create a PresenceManager instance."""
    return PresenceManager(hass)


class TestPresenceManagerInitialization:
    """Test PresenceManager initialization."""
    
    def test_init(self, presence_manager, hass):
        """Test PresenceManager initialization."""
        assert presence_manager.hass == hass
        assert presence_manager._presence_entities == []
        assert presence_manager._presence_rule == "anyone_home"
        assert presence_manager._timeout_seconds == 600  # 10 minutes default
        assert presence_manager._current_mode == MODE_HOME
        assert not presence_manager._initialized
    
    @patch('custom_components.roost_scheduler.presence_manager.async_track_state_change_event')
    async def test_async_initialize(self, mock_track, presence_manager, hass):
        """Test async initialization."""
        await presence_manager.configure_presence(
            ["device_tracker.phone"], "anyone_home", 600
        )
        
        # Mock the state to avoid datetime issues
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_HOME
        phone_state.last_updated = datetime.now()
        
        hass.states.get.return_value = phone_state
        
        await presence_manager.async_initialize()
        
        assert presence_manager._initialized
        assert mock_track.called


class TestPresenceEvaluation:
    """Test presence evaluation logic."""
    
    async def test_evaluate_presence_no_entities(self, presence_manager):
        """Test presence evaluation with no entities configured."""
        result = await presence_manager.evaluate_presence_entities()
        assert result is True  # Default to home when no entities
    
    async def test_evaluate_presence_anyone_home_rule(self, presence_manager, hass):
        """Test anyone_home rule evaluation."""
        # Configure presence entities
        await presence_manager.configure_presence(
            ["device_tracker.phone1", "device_tracker.phone2"], 
            "anyone_home", 
            600
        )
        
        # Mock states - one home, one away
        phone1_state = Mock(spec=State)
        phone1_state.domain = "device_tracker"
        phone1_state.state = STATE_HOME
        phone1_state.last_updated = datetime.now()
        
        phone2_state = Mock(spec=State)
        phone2_state.domain = "device_tracker"
        phone2_state.state = STATE_NOT_HOME
        phone2_state.last_updated = datetime.now()
        
        hass.states.get.side_effect = lambda entity_id: {
            "device_tracker.phone1": phone1_state,
            "device_tracker.phone2": phone2_state
        }.get(entity_id)
        
        result = await presence_manager.evaluate_presence_entities()
        assert result is True  # Anyone home = True
    
    async def test_evaluate_presence_everyone_home_rule(self, presence_manager, hass):
        """Test everyone_home rule evaluation."""
        # Configure presence entities
        await presence_manager.configure_presence(
            ["device_tracker.phone1", "device_tracker.phone2"], 
            "everyone_home", 
            600
        )
        
        # Mock states - one home, one away
        phone1_state = Mock(spec=State)
        phone1_state.domain = "device_tracker"
        phone1_state.state = STATE_HOME
        phone1_state.last_updated = datetime.now()
        
        phone2_state = Mock(spec=State)
        phone2_state.domain = "device_tracker"
        phone2_state.state = STATE_NOT_HOME
        phone2_state.last_updated = datetime.now()
        
        hass.states.get.side_effect = lambda entity_id: {
            "device_tracker.phone1": phone1_state,
            "device_tracker.phone2": phone2_state
        }.get(entity_id)
        
        result = await presence_manager.evaluate_presence_entities()
        assert result is False  # Everyone home = False (one is away)
    
    async def test_evaluate_presence_stale_entities(self, presence_manager, hass):
        """Test presence evaluation with stale entities."""
        # Configure presence entities
        await presence_manager.configure_presence(
            ["device_tracker.phone"], "anyone_home", 300  # 5 minutes timeout
        )
        
        # Mock stale state (older than timeout)
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_HOME
        phone_state.last_updated = datetime.now() - timedelta(minutes=10)  # Stale
        
        hass.states.get.return_value = phone_state
        
        result = await presence_manager.evaluate_presence_entities()
        assert result is False  # Stale entity treated as away


class TestEntityStateDetection:
    """Test entity state detection logic."""
    
    def test_is_entity_home_device_tracker(self, presence_manager):
        """Test device tracker state detection."""
        state = Mock(spec=State)
        state.domain = "device_tracker"
        state.state = STATE_HOME
        
        assert presence_manager._is_entity_home(state) is True
        
        state.state = STATE_NOT_HOME
        assert presence_manager._is_entity_home(state) is False
    
    def test_is_entity_home_person(self, presence_manager):
        """Test person entity state detection."""
        state = Mock(spec=State)
        state.domain = "person"
        state.state = STATE_HOME
        
        assert presence_manager._is_entity_home(state) is True
        
        state.state = STATE_NOT_HOME
        assert presence_manager._is_entity_home(state) is False
    
    def test_is_entity_home_input_boolean(self, presence_manager):
        """Test input_boolean state detection."""
        state = Mock(spec=State)
        state.domain = "input_boolean"
        state.state = "on"
        
        assert presence_manager._is_entity_home(state) is True
        
        state.state = "off"
        assert presence_manager._is_entity_home(state) is False
    
    def test_is_entity_stale(self, presence_manager, hass):
        """Test stale entity detection."""
        # Mock fresh state
        fresh_state = Mock(spec=State)
        fresh_state.last_updated = datetime.now()
        hass.states.get.return_value = fresh_state
        
        assert presence_manager.is_entity_stale("test.entity") is False
        
        # Mock stale state
        stale_state = Mock(spec=State)
        stale_state.last_updated = datetime.now() - timedelta(minutes=15)
        hass.states.get.return_value = stale_state
        
        assert presence_manager.is_entity_stale("test.entity") is True
        
        # Mock missing state
        hass.states.get.return_value = None
        assert presence_manager.is_entity_stale("test.entity") is True


class TestPresenceOverrides:
    """Test presence override functionality."""
    
    async def test_get_current_mode_force_home(self, presence_manager, hass):
        """Test force home override."""
        # Mock force home override active
        force_home_state = Mock(spec=State)
        force_home_state.state = "on"
        
        force_away_state = Mock(spec=State)
        force_away_state.state = "off"
        
        hass.states.get.side_effect = lambda entity_id: {
            "input_boolean.roost_force_home": force_home_state,
            "input_boolean.roost_force_away": force_away_state
        }.get(entity_id)
        
        mode = await presence_manager.get_current_mode()
        assert mode == MODE_HOME
    
    async def test_get_current_mode_force_away(self, presence_manager, hass):
        """Test force away override."""
        # Mock force away override active
        force_home_state = Mock(spec=State)
        force_home_state.state = "off"
        
        force_away_state = Mock(spec=State)
        force_away_state.state = "on"
        
        hass.states.get.side_effect = lambda entity_id: {
            "input_boolean.roost_force_home": force_home_state,
            "input_boolean.roost_force_away": force_away_state
        }.get(entity_id)
        
        mode = await presence_manager.get_current_mode()
        assert mode == MODE_AWAY
    
    async def test_set_override(self, presence_manager, hass):
        """Test setting presence override."""
        await presence_manager.set_override("force_home", True)
        
        hass.services.async_call.assert_called_once_with(
            "input_boolean",
            "turn_on",
            {"entity_id": "input_boolean.roost_force_home"}
        )
        
        hass.services.async_call.reset_mock()
        
        await presence_manager.set_override("force_away", False)
        
        hass.services.async_call.assert_called_once_with(
            "input_boolean",
            "turn_off",
            {"entity_id": "input_boolean.roost_force_away"}
        )


class TestModeChangeCallbacks:
    """Test mode change callback functionality."""
    
    async def test_mode_change_callback_registration(self, presence_manager):
        """Test callback registration."""
        callback = Mock()
        
        await presence_manager.register_mode_change_callback(callback)
        
        assert callback in presence_manager._mode_change_callbacks
    
    async def test_mode_change_callback_execution(self, presence_manager, hass):
        """Test callback execution on mode change."""
        callback = Mock()
        await presence_manager.register_mode_change_callback(callback)
        
        # Mock no overrides
        hass.states.get.return_value = None
        
        # Configure presence to return away mode
        await presence_manager.configure_presence(
            ["device_tracker.phone"], "anyone_home", 600
        )
        
        # Mock away state
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_NOT_HOME
        phone_state.last_updated = datetime.now()
        
        hass.states.get.side_effect = lambda entity_id: {
            "device_tracker.phone": phone_state
        }.get(entity_id) if entity_id == "device_tracker.phone" else None
        
        # First call should set mode to away and trigger callback
        mode = await presence_manager.get_current_mode()
        assert mode == MODE_AWAY
        callback.assert_called_once_with(MODE_AWAY)


class TestPresenceStatus:
    """Test presence status reporting."""
    
    def test_get_presence_status(self, presence_manager, hass):
        """Test getting detailed presence status."""
        # Configure presence
        presence_manager._presence_entities = ["device_tracker.phone"]
        presence_manager._current_mode = MODE_HOME
        
        # Mock entity state
        phone_state = Mock(spec=State)
        phone_state.state = STATE_HOME
        phone_state.last_updated = datetime.now()
        phone_state.domain = "device_tracker"
        
        # Mock override states
        force_home_state = Mock(spec=State)
        force_home_state.state = "off"
        
        force_away_state = Mock(spec=State)
        force_away_state.state = "off"
        
        hass.states.get.side_effect = lambda entity_id: {
            "device_tracker.phone": phone_state,
            "input_boolean.roost_force_home": force_home_state,
            "input_boolean.roost_force_away": force_away_state
        }.get(entity_id)
        
        status = presence_manager.get_presence_status()
        
        assert status["current_mode"] == MODE_HOME
        assert status["presence_rule"] == "anyone_home"
        assert "device_tracker.phone" in status["entities"]
        assert status["entities"]["device_tracker.phone"]["is_home"] is True
        assert status["overrides"]["force_home"]["active"] is False
        assert status["overrides"]["force_away"]["active"] is False


class TestPresenceConfiguration:
    """Test presence configuration."""
    
    @patch('custom_components.roost_scheduler.presence_manager.async_track_state_change_event')
    async def test_configure_presence(self, mock_track, presence_manager):
        """Test presence configuration."""
        entities = ["device_tracker.phone1", "device_tracker.phone2"]
        rule = "everyone_home"
        timeout = 300
        
        await presence_manager.configure_presence(entities, rule, timeout)
        
        assert presence_manager._presence_entities == entities
        assert presence_manager._presence_rule == rule
        assert presence_manager._timeout_seconds == timeout
    
    @patch('custom_components.roost_scheduler.presence_manager.async_track_state_change_event')
    async def test_configure_presence_updates_listeners(self, mock_track, presence_manager):
        """Test that configuring presence updates state listeners."""
        # Initialize first
        await presence_manager.async_initialize()
        
        # Configure new entities
        await presence_manager.configure_presence(
            ["device_tracker.new_phone"], "anyone_home", 600
        )
        
        # Should have set up new listeners
        assert mock_track.call_count >= 1