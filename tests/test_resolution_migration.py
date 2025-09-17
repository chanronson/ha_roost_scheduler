"""Tests for schedule resolution migration functionality."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.roost_scheduler.schedule_manager import ScheduleManager
from custom_components.roost_scheduler.models import ScheduleData, ScheduleSlot, BufferConfig


@pytest.fixture
def sample_schedule_data():
    """Create sample schedule data for testing."""
    return ScheduleData(
        version="0.3.0",
        entities_tracked=["climate.living_room"],
        presence_entities=["device_tracker.phone"],
        presence_rule="anyone_home",
        presence_timeout_seconds=600,
        buffer={"global": BufferConfig(time_minutes=15, value_delta=2.0)},
        ui={"resolution_minutes": 30},
        schedules={
            "home": {
                "monday": [
                    ScheduleSlot(
                        day="monday",
                        start_time="06:00",
                        end_time="08:30",
                        target_value=20.0,
                        entity_domain="climate"
                    ),
                    ScheduleSlot(
                        day="monday",
                        start_time="08:30",
                        end_time="18:00",
                        target_value=18.0,
                        entity_domain="climate"
                    ),
                    ScheduleSlot(
                        day="monday",
                        start_time="18:00",
                        end_time="22:00",
                        target_value=21.0,
                        entity_domain="climate"
                    )
                ]
            },
            "away": {
                "monday": [
                    ScheduleSlot(
                        day="monday",
                        start_time="00:00",
                        end_time="23:59",
                        target_value=16.0,
                        entity_domain="climate"
                    )
                ]
            }
        },
        metadata={"created_at": datetime.now().isoformat()}
    )


@pytest.fixture
def schedule_manager(sample_schedule_data):
    """Create a schedule manager with mocked dependencies."""
    hass = MagicMock()
    storage_service = AsyncMock()
    presence_manager = AsyncMock()
    buffer_manager = MagicMock()
    
    manager = ScheduleManager(hass, storage_service, presence_manager, buffer_manager)
    manager._schedule_data = sample_schedule_data
    
    return manager


class TestResolutionMigration:
    """Test schedule resolution migration functionality."""
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_preview_30_to_15(self, schedule_manager):
        """Test migration preview from 30 to 15 minutes."""
        result = await schedule_manager.migrate_resolution(15, preview=True)
        
        assert result["status"] == "preview"
        assert result["current_resolution"] == 30
        assert result["new_resolution"] == 15
        assert "changes" in result
        assert "warnings" in result
        assert result["summary"]["precision_gain"] is True
        assert result["summary"]["data_loss_risk"] is False
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_preview_30_to_60(self, schedule_manager):
        """Test migration preview from 30 to 60 minutes."""
        result = await schedule_manager.migrate_resolution(60, preview=True)
        
        assert result["status"] == "preview"
        assert result["current_resolution"] == 30
        assert result["new_resolution"] == 60
        assert result["summary"]["precision_gain"] is False
        assert result["summary"]["data_loss_risk"] is True
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_no_change(self, schedule_manager):
        """Test migration when resolution is already the target."""
        result = await schedule_manager.migrate_resolution(30, preview=True)
        
        assert result["status"] == "no_change"
        assert result["current_resolution"] == 30
        assert result["new_resolution"] == 30
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_invalid_resolution(self, schedule_manager):
        """Test migration with invalid resolution."""
        with pytest.raises(ValueError, match="Resolution must be one of"):
            await schedule_manager.migrate_resolution(45, preview=True)
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_apply_changes(self, schedule_manager):
        """Test actually applying migration changes."""
        # Mock storage service save method
        schedule_manager.storage_service.save_schedules = AsyncMock()
        
        # Mock event bus
        schedule_manager.hass.bus.async_fire = MagicMock()
        
        result = await schedule_manager.migrate_resolution(15, preview=False)
        
        assert result["status"] == "applied"
        assert result["new_resolution"] == 15
        
        # Verify storage was saved
        schedule_manager.storage_service.save_schedules.assert_called_once()
        
        # Verify event was fired
        schedule_manager.hass.bus.async_fire.assert_called_once()
        
        # Verify schedule data was updated
        assert schedule_manager._schedule_data.ui["resolution_minutes"] == 15
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_no_data(self, schedule_manager):
        """Test migration when no schedule data is available."""
        schedule_manager._schedule_data = None
        schedule_manager.storage_service.load_schedules = AsyncMock(return_value=None)
        
        with pytest.raises(ValueError, match="No schedule data available"):
            await schedule_manager.migrate_resolution(15, preview=True)
    
    def test_time_to_minutes_conversion(self, schedule_manager):
        """Test time string to minutes conversion."""
        assert schedule_manager._time_to_minutes("00:00") == 0
        assert schedule_manager._time_to_minutes("06:30") == 390
        assert schedule_manager._time_to_minutes("12:00") == 720
        assert schedule_manager._time_to_minutes("23:59") == 1439
    
    def test_minutes_to_time_conversion(self, schedule_manager):
        """Test minutes to time string conversion."""
        assert schedule_manager._minutes_to_time(0) == "00:00"
        assert schedule_manager._minutes_to_time(390) == "06:30"
        assert schedule_manager._minutes_to_time(720) == "12:00"
        assert schedule_manager._minutes_to_time(1439) == "23:59"
        assert schedule_manager._minutes_to_time(1440) == "23:59"  # Overflow handling - cap at 23:59
    
    def test_align_to_resolution(self, schedule_manager):
        """Test time alignment to resolution boundaries."""
        # Test 15-minute alignment
        assert schedule_manager._align_to_resolution(370, 15) == 360  # 6:10 -> 6:00
        assert schedule_manager._align_to_resolution(370, 15, align_up=True) == 375  # 6:10 -> 6:15
        
        # Test 60-minute alignment
        assert schedule_manager._align_to_resolution(390, 60) == 360  # 6:30 -> 6:00
        assert schedule_manager._align_to_resolution(390, 60, align_up=True) == 420  # 6:30 -> 7:00
    
    def test_migrate_day_slots_increase_resolution(self, schedule_manager):
        """Test migrating day slots to higher resolution (30 to 15 minutes)."""
        slots = [
            ScheduleSlot(
                day="monday",
                start_time="06:10",  # Not aligned to 15-min boundary
                end_time="08:25",    # Not aligned to 15-min boundary
                target_value=20.0,
                entity_domain="climate"
            )
        ]
        
        migrated_slots, changes = schedule_manager._migrate_day_slots(slots, 30, 15)
        
        assert len(migrated_slots) == 1
        assert migrated_slots[0].start_time == "06:00"  # Aligned down
        assert migrated_slots[0].end_time == "08:30"    # Aligned up
        assert len(changes["changes"]) == 1
    
    def test_migrate_day_slots_decrease_resolution(self, schedule_manager):
        """Test migrating day slots to lower resolution (30 to 60 minutes)."""
        slots = [
            ScheduleSlot(
                day="monday",
                start_time="06:15",
                end_time="07:45",
                target_value=20.0,
                entity_domain="climate"
            )
        ]
        
        migrated_slots, changes = schedule_manager._migrate_day_slots(slots, 30, 60)
        
        assert len(migrated_slots) == 1
        assert migrated_slots[0].start_time == "06:00"  # Aligned down
        assert migrated_slots[0].end_time == "08:00"    # Aligned up, minimum 1 hour
    
    def test_merge_overlapping_slots(self, schedule_manager):
        """Test merging overlapping slots with same target value."""
        slots = [
            ScheduleSlot(
                day="monday",
                start_time="06:00",
                end_time="07:00",
                target_value=20.0,
                entity_domain="climate"
            ),
            ScheduleSlot(
                day="monday",
                start_time="07:00",
                end_time="08:00",
                target_value=20.0,  # Same target value
                entity_domain="climate"
            ),
            ScheduleSlot(
                day="monday",
                start_time="08:00",
                end_time="09:00",
                target_value=21.0,  # Different target value
                entity_domain="climate"
            )
        ]
        
        merged = schedule_manager._merge_overlapping_slots(slots)
        
        assert len(merged) == 2  # First two should be merged
        assert merged[0].start_time == "06:00"
        assert merged[0].end_time == "08:00"
        assert merged[0].target_value == 20.0
        assert merged[1].start_time == "08:00"
        assert merged[1].end_time == "09:00"
        assert merged[1].target_value == 21.0
    
    def test_validate_migrated_slots_overlaps(self, schedule_manager):
        """Test validation of migrated slots for overlaps."""
        slots = [
            ScheduleSlot(
                day="monday",
                start_time="06:00",
                end_time="08:00",
                target_value=20.0,
                entity_domain="climate"
            ),
            ScheduleSlot(
                day="monday",
                start_time="07:30",  # Overlaps with previous
                end_time="09:00",
                target_value=21.0,
                entity_domain="climate"
            )
        ]
        
        warnings = schedule_manager._validate_migrated_slots(slots, "monday", "home")
        
        assert len(warnings) > 0
        assert any("Overlapping slots" in warning for warning in warnings)
    
    def test_validate_migrated_slots_gaps(self, schedule_manager):
        """Test validation of migrated slots for gaps."""
        slots = [
            ScheduleSlot(
                day="monday",
                start_time="06:00",
                end_time="08:00",
                target_value=20.0,
                entity_domain="climate"
            ),
            ScheduleSlot(
                day="monday",
                start_time="09:00",  # Gap from 08:00 to 09:00
                end_time="10:00",
                target_value=21.0,
                entity_domain="climate"
            )
        ]
        
        warnings = schedule_manager._validate_migrated_slots(slots, "monday", "home")
        
        assert len(warnings) > 0
        assert any("Gap after migration" in warning for warning in warnings)


class TestResolutionMigrationService:
    """Test the resolution migration service."""
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_service_valid_call(self, schedule_manager):
        """Test valid service call for resolution migration."""
        call = MagicMock()
        call.data = {
            "resolution_minutes": 15,
            "preview": True
        }
        
        # Mock the migrate_resolution method
        schedule_manager.migrate_resolution = AsyncMock(return_value={
            "status": "preview",
            "current_resolution": 30,
            "new_resolution": 15
        })
        
        # Mock event bus
        schedule_manager.hass.bus.async_fire = MagicMock()
        
        await schedule_manager.migrate_resolution_service(call)
        
        schedule_manager.migrate_resolution.assert_called_once_with(15, True)
        schedule_manager.hass.bus.async_fire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_service_invalid_resolution(self, schedule_manager):
        """Test service call with invalid resolution."""
        call = MagicMock()
        call.data = {
            "resolution_minutes": 45,  # Invalid
            "preview": True
        }
        
        with pytest.raises(ValueError, match="resolution_minutes must be 15, 30, or 60"):
            await schedule_manager.migrate_resolution_service(call)
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_service_missing_resolution(self, schedule_manager):
        """Test service call with missing resolution parameter."""
        call = MagicMock()
        call.data = {
            "preview": True
        }
        
        with pytest.raises(ValueError, match="resolution_minutes is required"):
            await schedule_manager.migrate_resolution_service(call)
    
    @pytest.mark.asyncio
    async def test_migrate_resolution_service_invalid_preview_type(self, schedule_manager):
        """Test service call with invalid preview parameter type."""
        call = MagicMock()
        call.data = {
            "resolution_minutes": 15,
            "preview": "yes"  # Should be boolean
        }
        
        with pytest.raises(ValueError, match="preview must be a boolean"):
            await schedule_manager.migrate_resolution_service(call)


@pytest.mark.asyncio
async def test_integration_resolution_migration_workflow():
    """Test complete resolution migration workflow."""
    # Create a more complex schedule for testing
    schedule_data = ScheduleData(
        version="0.3.0",
        entities_tracked=["climate.living_room"],
        presence_entities=["device_tracker.phone"],
        presence_rule="anyone_home",
        presence_timeout_seconds=600,
        buffer={"global": BufferConfig(time_minutes=15, value_delta=2.0)},
        ui={"resolution_minutes": 30},
        schedules={
            "home": {
                "monday": [
                    ScheduleSlot(day="monday", start_time="06:15", end_time="08:45", target_value=20.0, entity_domain="climate"),
                    ScheduleSlot(day="monday", start_time="08:45", end_time="17:30", target_value=18.0, entity_domain="climate"),
                    ScheduleSlot(day="monday", start_time="17:30", end_time="22:15", target_value=21.0, entity_domain="climate")
                ],
                "tuesday": [
                    ScheduleSlot(day="tuesday", start_time="07:00", end_time="09:00", target_value=19.5, entity_domain="climate")
                ]
            },
            "away": {
                "monday": [
                    ScheduleSlot(day="monday", start_time="00:00", end_time="23:59", target_value=16.0, entity_domain="climate")
                ]
            }
        },
        metadata={"created_at": datetime.now().isoformat()}
    )
    
    # Create manager with mocked dependencies
    hass = MagicMock()
    storage_service = AsyncMock()
    presence_manager = AsyncMock()
    buffer_manager = MagicMock()
    
    manager = ScheduleManager(hass, storage_service, presence_manager, buffer_manager)
    manager._schedule_data = schedule_data
    
    # Test preview first
    preview_result = await manager.migrate_resolution(60, preview=True)
    
    assert preview_result["status"] == "preview"
    assert preview_result["current_resolution"] == 30
    assert preview_result["new_resolution"] == 60
    assert preview_result["total_slots_before"] == 5
    assert preview_result["summary"]["data_loss_risk"] is True
    
    # Test actual migration
    storage_service.save_schedules = AsyncMock()
    hass.bus.async_fire = MagicMock()
    
    apply_result = await manager.migrate_resolution(60, preview=False)
    
    assert apply_result["status"] == "applied"
    assert manager._schedule_data.ui["resolution_minutes"] == 60
    
    # Verify storage was called
    storage_service.save_schedules.assert_called_once()
    
    # Verify event was fired
    hass.bus.async_fire.assert_called_once()
    
    # Verify metadata was updated
    assert "last_migration" in manager._schedule_data.metadata
    assert manager._schedule_data.metadata["last_migration"]["from_resolution"] == 30
    assert manager._schedule_data.metadata["last_migration"]["to_resolution"] == 60