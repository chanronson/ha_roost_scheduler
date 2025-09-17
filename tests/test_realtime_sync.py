"""Tests for real-time synchronization and conflict resolution."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from custom_components.roost_scheduler import _check_for_conflicts
from custom_components.roost_scheduler.schedule_manager import ScheduleManager
from custom_components.roost_scheduler.models import ScheduleSlot


@pytest.fixture
def mock_schedule_manager():
    """Create a mock schedule manager."""
    manager = MagicMock(spec=ScheduleManager)
    return manager


@pytest.mark.asyncio
async def test_check_for_conflicts_no_conflicts(mock_schedule_manager):
    """Test conflict checking when no conflicts exist."""
    # Mock current grid with matching values
    mock_schedule_manager.get_schedule_grid.return_value = {
        "monday": [
            {
                "start_time": "08:00",
                "end_time": "09:00", 
                "target_value": 20.0
            }
        ]
    }
    
    changes = [
        {"day": "monday", "time": "08:30", "value": 20.0}
    ]
    
    conflicts = await _check_for_conflicts(
        mock_schedule_manager, 
        "climate.test", 
        "home", 
        changes, 
        "update_123"
    )
    
    assert len(conflicts) == 0


@pytest.mark.asyncio
async def test_check_for_conflicts_with_conflicts(mock_schedule_manager):
    """Test conflict checking when conflicts exist."""
    # Mock current grid with different values
    mock_schedule_manager.get_schedule_grid.return_value = {
        "monday": [
            {
                "start_time": "08:00",
                "end_time": "09:00",
                "target_value": 22.0  # Different from proposed 20.0
            }
        ]
    }
    
    changes = [
        {"day": "monday", "time": "08:30", "value": 20.0}
    ]
    
    conflicts = await _check_for_conflicts(
        mock_schedule_manager,
        "climate.test",
        "home", 
        changes,
        "update_123"
    )
    
    assert len(conflicts) == 1
    assert conflicts[0]["day"] == "monday"
    assert conflicts[0]["time"] == "08:30"
    assert conflicts[0]["proposed_value"] == 20.0
    assert conflicts[0]["current_value"] == 22.0
    assert conflicts[0]["update_id"] == "update_123"


@pytest.mark.asyncio
async def test_check_for_conflicts_no_existing_slot(mock_schedule_manager):
    """Test conflict checking when no existing slot exists."""
    # Mock empty grid
    mock_schedule_manager.get_schedule_grid.return_value = {
        "monday": []
    }
    
    changes = [
        {"day": "monday", "time": "08:30", "value": 20.0}
    ]
    
    conflicts = await _check_for_conflicts(
        mock_schedule_manager,
        "climate.test",
        "home",
        changes,
        "update_123"
    )
    
    # No conflicts when no existing slot
    assert len(conflicts) == 0


@pytest.mark.asyncio
async def test_check_for_conflicts_error_handling(mock_schedule_manager):
    """Test conflict checking handles errors gracefully."""
    # Mock exception in get_schedule_grid
    mock_schedule_manager.get_schedule_grid.side_effect = Exception("Database error")
    
    changes = [
        {"day": "monday", "time": "08:30", "value": 20.0}
    ]
    
    conflicts = await _check_for_conflicts(
        mock_schedule_manager,
        "climate.test",
        "home",
        changes,
        "update_123"
    )
    
    # Should return empty list on error
    assert len(conflicts) == 0


@pytest.mark.asyncio
async def test_check_for_conflicts_multiple_changes(mock_schedule_manager):
    """Test conflict checking with multiple changes."""
    # Mock grid with mixed conflicts
    mock_schedule_manager.get_schedule_grid.return_value = {
        "monday": [
            {
                "start_time": "08:00",
                "end_time": "09:00",
                "target_value": 20.0  # Matches first change
            },
            {
                "start_time": "10:00", 
                "end_time": "11:00",
                "target_value": 25.0  # Conflicts with second change
            }
        ]
    }
    
    changes = [
        {"day": "monday", "time": "08:30", "value": 20.0},  # No conflict
        {"day": "monday", "time": "10:30", "value": 22.0}   # Conflict
    ]
    
    conflicts = await _check_for_conflicts(
        mock_schedule_manager,
        "climate.test",
        "home",
        changes,
        "update_123"
    )
    
    # Should detect only the conflicting change
    assert len(conflicts) == 1
    assert conflicts[0]["time"] == "10:30"
    assert conflicts[0]["proposed_value"] == 22.0
    assert conflicts[0]["current_value"] == 25.0


@pytest.mark.asyncio
async def test_check_for_conflicts_tolerance(mock_schedule_manager):
    """Test conflict checking respects tolerance threshold."""
    # Mock grid with small difference (within tolerance)
    mock_schedule_manager.get_schedule_grid.return_value = {
        "monday": [
            {
                "start_time": "08:00",
                "end_time": "09:00",
                "target_value": 20.05  # Small difference from 20.0
            }
        ]
    }
    
    changes = [
        {"day": "monday", "time": "08:30", "value": 20.0}
    ]
    
    conflicts = await _check_for_conflicts(
        mock_schedule_manager,
        "climate.test",
        "home",
        changes,
        "update_123"
    )
    
    # Should not detect conflict due to small difference (< 0.1)
    assert len(conflicts) == 0


class TestScheduleManagerEventEmission:
    """Test event emission in schedule manager."""
    
    @pytest.fixture
    def mock_hass(self):
        """Create mock Home Assistant instance."""
        hass = MagicMock()
        hass.bus = MagicMock()
        hass.bus.async_fire = MagicMock()  # async_fire is actually synchronous in HA
        return hass
    
    @pytest.fixture
    def mock_storage_service(self):
        """Create mock storage service."""
        storage = MagicMock()
        storage.save_schedules = AsyncMock()
        return storage
    
    @pytest.fixture
    def mock_presence_manager(self):
        """Create mock presence manager."""
        presence = MagicMock()
        return presence
    
    @pytest.fixture
    def mock_buffer_manager(self):
        """Create mock buffer manager."""
        buffer = MagicMock()
        return buffer
    
    @pytest.fixture
    def schedule_manager(self, mock_hass, mock_storage_service, mock_presence_manager, mock_buffer_manager):
        """Create schedule manager with mocked dependencies."""
        from custom_components.roost_scheduler.schedule_manager import ScheduleManager
        from custom_components.roost_scheduler.models import ScheduleData
        
        manager = ScheduleManager(
            mock_hass,
            mock_storage_service, 
            mock_presence_manager,
            mock_buffer_manager
        )
        
        # Mock schedule data
        manager._schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.test"],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        return manager
    
    @pytest.mark.asyncio
    async def test_update_slot_emits_event(self, schedule_manager, mock_hass):
        """Test that update_slot emits schedule_updated event."""
        # Mock successful slot update
        with patch.object(schedule_manager._schedule_data, 'to_dict', return_value={}):
            result = await schedule_manager.update_slot(
                entity_id="climate.test",
                mode="home",
                day="monday", 
                time_slot="08:00-09:00",
                target={"temperature": 20.0}
            )
        
        assert result is True
        
        # Verify event was emitted
        mock_hass.bus.async_fire.assert_called_once()
        call_args = mock_hass.bus.async_fire.call_args
        
        assert call_args[0][0] == "roost_scheduler_schedule_updated"
        event_data = call_args[0][1]
        
        assert event_data["entity_id"] == "climate.test"
        assert event_data["mode"] == "home"
        assert event_data["day"] == "monday"
        assert event_data["time_slot"] == "08:00-09:00"
        assert event_data["target_value"] == 20.0
        assert len(event_data["changes"]) == 1
        assert event_data["changes"][0]["day"] == "monday"
        assert event_data["changes"][0]["time"] == "08:00-09:00"
        assert event_data["changes"][0]["value"] == 20.0