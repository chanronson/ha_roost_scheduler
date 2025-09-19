"""Migration system for Roost Scheduler version upgrades."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY
from .version import VERSION, get_migration_path, is_version_supported

_LOGGER = logging.getLogger(__name__)

# Migration registry - maps version to migration function
MIGRATIONS: dict[str, Callable[[dict], dict]] = {}


def migration(version: str) -> Callable:
    """Decorator to register a migration function for a specific version."""
    def decorator(func: Callable[[dict], dict]) -> Callable:
        MIGRATIONS[version] = func
        _LOGGER.debug("Registered migration for version %s", version)
        return func
    return decorator


class MigrationManager:
    """Manages data migration between versions."""
    
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize migration manager."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, 1, f"{STORAGE_KEY}_{entry_id}")
        
    async def migrate_if_needed(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate data if version upgrade is detected."""
        if not data:
            _LOGGER.debug("No existing data to migrate")
            return data
            
        stored_version = data.get("version", "0.1.0")
        
        if stored_version == VERSION:
            _LOGGER.debug("Data is already at current version %s", VERSION)
            return data
            
        if not is_version_supported(stored_version):
            _LOGGER.error(
                "Cannot migrate from unsupported version %s to %s", 
                stored_version, 
                VERSION
            )
            raise ValueError(f"Unsupported migration from version {stored_version}")
        
        _LOGGER.info("Migrating data from version %s to %s", stored_version, VERSION)
        
        # Create backup before migration
        await self._create_migration_backup(data, stored_version)
        
        # Get migration path
        migration_path = get_migration_path(stored_version)
        
        if not migration_path:
            _LOGGER.warning("No migration path found from %s to %s", stored_version, VERSION)
            return data
        
        # Apply migrations in sequence
        migrated_data = data.copy()
        
        for target_version in migration_path:
            if target_version in MIGRATIONS:
                _LOGGER.info("Applying migration to version %s", target_version)
                try:
                    migrated_data = MIGRATIONS[target_version](migrated_data)
                    migrated_data["version"] = target_version
                    
                    # Update metadata
                    if "metadata" not in migrated_data:
                        migrated_data["metadata"] = {}
                    
                    migrated_data["metadata"]["last_migration"] = {
                        "from_version": stored_version,
                        "to_version": target_version,
                        "timestamp": datetime.now().isoformat(),
                        "migration_id": f"{stored_version}_to_{target_version}"
                    }
                    
                except Exception as e:
                    _LOGGER.error("Migration to version %s failed: %s", target_version, e)
                    raise
            else:
                _LOGGER.warning("No migration function found for version %s", target_version)
        
        _LOGGER.info("Migration completed successfully to version %s", VERSION)
        
        # Validate migrated data
        if not await self.validate_migrated_data(migrated_data):
            _LOGGER.error("Migration validation failed")
            raise ValueError("Migration validation failed - data integrity check failed")
        
        return migrated_data
    
    async def _create_migration_backup(self, data: dict[str, Any], from_version: str) -> None:
        """Create a backup before migration."""
        try:
            backup_dir = Path(self.hass.config.config_dir) / "roost_scheduler_backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"pre_migration_{from_version}_to_{VERSION}_{timestamp}.json"
            backup_path = backup_dir / backup_filename
            
            with backup_path.open("w") as f:
                json.dump(data, f, indent=2, default=str)
            
            _LOGGER.info("Created migration backup: %s", backup_path)
            
        except Exception as e:
            _LOGGER.error("Failed to create migration backup: %s", e)
            # Don't fail migration if backup fails
    
    async def validate_migrated_data(self, data: dict[str, Any]) -> bool:
        """Validate migrated data structure."""
        try:
            # Check required top-level keys
            required_keys = ["version", "entities_tracked", "schedules"]
            for key in required_keys:
                if key not in data:
                    _LOGGER.error("Missing required key after migration: %s", key)
                    return False
            
            # Validate version
            if data["version"] != VERSION:
                _LOGGER.error("Version mismatch after migration: expected %s, got %s", 
                            VERSION, data["version"])
                return False
            
            # Validate schedules structure
            schedules = data.get("schedules", {})
            for mode in ["home", "away"]:
                if mode not in schedules:
                    continue
                    
                mode_schedules = schedules[mode]
                if not isinstance(mode_schedules, dict):
                    _LOGGER.error("Invalid schedules structure for mode %s", mode)
                    return False
                
                # Validate each day's schedule
                for day, day_schedule in mode_schedules.items():
                    if not isinstance(day_schedule, list):
                        _LOGGER.error("Invalid day schedule structure for %s/%s", mode, day)
                        return False
                    
                    # Validate each slot
                    for slot in day_schedule:
                        if not isinstance(slot, dict):
                            _LOGGER.error("Invalid slot structure in %s/%s", mode, day)
                            return False
                        
                        required_slot_keys = ["start", "end", "target"]
                        for slot_key in required_slot_keys:
                            if slot_key not in slot:
                                _LOGGER.error("Missing slot key %s in %s/%s", slot_key, mode, day)
                                return False
            
            _LOGGER.debug("Migrated data validation passed")
            return True
            
        except Exception as e:
            _LOGGER.error("Error validating migrated data: %s", e)
            return False


