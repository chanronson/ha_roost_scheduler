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
        # Add bus mock to hass
        hass.bus = Mock()
        hass.bus.async_fire = Mock()
        
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


class TestCustomTemplateSupport:
    """Test custom Jinja template functionality."""
    
    @patch('custom_components.roost_scheduler.presence_manager.Template')
    async def test_configure_presence_with_template(self, mock_template_class, presence_manager):
        """Test configuring presence with custom template."""
        template_str = "{{ is_state('device_tracker.phone', 'home') or is_state('person.user', 'home') }}"
        
        # Mock Template class
        mock_template = Mock()
        mock_template_class.return_value = mock_template
        
        await presence_manager.configure_presence(
            ["device_tracker.phone"], "custom", 600, template_str
        )
        
        assert presence_manager._custom_template == mock_template
        assert presence_manager._presence_rule == "custom"
        mock_template_class.assert_called_once_with(template_str, presence_manager.hass)
    
    def test_extract_template_entities(self, presence_manager):
        """Test extracting entity IDs from template strings."""
        template_str = """
        {{ is_state('device_tracker.phone', 'home') and 
           states('person.user') == 'home' and
           state_attr('sensor.presence', 'value') > 0 }}
        """
        
        entities = presence_manager._extract_template_entities(template_str)
        
        expected_entities = ['device_tracker.phone', 'person.user', 'sensor.presence']
        assert set(entities) == set(expected_entities)
    
    def test_set_custom_template(self, presence_manager):
        """Test setting custom template."""
        template_str = "{{ is_state('device_tracker.phone', 'home') }}"
        
        with patch('custom_components.roost_scheduler.presence_manager.Template') as mock_template_class:
            mock_template = Mock()
            mock_template_class.return_value = mock_template
            
            result = presence_manager.set_custom_template(template_str)
            
            assert result is True
            assert presence_manager._custom_template == mock_template
            assert presence_manager._presence_rule == "custom"
            assert 'device_tracker.phone' in presence_manager._template_entities
    
    def test_set_custom_template_error(self, presence_manager):
        """Test setting invalid custom template."""
        template_str = "{{ invalid_template_syntax"
        
        with patch('custom_components.roost_scheduler.presence_manager.Template') as mock_template_class:
            mock_template_class.side_effect = Exception("Template error")
            
            result = presence_manager.set_custom_template(template_str)
            
            assert result is False
            assert presence_manager._custom_template is None
    
    def test_clear_custom_template(self, presence_manager):
        """Test clearing custom template."""
        # Set up template first
        presence_manager._custom_template = Mock()
        presence_manager._template_entities = ['device_tracker.phone']
        presence_manager._presence_rule = "custom"
        
        presence_manager.clear_custom_template()
        
        assert presence_manager._custom_template is None
        assert presence_manager._template_entities == []
        assert presence_manager._presence_rule == "anyone_home"
    
    async def test_evaluate_custom_template_boolean(self, presence_manager):
        """Test custom template evaluation with boolean result."""
        mock_template = Mock()
        mock_template.async_render.return_value = True
        presence_manager._custom_template = mock_template
        
        result = await presence_manager._evaluate_custom_template()
        
        assert result is True
        mock_template.async_render.assert_called_once()
    
    async def test_evaluate_custom_template_string(self, presence_manager):
        """Test custom template evaluation with string result."""
        mock_template = Mock()
        mock_template.async_render.return_value = "home"
        presence_manager._custom_template = mock_template
        
        result = await presence_manager._evaluate_custom_template()
        
        assert result is True
        
        # Test false string values
        for false_value in ['false', 'no', 'off', '0', 'away']:
            mock_template.async_render.return_value = false_value
            result = await presence_manager._evaluate_custom_template()
            assert result is False
    
    async def test_evaluate_custom_template_error(self, presence_manager, hass):
        """Test custom template evaluation with error fallback."""
        mock_template = Mock()
        mock_template.async_render.side_effect = Exception("Template error")
        presence_manager._custom_template = mock_template
        presence_manager._presence_entities = ["device_tracker.phone"]
        
        # Mock entity state for fallback
        phone_state = Mock(spec=State)
        phone_state.domain = "device_tracker"
        phone_state.state = STATE_HOME
        phone_state.last_updated = datetime.now()
        
        hass.states.get.return_value = phone_state
        
        result = await presence_manager._evaluate_custom_template()
        
        # Should fall back to standard evaluation
        assert result is True
    
    async def test_evaluate_presence_with_template(self, presence_manager):
        """Test presence evaluation using custom template."""
        mock_template = Mock()
        mock_template.async_render.return_value = True
        presence_manager._custom_template = mock_template
        
        result = await presence_manager.evaluate_presence_entities()
        
        assert result is True
        mock_template.async_render.assert_called_once()
    
    @patch('custom_components.roost_scheduler.presence_manager.async_track_state_change_event')
    async def test_template_entities_in_listeners(self, mock_track, presence_manager):
        """Test that template entities are included in state listeners."""
        template_str = "{{ is_state('device_tracker.phone', 'home') }}"
        
        with patch('custom_components.roost_scheduler.presence_manager.Template'):
            # Configure presence first, then initialize
            await presence_manager.configure_presence(
                ["person.user"], "custom", 600, template_str
            )
            
            # Mock the presence manager to keep the configured entities during initialization
            original_entities = presence_manager._presence_entities.copy()
            original_template_entities = presence_manager._template_entities.copy()
            
            await presence_manager.async_initialize()
            
            # Restore the configured entities (since async_initialize loads from storage and resets them)
            presence_manager._presence_entities = original_entities
            presence_manager._template_entities = original_template_entities
            
            # Set up listeners again with the restored configuration
            await presence_manager._setup_state_listeners()
            
            # Should include both presence entities and template entities
            call_args = mock_track.call_args[0]
            entities = call_args[1]  # Second argument is the entity list
            
            assert 'person.user' in entities
            assert 'device_tracker.phone' in entities
    
    def test_get_presence_status_with_template(self, presence_manager):
        """Test presence status includes template information."""
        template_str = "{{ is_state('device_tracker.phone', 'home') }}"
        mock_template = Mock()
        mock_template.template = template_str
        
        presence_manager._custom_template = mock_template
        presence_manager._template_entities = ['device_tracker.phone']
        presence_manager._presence_rule = "custom"
        
        status = presence_manager.get_presence_status()
        
        assert status["custom_template"] == template_str
        assert status["template_entities"] == ['device_tracker.phone']
        assert status["presence_rule"] == "custom"


