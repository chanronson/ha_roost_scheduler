"""Config flow for Roost Scheduler integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, NAME

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
                self._entities = entities
                return await self.async_step_presence()

        # Get available climate entities
        climate_entities = []
        for entity_id in self.hass.states.async_entity_ids("climate"):
            state = self.hass.states.get(entity_id)
            if state:
                climate_entities.append({
                    "value": entity_id,
                    "label": f"{state.attributes.get('friendly_name', entity_id)} ({entity_id})"
                })

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
        if user_input is not None:
            self._presence_entities = user_input.get("presence_entities", [])
            return await self.async_step_card()

        # Get available presence entities
        presence_entities = []
        
        # Device trackers
        for entity_id in self.hass.states.async_entity_ids("device_tracker"):
            state = self.hass.states.get(entity_id)
            if state:
                presence_entities.append({
                    "value": entity_id,
                    "label": f"{state.attributes.get('friendly_name', entity_id)} ({entity_id})"
                })

        # Person entities
        for entity_id in self.hass.states.async_entity_ids("person"):
            state = self.hass.states.get(entity_id)
            if state:
                presence_entities.append({
                    "value": entity_id,
                    "label": f"{state.attributes.get('friendly_name', entity_id)} ({entity_id})"
                })

        # Binary sensors that might be presence-related
        for entity_id in self.hass.states.async_entity_ids("binary_sensor"):
            if any(keyword in entity_id.lower() for keyword in ["presence", "occupancy", "motion"]):
                state = self.hass.states.get(entity_id)
                if state:
                    presence_entities.append({
                        "value": entity_id,
                        "label": f"{state.attributes.get('friendly_name', entity_id)} ({entity_id})"
                    })

        data_schema = vol.Schema({
            vol.Optional("presence_entities", default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=presence_entities,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Optional("presence_rule", default="anyone_home"): selector.SelectSelector(
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
                    "presence_rule": user_input.get("presence_rule", "anyone_home"),
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