# Migration functions for each version
@migration("0.2.0")
def migrate_to_0_2_0(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from 0.1.0 to 0.2.0 - Add presence management."""
    _LOGGER.info("Migrating to version 0.2.0: Adding presence management")
    
    migrated = data.copy()
    
    # Add presence configuration if not present
    if "presence_entities" not in migrated:
        migrated["presence_entities"] = []
    
    if "presence_rule" not in migrated:
        migrated["presence_rule"] = "anyone_home"
    
    if "presence_timeout_seconds" not in migrated:
        migrated["presence_timeout_seconds"] = 600
    
    # Ensure schedules have both home and away modes
    schedules = migrated.get("schedules", {})
    
    if "home" not in schedules:
        # Migrate existing schedules to "home" mode
        if schedules:
            migrated["schedules"] = {"home": schedules, "away": {}}
        else:
            migrated["schedules"] = {"home": {}, "away": {}}
    
    if "away" not in migrated["schedules"]:
        migrated["schedules"]["away"] = {}
    
    return migrated


@migration("0.3.0")
def migrate_to_0_3_0(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from 0.2.0 to 0.3.0 - Add buffer system and HACS support."""
    _LOGGER.info("Migrating to version 0.3.0: Adding buffer system")
    
    migrated = data.copy()
    
    # Add buffer configuration
    if "buffer" not in migrated:
        migrated["buffer"] = {
            "global": {
                "time_minutes": 15,
                "value_delta": 2.0,
                "apply_to": "climate"
            }
        }
    
    # Add UI configuration
    if "ui" not in migrated:
        migrated["ui"] = {
            "resolution_minutes": 30,
            "auto_add_card": False
        }
    
    # Update schedule structure to include buffer overrides
    schedules = migrated.get("schedules", {})
    for mode in ["home", "away"]:
        if mode not in schedules:
            continue
            
        for day, day_schedule in schedules[mode].items():
            for slot in day_schedule:
                # Ensure target has proper structure
                if "target" in slot and isinstance(slot["target"], (int, float)):
                    # Convert old numeric target to new structure
                    slot["target"] = {
                        "domain": "climate",
                        "temperature": float(slot["target"])
                    }
                
                # Add buffer_override placeholder if not present
                if "buffer_override" not in slot:
                    slot["buffer_override"] = None
    
    # Add metadata section
    if "metadata" not in migrated:
        migrated["metadata"] = {
            "created_by": "migration",
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat()
        }
    
    return migrated


@migration("0.3.1")
def migrate_to_0_3_1(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from 0.3.0 to 0.3.1 - Add manager configuration storage."""
    _LOGGER.info("Migrating to version 0.3.1: Adding manager configuration storage")
    
    migrated = data.copy()
    
    # Add presence_config if not present
    if "presence_config" not in migrated:
        # Migrate from legacy fields
        presence_config = {
            "entities": migrated.get("presence_entities", []),
            "rule": migrated.get("presence_rule", "anyone_home"),
            "timeout_seconds": migrated.get("presence_timeout_seconds", 600),
            "override_entities": {
                "force_home": "input_boolean.roost_force_home",
                "force_away": "input_boolean.roost_force_away"
            },
            "custom_template": None,
            "template_entities": []
        }
        migrated["presence_config"] = presence_config
        _LOGGER.info("Migrated presence configuration from legacy fields")
    
    # Add buffer_config if not present
    if "buffer_config" not in migrated:
        # Migrate from legacy buffer structure
        legacy_buffer = migrated.get("buffer", {}).get("global", {})
        buffer_config = {
            "time_minutes": legacy_buffer.get("time_minutes", 15),
            "value_delta": legacy_buffer.get("value_delta", 2.0),
            "enabled": legacy_buffer.get("enabled", True),
            "apply_to": legacy_buffer.get("apply_to", "climate"),
            "entity_overrides": {}
        }
        migrated["buffer_config"] = buffer_config
        _LOGGER.info("Migrated buffer configuration from legacy fields")
    
    # Update metadata
    if "metadata" not in migrated:
        migrated["metadata"] = {}
    
    migrated["metadata"]["manager_config_migration"] = {
        "timestamp": datetime.now().isoformat(),
        "from_version": "0.3.0",
        "to_version": "0.3.1"
    }
    
    return migrated


class ConfigurationMigrationManager:
    """Manages configuration migration for managers."""
    
    def __init__(self, hass: HomeAssistant, storage_service) -> None:
        """Initialize configuration migration manager."""
        self.hass = hass
        self.storage_service = storage_service
    
    async def migrate_presence_configuration(self) -> bool:
        """Migrate presence configuration from various sources."""
        try:
            _LOGGER.info("Starting presence configuration migration")
            
            # Check if modern configuration already exists
            schedule_data = await self.storage_service.load_schedules()
            if schedule_data and schedule_data.presence_config:
                _LOGGER.debug("Modern presence configuration already exists")
                return True
            
            # Try to migrate from legacy fields in schedule data
            if schedule_data and (schedule_data.presence_entities or schedule_data.presence_rule):
                _LOGGER.info("Migrating presence configuration from legacy schedule data fields")
                
                from .models import PresenceConfig
                presence_config = PresenceConfig(
                    entities=schedule_data.presence_entities.copy() if schedule_data.presence_entities else [],
                    rule=schedule_data.presence_rule if schedule_data.presence_rule else "anyone_home",
                    timeout_seconds=schedule_data.presence_timeout_seconds if schedule_data.presence_timeout_seconds else 600,
                    override_entities={
                        "force_home": "input_boolean.roost_force_home",
                        "force_away": "input_boolean.roost_force_away"
                    },
                    custom_template=None,
                    template_entities=[]
                )
                
                schedule_data.presence_config = presence_config
                await self.storage_service.save_schedules(schedule_data)
                _LOGGER.info("Successfully migrated presence configuration from legacy fields")
                return True
            
            # Try to migrate from config entry data
            config_entry_data = self.storage_service.get_config_entry_data()
            if config_entry_data and ('presence_entities' in config_entry_data or 'presence_rule' in config_entry_data):
                _LOGGER.info("Migrating presence configuration from config entry data")
                
                from .models import PresenceConfig, ScheduleData
                presence_config = PresenceConfig(
                    entities=config_entry_data.get('presence_entities', []),
                    rule=config_entry_data.get('presence_rule', 'anyone_home'),
                    timeout_seconds=config_entry_data.get('presence_timeout_seconds', 600),
                    override_entities={
                        "force_home": "input_boolean.roost_force_home",
                        "force_away": "input_boolean.roost_force_away"
                    },
                    custom_template=None,
                    template_entities=[]
                )
                
                # Create or update schedule data
                if not schedule_data:
                    schedule_data = ScheduleData(
                        version="0.3.1",
                        entities_tracked=[],
                        presence_entities=presence_config.entities.copy(),
                        presence_rule=presence_config.rule,
                        presence_timeout_seconds=presence_config.timeout_seconds,
                        buffer={},
                        ui={},
                        schedules={"home": {}, "away": {}},
                        metadata={},
                        presence_config=presence_config
                    )
                else:
                    schedule_data.presence_config = presence_config
                
                await self.storage_service.save_schedules(schedule_data)
                _LOGGER.info("Successfully migrated presence configuration from config entry")
                return True
            
            _LOGGER.info("No presence configuration found to migrate")
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to migrate presence configuration: %s", e)
            return False
    
    async def migrate_buffer_configuration(self) -> bool:
        """Migrate buffer configuration from various sources."""
        try:
            _LOGGER.info("Starting buffer configuration migration")
            
            # Check if modern configuration already exists
            schedule_data = await self.storage_service.load_schedules()
            if schedule_data and schedule_data.buffer_config:
                _LOGGER.debug("Modern buffer configuration already exists")
                return True
            
            # Try to migrate from legacy buffer fields in schedule data
            if schedule_data and schedule_data.buffer:
                _LOGGER.info("Migrating buffer configuration from legacy schedule data fields")
                
                from .models import GlobalBufferConfig
                # Extract legacy buffer configuration
                legacy_buffer_obj = schedule_data.buffer.get('global') if schedule_data.buffer else None
                if legacy_buffer_obj and hasattr(legacy_buffer_obj, 'to_dict'):
                    # It's a BufferConfig object, convert to dict
                    legacy_buffer = legacy_buffer_obj.to_dict()
                elif isinstance(legacy_buffer_obj, dict):
                    # It's already a dict
                    legacy_buffer = legacy_buffer_obj
                else:
                    # No valid buffer config found
                    legacy_buffer = {}
                
                buffer_config = GlobalBufferConfig(
                    time_minutes=legacy_buffer.get('time_minutes', 15),
                    value_delta=legacy_buffer.get('value_delta', 2.0),
                    enabled=legacy_buffer.get('enabled', True),
                    apply_to=legacy_buffer.get('apply_to', 'climate'),
                    entity_overrides={}
                )
                
                schedule_data.buffer_config = buffer_config
                await self.storage_service.save_schedules(schedule_data)
                _LOGGER.info("Successfully migrated buffer configuration from legacy fields")
                return True
            
            # Try to migrate from config entry data
            config_entry_data = self.storage_service.get_config_entry_data()
            if config_entry_data and ('buffer_time_minutes' in config_entry_data or 'buffer_value_delta' in config_entry_data):
                _LOGGER.info("Migrating buffer configuration from config entry data")
                
                from .models import GlobalBufferConfig, ScheduleData
                buffer_config = GlobalBufferConfig(
                    time_minutes=config_entry_data.get('buffer_time_minutes', 15),
                    value_delta=config_entry_data.get('buffer_value_delta', 2.0),
                    enabled=config_entry_data.get('buffer_enabled', True),
                    apply_to='climate',
                    entity_overrides={}
                )
                
                # Create or update schedule data
                if not schedule_data:
                    schedule_data = ScheduleData(
                        version="0.3.1",
                        entities_tracked=[],
                        presence_entities=[],
                        presence_rule="anyone_home",
                        presence_timeout_seconds=600,
                        buffer={},
                        ui={},
                        schedules={"home": {}, "away": {}},
                        metadata={},
                        buffer_config=buffer_config
                    )
                else:
                    schedule_data.buffer_config = buffer_config
                
                await self.storage_service.save_schedules(schedule_data)
                _LOGGER.info("Successfully migrated buffer configuration from config entry")
                return True
            
            _LOGGER.info("No buffer configuration found to migrate")
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to migrate buffer configuration: %s", e)
            return False
    
    async def migrate_all_configurations(self) -> bool:
        """Migrate all manager configurations."""
        try:
            _LOGGER.info("Starting complete configuration migration")
            
            presence_success = await self.migrate_presence_configuration()
            buffer_success = await self.migrate_buffer_configuration()
            
            if presence_success and buffer_success:
                _LOGGER.info("All configuration migrations completed successfully")
                return True
            else:
                _LOGGER.warning("Some configuration migrations failed: presence=%s, buffer=%s", 
                              presence_success, buffer_success)
                return False
                
        except Exception as e:
            _LOGGER.error("Failed to migrate configurations: %s", e)
            return False


class UninstallManager:
    """Manages clean uninstall with data preservation options."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize uninstall manager."""
        self.hass = hass
    
    async def prepare_uninstall(self, preserve_data: bool = True) -> dict[str, Any]:
        """Prepare for uninstall with optional data preservation."""
        _LOGGER.info("Preparing for uninstall (preserve_data=%s)", preserve_data)
        
        uninstall_info = {
            "timestamp": datetime.now().isoformat(),
            "preserve_data": preserve_data,
            "backup_locations": [],
            "cleanup_actions": []
        }
        
        if preserve_data:
            # Create final backup of all data
            backup_locations = await self._create_final_backup()
            uninstall_info["backup_locations"] = backup_locations
            
            # Create uninstall info file
            await self._create_uninstall_info(uninstall_info)
        else:
            # Clean up all data
            cleanup_actions = await self._cleanup_all_data()
            uninstall_info["cleanup_actions"] = cleanup_actions
        
        return uninstall_info
    
    async def _create_final_backup(self) -> list[str]:
        """Create final backup of all integration data."""
        backup_locations = []
        
        try:
            backup_dir = Path(self.hass.config.config_dir) / "roost_scheduler_backups"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup all storage files
            storage_dir = Path(self.hass.config.config_dir) / ".storage"
            
            for storage_file in storage_dir.glob("roost_scheduler*"):
                if storage_file.is_file():
                    backup_name = f"final_backup_{storage_file.name}_{timestamp}.json"
                    backup_path = backup_dir / backup_name
                    
                    with storage_file.open() as src, backup_path.open("w") as dst:
                        dst.write(src.read())
                    
                    backup_locations.append(str(backup_path))
                    _LOGGER.info("Created final backup: %s", backup_path)
            
        except Exception as e:
            _LOGGER.error("Failed to create final backup: %s", e)
        
        return backup_locations
    
    async def _create_uninstall_info(self, info: dict[str, Any]) -> None:
        """Create uninstall information file."""
        try:
            info_path = Path(self.hass.config.config_dir) / "roost_scheduler_uninstall_info.json"
            
            with info_path.open("w") as f:
                json.dump(info, f, indent=2, default=str)
            
            _LOGGER.info("Created uninstall info file: %s", info_path)
            
        except Exception as e:
            _LOGGER.error("Failed to create uninstall info: %s", e)
    
    async def _cleanup_all_data(self) -> list[str]:
        """Clean up all integration data."""
        cleanup_actions = []
        
        try:
            # Remove storage files
            storage_dir = Path(self.hass.config.config_dir) / ".storage"
            
            for storage_file in storage_dir.glob("roost_scheduler*"):
                if storage_file.is_file():
                    storage_file.unlink()
                    cleanup_actions.append(f"Removed storage file: {storage_file}")
                    _LOGGER.info("Removed storage file: %s", storage_file)
            
            # Remove backup directory
            backup_dir = Path(self.hass.config.config_dir) / "roost_scheduler_backups"
            if backup_dir.exists():
                import shutil
                shutil.rmtree(backup_dir)
                cleanup_actions.append(f"Removed backup directory: {backup_dir}")
                _LOGGER.info("Removed backup directory: %s", backup_dir)
            
        except Exception as e:
            _LOGGER.error("Error during cleanup: %s", e)
            cleanup_actions.append(f"Error during cleanup: {e}")
        
        return cleanup_actions
    
    async def restore_from_backup(self, backup_path: str) -> bool:
        """Restore data from a backup file."""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                _LOGGER.error("Backup file not found: %s", backup_path)
                return False
            
            with backup_file.open() as f:
                backup_data = json.load(f)
            
            # Validate backup data
            if "version" not in backup_data:
                _LOGGER.error("Invalid backup file: missing version")
                return False
            
            # Restore to storage
            storage_key = f"{STORAGE_KEY}_{backup_data.get('entry_id', 'default')}"
            store = Store(self.hass, 1, storage_key)
            await store.async_save(backup_data)
            
            _LOGGER.info("Successfully restored from backup: %s", backup_path)
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to restore from backup %s: %s", backup_path, e)
            return False