"""
Unit tests for Dashboard Integration Service.

Tests automatic card installation, dashboard detection, conflict resolution, and error handling.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import HomeAssistantError

from custom_components.roost_scheduler.dashboard_service import (
    DashboardIntegrationService,
    DashboardCardConfig,
    DashboardIntegrationStatus,
    CardInstallationResult,
)


@pytest.fixture
def hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    return hass


@pytest.fixture
def dashboard_service(hass):
    """Create a DashboardIntegrationService instance."""
    return DashboardIntegrationService(hass)


@pytest.fixture
def sample_entities():
    """Sample entity list for testing."""
    return ["climate.living_room", "climate.bedroom"]


@pytest.fixture
def sample_dashboard_config():
    """Sample dashboard configuration for testing."""
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


@pytest.fixture
def sample_dashboard_with_existing_card():
    """Sample dashboard configuration with existing Roost Scheduler card."""
    return {
        "views": [
            {
                "title": "Home",
                "path": "default",
                "cards": [
                    {
                        "type": "custom:roost-scheduler-card",
                        "title": "Roost Scheduler",
                        "entities": ["climate.existing"]
                    }
                ]
            }
        ]
    }


class TestDashboardIntegrationService:
    """Test cases for DashboardIntegrationService."""

    async def test_init(self, hass):
        """Test service initialization."""
        service = DashboardIntegrationService(hass)
        
        assert service.hass is hass
        assert service._default_card_config["type"] == "custom:roost-scheduler-card"
        assert service._default_card_config["title"] == "Roost Scheduler"

    async def test_get_default_dashboard_success(self, dashboard_service):
        """Test successful default dashboard detection."""
        with patch.object(dashboard_service, '_load_dashboard_config') as mock_load:
            mock_load.return_value = {"views": []}
            
            result = await dashboard_service.get_default_dashboard()
            
            assert result == "lovelace"
            mock_load.assert_called_once_with("lovelace")

    async def test_get_default_dashboard_fallback_to_available(self, dashboard_service):
        """Test fallback to available dashboard when default fails."""
        with patch.object(dashboard_service, '_load_dashboard_config') as mock_load, \
             patch.object(dashboard_service, '_get_available_dashboards') as mock_available:
            
            # First call (default) fails, then we get available dashboards
            mock_load.return_value = None
            mock_available.return_value = ["custom_dashboard"]
            
            result = await dashboard_service.get_default_dashboard()
            
            assert result == "custom_dashboard"
            mock_load.assert_called_once_with("lovelace")

    async def test_get_default_dashboard_ultimate_fallback(self, dashboard_service):
        """Test ultimate fallback when no dashboards are accessible."""
        with patch.object(dashboard_service, '_load_dashboard_config') as mock_load, \
             patch.object(dashboard_service, '_get_available_dashboards') as mock_available:
            
            mock_load.return_value = None
            mock_available.return_value = []
            
            result = await dashboard_service.get_default_dashboard()
            
            assert result == "lovelace"

    async def test_create_default_card_config_single_entity(self, dashboard_service, hass):
        """Test creating default card config with single entity."""
        entities = ["climate.living_room"]
        
        # Mock entity state
        mock_state = MagicMock()
        mock_state.attributes = {"friendly_name": "Living Room Climate"}
        hass.states.get.return_value = mock_state
        
        config = await dashboard_service.create_default_card_config(entities)
        
        assert config["type"] == "custom:roost-scheduler-card"
        assert config["title"] == "Roost Scheduler - Living Room Climate"
        assert config["entities"] == entities
        assert config["show_current_temperature"] is True

    async def test_create_default_card_config_multiple_entities(self, dashboard_service):
        """Test creating default card config with multiple entities."""
        entities = ["climate.living_room", "climate.bedroom", "climate.kitchen"]
        
        config = await dashboard_service.create_default_card_config(entities)
        
        assert config["type"] == "custom:roost-scheduler-card"
        assert config["title"] == "Roost Scheduler (3 devices)"
        assert config["entities"] == entities

    async def test_create_default_card_config_no_entities(self, dashboard_service):
        """Test creating default card config with no entities."""
        entities = []
        
        config = await dashboard_service.create_default_card_config(entities)
        
        assert config["type"] == "custom:roost-scheduler-card"
        assert config["title"] == "Roost Scheduler"
        assert "entities" not in config

    async def test_add_card_to_dashboard_success(self, dashboard_service, sample_entities, sample_dashboard_config):
        """Test successful card addition to dashboard."""
        with patch.object(dashboard_service, 'get_default_dashboard') as mock_default, \
             patch.object(dashboard_service, '_load_dashboard_config') as mock_load, \
             patch.object(dashboard_service, '_save_dashboard_config') as mock_save, \
             patch.object(dashboard_service, '_get_target_view') as mock_view, \
             patch.object(dashboard_service, '_handle_card_conflicts') as mock_conflicts, \
             patch.object(dashboard_service, 'create_default_card_config') as mock_config:
            
            mock_default.return_value = "lovelace"
            mock_load.return_value = sample_dashboard_config
            mock_view.return_value = (sample_dashboard_config["views"][0], 0)
            mock_conflicts.return_value = {"conflicts_found": False, "existing_updated": False}
            mock_config.return_value = {"type": "custom:roost-scheduler-card", "entities": sample_entities}
            
            result = await dashboard_service.add_card_to_dashboard(sample_entities)
            
            assert result.success is True
            assert result.dashboard_id == "lovelace"
            assert result.card_position == 1  # Added after existing weather card
            mock_save.assert_called_once()

    async def test_add_card_to_dashboard_with_specific_dashboard(self, dashboard_service, sample_entities, sample_dashboard_config):
        """Test card addition to specific dashboard."""
        dashboard_id = "custom_dashboard"
        
        with patch.object(dashboard_service, '_load_dashboard_config') as mock_load, \
             patch.object(dashboard_service, '_save_dashboard_config') as mock_save, \
             patch.object(dashboard_service, '_get_target_view') as mock_view, \
             patch.object(dashboard_service, '_handle_card_conflicts') as mock_conflicts, \
             patch.object(dashboard_service, 'create_default_card_config') as mock_config:
            
            mock_load.return_value = sample_dashboard_config
            mock_view.return_value = (sample_dashboard_config["views"][0], 0)
            mock_conflicts.return_value = {"conflicts_found": False, "existing_updated": False}
            mock_config.return_value = {"type": "custom:roost-scheduler-card", "entities": sample_entities}
            
            result = await dashboard_service.add_card_to_dashboard(sample_entities, dashboard_id=dashboard_id)
            
            assert result.success is True
            assert result.dashboard_id == dashboard_id
            mock_load.assert_called_once_with(dashboard_id)

    async def test_add_card_to_dashboard_with_position(self, dashboard_service, sample_entities, sample_dashboard_config):
        """Test card addition at specific position."""
        card_position = 0
        
        with patch.object(dashboard_service, 'get_default_dashboard') as mock_default, \
             patch.object(dashboard_service, '_load_dashboard_config') as mock_load, \
             patch.object(dashboard_service, '_save_dashboard_config') as mock_save, \
             patch.object(dashboard_service, '_get_target_view') as mock_view, \
             patch.object(dashboard_service, '_handle_card_conflicts') as mock_conflicts, \
             patch.object(dashboard_service, 'create_default_card_config') as mock_config:
            
            mock_default.return_value = "lovelace"
            mock_load.return_value = sample_dashboard_config
            mock_view.return_value = (sample_dashboard_config["views"][0], 0)
            mock_conflicts.return_value = {"conflicts_found": False, "existing_updated": False}
            mock_config.return_value = {"type": "custom:roost-scheduler-card", "entities": sample_entities}
            
            result = await dashboard_service.add_card_to_dashboard(
                sample_entities, card_position=card_position
            )
            
            assert result.success is True
            assert result.card_position == card_position

    async def test_add_card_to_dashboard_load_config_failure(self, dashboard_service, sample_entities):
        """Test card addition when dashboard config loading fails."""
        with patch.object(dashboard_service, 'get_default_dashboard') as mock_default, \
             patch.object(dashboard_service, '_load_dashboard_config') as mock_load:
            
            mock_default.return_value = "lovelace"
            mock_load.return_value = None
            
            result = await dashboard_service.add_card_to_dashboard(sample_entities)
            
            assert result.success is False
            assert "Could not load dashboard configuration" in result.error_message

    async def test_add_card_to_dashboard_exception_handling(self, dashboard_service, sample_entities):
        """Test card addition with exception handling."""
        with patch.object(dashboard_service, 'get_default_dashboard') as mock_default:
            mock_default.side_effect = Exception("Test exception")
            
            result = await dashboard_service.add_card_to_dashboard(sample_entities)
            
            assert result.success is False
            assert "Failed to add card to dashboard" in result.error_message

    async def test_handle_card_conflicts_no_conflicts(self, dashboard_service, sample_dashboard_config, sample_entities):
        """Test conflict handling when no conflicts exist."""
        result = await dashboard_service.handle_dashboard_conflicts(sample_dashboard_config, sample_entities)
        
        assert result["conflicts_found"] is False
        assert result["existing_cards"] == []
        assert result["existing_updated"] is False

    async def test_handle_card_conflicts_with_existing_card(self, dashboard_service, sample_dashboard_with_existing_card, sample_entities):
        """Test conflict handling with existing Roost Scheduler card."""
        with patch.object(dashboard_service, '_determine_conflict_resolution_strategy') as mock_strategy:
            mock_strategy.return_value = "update_existing"
            
            result = await dashboard_service.handle_dashboard_conflicts(
                sample_dashboard_with_existing_card, sample_entities
            )
            
            assert result["conflicts_found"] is True
            assert len(result["existing_cards"]) == 1
            assert result["existing_updated"] is True
            assert "Updated existing card" in result["resolution_actions"][0]

    async def test_handle_card_conflicts_remove_duplicates(self, dashboard_service, sample_entities):
        """Test conflict handling with duplicate card removal."""
        dashboard_config = {
            "views": [
                {
                    "title": "Home",
                    "cards": [
                        {"type": "custom:roost-scheduler-card", "entities": ["climate.old1"]},
                        {"type": "custom:roost-scheduler-card", "entities": ["climate.old2"]},
                        {"type": "custom:roost-scheduler-card", "entities": ["climate.old3"]}
                    ]
                }
            ]
        }
        
        with patch.object(dashboard_service, '_determine_conflict_resolution_strategy') as mock_strategy:
            mock_strategy.return_value = "remove_duplicates"
            
            result = await dashboard_service.handle_dashboard_conflicts(dashboard_config, sample_entities)
            
            assert result["conflicts_found"] is True
            assert len(result["existing_cards"]) == 3
            # Should have removed 2 duplicate cards (keeping the first one)
            assert len(dashboard_config["views"][0]["cards"]) == 1

    async def test_handle_dashboard_access_failures_with_fallback(self, dashboard_service):
        """Test dashboard access failure handling with successful fallback."""
        error_info = {"failed_dashboard": "lovelace", "error": "Access denied"}
        
        with patch.object(dashboard_service, '_get_available_dashboards') as mock_available, \
             patch.object(dashboard_service, '_load_dashboard_config') as mock_load:
            
            mock_available.return_value = ["custom_dashboard", "another_dashboard"]
            mock_load.side_effect = [{"views": []}, None]  # First succeeds, second fails
            
            result = await dashboard_service.handle_dashboard_access_failures(error_info)
            
            assert result["recovery_attempted"] is True
            assert result["recovery_successful"] is True
            assert result["fallback_dashboard"] == "custom_dashboard"

    async def test_handle_dashboard_access_failures_no_fallback(self, dashboard_service):
        """Test dashboard access failure handling with no available fallback."""
        error_info = {"failed_dashboard": "lovelace", "error": "Access denied"}
        
        with patch.object(dashboard_service, '_get_available_dashboards') as mock_available, \
             patch.object(dashboard_service, '_load_dashboard_config') as mock_load:
            
            mock_available.return_value = ["custom_dashboard"]
            mock_load.return_value = None  # All dashboards fail
            
            result = await dashboard_service.handle_dashboard_access_failures(error_info)
            
            assert result["recovery_attempted"] is True
            assert result["recovery_successful"] is False
            assert len(result["manual_steps_required"]) > 0
            assert "Check Home Assistant dashboard configuration" in result["manual_steps_required"][0]

    async def test_load_dashboard_config_default(self, dashboard_service):
        """Test loading default dashboard configuration."""
        with patch('custom_components.roost_scheduler.dashboard_service.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = {"views": []}
            mock_store_class.return_value = mock_store
            
            result = await dashboard_service._load_dashboard_config("lovelace")
            
            assert result == {"views": []}
            mock_store_class.assert_called_once_with(dashboard_service.hass, 1, "lovelace")

    async def test_load_dashboard_config_custom(self, dashboard_service):
        """Test loading custom dashboard configuration."""
        with patch('custom_components.roost_scheduler.dashboard_service.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = {"views": []}
            mock_store_class.return_value = mock_store
            
            result = await dashboard_service._load_dashboard_config("custom_dashboard")
            
            assert result == {"views": []}
            mock_store_class.assert_called_once_with(dashboard_service.hass, 1, "lovelace.custom_dashboard")

    async def test_load_dashboard_config_none_result(self, dashboard_service):
        """Test loading dashboard configuration when store returns None."""
        with patch('custom_components.roost_scheduler.dashboard_service.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.return_value = None
            mock_store_class.return_value = mock_store
            
            result = await dashboard_service._load_dashboard_config("lovelace")
            
            assert result == {}

    async def test_load_dashboard_config_exception(self, dashboard_service):
        """Test loading dashboard configuration with exception."""
        with patch('custom_components.roost_scheduler.dashboard_service.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_load.side_effect = Exception("Storage error")
            mock_store_class.return_value = mock_store
            
            result = await dashboard_service._load_dashboard_config("lovelace")
            
            assert result is None

    async def test_save_dashboard_config_default(self, dashboard_service):
        """Test saving default dashboard configuration."""
        config = {"views": []}
        
        with patch('custom_components.roost_scheduler.dashboard_service.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            
            await dashboard_service._save_dashboard_config("lovelace", config)
            
            mock_store.async_save.assert_called_once_with(config)
            mock_store_class.assert_called_once_with(dashboard_service.hass, 1, "lovelace")

    async def test_save_dashboard_config_custom(self, dashboard_service):
        """Test saving custom dashboard configuration."""
        config = {"views": []}
        
        with patch('custom_components.roost_scheduler.dashboard_service.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store
            
            await dashboard_service._save_dashboard_config("custom_dashboard", config)
            
            mock_store.async_save.assert_called_once_with(config)
            mock_store_class.assert_called_once_with(dashboard_service.hass, 1, "lovelace.custom_dashboard")

    async def test_save_dashboard_config_exception(self, dashboard_service):
        """Test saving dashboard configuration with exception."""
        config = {"views": []}
        
        with patch('custom_components.roost_scheduler.dashboard_service.Store') as mock_store_class:
            mock_store = AsyncMock()
            mock_store.async_save.side_effect = Exception("Storage error")
            mock_store_class.return_value = mock_store
            
            with pytest.raises(Exception, match="Storage error"):
                await dashboard_service._save_dashboard_config("lovelace", config)

    async def test_get_target_view_no_views(self, dashboard_service):
        """Test getting target view when no views exist."""
        dashboard_config = {}
        
        view, index = await dashboard_service._get_target_view(dashboard_config, None)
        
        assert view is not None
        assert view["title"] == "Home"
        assert view["path"] == "default"
        assert index == 0
        assert len(dashboard_config["views"]) == 1

    async def test_get_target_view_specific_view_by_path(self, dashboard_service, sample_dashboard_config):
        """Test getting specific view by path."""
        view, index = await dashboard_service._get_target_view(sample_dashboard_config, "climate")
        
        assert view["title"] == "Climate"
        assert view["path"] == "climate"
        assert index == 1

    async def test_get_target_view_specific_view_by_title(self, dashboard_service, sample_dashboard_config):
        """Test getting specific view by title."""
        view, index = await dashboard_service._get_target_view(sample_dashboard_config, "climate")
        
        assert view["title"] == "Climate"
        assert index == 1

    async def test_get_target_view_default_first(self, dashboard_service, sample_dashboard_config):
        """Test getting default (first) view."""
        view, index = await dashboard_service._get_target_view(sample_dashboard_config, None)
        
        assert view["title"] == "Home"
        assert index == 0

    async def test_handle_card_conflicts_in_view(self, dashboard_service, sample_entities):
        """Test handling card conflicts within a specific view."""
        target_view = {
            "title": "Home",
            "cards": [
                {"type": "custom:roost-scheduler-card", "entities": ["climate.existing"]}
            ]
        }
        
        result = await dashboard_service._handle_card_conflicts(target_view, sample_entities)
        
        assert result["conflicts_found"] is True
        assert result["existing_updated"] is True
        # Should merge entities
        expected_entities = ["climate.existing", "climate.living_room", "climate.bedroom"]
        assert set(target_view["cards"][0]["entities"]) == set(expected_entities)

    async def test_is_roost_scheduler_card_exact_match(self, dashboard_service):
        """Test identifying Roost Scheduler card with exact type match."""
        card = {"type": "custom:roost-scheduler-card"}
        
        result = dashboard_service._is_roost_scheduler_card(card)
        
        assert result is True

    async def test_is_roost_scheduler_card_partial_match(self, dashboard_service):
        """Test identifying Roost Scheduler card with partial type match."""
        card = {"type": "custom:roost-scheduler-card-v2"}
        
        result = dashboard_service._is_roost_scheduler_card(card)
        
        assert result is True

    async def test_is_roost_scheduler_card_no_match(self, dashboard_service):
        """Test identifying non-Roost Scheduler card."""
        card = {"type": "weather-forecast"}
        
        result = dashboard_service._is_roost_scheduler_card(card)
        
        assert result is False

    async def test_determine_conflict_resolution_strategy_single_card(self, dashboard_service):
        """Test conflict resolution strategy for single existing card."""
        existing_cards = [{"view_index": 0, "card_index": 0}]
        
        strategy = await dashboard_service._determine_conflict_resolution_strategy(
            existing_cards, ["climate.new"]
        )
        
        assert strategy == "update_existing"

    async def test_determine_conflict_resolution_strategy_multiple_cards(self, dashboard_service):
        """Test conflict resolution strategy for multiple existing cards."""
        existing_cards = [
            {"view_index": 0, "card_index": 0},
            {"view_index": 0, "card_index": 1},
            {"view_index": 1, "card_index": 0}
        ]
        
        strategy = await dashboard_service._determine_conflict_resolution_strategy(
            existing_cards, ["climate.new"]
        )
        
        assert strategy == "remove_duplicates"

    async def test_determine_conflict_resolution_strategy_no_conflicts(self, dashboard_service):
        """Test conflict resolution strategy with no conflicts."""
        existing_cards = []
        
        strategy = await dashboard_service._determine_conflict_resolution_strategy(
            existing_cards, ["climate.new"]
        )
        
        assert strategy == "no_action"

    async def test_get_available_dashboards(self, dashboard_service):
        """Test getting available dashboards."""
        dashboards = await dashboard_service._get_available_dashboards()
        
        assert "lovelace" in dashboards
        assert isinstance(dashboards, list)


class TestDataClasses:
    """Test cases for data classes."""

    def test_dashboard_card_config_defaults(self):
        """Test DashboardCardConfig with default values."""
        config = DashboardCardConfig(dashboard_id="test")
        
        assert config.dashboard_id == "test"
        assert config.view_id is None
        assert config.card_position is None
        assert config.default_entity is None
        assert config.card_settings == {}

    def test_dashboard_card_config_with_settings(self):
        """Test DashboardCardConfig with custom settings."""
        settings = {"theme": "dark", "compact": True}
        config = DashboardCardConfig(
            dashboard_id="test",
            view_id="home",
            card_position=1,
            default_entity="climate.test",
            card_settings=settings
        )
        
        assert config.dashboard_id == "test"
        assert config.view_id == "home"
        assert config.card_position == 1
        assert config.default_entity == "climate.test"
        assert config.card_settings == settings

    def test_dashboard_integration_status_defaults(self):
        """Test DashboardIntegrationStatus with default values."""
        status = DashboardIntegrationStatus()
        
        assert status.resources_registered is False
        assert status.card_available_in_picker is False
        assert status.card_added_to_dashboard is False
        assert status.dashboard_id is None
        assert status.error_messages == []
        assert status.next_steps == []

    def test_dashboard_integration_status_with_values(self):
        """Test DashboardIntegrationStatus with custom values."""
        errors = ["Error 1", "Error 2"]
        steps = ["Step 1", "Step 2"]
        status = DashboardIntegrationStatus(
            resources_registered=True,
            card_available_in_picker=True,
            card_added_to_dashboard=True,
            dashboard_id="lovelace",
            error_messages=errors,
            next_steps=steps
        )
        
        assert status.resources_registered is True
        assert status.card_available_in_picker is True
        assert status.card_added_to_dashboard is True
        assert status.dashboard_id == "lovelace"
        assert status.error_messages == errors
        assert status.next_steps == steps

    def test_card_installation_result_defaults(self):
        """Test CardInstallationResult with default values."""
        result = CardInstallationResult(success=True, dashboard_id="test")
        
        assert result.success is True
        assert result.dashboard_id == "test"
        assert result.view_id is None
        assert result.card_position is None
        assert result.error_message is None
        assert result.conflict_resolved is False
        assert result.existing_card_updated is False

    def test_card_installation_result_with_values(self):
        """Test CardInstallationResult with custom values."""
        result = CardInstallationResult(
            success=False,
            dashboard_id="test",
            view_id="home",
            card_position=2,
            error_message="Installation failed",
            conflict_resolved=True,
            existing_card_updated=True
        )
        
        assert result.success is False
        assert result.dashboard_id == "test"
        assert result.view_id == "home"
        assert result.card_position == 2
        assert result.error_message == "Installation failed"
        assert result.conflict_resolved is True
        assert result.existing_card_updated is True