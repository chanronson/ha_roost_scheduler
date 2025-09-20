"""Test the Roost Scheduler config flow."""
from unittest.mock import patch, MagicMock
import pytest
import pytest_asyncio

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from custom_components.roost_scheduler.const import DOMAIN, NAME
from custom_components.roost_scheduler.config_flow import RoostSchedulerConfigFlow

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.config = MagicMock()
    hass.config.config_dir = "/config"
    hass.states = MagicMock()
    return hass


@pytest.fixture
def config_flow(mock_hass):
    """Create a config flow instance."""
    flow = RoostSchedulerConfigFlow()
    flow.hass = mock_hass
    return flow


@pytest.fixture
def mock_climate_entity():
    """Mock a climate entity state."""
    state = MagicMock()
    state.domain = "climate"
    state.entity_id = "climate.living_room"
    state.state = "heat"
    state.attributes = {
        "friendly_name": "Living Room Thermostat",
        "temperature": 20.0,
        ATTR_SUPPORTED_FEATURES: 1
    }
    return state


@pytest.fixture
def mock_presence_entity():
    """Mock a presence entity state."""
    state = MagicMock()
    state.domain = "device_tracker"
    state.entity_id = "device_tracker.phone"
    state.state = "home"
    state.attributes = {
        "friendly_name": "Phone"
    }
    return state


async def test_form_user_step(config_flow, mock_climate_entity):
    """Test the user step of the config flow."""
    config_flow.hass.states.async_entity_ids.return_value = ["climate.living_room"]
    config_flow.hass.states.get.return_value = mock_climate_entity
    
    result = await config_flow.async_step_user()
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_form_user_step_no_entities(config_flow):
    """Test the user step with no climate entities."""
    config_flow.hass.states.async_entity_ids.return_value = []
    
    result = await config_flow.async_step_user()
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_climate_entities"


async def test_form_user_step_validation_error(config_flow, mock_climate_entity):
    """Test the user step with validation errors."""
    config_flow.hass.states.async_entity_ids.return_value = ["climate.living_room"]
    config_flow.hass.states.get.return_value = mock_climate_entity
    
    # Submit form with no entities selected
    result = await config_flow.async_step_user({"entities": []})
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"entities": "at_least_one_entity"}


async def test_form_presence_step(config_flow, mock_presence_entity):
    """Test the presence step of the config flow."""
    # Setup mocks for different entity types
    def entity_ids_side_effect(domain):
        if domain == "device_tracker":
            return ["device_tracker.phone"]
        elif domain == "person":
            return []
        elif domain == "binary_sensor":
            return []
        elif domain == "input_boolean":
            return []
        return []
    
    def get_side_effect(entity_id):
        if entity_id == "device_tracker.phone":
            return mock_presence_entity
        return None
    
    config_flow.hass.states.async_entity_ids.side_effect = entity_ids_side_effect
    config_flow.hass.states.get.side_effect = get_side_effect
    
    result = await config_flow.async_step_presence()
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "presence"
    assert result["errors"] == {}


async def test_form_card_step(config_flow):
    """Test the card step of the config flow."""
    result = await config_flow.async_step_card()
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "card"


async def test_complete_flow(config_flow, mock_climate_entity):
    """Test completing the entire config flow."""
    config_flow.hass.states.async_entity_ids.return_value = ["climate.living_room"]
    config_flow.hass.states.get.return_value = mock_climate_entity
    
    # Mock dashboard discovery to avoid Store issues
    with patch.object(config_flow, '_get_dashboards') as mock_get_dashboards:
        mock_get_dashboards.return_value = []
        
        # Complete user step
        result = await config_flow.async_step_user({"entities": ["climate.living_room"]})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "presence"
        
        # Complete presence step
        result2 = await config_flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result2["step_id"] == "card"
        
        # Complete card step
        result3 = await config_flow.async_step_card({"add_card": True})
        
        assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result3["title"] == NAME
        expected_data = {
            "entities": ["climate.living_room"],
            "presence_entities": [],
            "presence_rule": "anyone_home",
            "add_card": True,
            "dashboard": None,
            "view": None
        }
        assert result3["data"] == expected_data


