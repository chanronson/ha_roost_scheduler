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
    assert result3["data"] == {
        "entities": ["climate.living_room"],
        "presence_entities": [],
        "presence_rule": "anyone_home",
        "add_card": True
    }


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