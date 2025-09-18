"""Data models for the Roost Scheduler integration."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, time
from typing import Any, Dict, Optional, List


@dataclass
class PresenceConfig:
    """Configuration for presence detection."""
    entities: List[str] = field(default_factory=list)
    rule: str = "anyone_home"
    timeout_seconds: int = 600
    override_entities: Dict[str, str] = field(default_factory=lambda: {
        "force_home": "input_boolean.roost_force_home",
        "force_away": "input_boolean.roost_force_away"
    })
    custom_template: Optional[str] = None
    template_entities: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate presence configuration after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate presence configuration values."""
        # Validate entities list
        if not isinstance(self.entities, list):
            raise ValueError("entities must be a list")
        for entity_id in self.entities:
            if not isinstance(entity_id, str) or not entity_id:
                raise ValueError(f"Invalid entity_id in entities: {entity_id}")
            if '.' not in entity_id:
                raise ValueError(f"entity_id must be in format 'domain.entity': {entity_id}")
        
        # Validate rule
        valid_rules = {"anyone_home", "everyone_home", "custom"}
        if self.rule not in valid_rules:
            raise ValueError(f"rule must be one of {valid_rules}, got {self.rule}")
        
        # Validate timeout_seconds
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds < 0:
            raise ValueError(f"timeout_seconds must be a non-negative integer, got {self.timeout_seconds}")
        if self.timeout_seconds > 86400:  # 24 hours in seconds
            raise ValueError(f"timeout_seconds cannot exceed 86400 (24 hours), got {self.timeout_seconds}")
        
        # Validate override_entities
        if not isinstance(self.override_entities, dict):
            raise ValueError("override_entities must be a dictionary")
        for key, entity_id in self.override_entities.items():
            if not isinstance(entity_id, str) or not entity_id:
                raise ValueError(f"Invalid override entity_id for {key}: {entity_id}")
            if '.' not in entity_id:
                raise ValueError(f"Override entity_id must be in format 'domain.entity': {entity_id}")
        
        # Validate custom_template
        if self.custom_template is not None and not isinstance(self.custom_template, str):
            raise ValueError("custom_template must be a string or None")
        
        # Validate template_entities
        if not isinstance(self.template_entities, list):
            raise ValueError("template_entities must be a list")
        for entity_id in self.template_entities:
            if not isinstance(entity_id, str) or not entity_id:
                raise ValueError(f"Invalid entity_id in template_entities: {entity_id}")
            if '.' not in entity_id:
                raise ValueError(f"Template entity_id must be in format 'domain.entity': {entity_id}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PresenceConfig':
        """Create from dictionary loaded from storage."""
        return cls(
            entities=data.get("entities", []),
            rule=data.get("rule", "anyone_home"),
            timeout_seconds=data.get("timeout_seconds", 600),
            override_entities=data.get("override_entities", {
                "force_home": "input_boolean.roost_force_home",
                "force_away": "input_boolean.roost_force_away"
            }),
            custom_template=data.get("custom_template"),
            template_entities=data.get("template_entities", [])
        )


@dataclass
class BufferConfig:
    """Configuration for intelligent buffering."""
    time_minutes: int
    value_delta: float
    enabled: bool = True
    apply_to: str = "climate"
    
    def __post_init__(self):
        """Validate buffer configuration after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate buffer configuration values."""
        if not isinstance(self.time_minutes, int) or self.time_minutes < 0:
            raise ValueError(f"time_minutes must be a non-negative integer, got {self.time_minutes}")
        if self.time_minutes > 1440:  # 24 hours in minutes
            raise ValueError(f"time_minutes cannot exceed 1440 (24 hours), got {self.time_minutes}")
        
        if not isinstance(self.value_delta, (int, float)) or self.value_delta < 0:
            raise ValueError(f"value_delta must be a non-negative number, got {self.value_delta}")
        if self.value_delta > 50:  # Reasonable upper limit for temperature delta
            raise ValueError(f"value_delta cannot exceed 50, got {self.value_delta}")
        
        if not isinstance(self.enabled, bool):
            raise ValueError(f"enabled must be a boolean, got {type(self.enabled)}")
        
        if not isinstance(self.apply_to, str) or not self.apply_to:
            raise ValueError(f"apply_to must be a non-empty string, got {self.apply_to}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BufferConfig:
        """Create from dictionary."""
        return cls(
            time_minutes=data.get("time_minutes", 15),
            value_delta=data.get("value_delta", 2.0),
            enabled=data.get("enabled", True),
            apply_to=data.get("apply_to", "climate")
        )


@dataclass
class GlobalBufferConfig:
    """Global buffer configuration with entity-specific overrides."""
    time_minutes: int = 15
    value_delta: float = 2.0
    enabled: bool = True
    apply_to: str = "climate"
    entity_overrides: Dict[str, BufferConfig] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate global buffer configuration after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate global buffer configuration values."""
        if not isinstance(self.time_minutes, int) or self.time_minutes < 0:
            raise ValueError(f"time_minutes must be a non-negative integer, got {self.time_minutes}")
        if self.time_minutes > 1440:  # 24 hours in minutes
            raise ValueError(f"time_minutes cannot exceed 1440 (24 hours), got {self.time_minutes}")
        
        if not isinstance(self.value_delta, (int, float)) or self.value_delta < 0:
            raise ValueError(f"value_delta must be a non-negative number, got {self.value_delta}")
        if self.value_delta > 50:  # Reasonable upper limit for temperature delta
            raise ValueError(f"value_delta cannot exceed 50, got {self.value_delta}")
        
        if not isinstance(self.enabled, bool):
            raise ValueError(f"enabled must be a boolean, got {type(self.enabled)}")
        
        if not isinstance(self.apply_to, str) or not self.apply_to:
            raise ValueError(f"apply_to must be a non-empty string, got {self.apply_to}")
        
        if not isinstance(self.entity_overrides, dict):
            raise ValueError("entity_overrides must be a dictionary")
        
        # Validate each entity override
        for entity_id, config in self.entity_overrides.items():
            if not isinstance(entity_id, str) or '.' not in entity_id:
                raise ValueError(f"Invalid entity_id in overrides: {entity_id}")
            if not isinstance(config, BufferConfig):
                raise ValueError(f"Override for {entity_id} must be BufferConfig instance")
            config.validate()
    
    def get_effective_config(self, entity_id: str) -> BufferConfig:
        """Get effective buffer configuration for an entity."""
        if entity_id in self.entity_overrides:
            return self.entity_overrides[entity_id]
        
        # Return global config as BufferConfig
        return BufferConfig(
            time_minutes=self.time_minutes,
            value_delta=self.value_delta,
            enabled=self.enabled,
            apply_to=self.apply_to
        )
    
    def set_entity_override(self, entity_id: str, config: BufferConfig) -> None:
        """Set entity-specific buffer override."""
        if not isinstance(entity_id, str) or '.' not in entity_id:
            raise ValueError(f"Invalid entity_id: {entity_id}")
        if not isinstance(config, BufferConfig):
            raise ValueError("config must be BufferConfig instance")
        
        config.validate()
        self.entity_overrides[entity_id] = config
    
    def remove_entity_override(self, entity_id: str) -> bool:
        """Remove entity-specific buffer override."""
        return self.entity_overrides.pop(entity_id, None) is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "time_minutes": self.time_minutes,
            "value_delta": self.value_delta,
            "enabled": self.enabled,
            "apply_to": self.apply_to,
            "entity_overrides": {
                entity_id: config.to_dict() 
                for entity_id, config in self.entity_overrides.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlobalBufferConfig':
        """Create from dictionary loaded from storage."""
        entity_overrides = {}
        for entity_id, config_data in data.get("entity_overrides", {}).items():
            entity_overrides[entity_id] = BufferConfig.from_dict(config_data)
        
        return cls(
            time_minutes=data.get("time_minutes", 15),
            value_delta=data.get("value_delta", 2.0),
            enabled=data.get("enabled", True),
            apply_to=data.get("apply_to", "climate"),
            entity_overrides=entity_overrides
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
    
    # Valid days of the week
    VALID_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    VALID_DOMAINS = {"climate", "input_number", "number"}
    
    def __post_init__(self):
        """Validate schedule slot after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate schedule slot values."""
        # Validate day
        if not isinstance(self.day, str) or self.day.lower() not in self.VALID_DAYS:
            raise ValueError(f"day must be one of {self.VALID_DAYS}, got {self.day}")
        self.day = self.day.lower()
        
        # Validate time format
        if not self._is_valid_time_format(self.start_time):
            raise ValueError(f"start_time must be in HH:MM format, got {self.start_time}")
        if not self._is_valid_time_format(self.end_time):
            raise ValueError(f"end_time must be in HH:MM format, got {self.end_time}")
        
        # Validate time range
        start = self._parse_time(self.start_time)
        end = self._parse_time(self.end_time)
        if start >= end:
            raise ValueError(f"start_time ({self.start_time}) must be before end_time ({self.end_time})")
        
        # Validate target value
        if not isinstance(self.target_value, (int, float)):
            raise ValueError(f"target_value must be a number, got {type(self.target_value)}")
        if self.target_value < -50 or self.target_value > 50:
            raise ValueError(f"target_value must be between -50 and 50, got {self.target_value}")
        
        # Validate entity domain
        if not isinstance(self.entity_domain, str) or self.entity_domain not in self.VALID_DOMAINS:
            raise ValueError(f"entity_domain must be one of {self.VALID_DOMAINS}, got {self.entity_domain}")
        
        # Validate buffer override if present
        if self.buffer_override is not None:
            self.buffer_override.validate()
    
    def _is_valid_time_format(self, time_str: str) -> bool:
        """Check if time string is in valid HH:MM format."""
        if not isinstance(time_str, str):
            return False
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return bool(re.match(pattern, time_str))
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object."""
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid time format: {time_str}")
    
    def overlaps_with(self, other: 'ScheduleSlot') -> bool:
        """Check if this slot overlaps with another slot."""
        if self.day != other.day:
            return False
        
        start1 = self._parse_time(self.start_time)
        end1 = self._parse_time(self.end_time)
        start2 = other._parse_time(other.start_time)
        end2 = other._parse_time(other.end_time)
        
        return start1 < end2 and start2 < end1
    
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
    
    def __post_init__(self):
        """Validate entity state after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate entity state values."""
        # Validate entity_id format
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise ValueError("entity_id must be a non-empty string")
        
        # Basic entity_id format validation (domain.entity)
        if '.' not in self.entity_id or self.entity_id.count('.') != 1:
            raise ValueError(f"entity_id must be in format 'domain.entity', got {self.entity_id}")
        
        domain, entity = self.entity_id.split('.')
        if not domain or not entity:
            raise ValueError(f"entity_id must have non-empty domain and entity parts, got {self.entity_id}")
        
        # Validate current_value
        if not isinstance(self.current_value, (int, float)):
            raise ValueError(f"current_value must be a number, got {type(self.current_value)}")
        
        # Validate datetime objects
        if self.last_manual_change is not None and not isinstance(self.last_manual_change, datetime):
            raise ValueError(f"last_manual_change must be datetime or None, got {type(self.last_manual_change)}")
        
        if self.last_scheduled_change is not None and not isinstance(self.last_scheduled_change, datetime):
            raise ValueError(f"last_scheduled_change must be datetime or None, got {type(self.last_scheduled_change)}")
        
        # Validate buffer_config
        if not isinstance(self.buffer_config, BufferConfig):
            raise ValueError(f"buffer_config must be BufferConfig instance, got {type(self.buffer_config)}")
        
        self.buffer_config.validate()
    
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
            try:
                last_manual = datetime.fromisoformat(data["last_manual_change"])
            except ValueError as e:
                raise ValueError(f"Invalid last_manual_change format: {e}")
        
        last_scheduled = None
        if data.get("last_scheduled_change"):
            try:
                last_scheduled = datetime.fromisoformat(data["last_scheduled_change"])
            except ValueError as e:
                raise ValueError(f"Invalid last_scheduled_change format: {e}")
        
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
    presence_config: Optional[PresenceConfig] = None
    buffer_config: Optional[GlobalBufferConfig] = None
    
    # Valid presence rules
    VALID_PRESENCE_RULES = {"anyone_home", "everyone_home", "custom"}
    VALID_MODES = {"home", "away"}
    
    def __post_init__(self):
        """Validate schedule data after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate complete schedule data integrity."""
        # Validate version format
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        
        # Validate entities_tracked
        if not isinstance(self.entities_tracked, list):
            raise ValueError("entities_tracked must be a list")
        for entity_id in self.entities_tracked:
            if not isinstance(entity_id, str) or '.' not in entity_id:
                raise ValueError(f"Invalid entity_id in entities_tracked: {entity_id}")
        
        # Validate presence_entities
        if not isinstance(self.presence_entities, list):
            raise ValueError("presence_entities must be a list")
        for entity_id in self.presence_entities:
            if not isinstance(entity_id, str) or '.' not in entity_id:
                raise ValueError(f"Invalid entity_id in presence_entities: {entity_id}")
        
        # Validate presence_rule
        if self.presence_rule not in self.VALID_PRESENCE_RULES:
            raise ValueError(f"presence_rule must be one of {self.VALID_PRESENCE_RULES}, got {self.presence_rule}")
        
        # Validate presence_timeout_seconds
        if not isinstance(self.presence_timeout_seconds, int) or self.presence_timeout_seconds < 0:
            raise ValueError(f"presence_timeout_seconds must be a non-negative integer, got {self.presence_timeout_seconds}")
        
        # Validate buffer configs
        if not isinstance(self.buffer, dict):
            raise ValueError("buffer must be a dictionary")
        for key, config in self.buffer.items():
            if not isinstance(config, BufferConfig):
                raise ValueError(f"buffer[{key}] must be BufferConfig instance")
            config.validate()
        
        # Validate UI config
        if not isinstance(self.ui, dict):
            raise ValueError("ui must be a dictionary")
        
        # Validate schedules structure
        if not isinstance(self.schedules, dict):
            raise ValueError("schedules must be a dictionary")
        
        for mode, mode_schedules in self.schedules.items():
            if mode not in self.VALID_MODES:
                raise ValueError(f"schedule mode must be one of {self.VALID_MODES}, got {mode}")
            
            if not isinstance(mode_schedules, dict):
                raise ValueError(f"schedules[{mode}] must be a dictionary")
            
            for day, slots in mode_schedules.items():
                if day.lower() not in ScheduleSlot.VALID_DAYS:
                    raise ValueError(f"Invalid day in schedules[{mode}]: {day}")
                
                if not isinstance(slots, list):
                    raise ValueError(f"schedules[{mode}][{day}] must be a list")
                
                # Validate each slot and check for overlaps
                validated_slots = []
                for slot in slots:
                    if not isinstance(slot, ScheduleSlot):
                        raise ValueError(f"All slots must be ScheduleSlot instances")
                    slot.validate()
                    
                    # Check for overlaps with previously validated slots
                    for existing_slot in validated_slots:
                        if slot.overlaps_with(existing_slot):
                            raise ValueError(
                                f"Overlapping slots found in {mode}/{day}: "
                                f"{slot.start_time}-{slot.end_time} overlaps with "
                                f"{existing_slot.start_time}-{existing_slot.end_time}"
                            )
                    validated_slots.append(slot)
        
        # Validate metadata
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        
        # Validate presence_config if present
        if self.presence_config is not None:
            if not isinstance(self.presence_config, PresenceConfig):
                raise ValueError("presence_config must be PresenceConfig instance or None")
            self.presence_config.validate()
        
        # Validate buffer_config if present
        if self.buffer_config is not None:
            if not isinstance(self.buffer_config, GlobalBufferConfig):
                raise ValueError("buffer_config must be GlobalBufferConfig instance or None")
            self.buffer_config.validate()
    
    def validate_schedule_integrity(self) -> List[str]:
        """Validate schedule integrity and return list of warnings."""
        warnings = []
        
        # Check for gaps in schedules
        for mode in self.VALID_MODES:
            if mode not in self.schedules:
                warnings.append(f"No schedules defined for {mode} mode")
                continue
            
            for day in ScheduleSlot.VALID_DAYS:
                if day not in self.schedules[mode] or not self.schedules[mode][day]:
                    warnings.append(f"No schedules defined for {mode} mode on {day}")
                    continue
                
                # Check for 24-hour coverage
                slots = sorted(self.schedules[mode][day], key=lambda s: s.start_time)
                
                # Check if first slot starts at 00:00
                if slots[0].start_time != "00:00":
                    warnings.append(f"Schedule gap at start of {day} in {mode} mode (before {slots[0].start_time})")
                
                # Check for gaps between slots
                for i in range(len(slots) - 1):
                    if slots[i].end_time != slots[i + 1].start_time:
                        warnings.append(
                            f"Schedule gap in {mode} mode on {day}: "
                            f"{slots[i].end_time} to {slots[i + 1].start_time}"
                        )
                
                # Check if last slot ends at 24:00 (or 23:59)
                if slots[-1].end_time not in ["23:59", "24:00"]:
                    warnings.append(f"Schedule gap at end of {day} in {mode} mode (after {slots[-1].end_time})")
        
        return warnings
    
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
        
        result = {
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
        
        if self.presence_config is not None:
            result["presence_config"] = self.presence_config.to_dict()
        
        if self.buffer_config is not None:
            result["buffer_config"] = self.buffer_config.to_dict()
        
        return result
    
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
        
        # Parse presence_config if present
        presence_config = None
        if "presence_config" in data:
            presence_config = PresenceConfig.from_dict(data["presence_config"])
        
        # Parse buffer_config if present
        buffer_config = None
        if "buffer_config" in data:
            buffer_config = GlobalBufferConfig.from_dict(data["buffer_config"])
        
        return cls(
            version=data.get("version", "0.3.0"),
            entities_tracked=data.get("entities_tracked", []),
            presence_entities=data.get("presence_entities", []),
            presence_rule=data.get("presence_rule", "anyone_home"),
            presence_timeout_seconds=data.get("presence_timeout_seconds", 600),
            buffer=buffer,
            ui=data.get("ui", {}),
            schedules=schedules,
            metadata=data.get("metadata", {}),
            presence_config=presence_config,
            buffer_config=buffer_config
        )
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> ScheduleData:
        """Create from JSON string."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse schedule data: {e}")