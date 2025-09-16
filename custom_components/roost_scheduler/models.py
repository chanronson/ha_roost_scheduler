"""Data models for the Roost Scheduler integration."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class BufferConfig:
    """Configuration for intelligent buffering."""
    time_minutes: int
    value_delta: float
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BufferConfig:
        """Create from dictionary."""
        return cls(
            time_minutes=data.get("time_minutes", 15),
            value_delta=data.get("value_delta", 2.0),
            enabled=data.get("enabled", True)
        )


@dataclass
class ScheduleSlot:
    """Represents a single schedule time slot."""
    day: str  # monday, tuesday, etc.
    start_time: str  # "06:00"
    end_time: str   # "08:30"
    target_value: float
    entity_domain: str
    buffer_override: Optional[BufferConfig] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "start": self.start_time,
            "end": self.end_time,
            "target": {
                "domain": self.entity_domain,
                "temperature": self.target_value
            }
        }
        if self.buffer_override:
            result["buffer_override"] = self.buffer_override.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, day: str, data: Dict[str, Any]) -> ScheduleSlot:
        """Create from dictionary."""
        target = data.get("target", {})
        buffer_data = data.get("buffer_override")
        buffer_override = BufferConfig.from_dict(buffer_data) if buffer_data else None
        
        return cls(
            day=day,
            start_time=data.get("start", "00:00"),
            end_time=data.get("end", "23:59"),
            target_value=target.get("temperature", 20.0),
            entity_domain=target.get("domain", "climate"),
            buffer_override=buffer_override
        )


@dataclass
class EntityState:
    """Tracks state of a managed entity."""
    entity_id: str
    current_value: float
    last_manual_change: Optional[datetime]
    last_scheduled_change: Optional[datetime]
    buffer_config: BufferConfig
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": self.entity_id,
            "current_value": self.current_value,
            "last_manual_change": self.last_manual_change.isoformat() if self.last_manual_change else None,
            "last_scheduled_change": self.last_scheduled_change.isoformat() if self.last_scheduled_change else None,
            "buffer_config": self.buffer_config.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EntityState:
        """Create from dictionary."""
        last_manual = None
        if data.get("last_manual_change"):
            last_manual = datetime.fromisoformat(data["last_manual_change"])
        
        last_scheduled = None
        if data.get("last_scheduled_change"):
            last_scheduled = datetime.fromisoformat(data["last_scheduled_change"])
        
        return cls(
            entity_id=data["entity_id"],
            current_value=data.get("current_value", 0.0),
            last_manual_change=last_manual,
            last_scheduled_change=last_scheduled,
            buffer_config=BufferConfig.from_dict(data.get("buffer_config", {}))
        )


@dataclass
class ScheduleData:
    """Complete schedule configuration."""
    version: str
    entities_tracked: list[str]
    presence_entities: list[str]
    presence_rule: str
    presence_timeout_seconds: int
    buffer: Dict[str, BufferConfig]
    ui: Dict[str, Any]
    schedules: Dict[str, Dict[str, list[ScheduleSlot]]]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        schedules_dict = {}
        for mode, mode_schedules in self.schedules.items():
            schedules_dict[mode] = {}
            for day, slots in mode_schedules.items():
                schedules_dict[mode][day] = [slot.to_dict() for slot in slots]
        
        buffer_dict = {}
        for key, config in self.buffer.items():
            buffer_dict[key] = config.to_dict()
        
        return {
            "version": self.version,
            "entities_tracked": self.entities_tracked,
            "presence_entities": self.presence_entities,
            "presence_rule": self.presence_rule,
            "presence_timeout_seconds": self.presence_timeout_seconds,
            "buffer": buffer_dict,
            "ui": self.ui,
            "schedules": schedules_dict,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScheduleData:
        """Create from dictionary."""
        # Parse buffer configs
        buffer = {}
        for key, config_data in data.get("buffer", {}).items():
            buffer[key] = BufferConfig.from_dict(config_data)
        
        # Parse schedules
        schedules = {}
        for mode, mode_data in data.get("schedules", {}).items():
            schedules[mode] = {}
            for day, slots_data in mode_data.items():
                schedules[mode][day] = [
                    ScheduleSlot.from_dict(day, slot_data) 
                    for slot_data in slots_data
                ]
        
        return cls(
            version=data.get("version", "0.3.0"),
            entities_tracked=data.get("entities_tracked", []),
            presence_entities=data.get("presence_entities", []),
            presence_rule=data.get("presence_rule", "anyone_home"),
            presence_timeout_seconds=data.get("presence_timeout_seconds", 600),
            buffer=buffer,
            ui=data.get("ui", {}),
            schedules=schedules,
            metadata=data.get("metadata", {})
        )
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> ScheduleData:
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)