class TestPresenceManagerStorageIntegration:
    """Test PresenceManager storage integration functionality."""
    
    @pytest.fixture
    def mock_storage_service(self):
        """Create a mock storage service."""
        storage = Mock()
        storage.load_schedules = AsyncMock()
        storage.save_schedules = AsyncMock()
        return storage
    
    @pytest.fixture
    def presence_manager_with_storage(self, hass, mock_storage_service):
        """Create a PresenceManager with storage service."""
        # Add bus mock to hass
        hass.bus = Mock()
        hass.bus.async_fire = Mock()
        return PresenceManager(hass, mock_storage_service)
    
    def test_init_with_storage_service(self, hass, mock_storage_service):
        """Test PresenceManager initialization with storage service."""
        manager = PresenceManager(hass, mock_storage_service)
        
        assert manager.hass == hass
        assert manager.storage_service == mock_storage_service
        assert manager._presence_config is None
        assert manager._presence_entities == []
        assert manager._presence_rule == "anyone_home"
    
    def test_init_without_storage_service(self, hass):
        """Test PresenceManager initialization without storage service."""
        manager = PresenceManager(hass)
        
        assert manager.hass == hass
        assert manager.storage_service is None
        assert manager._presence_config is None
    
    async def test_load_configuration_no_storage(self, hass):
        """Test loading configuration without storage service."""
        manager = PresenceManager(hass, None)
        
        await manager.load_configuration()
        
        # Should initialize with defaults
        assert manager._presence_entities == []
        assert manager._presence_rule == "anyone_home"
        assert manager._timeout_seconds == 600
    
    async def test_load_configuration_with_presence_config(self, presence_manager_with_storage, mock_storage_service):
        """Test loading configuration with existing PresenceConfig."""
        from custom_components.roost_scheduler.models import ScheduleData, PresenceConfig
        
        # Mock schedule data with presence config
        presence_config = PresenceConfig(
            entities=["device_tracker.phone", "person.user"],
            rule="everyone_home",
            timeout_seconds=300,
            custom_template="{{ is_state('device_tracker.phone', 'home') }}"
        )
        
        schedule_data = Mock(spec=ScheduleData)
        schedule_data.presence_config = presence_config
        
        mock_storage_service.load_schedules.return_value = schedule_data
        
        with patch('custom_components.roost_scheduler.presence_manager.Template') as mock_template_class:
            mock_template = Mock()
            mock_template_class.return_value = mock_template
            
            await presence_manager_with_storage.load_configuration()
        
        assert presence_manager_with_storage._presence_entities == ["device_tracker.phone", "person.user"]
        assert presence_manager_with_storage._presence_rule == "everyone_home"
        assert presence_manager_with_storage._timeout_seconds == 300
        assert presence_manager_with_storage._custom_template == mock_template
    
    async def test_load_configuration_migration_from_legacy(self, presence_manager_with_storage, mock_storage_service):
        """Test loading configuration with migration from legacy fields."""
        from custom_components.roost_scheduler.models import ScheduleData
        
        # Mock schedule data without presence_config but with legacy fields
        schedule_data = Mock(spec=ScheduleData)
        schedule_data.presence_config = None
        schedule_data.presence_entities = ["device_tracker.legacy"]
        schedule_data.presence_rule = "anyone_home"
        schedule_data.presence_timeout_seconds = 900
        
        mock_storage_service.load_schedules.return_value = schedule_data
        
        await presence_manager_with_storage.load_configuration()
        
        # Should have migrated from legacy fields
        assert presence_manager_with_storage._presence_entities == ["device_tracker.legacy"]
        assert presence_manager_with_storage._presence_rule == "anyone_home"
        assert presence_manager_with_storage._timeout_seconds == 900
        
        # Should have saved the migrated configuration
        mock_storage_service.save_schedules.assert_called_once()
    
    async def test_load_configuration_no_data(self, presence_manager_with_storage, mock_storage_service):
        """Test loading configuration with no existing data."""
        mock_storage_service.load_schedules.return_value = None
        
        await presence_manager_with_storage.load_configuration()
        
        # Should initialize with defaults
        assert presence_manager_with_storage._presence_entities == []
        assert presence_manager_with_storage._presence_rule == "anyone_home"
        assert presence_manager_with_storage._timeout_seconds == 600
    
    async def test_load_configuration_error_handling(self, presence_manager_with_storage, mock_storage_service):
        """Test error handling during configuration loading."""
        mock_storage_service.load_schedules.side_effect = Exception("Storage error")
        
        await presence_manager_with_storage.load_configuration()
        
        # Should fall back to defaults on error
        assert presence_manager_with_storage._presence_entities == []
        assert presence_manager_with_storage._presence_rule == "anyone_home"
        assert presence_manager_with_storage._timeout_seconds == 600
    
    async def test_save_configuration_no_storage(self, hass):
        """Test saving configuration without storage service."""
        manager = PresenceManager(hass, None)
        
        # Should not raise error, just log warning
        await manager.save_configuration()
    
    async def test_save_configuration_new_schedule_data(self, presence_manager_with_storage, mock_storage_service):
        """Test saving configuration when no schedule data exists."""
        mock_storage_service.load_schedules.return_value = None
        
        # Configure some presence settings
        presence_manager_with_storage._presence_entities = ["device_tracker.phone"]
        presence_manager_with_storage._presence_rule = "anyone_home"
        presence_manager_with_storage._timeout_seconds = 300
        
        await presence_manager_with_storage.save_configuration()
        
        # Should have created new schedule data and saved it
        mock_storage_service.save_schedules.assert_called_once()
        saved_data = mock_storage_service.save_schedules.call_args[0][0]
        
        assert saved_data.presence_config is not None
        assert saved_data.presence_config.entities == ["device_tracker.phone"]
        assert saved_data.presence_config.rule == "anyone_home"
        assert saved_data.presence_config.timeout_seconds == 300
    
    async def test_save_configuration_existing_schedule_data(self, presence_manager_with_storage, mock_storage_service):
        """Test saving configuration with existing schedule data."""
        from custom_components.roost_scheduler.models import ScheduleData
        
        # Mock existing schedule data
        existing_data = Mock(spec=ScheduleData)
        existing_data.presence_entities = []
        existing_data.presence_rule = "anyone_home"
        existing_data.presence_timeout_seconds = 600
        
        mock_storage_service.load_schedules.return_value = existing_data
        
        # Configure some presence settings
        presence_manager_with_storage._presence_entities = ["device_tracker.phone"]
        presence_manager_with_storage._presence_rule = "everyone_home"
        presence_manager_with_storage._timeout_seconds = 300
        
        await presence_manager_with_storage.save_configuration()
        
        # Should have updated existing data
        mock_storage_service.save_schedules.assert_called_once()
        assert existing_data.presence_config is not None
        assert existing_data.presence_config.entities == ["device_tracker.phone"]
        assert existing_data.presence_config.rule == "everyone_home"
        
        # Should also update legacy fields for backward compatibility
        assert existing_data.presence_entities == ["device_tracker.phone"]
        assert existing_data.presence_rule == "everyone_home"
        assert existing_data.presence_timeout_seconds == 300
    
    async def test_save_configuration_error_handling(self, presence_manager_with_storage, mock_storage_service):
        """Test error handling during configuration saving."""
        mock_storage_service.load_schedules.return_value = None
        mock_storage_service.save_schedules.side_effect = Exception("Save error")
        
        # Should not raise error, just log it
        await presence_manager_with_storage.save_configuration()
    
    async def test_update_presence_entities(self, presence_manager_with_storage, mock_storage_service):
        """Test updating presence entities with persistence."""
        mock_storage_service.load_schedules.return_value = None
        
        new_entities = ["device_tracker.phone1", "device_tracker.phone2"]
        
        await presence_manager_with_storage.update_presence_entities(new_entities)
        
        assert presence_manager_with_storage._presence_entities == new_entities
        mock_storage_service.save_schedules.assert_called_once()
    
    async def test_update_presence_entities_validation_error(self, presence_manager_with_storage, mock_storage_service):
        """Test updating presence entities with invalid data."""
        original_entities = ["device_tracker.original"]
        presence_manager_with_storage._presence_entities = original_entities
        
        invalid_entities = ["invalid_entity_id", "device_tracker.valid"]
        
        with pytest.raises(ValueError):
            await presence_manager_with_storage.update_presence_entities(invalid_entities)
        
        # Should revert to original entities on error
        assert presence_manager_with_storage._presence_entities == original_entities
    
    async def test_update_presence_rule(self, presence_manager_with_storage, mock_storage_service):
        """Test updating presence rule with persistence."""
        mock_storage_service.load_schedules.return_value = None
        
        await presence_manager_with_storage.update_presence_rule("everyone_home")
        
        assert presence_manager_with_storage._presence_rule == "everyone_home"
        mock_storage_service.save_schedules.assert_called_once()
    
    async def test_update_presence_rule_validation_error(self, presence_manager_with_storage, mock_storage_service):
        """Test updating presence rule with invalid value."""
        original_rule = "anyone_home"
        presence_manager_with_storage._presence_rule = original_rule
        
        with pytest.raises(ValueError):
            await presence_manager_with_storage.update_presence_rule("invalid_rule")
        
        # Should revert to original rule on error
        assert presence_manager_with_storage._presence_rule == original_rule
    
    def test_get_configuration_summary(self, presence_manager_with_storage, mock_storage_service):
        """Test getting configuration summary."""
        # Set up some configuration
        presence_manager_with_storage._presence_entities = ["device_tracker.phone"]
        presence_manager_with_storage._presence_rule = "anyone_home"
        presence_manager_with_storage._timeout_seconds = 300
        presence_manager_with_storage._initialized = True
        presence_manager_with_storage._presence_config = Mock()
        
        summary = presence_manager_with_storage.get_configuration_summary()
        
        assert summary["presence_entities"] == ["device_tracker.phone"]
        assert summary["presence_rule"] == "anyone_home"
        assert summary["timeout_seconds"] == 300
        assert summary["initialized"] is True
        assert summary["storage_service_available"] is True
        assert summary["presence_config_loaded"] is True
    
    def test_get_configuration_summary_no_storage(self, hass):
        """Test getting configuration summary without storage service."""
        manager = PresenceManager(hass, None)
        
        summary = manager.get_configuration_summary()
        
        assert summary["storage_service_available"] is False
        assert summary["presence_config_loaded"] is False
    
    async def test_configure_presence_saves_to_storage(self, presence_manager_with_storage, mock_storage_service):
        """Test that configure_presence saves configuration to storage."""
        mock_storage_service.load_schedules.return_value = None
        
        entities = ["device_tracker.phone"]
        rule = "anyone_home"
        timeout = 300
        
        await presence_manager_with_storage.configure_presence(entities, rule, timeout)
        
        # Should have saved configuration
        mock_storage_service.save_schedules.assert_called_once()
        
        assert presence_manager_with_storage._presence_entities == entities
        assert presence_manager_with_storage._presence_rule == rule
        assert presence_manager_with_storage._timeout_seconds == timeout
    
    async def test_async_initialize_loads_configuration(self, presence_manager_with_storage, mock_storage_service):
        """Test that async_initialize loads configuration from storage."""
        from custom_components.roost_scheduler.models import ScheduleData, PresenceConfig
        
        # Mock schedule data with presence config
        presence_config = PresenceConfig(
            entities=["device_tracker.phone"],
            rule="anyone_home",
            timeout_seconds=300
        )
        
        schedule_data = Mock(spec=ScheduleData)
        schedule_data.presence_config = presence_config
        
        mock_storage_service.load_schedules.return_value = schedule_data
        
        # Mock hass.states.get to return None (no entities exist)
        presence_manager_with_storage.hass.states.get.return_value = None
        
        with patch('custom_components.roost_scheduler.presence_manager.async_track_state_change_event'):
            await presence_manager_with_storage.async_initialize()
        
        assert presence_manager_with_storage._presence_entities == ["device_tracker.phone"]
        assert presence_manager_with_storage._presence_rule == "anyone_home"
        assert presence_manager_with_storage._timeout_seconds == 300
        assert presence_manager_with_storage._initialized is True


