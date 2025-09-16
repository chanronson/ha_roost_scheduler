"""Config flow for Roost Scheduler integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from .const import DOMAIN, NAME, DEFAULT_PRESENCE_RULE

_LOGGER = logging.getLogger(__name__)


class RoostSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roost Scheduler."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._entities: list[str] = []
        self._presence_entities: list[str] = []
        self._add_card = False

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate that at least one entity is selected
            entities = user_input.get("entities", [])
            if not entities:
                errors["entities"] = "at_least_one_entity"
            else:
                # Validate selected entities
                validation_errors = await self._validate_climate_entities(entities)
                if validation_errors:
                    errors.update(validation_errors)
                else:
                    self._entities = entities
                    return await self.async_step_presence()

        # Get available climate entities
        climate_entities = await self._get_climate_entities()

        if not climate_entities:
            return self.async_abort(reason="no_climate_entities")

        data_schema = vol.Schema({
            vol.Required("entities"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=climate_entities,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"name": NAME}
        )

    async def async_step_presence(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle presence configuration step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            presence_entities = user_input.get("presence_entities", [])
            presence_rule = user_input.get("presence_rule", DEFAULT_PRESENCE_RULE)
            
            # Validate presence entities if any are selected
            if presence_entities:
                validation_errors = await self._validate_presence_entities(presence_entities)
                if validation_errors:
                    errors.update(validation_errors)
                else:
                    self._presence_entities = presence_entities
                    self._presence_rule = presence_rule
                    return await self.async_step_card()
            else:
                self._presence_entities = []
                self._presence_rule = presence_rule
                return await self.async_step_card()

        # Get available presence entities
        presence_entities = await self._get_presence_entities()

        data_schema = vol.Schema({
            vol.Optional("presence_entities", default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=presence_entities,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("presence_rule", default=DEFAULT_PRESENCE_RULE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "anyone_home", "label": "Anyone Home"},
                        {"value": "everyone_home", "label": "Everyone Home"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        })

        return self.async_show_form(
            step_id="presence",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"name": NAME}
        )

    async def async_step_card(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle Lovelace card installation step."""
        if user_input is not None:
            self._add_card = user_input.get("add_card", False)
            
            # Create the config entry
            return self.async_create_entry(
                title=NAME,
                data={
                    "entities": self._entities,
                    "presence_entities": self._presence_entities,
                    "presence_rule": getattr(self, '_presence_rule', DEFAULT_PRESENCE_RULE),
                    "add_card": self._add_card
                }
            )

        data_schema = vol.Schema({
            vol.Optional("add_card", default=True): selector.BooleanSelector(),
        })

        return self.async_show_form(
            step_id="card",
            data_schema=data_schema,
            description_placeholders={"name": NAME}
        )

    async def async_step_import(self, import_data: Dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def _get_climate_entities(self) -> list[dict[str, str]]:
        """Get available climate entities with validation."""
        climate_entities = []
        
        for entity_id in self.hass.states.async_entity_ids("climate"):
            state = self.hass.states.get(entity_id)
            if state and self._is_climate_entity_supported(state):
                friendly_name = state.attributes.get('friendly_name', entity_id)
                climate_entities.append({
                    "value": entity_id,
                    "label": f"{friendly_name} ({entity_id})"
                })
        
        return sorted(climate_entities, key=lambda x: x["label"])

    async def _get_presence_entities(self) -> list[dict[str, str]]:
        """Get available presence entities."""
        presence_entities = []
        
        # Device trackers
        for entity_id in self.hass.states.async_entity_ids("device_tracker"):
            state = self.hass.states.get(entity_id)
            if state:
                friendly_name = state.attributes.get('friendly_name', entity_id)
                presence_entities.append({
                    "value": entity_id,
                    "label": f"{friendly_name} ({entity_id})"
                })

        # Person entities
        for entity_id in self.hass.states.async_entity_ids("person"):
            state = self.hass.states.get(entity_id)
            if state:
                friendly_name = state.attributes.get('friendly_name', entity_id)
                presence_entities.append({
                    "value": entity_id,
                    "label": f"{friendly_name} ({entity_id})"
                })

        # Binary sensors that might be presence-related
        for entity_id in self.hass.states.async_entity_ids("binary_sensor"):
            if any(keyword in entity_id.lower() for keyword in ["presence", "occupancy", "motion"]):
                state = self.hass.states.get(entity_id)
                if state:
                    friendly_name = state.attributes.get('friendly_name', entity_id)
                    presence_entities.append({
                        "value": entity_id,
                        "label": f"{friendly_name} ({entity_id})"
                    })

        # Input boolean helpers
        for entity_id in self.hass.states.async_entity_ids("input_boolean"):
            if any(keyword in entity_id.lower() for keyword in ["home", "away", "presence", "vacation"]):
                state = self.hass.states.get(entity_id)
                if state:
                    friendly_name = state.attributes.get('friendly_name', entity_id)
                    presence_entities.append({
                        "value": entity_id,
                        "label": f"{friendly_name} ({entity_id})"
                    })
        
        return sorted(presence_entities, key=lambda x: x["label"])

    def _is_climate_entity_supported(self, state) -> bool:
        """Check if a climate entity supports the required features."""
        # Check if entity supports temperature setting
        supported_features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        
        # Climate entities should support temperature setting (feature flag 1)
        # This is a basic check - we could add more sophisticated validation
        return (
            state.domain == "climate" and
            state.state not in ["unavailable", "unknown"] and
            "temperature" in state.attributes
        )

    async def _validate_climate_entities(self, entities: list[str]) -> dict[str, str]:
        """Validate selected climate entities."""
        errors = {}
        
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            if not state:
                errors["entities"] = "entity_not_found"
                break
            elif not self._is_climate_entity_supported(state):
                errors["entities"] = "unsupported_climate_entity"
                break
        
        return errors

    async def _validate_presence_entities(self, entities: list[str]) -> dict[str, str]:
        """Validate selected presence entities."""
        errors = {}
        
        for entity_id in entities:
            state = self.hass.states.get(entity_id)
            if not state:
                errors["presence_entities"] = "entity_not_found"
                break
            elif state.domain not in ["device_tracker", "person", "binary_sensor", "input_boolean"]:
                errors["presence_entities"] = "unsupported_presence_entity"
                break
        
        return errors