async def test_unsupported_climate_entity(config_flow, mock_climate_entity):
    """Test validation of unsupported climate entity."""
    unsupported_entity = MagicMock()
    unsupported_entity.domain = "climate"
    unsupported_entity.entity_id = "climate.broken"
    unsupported_entity.state = "unavailable"
    unsupported_entity.attributes = {}
    
    # Return both supported and unsupported entities for discovery
    config_flow.hass.states.async_entity_ids.return_value = ["climate.living_room", "climate.broken"]
    
    def get_side_effect(entity_id):
        if entity_id == "climate.living_room":
            return mock_climate_entity
        elif entity_id == "climate.broken":
            return unsupported_entity
        return None
    
    config_flow.hass.states.get.side_effect = get_side_effect
    
    # First call to show the form - should work because we have at least one supported entity
    result = await config_flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    
    # Submit form with unsupported entity
    result2 = await config_flow.async_step_user({"entities": ["climate.broken"]})
    
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"entities": "unsupported_climate_entity"}


async def test_dashboard_discovery(config_flow):
    """Test dashboard discovery functionality."""
    # Mock the Store class
    with patch('custom_components.roost_scheduler.config_flow.Store') as mock_store_class:
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store
        
        # Mock dashboard data - make async_load return a coroutine
        async def mock_async_load():
            return {
                "dashboards": {
                    "custom_dashboard": {
                        "title": "Custom Dashboard"
                    },
                    "another_dashboard": {
                        "title": "Another Dashboard"
                    }
                }
            }
        
        mock_store.async_load = mock_async_load
        
        dashboards = await config_flow._get_dashboards()
        
        assert len(dashboards) == 3  # Default + 2 custom
        assert dashboards[0]["value"] == "lovelace"
        assert dashboards[0]["label"] == "Default Dashboard (Lovelace)"
        assert dashboards[1]["value"] == "custom_dashboard"
        assert dashboards[1]["label"] == "Custom Dashboard (custom_dashboard)"


async def test_card_installation(config_flow, mock_climate_entity):
    """Test Lovelace card installation."""
    config_flow._entities = ["climate.living_room"]
    config_flow._selected_dashboard = "lovelace"
    config_flow._selected_view = "default"
    
    # Mock the Store class
    with patch('custom_components.roost_scheduler.config_flow.Store') as mock_store_class:
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store
        
        # Mock existing dashboard config - make async methods return coroutines
        async def mock_async_load():
            return {
                "views": [
                    {
                        "title": "Home",
                        "path": "default",
                        "cards": []
                    }
                ]
            }
        
        async def mock_async_save(config):
            pass
        
        mock_store.async_load = mock_async_load
        mock_store.async_save = mock_async_save
        
        await config_flow._install_lovelace_card()
        
        # Verify store was called correctly
        mock_store_class.assert_called_with(config_flow.hass, 1, "lovelace")


async def test_card_installation_new_dashboard(config_flow, mock_climate_entity):
    """Test card installation on empty dashboard."""
    config_flow._entities = ["climate.living_room"]
    config_flow._selected_dashboard = "lovelace"
    config_flow._selected_view = "default"
    
    # Mock the Store class
    with patch('custom_components.roost_scheduler.config_flow.Store') as mock_store_class:
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store
        
        # Mock empty dashboard config - make async methods return coroutines
        async def mock_async_load():
            return {}
        
        saved_configs = []
        
        async def mock_async_save(config):
            saved_configs.append(config)
        
        mock_store.async_load = mock_async_load
        mock_store.async_save = mock_async_save
        
        await config_flow._install_lovelace_card()
        
        # Verify the default view was created
        assert len(saved_configs) == 1
        saved_config = saved_configs[0]
        assert "views" in saved_config
        assert len(saved_config["views"]) == 1
        assert saved_config["views"][0]["title"] == "Home"
        assert saved_config["views"][0]["path"] == "default"
        assert len(saved_config["views"][0]["cards"]) == 1


