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
from homeassistant.components import frontend
from homeassistant.helpers.storage import Store

from .const import DOMAIN, NAME, DEFAULT_PRESENCE_RULE, DEFAULT_BUFFER_TIME_MINUTES, DEFAULT_BUFFER_VALUE_DELTA
from .storage import StorageService
from .models import PresenceConfig, GlobalBufferConfig, ScheduleData
from .presence_manager import PresenceManager
from .buffer_manager import BufferManager

_LOGGER = logging.getLogger(__name__)


class RoostSchedulerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roost Scheduler."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._entities: list[str] = []
        self._presence_entities: list[str] = []
        self._presence_rule: str = DEFAULT_PRESENCE_RULE
        self._add_card = False
        self._selected_dashboard: str | None = None
        self._selected_view: str | None = None
        self._buffer_time_minutes: int = DEFAULT_BUFFER_TIME_MINUTES
        self._buffer_value_delta: float = DEFAULT_BUFFER_VALUE_DELTA
        self._buffer_enabled: bool = True

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
                    return await self.async_step_buffer()
            else:
                self._presence_entities = []
                self._presence_rule = presence_rule
                return await self.async_step_buffer()

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

    async def async_step_buffer(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle buffer configuration step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            buffer_enabled = user_input.get("buffer_enabled", True)
            buffer_time_minutes = user_input.get("buffer_time_minutes", DEFAULT_BUFFER_TIME_MINUTES)
            buffer_value_delta = user_input.get("buffer_value_delta", DEFAULT_BUFFER_VALUE_DELTA)
            
            # Convert float to int if it's a whole number (Home Assistant NumberSelector can return floats)
            if isinstance(buffer_time_minutes, float) and buffer_time_minutes.is_integer():
                buffer_time_minutes = int(buffer_time_minutes)
            
            # Validate buffer settings
            validation_errors = await self._validate_buffer_settings(
                buffer_enabled, buffer_time_minutes, buffer_value_delta
            )
            if validation_errors:
                errors.update(validation_errors)
            else:
                self._buffer_enabled = buffer_enabled
                self._buffer_time_minutes = buffer_time_minutes
                self._buffer_value_delta = buffer_value_delta
                return await self.async_step_card()

        data_schema = vol.Schema({
            vol.Optional("buffer_enabled", default=True): selector.BooleanSelector(),
            vol.Optional("buffer_time_minutes", default=DEFAULT_BUFFER_TIME_MINUTES): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=1440,  # 24 hours
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="minutes"
                )
            ),
            vol.Optional("buffer_value_delta", default=DEFAULT_BUFFER_VALUE_DELTA): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=10.0,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="°C"
                )
            )
        })

        return self.async_show_form(
            step_id="buffer",
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
            
            if self._add_card:
                # Get dashboard selection
                self._selected_dashboard = user_input.get("dashboard")
                self._selected_view = user_input.get("view")
                
                if self._selected_dashboard and self._selected_view:
                    # Install the card
                    try:
                        await self._install_lovelace_card()
                    except Exception as err:
                        _LOGGER.error("Failed to install Lovelace card: %s", err)
                        # Continue anyway - card installation is optional
            
            # Create the config entry with enhanced configuration
            config_data = {
                "entities": self._entities,
                "presence_entities": self._presence_entities,
                "presence_rule": getattr(self, '_presence_rule', DEFAULT_PRESENCE_RULE),
                "buffer_enabled": getattr(self, '_buffer_enabled', True),
                "buffer_time_minutes": getattr(self, '_buffer_time_minutes', DEFAULT_BUFFER_TIME_MINUTES),
                "buffer_value_delta": getattr(self, '_buffer_value_delta', DEFAULT_BUFFER_VALUE_DELTA),
                "add_card": self._add_card,
                "dashboard": self._selected_dashboard,
                "view": self._selected_view
            }
            
            # Try to validate manager initialization with the configuration
            try:
                await self._validate_manager_initialization(config_data)
            except Exception as err:
                _LOGGER.error("Failed to validate manager initialization: %s", err)
                # Continue anyway - this validation is optional and managers will be initialized during integration setup
            
            return self.async_create_entry(title=NAME, data=config_data)

        # Get available dashboards and views
        dashboards = await self._get_dashboards()
        
        data_schema_fields = {
            vol.Optional("add_card", default=True): selector.BooleanSelector(),
        }
        
        # Only show dashboard/view selection if we have dashboards and user wants to add card
        if dashboards:
            data_schema_fields[vol.Optional("dashboard")] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=dashboards,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
            
            # For now, we'll use the default view. In a full implementation,
            # we'd dynamically load views based on selected dashboard
            data_schema_fields[vol.Optional("view", default="default")] = selector.TextSelector()

        data_schema = vol.Schema(data_schema_fields)

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

    async def _validate_buffer_settings(self, enabled: bool, time_minutes: int, value_delta: float) -> dict[str, str]:
        """Validate buffer configuration settings."""
        errors = {}
        
        if not isinstance(enabled, bool):
            errors["buffer_enabled"] = "invalid_boolean"
        
        # Convert float to int if it's a whole number (Home Assistant NumberSelector can return floats)
        if isinstance(time_minutes, float) and time_minutes.is_integer():
            time_minutes = int(time_minutes)
        
        if not isinstance(time_minutes, (int, float)) or time_minutes < 0 or time_minutes > 1440:
            errors["buffer_time_minutes"] = "invalid_time_range"
        
        # Also validate that it's a whole number
        if isinstance(time_minutes, float) and not time_minutes.is_integer():
            errors["buffer_time_minutes"] = "invalid_time_range"
        
        if not isinstance(value_delta, (int, float)) or value_delta < 0.1 or value_delta > 10.0:
            errors["buffer_value_delta"] = "invalid_delta_range"
        
        return errors

    async def _validate_manager_initialization(self, config_data: Dict[str, Any]) -> None:
        """Validate that managers can be initialized with the provided configuration."""
        try:
            # Create a temporary entry ID for validation
            temp_entry_id = "config_flow_validation"
            
            # Initialize storage service
            storage_service = StorageService(self.hass, temp_entry_id)
            
            # Test manager initialization to validate configuration
            try:
                presence_manager = PresenceManager(self.hass, storage_service)
                buffer_manager = BufferManager(self.hass, storage_service)
                
                # Test loading configuration (will use defaults if none exists)
                await presence_manager.load_configuration()
                await buffer_manager.load_configuration()
                
                # Test updating configuration with config flow values
                if config_data.get("presence_entities"):
                    await presence_manager.update_presence_entities(config_data["presence_entities"])
                
                if config_data.get("presence_rule"):
                    await presence_manager.update_presence_rule(config_data["presence_rule"])
                
                # Test buffer configuration
                from .models import BufferConfig
                test_buffer_config = BufferConfig(
                    time_minutes=config_data.get("buffer_time_minutes", DEFAULT_BUFFER_TIME_MINUTES),
                    value_delta=config_data.get("buffer_value_delta", DEFAULT_BUFFER_VALUE_DELTA),
                    enabled=config_data.get("buffer_enabled", True),
                    apply_to="climate"
                )
                
                _LOGGER.info("Successfully validated manager initialization during config flow")
                
            except Exception as manager_err:
                _LOGGER.error("Manager initialization validation failed: %s", manager_err)
                raise
            
        except Exception as e:
            _LOGGER.error("Failed to validate manager initialization: %s", e)
            raise

    async def _get_dashboards(self) -> list[dict[str, str]]:
        """Get available Lovelace dashboards."""
        dashboards = []
        
        try:
            # Get the default dashboard
            dashboards.append({
                "value": "lovelace",
                "label": "Default Dashboard (Lovelace)"
            })
            
            # Try to get additional dashboards from Lovelace storage
            lovelace_store = Store(self.hass, 1, "lovelace")
            try:
                lovelace_data = await lovelace_store.async_load()
                if lovelace_data and "dashboards" in lovelace_data:
                    for dashboard_id, dashboard_config in lovelace_data["dashboards"].items():
                        title = dashboard_config.get("title", dashboard_id)
                        dashboards.append({
                            "value": dashboard_id,
                            "label": f"{title} ({dashboard_id})"
                        })
            except Exception as err:
                _LOGGER.debug("Could not load additional dashboards: %s", err)
                
        except Exception as err:
            _LOGGER.error("Error getting dashboards: %s", err)
        
        return dashboards

    async def _install_lovelace_card(self) -> None:
        """Install the Roost Scheduler card to the selected dashboard."""
        if not self._selected_dashboard or not self._selected_view:
            return
            
        try:
            # Load the dashboard configuration
            if self._selected_dashboard == "lovelace":
                # Default dashboard
                store = Store(self.hass, 1, "lovelace")
            else:
                # Custom dashboard
                store = Store(self.hass, 1, f"lovelace.{self._selected_dashboard}")
            
            config = await store.async_load() or {}
            
            # Initialize views if not present
            if "views" not in config:
                config["views"] = []
            
            # Find or create the target view
            target_view = None
            for view in config["views"]:
                if view.get("path") == self._selected_view or view.get("title", "").lower() == self._selected_view.lower():
                    target_view = view
                    break
            
            # If view doesn't exist, create it or use the first view
            if not target_view:
                if not config["views"]:
                    # Create a default view
                    config["views"].append({
                        "title": "Home",
                        "path": "default",
                        "cards": []
                    })
                target_view = config["views"][0]
            
            # Initialize cards if not present
            if "cards" not in target_view:
                target_view["cards"] = []
            
            # Create the card configuration
            card_config = {
                "type": "custom:roost-scheduler-card",
                "title": "Roost Scheduler",
                "entities": self._entities
            }
            
            # Add the card to the view
            target_view["cards"].append(card_config)
            
            # Save the updated configuration
            await store.async_save(config)
            
            _LOGGER.info("Successfully installed Roost Scheduler card to dashboard %s, view %s", 
                        self._selected_dashboard, self._selected_view)
                        
        except Exception as err:
            _LOGGER.error("Failed to install Lovelace card: %s", err)
            raise