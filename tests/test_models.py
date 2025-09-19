"""Tests for data models."""
import pytest
from datetime import datetime, time
from unittest.mock import MagicMock

from custom_components.roost_scheduler.models import (
    PresenceConfig,
    BufferConfig,
    GlobalBufferConfig,
    ScheduleSlot,
    EntityState,
    ScheduleData
)


class TestScheduleDataEnhanced:
    """Test enhanced ScheduleData model with manager configurations."""
    
    def test_schedule_data_with_presence_config(self):
        """Test ScheduleData with presence_config field."""
        presence_config = PresenceConfig(
            entities=["device_tracker.phone"],
            rule="anyone_home",
            timeout_seconds=300
        )
        
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone"],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            presence_config=presence_config
        )
        
        assert schedule_data.presence_config == presence_config
        assert schedule_data.presence_config.entities == ["device_tracker.phone"]
        assert schedule_data.presence_config.rule == "anyone_home"
        assert schedule_data.presence_config.timeout_seconds == 300
    
    def test_schedule_data_with_buffer_config(self):
        """Test ScheduleData with buffer_config field."""
        buffer_config = GlobalBufferConfig(
            time_minutes=20,
            value_delta=3.0,
            enabled=True,
            apply_to="climate"
        )
        
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            buffer_config=buffer_config
        )
        
        assert schedule_data.buffer_config == buffer_config
        assert schedule_data.buffer_config.time_minutes == 20
        assert schedule_data.buffer_config.value_delta == 3.0
        assert schedule_data.buffer_config.enabled is True
    
    def test_schedule_data_with_both_configs(self):
        """Test ScheduleData with both presence_config and buffer_config."""
        presence_config = PresenceConfig(
            entities=["device_tracker.phone", "person.user"],
            rule="everyone_home",
            timeout_seconds=900
        )
        
        buffer_config = GlobalBufferConfig(
            time_minutes=25,
            value_delta=1.5,
            enabled=False,
            apply_to="climate"
        )
        
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room", "climate.bedroom"],
            presence_entities=["device_tracker.phone", "person.user"],
            presence_rule="everyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            presence_config=presence_config,
            buffer_config=buffer_config
        )
        
        assert schedule_data.presence_config == presence_config
        assert schedule_data.buffer_config == buffer_config
        assert schedule_data.presence_config.rule == "everyone_home"
        assert schedule_data.buffer_config.enabled is False
    
    def test_schedule_data_without_new_configs(self):
        """Test ScheduleData without new configuration fields (backward compatibility)."""
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone"],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        assert schedule_data.presence_config is None
        assert schedule_data.buffer_config is None
    
    def test_schedule_data_serialization_with_presence_config(self):
        """Test ScheduleData to_dict with presence_config."""
        presence_config = PresenceConfig(
            entities=["device_tracker.phone"],
            rule="custom",
            timeout_seconds=1200,
            custom_template="{{ is_state('device_tracker.phone', 'home') }}"
        )
        
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone"],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            presence_config=presence_config
        )
        
        data_dict = schedule_data.to_dict()
        
        assert "presence_config" in data_dict
        assert data_dict["presence_config"]["entities"] == ["device_tracker.phone"]
        assert data_dict["presence_config"]["rule"] == "custom"
        assert data_dict["presence_config"]["timeout_seconds"] == 1200
        assert data_dict["presence_config"]["custom_template"] == "{{ is_state('device_tracker.phone', 'home') }}"
    
    def test_schedule_data_serialization_with_buffer_config(self):
        """Test ScheduleData to_dict with buffer_config."""
        entity_override = BufferConfig(
            time_minutes=10,
            value_delta=1.0,
            enabled=True,
            apply_to="climate"
        )
        
        buffer_config = GlobalBufferConfig(
            time_minutes=15,
            value_delta=2.0,
            enabled=True,
            apply_to="climate"
        )
        buffer_config.set_entity_override("climate.bedroom", entity_override)
        
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=[],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            buffer_config=buffer_config
        )
        
        data_dict = schedule_data.to_dict()
        
        assert "buffer_config" in data_dict
        assert data_dict["buffer_config"]["time_minutes"] == 15
        assert data_dict["buffer_config"]["value_delta"] == 2.0
        assert data_dict["buffer_config"]["enabled"] is True
        assert "entity_overrides" in data_dict["buffer_config"]
        assert "climate.bedroom" in data_dict["buffer_config"]["entity_overrides"]
    
    def test_schedule_data_serialization_without_new_configs(self):
        """Test ScheduleData to_dict without new configuration fields."""
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone"],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={}
        )
        
        data_dict = schedule_data.to_dict()
        
        # New fields should not be present when None
        assert "presence_config" not in data_dict
        assert "buffer_config" not in data_dict
    
    def test_schedule_data_deserialization_with_presence_config(self):
        """Test ScheduleData from_dict with presence_config."""
        data = {
            "version": "0.3.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "buffer": {},
            "ui": {},
            "schedules": {"home": {}, "away": {}},
            "metadata": {},
            "presence_config": {
                "entities": ["device_tracker.phone", "person.user"],
                "rule": "everyone_home",
                "timeout_seconds": 1800,
                "override_entities": {
                    "force_home": "input_boolean.custom_force_home",
                    "force_away": "input_boolean.custom_force_away"
                },
                "custom_template": None,
                "template_entities": []
            }
        }
        
        schedule_data = ScheduleData.from_dict(data)
        
        assert schedule_data.presence_config is not None
        assert schedule_data.presence_config.entities == ["device_tracker.phone", "person.user"]
        assert schedule_data.presence_config.rule == "everyone_home"
        assert schedule_data.presence_config.timeout_seconds == 1800
        assert schedule_data.presence_config.override_entities["force_home"] == "input_boolean.custom_force_home"
    
    def test_schedule_data_deserialization_with_buffer_config(self):
        """Test ScheduleData from_dict with buffer_config."""
        data = {
            "version": "0.3.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": [],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "buffer": {},
            "ui": {},
            "schedules": {"home": {}, "away": {}},
            "metadata": {},
            "buffer_config": {
                "time_minutes": 30,
                "value_delta": 4.0,
                "enabled": False,
                "apply_to": "climate",
                "entity_overrides": {
                    "climate.bedroom": {
                        "time_minutes": 20,
                        "value_delta": 1.5,
                        "enabled": True,
                        "apply_to": "climate"
                    }
                }
            }
        }
        
        schedule_data = ScheduleData.from_dict(data)
        
        assert schedule_data.buffer_config is not None
        assert schedule_data.buffer_config.time_minutes == 30
        assert schedule_data.buffer_config.value_delta == 4.0
        assert schedule_data.buffer_config.enabled is False
        assert "climate.bedroom" in schedule_data.buffer_config.entity_overrides
        
        bedroom_config = schedule_data.buffer_config.entity_overrides["climate.bedroom"]
        assert bedroom_config.time_minutes == 20
        assert bedroom_config.value_delta == 1.5
        assert bedroom_config.enabled is True
    
    def test_schedule_data_deserialization_without_new_configs(self):
        """Test ScheduleData from_dict without new configuration fields (backward compatibility)."""
        data = {
            "version": "0.3.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "buffer": {},
            "ui": {},
            "schedules": {"home": {}, "away": {}},
            "metadata": {}
        }
        
        schedule_data = ScheduleData.from_dict(data)
        
        assert schedule_data.presence_config is None
        assert schedule_data.buffer_config is None
        # Ensure other fields are still properly loaded
        assert schedule_data.version == "0.3.0"
        assert schedule_data.entities_tracked == ["climate.living_room"]
        assert schedule_data.presence_entities == ["device_tracker.phone"]
    
    def test_schedule_data_validation_with_invalid_presence_config(self):
        """Test ScheduleData validation with invalid presence_config."""
        with pytest.raises(ValueError, match="presence_config must be PresenceConfig instance or None"):
            ScheduleData(
                version="0.3.0",
                entities_tracked=["climate.living_room"],
                presence_entities=[],
                presence_rule="anyone_home",
                presence_timeout_seconds=600,
                buffer={},
                ui={},
                schedules={"home": {}, "away": {}},
                metadata={},
                presence_config="invalid"  # Should be PresenceConfig instance
            )
    
    def test_schedule_data_validation_with_invalid_buffer_config(self):
        """Test ScheduleData validation with invalid buffer_config."""
        with pytest.raises(ValueError, match="buffer_config must be GlobalBufferConfig instance or None"):
            ScheduleData(
                version="0.3.0",
                entities_tracked=["climate.living_room"],
                presence_entities=[],
                presence_rule="anyone_home",
                presence_timeout_seconds=600,
                buffer={},
                ui={},
                schedules={"home": {}, "away": {}},
                metadata={},
                buffer_config={"invalid": "dict"}  # Should be GlobalBufferConfig instance
            )
    
    def test_schedule_data_validation_with_invalid_presence_config_data(self):
        """Test ScheduleData validation with PresenceConfig that has invalid data."""
        with pytest.raises(ValueError):
            # This should fail during PresenceConfig validation
            invalid_presence_config = PresenceConfig(
                entities=["invalid_entity_format"],  # Missing domain.entity format
                rule="anyone_home"
            )
            
            ScheduleData(
                version="0.3.0",
                entities_tracked=["climate.living_room"],
                presence_entities=[],
                presence_rule="anyone_home",
                presence_timeout_seconds=600,
                buffer={},
                ui={},
                schedules={"home": {}, "away": {}},
                metadata={},
                presence_config=invalid_presence_config
            )
    
    def test_schedule_data_json_serialization_with_configs(self):
        """Test ScheduleData JSON serialization with both configs."""
        presence_config = PresenceConfig(
            entities=["device_tracker.phone"],
            rule="anyone_home",
            timeout_seconds=600
        )
        
        buffer_config = GlobalBufferConfig(
            time_minutes=15,
            value_delta=2.0,
            enabled=True,
            apply_to="climate"
        )
        
        schedule_data = ScheduleData(
            version="0.3.0",
            entities_tracked=["climate.living_room"],
            presence_entities=["device_tracker.phone"],
            presence_rule="anyone_home",
            presence_timeout_seconds=600,
            buffer={},
            ui={},
            schedules={"home": {}, "away": {}},
            metadata={},
            presence_config=presence_config,
            buffer_config=buffer_config
        )
        
        json_str = schedule_data.to_json()
        
        # Should be valid JSON
        assert isinstance(json_str, str)
        assert "presence_config" in json_str
        assert "buffer_config" in json_str
        
        # Should be able to deserialize back
        restored_schedule_data = ScheduleData.from_json(json_str)
        
        assert restored_schedule_data.presence_config is not None
        assert restored_schedule_data.buffer_config is not None
        assert restored_schedule_data.presence_config.entities == ["device_tracker.phone"]
        assert restored_schedule_data.buffer_config.time_minutes == 15
    
    def test_schedule_data_migration_compatibility(self):
        """Test that ScheduleData maintains compatibility with older data formats."""
        # Simulate old format data without presence_config and buffer_config
        old_format_data = {
            "version": "0.2.0",
            "entities_tracked": ["climate.living_room"],
            "presence_entities": ["device_tracker.phone"],
            "presence_rule": "anyone_home",
            "presence_timeout_seconds": 600,
            "buffer": {
                "global": {
                    "time_minutes": 15,
                    "value_delta": 2.0,
                    "enabled": True,
                    "apply_to": "climate"
                }
            },
            "ui": {},
            "schedules": {"home": {}, "away": {}},
            "metadata": {}
            # Note: no presence_config or buffer_config fields
        }
        
        # Should load successfully without the new fields
        schedule_data = ScheduleData.from_dict(old_format_data)
        
        assert schedule_data.presence_config is None
        assert schedule_data.buffer_config is None
        assert schedule_data.version == "0.2.0"
        assert schedule_data.entities_tracked == ["climate.living_room"]
        assert schedule_data.presence_entities == ["device_tracker.phone"]
        
        # Should serialize without the new fields
        serialized = schedule_data.to_dict()
        assert "presence_config" not in serialized
        assert "buffer_config" not in serialized