async def test_complete_flow_with_card_installation(config_flow, mock_climate_entity):
    """Test completing the entire config flow with card installation."""
    config_flow.hass.states.async_entity_ids.return_value = ["climate.living_room"]
    config_flow.hass.states.get.return_value = mock_climate_entity
    
    # Mock dashboard discovery
    with patch.object(config_flow, '_get_dashboards') as mock_get_dashboards, \
         patch.object(config_flow, '_install_lovelace_card') as mock_install_card:
        
        mock_get_dashboards.return_value = [
            {"value": "lovelace", "label": "Default Dashboard (Lovelace)"}
        ]
        
        # Complete user step
        result = await config_flow.async_step_user({"entities": ["climate.living_room"]})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "presence"
        
        # Complete presence step
        result2 = await config_flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result2["step_id"] == "card"
        
        # Complete card step with installation
        result3 = await config_flow.async_step_card({
            "add_card": True,
            "dashboard": "lovelace",
            "view": "default"
        })
        
        assert result3["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result3["title"] == NAME
        assert result3["data"]["add_card"] is True
        assert result3["data"]["dashboard"] == "lovelace"
        assert result3["data"]["view"] == "default"
        
        # Verify card installation was attempted
        mock_install_card.assert_called_once()

# Enhanced Config Flow Tests for Manager Integration

async def test_buffer_configuration_step(config_flow):
    """Test the buffer configuration step."""
    result = await config_flow.async_step_buffer()
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "buffer"
    assert result["errors"] == {}


async def test_buffer_configuration_validation(config_flow):
    """Test buffer configuration validation."""
    # Test invalid time range
    result = await config_flow.async_step_buffer({
        "buffer_enabled": True,
        "buffer_time_minutes": -1,  # Invalid
        "buffer_value_delta": 2.0
    })
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"buffer_time_minutes": "invalid_time_range"}
    
    # Test invalid delta range
    result2 = await config_flow.async_step_buffer({
        "buffer_enabled": True,
        "buffer_time_minutes": 15,
        "buffer_value_delta": 15.0  # Invalid (too high)
    })
    
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"buffer_value_delta": "invalid_delta_range"}


async def test_buffer_configuration_success(config_flow):
    """Test successful buffer configuration."""
    result = await config_flow.async_step_buffer({
        "buffer_enabled": True,
        "buffer_time_minutes": 30,
        "buffer_value_delta": 1.5
    })
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "card"
    assert config_flow._buffer_enabled is True
    assert config_flow._buffer_time_minutes == 30
    assert config_flow._buffer_value_delta == 1.5