class TestPresenceConfigModel:
    """Test PresenceConfig data model."""
    
    def test_presence_config_creation(self):
        """Test creating PresenceConfig with default values."""
        from custom_components.roost_scheduler.models import PresenceConfig
        
        config = PresenceConfig()
        
        assert config.entities == []
        assert config.rule == "anyone_home"
        assert config.timeout_seconds == 600
        assert config.override_entities == {
            "force_home": "input_boolean.roost_force_home",
            "force_away": "input_boolean.roost_force_away"
        }
        assert config.custom_template is None
        assert config.template_entities == []
    
    def test_presence_config_validation_valid(self):
        """Test PresenceConfig validation with valid data."""
        from custom_components.roost_scheduler.models import PresenceConfig
        
        config = PresenceConfig(
            entities=["device_tracker.phone", "person.user"],
            rule="everyone_home",
            timeout_seconds=300,
            override_entities={
                "force_home": "input_boolean.custom_home",
                "force_away": "input_boolean.custom_away"
            },
            custom_template="{{ is_state('device_tracker.phone', 'home') }}",
            template_entities=["device_tracker.phone"]
        )
        
        # Should not raise any validation errors
        config.validate()
    
    def test_presence_config_validation_invalid_entities(self):
        """Test PresenceConfig validation with invalid entities."""
        from custom_components.roost_scheduler.models import PresenceConfig
        
        with pytest.raises(ValueError, match="entity_id must be in format 'domain.entity'"):
            PresenceConfig(entities=["invalid_entity"])
    
    def test_presence_config_validation_invalid_rule(self):
        """Test PresenceConfig validation with invalid rule."""
        from custom_components.roost_scheduler.models import PresenceConfig
        
        with pytest.raises(ValueError, match="rule must be one of"):
            PresenceConfig(rule="invalid_rule")
    
    def test_presence_config_validation_invalid_timeout(self):
        """Test PresenceConfig validation with invalid timeout."""
        from custom_components.roost_scheduler.models import PresenceConfig
        
        with pytest.raises(ValueError, match="timeout_seconds must be a non-negative integer"):
            PresenceConfig(timeout_seconds=-1)
        
        with pytest.raises(ValueError, match="timeout_seconds cannot exceed 86400"):
            PresenceConfig(timeout_seconds=90000)
    
    def test_presence_config_to_dict(self):
        """Test PresenceConfig serialization to dictionary."""
        from custom_components.roost_scheduler.models import PresenceConfig
        
        config = PresenceConfig(
            entities=["device_tracker.phone"],
            rule="anyone_home",
            timeout_seconds=300
        )
        
        data = config.to_dict()
        
        assert data["entities"] == ["device_tracker.phone"]
        assert data["rule"] == "anyone_home"
        assert data["timeout_seconds"] == 300
        assert "override_entities" in data
        assert "custom_template" in data
        assert "template_entities" in data
    
    def test_presence_config_from_dict(self):
        """Test PresenceConfig deserialization from dictionary."""
        from custom_components.roost_scheduler.models import PresenceConfig
        
        data = {
            "entities": ["device_tracker.phone"],
            "rule": "everyone_home",
            "timeout_seconds": 300,
            "custom_template": "{{ is_state('device_tracker.phone', 'home') }}",
            "template_entities": ["device_tracker.phone"]
        }
        
        config = PresenceConfig.from_dict(data)
        
        assert config.entities == ["device_tracker.phone"]
        assert config.rule == "everyone_home"
        assert config.timeout_seconds == 300
        assert config.custom_template == "{{ is_state('device_tracker.phone', 'home') }}"
        assert config.template_entities == ["device_tracker.phone"]
    
    def test_presence_config_from_dict_defaults(self):
        """Test PresenceConfig deserialization with missing fields uses defaults."""
        from custom_components.roost_scheduler.models import PresenceConfig
        
        data = {}
        
        config = PresenceConfig.from_dict(data)
        
        assert config.entities == []
        assert config.rule == "anyone_home"
        assert config.timeout_seconds == 600
        assert config.custom_template is None
        assert config.template_entities == []