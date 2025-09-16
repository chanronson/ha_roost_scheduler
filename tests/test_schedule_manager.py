"""Tests for the ScheduleManager class."""
import pytest
import pytest_asyncio
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.roost_scheduler.schedule_manager import ScheduleManager
from custom_components.roost_scheduler.models import ScheduleSlot, ScheduleData, BufferConfig
from custom_components.roost_scheduler.const import MODE_HOME, MODE_AWAY, WEEKDAYS

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states = MagicMock()
    return hass


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service."""
    storage = MagicMock()
    storage.load_schedules = AsyncMock()
    storage.save_schedules = AsyncMock()
    return storage


@pytest.fixture
def mock_presence_manager():
    """Create a mock presence manager."""
    presence = MagicMock()
    presence.get_current_mode = AsyncMock(return_value=MODE_HOME)
    return presence


@pytest.fixture
def mock_buffer_manager():
    """Create a mock buffer manager."""
    buffer = MagicMock()
    buffer.should_suppress_change = MagicMock(return_value=False)
    buffer.update_current_value = MagicMock()
    buffer.update_scheduled_change = MagicMock()
    return buffer


@pytest.fixture
def sample_schedule_data():
    """Create sample schedule data for testing."""
    home_slot = ScheduleSlot(
        day="monday",
        start_time="08:00",
        end_time="18:00",
        target_value=22.0,
        entity_domain="climate"
    )
    
    away_slot = ScheduleSlot(
        day="monday",
        start_time="08:00",
        end_time="18:00",
        target_value=16.0,
        entity_domain="climate"
    )
    
    return ScheduleData(
        version="0.3.0",
        entities_tracked=["climate.living_room"],
        presence_entities=["device_tracker.phone"],
        presence_rule="anyone_home",
        presence_timeout_seconds=600,
        buffer={"global": BufferConfig(time_minutes=15, value_delta=2.0)},
        ui={"resolution_minutes": 30},
        schedules={
            MODE_HOME: {"monday": [home_slot]},
            MODE_AWAY: {"monday": [away_slot]}
        },
        metadata={"created_at": "2025-09-16T12:00:00Z"}
    )


@pytest.fixture
def schedule_manager(mock_hass, mock_storage_service, mock_presence_manager, mock_buffer_manager):
    """Create a ScheduleManager instance for testing."""
    return ScheduleManager(
        mock_hass,
        mock_storage_service,
        mock_presence_manager,
        mock_buffer_manager
    )


class TestScheduleManager:
    """Test cases for ScheduleManager."""
    
    @pytest.mark.asyncio
    async def test_evaluate_current_slot_found(self, schedule_manager, mock_storage_service, 
                                              mock_presence_manager, sample_schedule_data):
        """Test evaluating current slot when a matching slot exists."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        mock_presence_manager.get_current_mode.return_value = MODE_HOME
        
        # Mock current time to be within the slot (10:00 AM on Monday)
        mock_datetime = datetime(2025, 9, 15, 10, 0)  # Monday 10:00 AM
        with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Test
            result = await schedule_manager.evaluate_current_slot("climate.living_room")
            
            # Verify
            assert result is not None
            assert result.target_value == 22.0
            assert result.start_time == "08:00"
            assert result.end_time == "18:00"
    
    @pytest.mark.asyncio
    async def test_evaluate_current_slot_not_found(self, schedule_manager, mock_storage_service,
                                                  mock_presence_manager, sample_schedule_data):
        """Test evaluating current slot when no matching slot exists."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        mock_presence_manager.get_current_mode.return_value = MODE_HOME
        
        # Mock current time to be outside the slot (6:00 AM on Monday)
        mock_datetime = datetime(2025, 9, 15, 6, 0)  # Monday 6:00 AM
        with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Test
            result = await schedule_manager.evaluate_current_slot("climate.living_room")
            
            # Verify
            assert result is None
    
    @pytest.mark.asyncio
    async def test_evaluate_current_slot_entity_not_tracked(self, schedule_manager, mock_storage_service,
                                                           mock_presence_manager, sample_schedule_data):
        """Test evaluating current slot for an entity that is not tracked."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        
        # Test
        result = await schedule_manager.evaluate_current_slot("climate.bedroom")
        
        # Verify
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_schedule_grid_success(self, schedule_manager, mock_storage_service, sample_schedule_data):
        """Test getting schedule grid successfully."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        
        # Test
        result = await schedule_manager.get_schedule_grid("climate.living_room", MODE_HOME)
        
        # Verify
        assert result["entity_id"] == "climate.living_room"
        assert result["mode"] == MODE_HOME
        assert result["resolution_minutes"] == 30
        assert "grid" in result
        assert "monday" in result["grid"]
        assert len(result["grid"]["monday"]) == 1
        assert result["grid"]["monday"][0]["target"]["temperature"] == 22.0
    
    @pytest.mark.asyncio
    async def test_get_schedule_grid_entity_not_tracked(self, schedule_manager, mock_storage_service, sample_schedule_data):
        """Test getting schedule grid for untracked entity."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        
        # Test
        result = await schedule_manager.get_schedule_grid("climate.bedroom", MODE_HOME)
        
        # Verify
        assert "error" in result
        assert "not tracked" in result["error"]
    
    @pytest.mark.asyncio
    async def test_apply_schedule_success(self, schedule_manager, mock_hass, mock_storage_service,
                                        mock_presence_manager, mock_buffer_manager, sample_schedule_data):
        """Test applying schedule successfully."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        mock_presence_manager.get_current_mode.return_value = MODE_HOME
        mock_buffer_manager.should_suppress_change.return_value = False
        
        # Mock entity state
        mock_entity_state = MagicMock()
        mock_entity_state.state = "20.0"
        mock_entity_state.attributes = {"temperature": 20.0}
        mock_hass.states.get.return_value = mock_entity_state
        
        # Mock current time to be within the slot
        mock_datetime = datetime(2025, 9, 15, 10, 0)  # Monday 10:00 AM
        with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Test
            result = await schedule_manager.apply_schedule("climate.living_room")
            
            # Verify
            assert result is True
            mock_hass.services.async_call.assert_called_once_with(
                "climate",
                "set_temperature",
                {"entity_id": "climate.living_room", "temperature": 22.0}
            )
            mock_buffer_manager.update_scheduled_change.assert_called_once_with("climate.living_room", 22.0)
    
    @pytest.mark.asyncio
    async def test_apply_schedule_suppressed_by_buffer(self, schedule_manager, mock_hass, mock_storage_service,
                                                      mock_presence_manager, mock_buffer_manager, sample_schedule_data):
        """Test applying schedule when suppressed by buffer logic."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        mock_presence_manager.get_current_mode.return_value = MODE_HOME
        mock_buffer_manager.should_suppress_change.return_value = True  # Suppress the change
        
        # Mock entity state
        mock_entity_state = MagicMock()
        mock_entity_state.state = "22.0"  # Already at target
        mock_entity_state.attributes = {"temperature": 22.0}
        mock_hass.states.get.return_value = mock_entity_state
        
        # Mock current time to be within the slot
        mock_datetime = datetime(2025, 9, 15, 10, 0)  # Monday 10:00 AM
        with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Test
            result = await schedule_manager.apply_schedule("climate.living_room")
            
            # Verify
            assert result is True  # Still successful, just suppressed
            mock_hass.services.async_call.assert_not_called()  # No service call made
            mock_buffer_manager.update_scheduled_change.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_apply_schedule_entity_unavailable(self, schedule_manager, mock_hass, mock_storage_service,
                                                    mock_presence_manager, sample_schedule_data):
        """Test applying schedule when entity is unavailable."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        mock_presence_manager.get_current_mode.return_value = MODE_HOME
        
        # Mock unavailable entity state
        mock_entity_state = MagicMock()
        mock_entity_state.state = "unavailable"
        mock_hass.states.get.return_value = mock_entity_state
        
        # Mock current time to be within the slot
        mock_datetime = datetime(2025, 9, 15, 10, 0)  # Monday 10:00 AM
        with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Test
            result = await schedule_manager.apply_schedule("climate.living_room")
            
            # Verify
            assert result is False
            mock_hass.services.async_call.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_apply_schedule_no_active_slot(self, schedule_manager, mock_storage_service,
                                                mock_presence_manager, sample_schedule_data):
        """Test applying schedule when no active slot exists."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        mock_presence_manager.get_current_mode.return_value = MODE_HOME
        
        # Mock current time to be outside any slot
        mock_datetime = datetime(2025, 9, 15, 6, 0)  # Monday 6:00 AM (outside slot)
        with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Test
            result = await schedule_manager.apply_schedule("climate.living_room")
            
            # Verify
            assert result is False
    
    @pytest.mark.asyncio
    async def test_update_slot_success(self, schedule_manager, mock_storage_service,
                                      mock_presence_manager, sample_schedule_data):
        """Test updating a schedule slot successfully."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        mock_presence_manager.get_current_mode.return_value = MODE_HOME
        
        # Test
        result = await schedule_manager.update_slot(
            "climate.living_room",
            "monday",
            "08:00-18:00",
            {"temperature": 23.0, "domain": "climate"}
        )
        
        # Verify
        assert result is True
        mock_storage_service.save_schedules.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_slot_invalid_time_format(self, schedule_manager, mock_storage_service, sample_schedule_data):
        """Test updating slot with invalid time format."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        
        # Test
        result = await schedule_manager.update_slot(
            "climate.living_room",
            "monday",
            "invalid-time",
            {"temperature": 23.0}
        )
        
        # Verify
        assert result is False
        mock_storage_service.save_schedules.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_validate_entity_compatibility_climate(self, schedule_manager, mock_hass):
        """Test entity compatibility validation for climate entity."""
        # Setup
        mock_entity_state = MagicMock()
        mock_entity_state.state = "heat"
        mock_entity_state.attributes = {
            "supported_features": 1,  # SUPPORT_TARGET_TEMPERATURE
            "temperature": 20.0,
            "min_temp": 5.0,
            "max_temp": 35.0
        }
        mock_hass.states.get.return_value = mock_entity_state
        
        # Test
        result = await schedule_manager.validate_entity_compatibility("climate.living_room")
        
        # Verify
        assert result["compatible"] is True
        assert result["domain"] == "climate"
        assert result["current_temperature"] == 20.0
    
    @pytest.mark.asyncio
    async def test_validate_entity_compatibility_unsupported_domain(self, schedule_manager, mock_hass):
        """Test entity compatibility validation for unsupported domain."""
        # Setup
        mock_entity_state = MagicMock()
        mock_entity_state.state = "on"
        mock_hass.states.get.return_value = mock_entity_state
        
        # Test
        result = await schedule_manager.validate_entity_compatibility("light.living_room")
        
        # Verify
        assert result["compatible"] is False
        assert "Unsupported domain" in result["reason"]
    
    @pytest.mark.asyncio
    async def test_apply_all_tracked_entities(self, schedule_manager, mock_hass, mock_storage_service,
                                            mock_presence_manager, mock_buffer_manager, sample_schedule_data):
        """Test applying schedules to all tracked entities."""
        # Setup
        mock_storage_service.load_schedules.return_value = sample_schedule_data.to_dict()
        mock_presence_manager.get_current_mode.return_value = MODE_HOME
        mock_buffer_manager.should_suppress_change.return_value = False
        
        # Mock entity state
        mock_entity_state = MagicMock()
        mock_entity_state.state = "20.0"
        mock_entity_state.attributes = {"temperature": 20.0}
        mock_hass.states.get.return_value = mock_entity_state
        
        # Mock current time to be within the slot
        mock_datetime = datetime(2025, 9, 15, 10, 0)  # Monday 10:00 AM
        with patch('custom_components.roost_scheduler.schedule_manager.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Test
            results = await schedule_manager.apply_all_tracked_entities()
            
            # Verify
            assert len(results) == 1
            assert results["climate.living_room"] is True
            mock_hass.services.async_call.assert_called_once()
    
    def test_time_in_slot_normal_range(self, schedule_manager):
        """Test time_in_slot method with normal time range."""
        current_time = time(10, 0)
        assert schedule_manager._time_in_slot(current_time, "08:00", "18:00") is True
        assert schedule_manager._time_in_slot(current_time, "12:00", "18:00") is False
    
    def test_time_in_slot_midnight_crossover(self, schedule_manager):
        """Test time_in_slot method with midnight crossover."""
        # Test time that crosses midnight (22:00 to 06:00)
        current_time = time(23, 0)  # 11 PM
        assert schedule_manager._time_in_slot(current_time, "22:00", "06:00") is True
        
        current_time = time(2, 0)  # 2 AM
        assert schedule_manager._time_in_slot(current_time, "22:00", "06:00") is True
        
        current_time = time(10, 0)  # 10 AM
        assert schedule_manager._time_in_slot(current_time, "22:00", "06:00") is False
    
    def test_calculate_slot_duration(self, schedule_manager):
        """Test slot duration calculation."""
        # Normal duration
        duration = schedule_manager._calculate_slot_duration("08:00", "18:00")
        assert duration == 600  # 10 hours * 60 minutes
        
        # Midnight crossover
        duration = schedule_manager._calculate_slot_duration("22:00", "06:00")
        assert duration == 480  # 8 hours * 60 minutes
    
    def test_time_to_minutes(self, schedule_manager):
        """Test time to minutes conversion."""
        assert schedule_manager._time_to_minutes("00:00") == 0
        assert schedule_manager._time_to_minutes("12:00") == 720
        assert schedule_manager._time_to_minutes("23:59") == 1439
    
    def test_minutes_to_time(self, schedule_manager):
        """Test minutes to time conversion."""
        assert schedule_manager._minutes_to_time(0) == "00:00"
        assert schedule_manager._minutes_to_time(720) == "12:00"
        assert schedule_manager._minutes_to_time(1439) == "23:59"