async def test_complete_enhanced_flow(config_flow, mock_climate_entity, mock_presence_entity):
    """Test completing the entire enhanced config flow with buffer configuration."""
    config_flow.hass.states.async_entity_ids.return_value = ["climate.living_room"]
    
    # Mock entity states for both climate and presence entities
    def get_side_effect(entity_id):
        if entity_id == "climate.living_room":
            return mock_climate_entity
        elif entity_id == "device_tracker.phone":
            return mock_presence_entity
        return None
    
    config_flow.hass.states.get.side_effect = get_side_effect
    
    # Mock manager validation to avoid actual storage operations
    with patch.object(config_flow, '_validate_manager_initialization') as mock_validate:
        mock_validate.return_value = None  # Success
        
        # Mock dashboard discovery
        with patch.object(config_flow, '_get_dashboards') as mock_get_dashboards:
            mock_get_dashboards.return_value = []
            
            # Complete user step
            result = await config_flow.async_step_user({"entities": ["climate.living_room"]})
            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "presence"
            
            # Complete presence step
            result2 = await config_flow.async_step_presence({
                "presence_entities": ["device_tracker.phone"],
                "presence_rule": "anyone_home"
            })
            assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result2["step_id"] == "buffer"
            
            # Complete buffer step
            result3 = await config_flow.async_step_buffer({
                "buffer_enabled": True,
                "buffer_time_minutes": 20,
                "buffer_value_delta": 1.0
            })
            assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result3["step_id"] == "card"
            
            # Complete card step
            result4 = await config_flow.async_step_card({"add_card": False})
            
            assert result4["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result4["title"] == NAME
            expected_data = {
                "entities": ["climate.living_room"],
                "presence_entities": ["device_tracker.phone"],
                "presence_rule": "anyone_home",
                "buffer_enabled": True,
                "buffer_time_minutes": 20,
                "buffer_value_delta": 1.0,
                "add_card": False,
                "dashboard": None,
                "view": None
            }
            assert result4["data"] == expected_data
            
            # Verify manager validation was called
            mock_validate.assert_called_once()


async def test_manager_validation_success(config_flow):
    """Test successful manager validation during config flow."""
    config_data = {
        "entities": ["climate.living_room"],
        "presence_entities": ["device_tracker.phone"],
        "presence_rule": "anyone_home",
        "buffer_enabled": True,
        "buffer_time_minutes": 15,
        "buffer_value_delta": 2.0
    }
    
    # Mock the managers and storage service
    with patch('custom_components.roost_scheduler.config_flow.StorageService') as mock_storage_class, \
         patch('custom_components.roost_scheduler.config_flow.PresenceManager') as mock_presence_class, \
         patch('custom_components.roost_scheduler.config_flow.BufferManager') as mock_buffer_class:
        
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        
        mock_presence = MagicMock()
        mock_presence_class.return_value = mock_presence
        
        # Mock async methods to return coroutines
        async def mock_load_config():
            return None
        
        async def mock_update_entities(entities):
            return None
            
        async def mock_update_rule(rule):
            return None
        
        mock_presence.load_configuration = mock_load_config
        mock_presence.update_presence_entities = mock_update_entities
        mock_presence.update_presence_rule = mock_update_rule
        
        mock_buffer = MagicMock()
        mock_buffer_class.return_value = mock_buffer
        mock_buffer.load_configuration = mock_load_config
        
        # Should not raise any exceptions
        await config_flow._validate_manager_initialization(config_data)
        
        # Verify managers were initialized correctly
        mock_storage_class.assert_called_once_with(config_flow.hass, "config_flow_validation")
        mock_presence_class.assert_called_once_with(config_flow.hass, mock_storage)
        mock_buffer_class.assert_called_once_with(config_flow.hass, mock_storage)


async def test_manager_validation_failure(config_flow):
    """Test manager validation failure during config flow."""
    config_data = {
        "entities": ["climate.living_room"],
        "presence_entities": ["device_tracker.phone"],
        "presence_rule": "anyone_home",
        "buffer_enabled": True,
        "buffer_time_minutes": 15,
        "buffer_value_delta": 2.0
    }
    
    # Mock the managers to raise an exception
    with patch('custom_components.roost_scheduler.config_flow.StorageService') as mock_storage_class, \
         patch('custom_components.roost_scheduler.config_flow.PresenceManager') as mock_presence_class:
        
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        
        # Make presence manager initialization fail
        mock_presence_class.side_effect = Exception("Manager initialization failed")
        
        # Should raise the exception
        with pytest.raises(Exception, match="Manager initialization failed"):
            await config_flow._validate_manager_initialization(config_data)


async def test_config_flow_with_validation_failure(config_flow, mock_climate_entity):
    """Test config flow continues even when manager validation fails."""
    config_flow.hass.states.async_entity_ids.return_value = ["climate.living_room"]
    config_flow.hass.states.get.return_value = mock_climate_entity
    
    # Mock manager validation to fail
    with patch.object(config_flow, '_validate_manager_initialization') as mock_validate:
        mock_validate.side_effect = Exception("Validation failed")
        
        # Mock dashboard discovery
        with patch.object(config_flow, '_get_dashboards') as mock_get_dashboards:
            mock_get_dashboards.return_value = []
            
            # Complete the flow
            result1 = await config_flow.async_step_user({"entities": ["climate.living_room"]})
            result2 = await config_flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
            result3 = await config_flow.async_step_buffer({"buffer_enabled": True, "buffer_time_minutes": 15, "buffer_value_delta": 2.0})
            result4 = await config_flow.async_step_card({"add_card": False})
            
            # Should still create the entry despite validation failure
            assert result4["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result4["title"] == NAME
            
            # Verify validation was attempted
            mock_validate.assert_called_once()


async def test_presence_entities_validation_in_config_flow(config_flow):
    """Test presence entities validation in config flow."""
    # Mock entity states
    def get_side_effect(entity_id):
        if entity_id == "device_tracker.phone":
            state = MagicMock()
            state.domain = "device_tracker"
            return state
        elif entity_id == "invalid.entity":
            return None  # Entity not found
        return None
    
    config_flow.hass.states.get.side_effect = get_side_effect
    
    # Test with invalid entity
    result = await config_flow.async_step_presence({
        "presence_entities": ["invalid.entity"],
        "presence_rule": "anyone_home"
    })
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"presence_entities": "entity_not_found"}


async def test_buffer_settings_validation_edge_cases(config_flow):
    """Test buffer settings validation with edge cases."""
    # Test maximum valid values
    result1 = await config_flow.async_step_buffer({
        "buffer_enabled": True,
        "buffer_time_minutes": 1440,  # 24 hours - maximum
        "buffer_value_delta": 10.0    # Maximum
    })
    
    assert result1["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result1["step_id"] == "card"
    assert result1.get("errors") is None or result1.get("errors") == {}
    
    # Test minimum valid values
    result2 = await config_flow.async_step_buffer({
        "buffer_enabled": False,
        "buffer_time_minutes": 0,     # Minimum
        "buffer_value_delta": 0.1     # Minimum
    })
    
    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "card"
    assert result2.get("errors") is None or result2.get("errors") == {}
    
    # Test values just outside valid range
    result3 = await config_flow.async_step_buffer({
        "buffer_enabled": True,
        "buffer_time_minutes": 1441,  # Just over maximum
        "buffer_value_delta": 2.0
    })
    
    assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result3["errors"] == {"buffer_time_minutes": "invalid_time_range"}
    
    result4 = await config_flow.async_step_buffer({
        "buffer_enabled": True,
        "buffer_time_minutes": 15,
        "buffer_value_delta": 0.05    # Just under minimum
    })
    
    assert result4["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result4["errors"] == {"buffer_value_delta": "invalid_delta_range"}


async def test_config_flow_preserves_existing_installations(config_flow, mock_climate_entity):
    """Test that config flow works with existing installations."""
    config_flow.hass.states.async_entity_ids.return_value = ["climate.living_room"]
    config_flow.hass.states.get.return_value = mock_climate_entity
    
    # Mock existing storage data
    with patch('custom_components.roost_scheduler.config_flow.StorageService') as mock_storage_class:
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        
        # Mock existing schedule data
        async def mock_load_schedules():
            from custom_components.roost_scheduler.models import ScheduleData, PresenceConfig, GlobalBufferConfig
            return ScheduleData(
                version="0.3.0",
                entities_tracked=["climate.existing"],
                presence_entities=["device_tracker.existing"],
                presence_rule="everyone_home",
                presence_timeout_seconds=300,
                buffer={},
                ui={},
                schedules={"home": {}, "away": {}},
                metadata={},
                presence_config=PresenceConfig(
                    entities=["device_tracker.existing"],
                    rule="everyone_home"
                ),
                buffer_config=GlobalBufferConfig(
                    time_minutes=10,
                    value_delta=1.0
                )
            )
        
        mock_storage.load_schedules = mock_load_schedules
        
        # Mock manager validation to succeed
        with patch.object(config_flow, '_validate_manager_initialization') as mock_validate, \
             patch.object(config_flow, '_get_dashboards') as mock_get_dashboards:
            
            mock_validate.return_value = None
            mock_get_dashboards.return_value = []
            
            # Complete the flow
            result1 = await config_flow.async_step_user({"entities": ["climate.living_room"]})
            result2 = await config_flow.async_step_presence({"presence_entities": ["device_tracker.new"], "presence_rule": "anyone_home"})
            result3 = await config_flow.async_step_buffer({"buffer_enabled": True, "buffer_time_minutes": 20, "buffer_value_delta": 2.5})
            result4 = await config_flow.async_step_card({"add_card": False})
            
            # Should create entry with new configuration
            assert result4["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result4["data"]["entities"] == ["climate.living_room"]
            assert result4["data"]["presence_entities"] == ["device_tracker.new"]
            assert result4["data"]["buffer_time_minutes"] == 20
            assert result4["data"]["buffer_value_delta"] == 2.5