"""
Integration tests for complete dashboard flow.

Tests end-to-end functionality including configuration flow with automatic card installation,
user feedback, and various failure scenarios with recovery mechanisms.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.exceptions import HomeAssistantError

from custom_components.roost_scheduler.const import DOMAIN, NAME
from custom_components.roost_scheduler.config_flow import RoostSchedulerConfigFlow
from custom_components.roost_scheduler.dashboard_service import DashboardIntegrationService
from custom_components.roost_scheduler.frontend_manager import FrontendResourceManager
from custom_components.roost_scheduler.setup_feedback import SetupFeedbackManager


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config = MagicMock()
    hass.config.config_dir = "/config"
    hass.config.components = {"frontend", "lovelace"}
    hass.states = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {
        "entities": ["climate.living_room", "climate.bedroom"],
        "presence_entities": ["device_tracker.phone"],
        "presence_rule": "anyone_home",
        "buffer_enabled": True,
        "buffer_time_minutes": 15,
        "buffer_value_delta": 2.0,
        "add_card": True,
        "dashboard": "lovelace",
        "view": "default"
    }
    return entry


@pytest.fixture
def mock_climate_entities():
    """Mock climate entity states."""
    entities = {}
    for entity_id in ["climate.living_room", "climate.bedroom"]:
        state = MagicMock()
        state.domain = "climate"
        state.entity_id = entity_id
        state.state = "heat"
        state.attributes = {
            "friendly_name": entity_id.replace("climate.", "").replace("_", " ").title(),
            "temperature": 20.0,
            ATTR_SUPPORTED_FEATURES: 1
        }
        entities[entity_id] = state
    return entities


@pytest.fixture
def mock_presence_entities():
    """Mock presence entity states."""
    entities = {}
    for entity_id in ["device_tracker.phone", "person.user"]:
        state = MagicMock()
        state.domain = entity_id.split(".")[0]
        state.entity_id = entity_id
        state.state = "home"
        state.attributes = {
            "friendly_name": entity_id.replace("_", " ").title()
        }
        entities[entity_id] = state
    return entities


@pytest.fixture
def sample_dashboard_config():
    """Sample dashboard configuration."""
    return {
        "views": [
            {
                "title": "Home",
                "path": "default",
                "cards": [
                    {
                        "type": "weather-forecast",
                        "entity": "weather.home"
                    }
                ]
            },
            {
                "title": "Climate",
                "path": "climate",
                "cards": []
            }
        ]
    }


class TestCompleteConfigurationFlow:
    """Test complete configuration flow with dashboard integration."""

    @pytest.mark.asyncio
    async def test_successful_complete_flow_with_card_installation(
        self, mock_hass, mock_climate_entities, mock_presence_entities, sample_dashboard_config
    ):
        """Test successful complete configuration flow with automatic card installation."""
        # Setup entity mocks
        def entity_ids_side_effect(domain):
            if domain == "climate":
                return list(mock_climate_entities.keys())
            elif domain == "device_tracker":
                return ["device_tracker.phone"]
            elif domain == "person":
                return ["person.user"]
            return []

        def get_side_effect(entity_id):
            return mock_climate_entities.get(entity_id) or mock_presence_entities.get(entity_id)

        mock_hass.states.async_entity_ids.side_effect = entity_ids_side_effect
        mock_hass.states.get.side_effect = get_side_effect

        # Mock storage operations
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.async_load.return_value = sample_dashboard_config

            # Mock manager validation
            with patch.object(RoostSchedulerConfigFlow, '_validate_manager_initialization') as mock_validate:
                mock_validate.return_value = None

                # Mock dashboard discovery
                with patch.object(RoostSchedulerConfigFlow, '_get_dashboards') as mock_get_dashboards:
                    mock_get_dashboards.return_value = [
                        {"value": "lovelace", "label": "Default Dashboard (Lovelace)"}
                    ]

                    # Create config flow
                    flow = RoostSchedulerConfigFlow()
                    flow.hass = mock_hass

                    # Step 1: User entity selection
                    result1 = await flow.async_step_user({
                        "entities": ["climate.living_room", "climate.bedroom"]
                    })
                    assert result1["type"] == RESULT_TYPE_FORM
                    assert result1["step_id"] == "presence"

                    # Step 2: Presence configuration
                    result2 = await flow.async_step_presence({
                        "presence_entities": ["device_tracker.phone"],
                        "presence_rule": "anyone_home"
                    })
                    assert result2["type"] == RESULT_TYPE_FORM
                    assert result2["step_id"] == "buffer"

                    # Step 3: Buffer configuration
                    result3 = await flow.async_step_buffer({
                        "buffer_enabled": True,
                        "buffer_time_minutes": 15,
                        "buffer_value_delta": 2.0
                    })
                    assert result3["type"] == RESULT_TYPE_FORM
                    assert result3["step_id"] == "card"

                    # Step 4: Card installation
                    result4 = await flow.async_step_card({
                        "add_card": True,
                        "dashboard": "lovelace",
                        "view": "default"
                    })

                    # Verify successful completion
                    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY
                    assert result4["title"] == NAME
                    assert result4["data"]["entities"] == ["climate.living_room", "climate.bedroom"]
                    assert result4["data"]["presence_entities"] == ["device_tracker.phone"]
                    assert result4["data"]["add_card"] is True
                    assert result4["data"]["dashboard"] == "lovelace"

                    # Verify card was added to dashboard
                    saved_configs = []
                    async def capture_save(config):
                        saved_configs.append(config)
                    mock_store.async_save = capture_save

                    # Verify dashboard was modified
                    assert len(saved_configs) >= 1
                    final_config = saved_configs[-1]
                    assert "views" in final_config
                    
                    # Find the view that should contain our card
                    target_view = None
                    for view in final_config["views"]:
                        if view.get("path") == "default":
                            target_view = view
                            break
                    
                    assert target_view is not None
                    assert len(target_view["cards"]) >= 2  # Original weather card + our card
                    
                    # Find our card
                    roost_card = None
                    for card in target_view["cards"]:
                        if card.get("type") == "custom:roost-scheduler-card":
                            roost_card = card
                            break
                    
                    assert roost_card is not None
                    assert roost_card["entities"] == ["climate.living_room", "climate.bedroom"]

    @pytest.mark.asyncio
    async def test_complete_flow_with_dashboard_access_failure_and_recovery(
        self, mock_hass, mock_climate_entities, sample_dashboard_config
    ):
        """Test complete flow with dashboard access failure and successful recovery."""
        # Setup entity mocks
        mock_hass.states.async_entity_ids.return_value = list(mock_climate_entities.keys())
        mock_hass.states.get.side_effect = lambda entity_id: mock_climate_entities.get(entity_id)

        # Mock storage operations with initial failure then success
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # First call fails, second succeeds (fallback dashboard)
            mock_store.async_load.side_effect = [
                Exception("Dashboard access denied"),
                sample_dashboard_config
            ]

            # Mock manager validation
            with patch.object(RoostSchedulerConfigFlow, '_validate_manager_initialization') as mock_validate:
                mock_validate.return_value = None

                # Mock dashboard discovery with multiple options
                with patch.object(RoostSchedulerConfigFlow, '_get_dashboards') as mock_get_dashboards:
                    mock_get_dashboards.return_value = [
                        {"value": "lovelace", "label": "Default Dashboard (Lovelace)"},
                        {"value": "custom_dashboard", "label": "Custom Dashboard"}
                    ]

                    # Create config flow
                    flow = RoostSchedulerConfigFlow()
                    flow.hass = mock_hass

                    # Complete the flow
                    result1 = await flow.async_step_user({"entities": ["climate.living_room"]})
                    result2 = await flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
                    result3 = await flow.async_step_buffer({"buffer_enabled": False, "buffer_time_minutes": 15, "buffer_value_delta": 2.0})
                    result4 = await flow.async_step_card({
                        "add_card": True,
                        "dashboard": "lovelace",
                        "view": "default"
                    })

                    # Should still succeed despite initial dashboard access failure
                    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY
                    assert result4["data"]["add_card"] is True

    @pytest.mark.asyncio
    async def test_complete_flow_with_frontend_resource_registration_failure(
        self, mock_hass, mock_climate_entities
    ):
        """Test complete flow with frontend resource registration failure."""
        # Setup entity mocks
        mock_hass.states.async_entity_ids.return_value = list(mock_climate_entities.keys())
        mock_hass.states.get.side_effect = lambda entity_id: mock_climate_entities.get(entity_id)

        # Mock frontend not available
        mock_hass.config.components = set()  # No frontend component

        # Mock storage operations
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.async_load.return_value = {"views": []}

            # Mock manager validation
            with patch.object(RoostSchedulerConfigFlow, '_validate_manager_initialization') as mock_validate:
                mock_validate.return_value = None

                # Mock dashboard discovery
                with patch.object(RoostSchedulerConfigFlow, '_get_dashboards') as mock_get_dashboards:
                    mock_get_dashboards.return_value = []

                    # Create config flow
                    flow = RoostSchedulerConfigFlow()
                    flow.hass = mock_hass

                    # Complete the flow
                    result1 = await flow.async_step_user({"entities": ["climate.living_room"]})
                    result2 = await flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
                    result3 = await flow.async_step_buffer({"buffer_enabled": True, "buffer_time_minutes": 15, "buffer_value_delta": 2.0})
                    result4 = await flow.async_step_card({"add_card": False})

                    # Should still succeed despite frontend issues
                    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY
                    assert result4["data"]["entities"] == ["climate.living_room"]

    @pytest.mark.asyncio
    async def test_complete_flow_with_manager_validation_failure(
        self, mock_hass, mock_climate_entities
    ):
        """Test complete flow with manager validation failure."""
        # Setup entity mocks
        mock_hass.states.async_entity_ids.return_value = list(mock_climate_entities.keys())
        mock_hass.states.get.side_effect = lambda entity_id: mock_climate_entities.get(entity_id)

        # Mock manager validation failure
        with patch.object(RoostSchedulerConfigFlow, '_validate_manager_initialization') as mock_validate:
            mock_validate.side_effect = Exception("Manager initialization failed")

            # Mock dashboard discovery
            with patch.object(RoostSchedulerConfigFlow, '_get_dashboards') as mock_get_dashboards:
                mock_get_dashboards.return_value = []

                # Create config flow
                flow = RoostSchedulerConfigFlow()
                flow.hass = mock_hass

                # Complete the flow
                result1 = await flow.async_step_user({"entities": ["climate.living_room"]})
                result2 = await flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
                result3 = await flow.async_step_buffer({"buffer_enabled": True, "buffer_time_minutes": 15, "buffer_value_delta": 2.0})
                result4 = await flow.async_step_card({"add_card": False})

                # Should still succeed despite manager validation failure
                assert result4["type"] == RESULT_TYPE_CREATE_ENTRY
                assert result4["data"]["entities"] == ["climate.living_room"]


class TestIntegrationSetupWithDashboardIntegration:
    """Test integration setup with dashboard integration components."""

    @pytest.mark.asyncio
    async def test_successful_integration_setup_with_dashboard_components(
        self, mock_hass, mock_config_entry
    ):
        """Test successful integration setup with all dashboard components."""
        # Mock the main integration setup
        with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage_class, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule_class, \
             patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend_class, \
             patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard_class, \
             patch('custom_components.roost_scheduler.setup_feedback.SetupFeedbackManager') as mock_feedback_class:

            # Setup mocks
            mock_storage = AsyncMock()
            mock_storage_class.return_value = mock_storage

            mock_schedule = AsyncMock()
            mock_schedule_class.return_value = mock_schedule

            mock_frontend = AsyncMock()
            mock_frontend_class.return_value = mock_frontend
            mock_frontend.register_frontend_resources.return_value = {
                "success": True,
                "resources_registered": [{"resource": "/test/card.js"}],
                "resources_failed": []
            }

            mock_dashboard = AsyncMock()
            mock_dashboard_class.return_value = mock_dashboard
            mock_dashboard.add_card_to_dashboard.return_value = MagicMock(
                success=True,
                dashboard_id="lovelace",
                card_position=1
            )

            mock_feedback = AsyncMock()
            mock_feedback_class.return_value = mock_feedback

            # Import and run setup
            from custom_components.roost_scheduler import async_setup_entry
            
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Verify setup succeeded
            assert result is True

            # Verify components were initialized
            mock_storage_class.assert_called_once()
            mock_schedule_class.assert_called_once()
            mock_frontend_class.assert_called_once()

            # Verify frontend resources were registered
            mock_frontend.register_frontend_resources.assert_called_once()

            # Verify dashboard integration was attempted if card installation was requested
            if mock_config_entry.data.get("add_card"):
                mock_dashboard_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_integration_setup_with_frontend_registration_failure(
        self, mock_hass, mock_config_entry
    ):
        """Test integration setup continues when frontend registration fails."""
        # Mock the main integration setup
        with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage_class, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule_class, \
             patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend_class:

            # Setup mocks
            mock_storage = AsyncMock()
            mock_storage_class.return_value = mock_storage

            mock_schedule = AsyncMock()
            mock_schedule_class.return_value = mock_schedule

            mock_frontend = AsyncMock()
            mock_frontend_class.return_value = mock_frontend
            # Frontend registration fails
            mock_frontend.register_frontend_resources.return_value = {
                "success": False,
                "resources_registered": [],
                "resources_failed": [{"resource": "/test/card.js", "error": "File not found"}]
            }

            # Import and run setup
            from custom_components.roost_scheduler import async_setup_entry
            
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Setup should still succeed
            assert result is True

            # Verify frontend registration was attempted
            mock_frontend.register_frontend_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_integration_setup_with_dashboard_service_failure(
        self, mock_hass, mock_config_entry
    ):
        """Test integration setup continues when dashboard service fails."""
        # Mock the main integration setup
        with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage_class, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule_class, \
             patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend_class, \
             patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard_class:

            # Setup mocks
            mock_storage = AsyncMock()
            mock_storage_class.return_value = mock_storage

            mock_schedule = AsyncMock()
            mock_schedule_class.return_value = mock_schedule

            mock_frontend = AsyncMock()
            mock_frontend_class.return_value = mock_frontend
            mock_frontend.register_frontend_resources.return_value = {
                "success": True,
                "resources_registered": [{"resource": "/test/card.js"}],
                "resources_failed": []
            }

            mock_dashboard = AsyncMock()
            mock_dashboard_class.return_value = mock_dashboard
            # Dashboard service fails
            mock_dashboard.add_card_to_dashboard.side_effect = Exception("Dashboard service failed")

            # Import and run setup
            from custom_components.roost_scheduler import async_setup_entry
            
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Setup should still succeed
            assert result is True

            # Verify dashboard service was attempted
            if mock_config_entry.data.get("add_card"):
                mock_dashboard_class.assert_called_once()


class TestEndToEndDashboardIntegrationScenarios:
    """Test end-to-end dashboard integration scenarios."""

    @pytest.mark.asyncio
    async def test_complete_successful_dashboard_integration(
        self, mock_hass, mock_climate_entities, sample_dashboard_config
    ):
        """Test complete successful dashboard integration from config flow to setup."""
        entities = ["climate.living_room", "climate.bedroom"]
        
        # Setup entity mocks
        mock_hass.states.async_entity_ids.return_value = entities
        mock_hass.states.get.side_effect = lambda entity_id: mock_climate_entities.get(entity_id)

        # Mock storage operations
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.async_load.return_value = sample_dashboard_config

            saved_configs = []
            async def capture_save(config):
                saved_configs.append(config)
            mock_store.async_save = capture_save

            # Mock manager validation
            with patch.object(RoostSchedulerConfigFlow, '_validate_manager_initialization') as mock_validate:
                mock_validate.return_value = None

                # Mock dashboard discovery
                with patch.object(RoostSchedulerConfigFlow, '_get_dashboards') as mock_get_dashboards:
                    mock_get_dashboards.return_value = [
                        {"value": "lovelace", "label": "Default Dashboard (Lovelace)"}
                    ]

                    # Step 1: Complete config flow
                    flow = RoostSchedulerConfigFlow()
                    flow.hass = mock_hass

                    result1 = await flow.async_step_user({"entities": entities})
                    result2 = await flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
                    result3 = await flow.async_step_buffer({"buffer_enabled": True, "buffer_time_minutes": 15, "buffer_value_delta": 2.0})
                    result4 = await flow.async_step_card({
                        "add_card": True,
                        "dashboard": "lovelace",
                        "view": "default"
                    })

                    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY

                    # Step 2: Test integration setup with dashboard components
                    config_entry = MagicMock(spec=ConfigEntry)
                    config_entry.entry_id = "test_entry"
                    config_entry.data = result4["data"]

                    # Mock integration components
                    with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage_class, \
                         patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule_class, \
                         patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend_class, \
                         patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard_class:

                        mock_storage = AsyncMock()
                        mock_storage_class.return_value = mock_storage

                        mock_schedule = AsyncMock()
                        mock_schedule_class.return_value = mock_schedule

                        mock_frontend = AsyncMock()
                        mock_frontend_class.return_value = mock_frontend
                        mock_frontend.register_frontend_resources.return_value = {
                            "success": True,
                            "resources_registered": [{"resource": "/hacsfiles/roost-scheduler-card/roost-scheduler-card.js"}],
                            "resources_failed": []
                        }

                        mock_dashboard = AsyncMock()
                        mock_dashboard_class.return_value = mock_dashboard
                        mock_dashboard.add_card_to_dashboard.return_value = MagicMock(
                            success=True,
                            dashboard_id="lovelace",
                            card_position=1
                        )

                        # Run integration setup
                        from custom_components.roost_scheduler import async_setup_entry
                        setup_result = await async_setup_entry(mock_hass, config_entry)

                        # Verify complete success
                        assert setup_result is True
                        mock_frontend.register_frontend_resources.assert_called_once()
                        mock_dashboard.add_card_to_dashboard.assert_called_once()

                        # Verify card was added to dashboard during config flow
                        assert len(saved_configs) >= 1
                        final_config = saved_configs[-1]
                        
                        # Find the default view
                        default_view = None
                        for view in final_config["views"]:
                            if view.get("path") == "default":
                                default_view = view
                                break
                        
                        assert default_view is not None
                        
                        # Verify our card was added
                        roost_cards = [card for card in default_view["cards"] if card.get("type") == "custom:roost-scheduler-card"]
                        assert len(roost_cards) == 1
                        assert roost_cards[0]["entities"] == entities

    @pytest.mark.asyncio
    async def test_dashboard_integration_with_existing_card_conflict_resolution(
        self, mock_hass, mock_climate_entities
    ):
        """Test dashboard integration with existing card conflict resolution."""
        entities = ["climate.living_room", "climate.bedroom"]
        
        # Dashboard config with existing Roost Scheduler card
        dashboard_with_existing_card = {
            "views": [
                {
                    "title": "Home",
                    "path": "default",
                    "cards": [
                        {
                            "type": "custom:roost-scheduler-card",
                            "title": "Existing Roost Scheduler",
                            "entities": ["climate.old_entity"]
                        },
                        {
                            "type": "weather-forecast",
                            "entity": "weather.home"
                        }
                    ]
                }
            ]
        }

        # Setup entity mocks
        mock_hass.states.async_entity_ids.return_value = entities
        mock_hass.states.get.side_effect = lambda entity_id: mock_climate_entities.get(entity_id)

        # Mock storage operations
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.async_load.return_value = dashboard_with_existing_card

            saved_configs = []
            async def capture_save(config):
                saved_configs.append(config)
            mock_store.async_save = capture_save

            # Mock manager validation
            with patch.object(RoostSchedulerConfigFlow, '_validate_manager_initialization') as mock_validate:
                mock_validate.return_value = None

                # Mock dashboard discovery
                with patch.object(RoostSchedulerConfigFlow, '_get_dashboards') as mock_get_dashboards:
                    mock_get_dashboards.return_value = [
                        {"value": "lovelace", "label": "Default Dashboard (Lovelace)"}
                    ]

                    # Complete config flow
                    flow = RoostSchedulerConfigFlow()
                    flow.hass = mock_hass

                    result1 = await flow.async_step_user({"entities": entities})
                    result2 = await flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
                    result3 = await flow.async_step_buffer({"buffer_enabled": True, "buffer_time_minutes": 15, "buffer_value_delta": 2.0})
                    result4 = await flow.async_step_card({
                        "add_card": True,
                        "dashboard": "lovelace",
                        "view": "default"
                    })

                    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY

                    # Verify conflict resolution occurred
                    assert len(saved_configs) >= 1
                    final_config = saved_configs[-1]
                    
                    # Find the default view
                    default_view = None
                    for view in final_config["views"]:
                        if view.get("path") == "default":
                            default_view = view
                            break
                    
                    assert default_view is not None
                    
                    # Should still have 2 cards (existing card updated, weather card unchanged)
                    assert len(default_view["cards"]) == 2
                    
                    # Find the Roost Scheduler card
                    roost_cards = [card for card in default_view["cards"] if card.get("type") == "custom:roost-scheduler-card"]
                    assert len(roost_cards) == 1
                    
                    # Verify entities were merged
                    expected_entities = ["climate.old_entity", "climate.living_room", "climate.bedroom"]
                    assert set(roost_cards[0]["entities"]) == set(expected_entities)

    @pytest.mark.asyncio
    async def test_dashboard_integration_with_multiple_failure_recovery(
        self, mock_hass, mock_climate_entities
    ):
        """Test dashboard integration with multiple failures and recovery mechanisms."""
        entities = ["climate.living_room"]
        
        # Setup entity mocks
        mock_hass.states.async_entity_ids.return_value = entities
        mock_hass.states.get.side_effect = lambda entity_id: mock_climate_entities.get(entity_id)

        # Mock storage operations with multiple failures
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            
            # Simulate multiple dashboard access failures, then success
            mock_store.async_load.side_effect = [
                Exception("Primary dashboard access failed"),
                Exception("Secondary dashboard access failed"),
                {"views": [{"title": "Home", "path": "default", "cards": []}]}  # Third attempt succeeds
            ]

            saved_configs = []
            async def capture_save(config):
                saved_configs.append(config)
            mock_store.async_save = capture_save

            # Mock manager validation
            with patch.object(RoostSchedulerConfigFlow, '_validate_manager_initialization') as mock_validate:
                mock_validate.return_value = None

                # Mock dashboard discovery with multiple options
                with patch.object(RoostSchedulerConfigFlow, '_get_dashboards') as mock_get_dashboards:
                    mock_get_dashboards.return_value = [
                        {"value": "lovelace", "label": "Default Dashboard (Lovelace)"},
                        {"value": "custom1", "label": "Custom Dashboard 1"},
                        {"value": "custom2", "label": "Custom Dashboard 2"}
                    ]

                    # Complete config flow
                    flow = RoostSchedulerConfigFlow()
                    flow.hass = mock_hass

                    result1 = await flow.async_step_user({"entities": entities})
                    result2 = await flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
                    result3 = await flow.async_step_buffer({"buffer_enabled": False, "buffer_time_minutes": 15, "buffer_value_delta": 2.0})
                    result4 = await flow.async_step_card({
                        "add_card": True,
                        "dashboard": "lovelace",
                        "view": "default"
                    })

                    # Should eventually succeed despite multiple failures
                    assert result4["type"] == RESULT_TYPE_CREATE_ENTRY
                    assert result4["data"]["add_card"] is True

                    # Verify recovery mechanism worked (card was eventually added)
                    assert len(saved_configs) >= 1

    @pytest.mark.asyncio
    async def test_concurrent_dashboard_integration_operations(
        self, mock_hass, mock_climate_entities, sample_dashboard_config
    ):
        """Test concurrent dashboard integration operations."""
        entities = ["climate.living_room", "climate.bedroom"]
        
        # Setup entity mocks
        mock_hass.states.async_entity_ids.return_value = entities
        mock_hass.states.get.side_effect = lambda entity_id: mock_climate_entities.get(entity_id)

        # Mock storage operations
        with patch('homeassistant.helpers.storage.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            mock_store.async_load.return_value = sample_dashboard_config

            saved_configs = []
            async def capture_save(config):
                # Simulate some processing time
                await asyncio.sleep(0.01)
                saved_configs.append(config)
            mock_store.async_save = capture_save

            # Mock manager validation
            with patch.object(RoostSchedulerConfigFlow, '_validate_manager_initialization') as mock_validate:
                mock_validate.return_value = None

                # Mock dashboard discovery
                with patch.object(RoostSchedulerConfigFlow, '_get_dashboards') as mock_get_dashboards:
                    mock_get_dashboards.return_value = [
                        {"value": "lovelace", "label": "Default Dashboard (Lovelace)"}
                    ]

                    # Create multiple concurrent config flows
                    async def run_config_flow(flow_id):
                        flow = RoostSchedulerConfigFlow()
                        flow.hass = mock_hass

                        result1 = await flow.async_step_user({"entities": [f"climate.device_{flow_id}"]})
                        result2 = await flow.async_step_presence({"presence_entities": [], "presence_rule": "anyone_home"})
                        result3 = await flow.async_step_buffer({"buffer_enabled": True, "buffer_time_minutes": 15, "buffer_value_delta": 2.0})
                        result4 = await flow.async_step_card({
                            "add_card": True,
                            "dashboard": "lovelace",
                            "view": "default"
                        })
                        return result4

                    # Run multiple flows concurrently
                    tasks = [run_config_flow(i) for i in range(3)]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # All flows should complete successfully
                    for result in results:
                        if isinstance(result, Exception):
                            pytest.fail(f"Config flow failed with exception: {result}")
                        assert result["type"] == RESULT_TYPE_CREATE_ENTRY

                    # Verify all dashboard modifications were saved
                    assert len(saved_configs) >= 3


class TestUserFeedbackAndErrorHandling:
    """Test user feedback and error handling in dashboard integration."""

    @pytest.mark.asyncio
    async def test_setup_feedback_generation_success(self, mock_hass, mock_config_entry):
        """Test setup feedback generation for successful integration."""
        # Mock successful setup components
        with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage_class, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule_class, \
             patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend_class, \
             patch('custom_components.roost_scheduler.dashboard_service.DashboardIntegrationService') as mock_dashboard_class, \
             patch('custom_components.roost_scheduler.setup_feedback.SetupFeedbackManager') as mock_feedback_class:

            # Setup successful mocks
            mock_storage = AsyncMock()
            mock_storage_class.return_value = mock_storage

            mock_schedule = AsyncMock()
            mock_schedule_class.return_value = mock_schedule

            mock_frontend = AsyncMock()
            mock_frontend_class.return_value = mock_frontend
            mock_frontend.register_frontend_resources.return_value = {
                "success": True,
                "resources_registered": [{"resource": "/test/card.js"}],
                "resources_failed": []
            }

            mock_dashboard = AsyncMock()
            mock_dashboard_class.return_value = mock_dashboard
            mock_dashboard.add_card_to_dashboard.return_value = MagicMock(
                success=True,
                dashboard_id="lovelace",
                card_position=1
            )

            mock_feedback = AsyncMock()
            mock_feedback_class.return_value = mock_feedback
            mock_feedback.generate_setup_summary.return_value = {
                "success": True,
                "message": "Roost Scheduler has been successfully configured!",
                "next_steps": ["Navigate to your dashboard to see the new card"]
            }

            # Run setup
            from custom_components.roost_scheduler import async_setup_entry
            result = await async_setup_entry(mock_hass, mock_config_entry)

            assert result is True
            
            # Verify feedback was generated
            mock_feedback.generate_setup_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_feedback_generation_with_warnings(self, mock_hass, mock_config_entry):
        """Test setup feedback generation with warnings."""
        # Mock setup with warnings
        with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage_class, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule_class, \
             patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend_class, \
             patch('custom_components.roost_scheduler.setup_feedback.SetupFeedbackManager') as mock_feedback_class:

            mock_storage = AsyncMock()
            mock_storage_class.return_value = mock_storage

            mock_schedule = AsyncMock()
            mock_schedule_class.return_value = mock_schedule

            mock_frontend = AsyncMock()
            mock_frontend_class.return_value = mock_frontend
            # Frontend registration partially fails
            mock_frontend.register_frontend_resources.return_value = {
                "success": False,
                "resources_registered": [{"resource": "/test/card.js"}],
                "resources_failed": [{"resource": "/test/styles.css", "error": "File not found"}],
                "warnings": ["CSS file not found, using default styles"]
            }

            mock_feedback = AsyncMock()
            mock_feedback_class.return_value = mock_feedback
            mock_feedback.generate_setup_summary.return_value = {
                "success": True,
                "message": "Roost Scheduler has been configured with some warnings.",
                "warnings": ["CSS file not found, using default styles"],
                "next_steps": ["Check the logs for more details", "Navigate to your dashboard"]
            }

            # Run setup
            from custom_components.roost_scheduler import async_setup_entry
            result = await async_setup_entry(mock_hass, mock_config_entry)

            assert result is True
            
            # Verify feedback included warnings
            mock_feedback.generate_setup_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_diagnostics_generation(self, mock_hass, mock_config_entry):
        """Test error diagnostics generation for failed components."""
        # Mock setup with component failures
        with patch('custom_components.roost_scheduler.storage.StorageService') as mock_storage_class, \
             patch('custom_components.roost_scheduler.schedule_manager.ScheduleManager') as mock_schedule_class, \
             patch('custom_components.roost_scheduler.frontend_manager.FrontendResourceManager') as mock_frontend_class, \
             patch('custom_components.roost_scheduler.setup_feedback.SetupFeedbackManager') as mock_feedback_class:

            mock_storage = AsyncMock()
            mock_storage_class.return_value = mock_storage

            # Schedule manager fails
            mock_schedule_class.side_effect = Exception("Schedule manager initialization failed")

            mock_frontend = AsyncMock()
            mock_frontend_class.return_value = mock_frontend

            mock_feedback = AsyncMock()
            mock_feedback_class.return_value = mock_feedback
            mock_feedback.create_troubleshooting_info.return_value = {
                "error_summary": "Schedule manager initialization failed",
                "troubleshooting_steps": [
                    "Check Home Assistant logs for detailed error information",
                    "Verify climate entities are available and accessible",
                    "Try restarting Home Assistant"
                ],
                "support_info": {
                    "ha_version": "2024.1.0",
                    "integration_version": "0.3.0",
                    "error_type": "InitializationError"
                }
            }

            # Run setup (should handle the failure gracefully)
            from custom_components.roost_scheduler import async_setup_entry
            result = await async_setup_entry(mock_hass, mock_config_entry)

            # Setup might fail, but diagnostics should be generated
            mock_feedback.create_troubleshooting_info.assert_called()


class TestRecoveryMechanisms:
    """Test recovery mechanisms for various failure scenarios."""

    @pytest.mark.asyncio
    async def test_dashboard_access_recovery_with_fallback_dashboards(self, mock_hass):
        """Test dashboard access recovery using fallback dashboards."""
        dashboard_service = DashboardIntegrationService(mock_hass)
        entities = ["climate.living_room"]

        # Mock dashboard loading with failures then success
        with patch.object(dashboard_service, '_load_dashboard_config') as mock_load, \
             patch.object(dashboard_service, '_save_dashboard_config') as mock_save, \
             patch.object(dashboard_service, '_get_available_dashboards') as mock_available:

            # First two calls fail, third succeeds
            mock_load.side_effect = [
                None,  # Primary dashboard fails
                None,  # First fallback fails
                {"views": [{"title": "Home", "path": "default", "cards": []}]}  # Second fallback succeeds
            ]
            
            mock_available.return_value = ["custom1", "custom2", "custom3"]

            # Attempt card installation
            result = await dashboard_service.add_card_to_dashboard(entities)

            # Should eventually succeed with fallback
            assert result.success is True
            assert result.dashboard_id in ["custom1", "custom2", "custom3"]
            
            # Verify multiple attempts were made
            assert mock_load.call_count >= 2

    @pytest.mark.asyncio
    async def test_frontend_resource_recovery_with_fallback_paths(self, mock_hass):
        """Test frontend resource recovery using fallback paths."""
        frontend_manager = FrontendResourceManager(mock_hass)

        # Mock file system with primary path failing, fallback succeeding
        with patch('os.path.isfile') as mock_isfile, \
             patch('os.path.getsize') as mock_getsize, \
             patch('custom_components.roost_scheduler.frontend_manager.frontend.add_extra_js_url') as mock_add_js:

            def mock_file_exists(path):
                # Primary HACS path fails
                if "/config/www/community/roost-scheduler-card/roost-scheduler-card.js" in path:
                    return False
                # Fallback local path succeeds
                elif "/config/www/roost-scheduler-card/roost-scheduler-card.js" in path:
                    return True
                return False

            mock_isfile.side_effect = mock_file_exists
            mock_getsize.return_value = 1024

            # Attempt resource registration
            result = await frontend_manager.register_frontend_resources()

            # Should succeed with fallback
            assert result["success"] is True
            assert len(result["resources_registered"]) >= 1
            assert any(r.get("fallback_used", False) for r in result["resources_registered"])
            assert len(result["warnings"]) >= 1

    @pytest.mark.asyncio
    async def test_card_conflict_resolution_recovery(self, mock_hass):
        """Test card conflict resolution recovery mechanisms."""
        dashboard_service = DashboardIntegrationService(mock_hass)
        entities = ["climate.living_room", "climate.bedroom"]

        # Dashboard with multiple conflicting cards
        dashboard_config = {
            "views": [
                {
                    "title": "Home",
                    "path": "default",
                    "cards": [
                        {"type": "custom:roost-scheduler-card", "entities": ["climate.old1"]},
                        {"type": "custom:roost-scheduler-card", "entities": ["climate.old2"]},
                        {"type": "custom:roost-scheduler-card", "entities": ["climate.old3"]},
                        {"type": "weather-forecast", "entity": "weather.home"}
                    ]
                }
            ]
        }

        # Test conflict resolution
        result = await dashboard_service.handle_dashboard_conflicts(dashboard_config, entities)

        # Should resolve conflicts
        assert result["conflicts_found"] is True
        assert len(result["existing_cards"]) == 3
        
        # Should have applied resolution strategy
        assert result["resolution_strategy"] in ["update_existing", "remove_duplicates"]
        
        # Verify cards were modified
        roost_cards = [
            card for card in dashboard_config["views"][0]["cards"] 
            if card.get("type") == "custom:roost-scheduler-card"
        ]
        
        # Should have fewer cards after conflict resolution
        assert len(roost_cards) <= 3
        assert len(result["resolution_actions"]) >= 1