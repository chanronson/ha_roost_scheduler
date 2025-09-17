"""Upgrade manager for handling version upgrades and compatibility."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY
from .version import VERSION, VersionInfo, is_version_supported
from .migration import MigrationManager, UninstallManager

_LOGGER = logging.getLogger(__name__)


class UpgradeManager:
    """Manages version upgrades and compatibility checks."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize upgrade manager."""
        self.hass = hass
        self._version_info = VersionInfo()
    
    async def check_upgrade_compatibility(self, entry_id: str) -> dict[str, Any]:
        """Check if an upgrade is compatible and safe."""
        try:
            # Load existing data to check version
            store = Store(self.hass, 1, f"{STORAGE_KEY}_{entry_id}")
            existing_data = await store.async_load()
            
            if not existing_data:
                return {
                    "compatible": True,
                    "upgrade_type": "fresh_install",
                    "current_version": None,
                    "target_version": VERSION,
                    "migration_required": False,
                    "backup_recommended": False
                }
            
            current_version = existing_data.get("version", "0.1.0")
            
            # Check version compatibility
            if not is_version_supported(current_version):
                return {
                    "compatible": False,
                    "upgrade_type": "unsupported",
                    "current_version": current_version,
                    "target_version": VERSION,
                    "migration_required": False,
                    "backup_recommended": True,
                    "error": f"Version {current_version} is not supported for upgrade to {VERSION}"
                }
            
            # Determine upgrade type
            upgrade_type = self._determine_upgrade_type(current_version)
            migration_required = current_version != VERSION
            backup_recommended = migration_required and upgrade_type in ["major", "minor"]
            
            return {
                "compatible": True,
                "upgrade_type": upgrade_type,
                "current_version": current_version,
                "target_version": VERSION,
                "migration_required": migration_required,
                "backup_recommended": backup_recommended,
                "breaking_changes": self._get_breaking_changes(current_version),
                "new_features": self._get_new_features(current_version)
            }
            
        except Exception as e:
            _LOGGER.error("Error checking upgrade compatibility: %s", e)
            return {
                "compatible": False,
                "upgrade_type": "error",
                "error": str(e)
            }
    
    def _determine_upgrade_type(self, from_version: str) -> str:
        """Determine the type of upgrade based on version difference."""
        try:
            from_parts = [int(x) for x in from_version.split(".")]
            to_parts = [int(x) for x in VERSION.split(".")]
            
            if from_parts[0] < to_parts[0]:
                return "major"
            elif from_parts[1] < to_parts[1]:
                return "minor"
            elif from_parts[2] < to_parts[2]:
                return "patch"
            else:
                return "none"
                
        except (ValueError, IndexError):
            return "unknown"
    
    def _get_breaking_changes(self, from_version: str) -> list[str]:
        """Get list of breaking changes since the from_version."""
        breaking_changes = []
        
        # Define breaking changes by version
        version_breaking_changes = {
            "0.2.0": [
                "Schedule structure changed to support Home/Away modes",
                "Presence entities configuration is now required"
            ],
            "0.3.0": [
                "Target value structure changed to support multiple domains",
                "Buffer configuration moved to separate section"
            ]
        }
        
        try:
            from_parts = [int(x) for x in from_version.split(".")]
            
            for version, changes in version_breaking_changes.items():
                version_parts = [int(x) for x in version.split(".")]
                
                # If from_version is older than this version, include breaking changes
                if (from_parts[0] < version_parts[0] or 
                    (from_parts[0] == version_parts[0] and from_parts[1] < version_parts[1]) or
                    (from_parts[0] == version_parts[0] and from_parts[1] == version_parts[1] and from_parts[2] < version_parts[2])):
                    breaking_changes.extend(changes)
                    
        except (ValueError, IndexError):
            _LOGGER.warning("Could not parse version for breaking changes: %s", from_version)
        
        return breaking_changes
    
    def _get_new_features(self, from_version: str) -> list[str]:
        """Get list of new features since the from_version."""
        new_features = []
        
        # Define new features by version
        version_new_features = {
            "0.2.0": [
                "Home/Away presence-based scheduling",
                "Presence entity monitoring with timeout detection",
                "Override boolean helpers for manual presence control"
            ],
            "0.3.0": [
                "Intelligent buffering system to prevent schedule conflicts",
                "Per-slot buffer override configuration",
                "Enhanced Lovelace card with real-time synchronization",
                "HACS compatibility and automated updates",
                "Backup and restore functionality"
            ]
        }
        
        try:
            from_parts = [int(x) for x in from_version.split(".")]
            
            for version, features in version_new_features.items():
                version_parts = [int(x) for x in version.split(".")]
                
                # If from_version is older than this version, include new features
                if (from_parts[0] < version_parts[0] or 
                    (from_parts[0] == version_parts[0] and from_parts[1] < version_parts[1]) or
                    (from_parts[0] == version_parts[0] and from_parts[1] == version_parts[1] and from_parts[2] < version_parts[2])):
                    new_features.extend(features)
                    
        except (ValueError, IndexError):
            _LOGGER.warning("Could not parse version for new features: %s", from_version)
        
        return new_features
    
    async def perform_upgrade(self, entry_id: str, create_backup: bool = True) -> dict[str, Any]:
        """Perform the upgrade process with proper error handling."""
        upgrade_info = {
            "success": False,
            "timestamp": datetime.now().isoformat(),
            "backup_created": False,
            "migration_applied": False,
            "validation_passed": False,
            "errors": []
        }
        
        try:
            # Check compatibility first
            compatibility = await self.check_upgrade_compatibility(entry_id)
            if not compatibility["compatible"]:
                upgrade_info["errors"].append(compatibility.get("error", "Upgrade not compatible"))
                return upgrade_info
            
            # Create backup if requested and recommended
            if create_backup and compatibility.get("backup_recommended", False):
                uninstall_manager = UninstallManager(self.hass)
                try:
                    backup_locations = await uninstall_manager._create_final_backup()
                    upgrade_info["backup_created"] = len(backup_locations) > 0
                    upgrade_info["backup_locations"] = backup_locations
                except Exception as e:
                    _LOGGER.warning("Failed to create upgrade backup: %s", e)
                    upgrade_info["errors"].append(f"Backup creation failed: {e}")
            
            # Perform migration if needed
            if compatibility.get("migration_required", False):
                migration_manager = MigrationManager(self.hass, entry_id)
                
                # Load and migrate data
                store = Store(self.hass, 1, f"{STORAGE_KEY}_{entry_id}")
                existing_data = await store.async_load()
                
                if existing_data:
                    try:
                        migrated_data = await migration_manager.migrate_if_needed(existing_data)
                        
                        # Save migrated data
                        await store.async_save(migrated_data)
                        upgrade_info["migration_applied"] = True
                        
                        # Validate migrated data
                        validation_passed = await migration_manager.validate_migrated_data(migrated_data)
                        upgrade_info["validation_passed"] = validation_passed
                        
                        if not validation_passed:
                            upgrade_info["errors"].append("Migration validation failed")
                            return upgrade_info
                            
                    except Exception as e:
                        upgrade_info["errors"].append(f"Migration failed: {e}")
                        return upgrade_info
            
            # Record upgrade completion
            await self._record_upgrade_completion(entry_id, compatibility)
            upgrade_info["success"] = True
            
            _LOGGER.info("Upgrade completed successfully from %s to %s", 
                        compatibility.get("current_version"), VERSION)
            
        except Exception as e:
            _LOGGER.error("Unexpected error during upgrade: %s", e)
            upgrade_info["errors"].append(f"Unexpected error: {e}")
        
        return upgrade_info
    
    async def _record_upgrade_completion(self, entry_id: str, compatibility_info: dict) -> None:
        """Record successful upgrade completion for tracking."""
        try:
            upgrade_record = {
                "timestamp": datetime.now().isoformat(),
                "from_version": compatibility_info.get("current_version"),
                "to_version": VERSION,
                "upgrade_type": compatibility_info.get("upgrade_type"),
                "breaking_changes": compatibility_info.get("breaking_changes", []),
                "new_features": compatibility_info.get("new_features", [])
            }
            
            # Store upgrade record
            upgrade_store = Store(self.hass, 1, f"{STORAGE_KEY}_upgrades")
            existing_records = await upgrade_store.async_load() or []
            existing_records.append(upgrade_record)
            
            # Keep only last 10 upgrade records
            if len(existing_records) > 10:
                existing_records = existing_records[-10:]
            
            await upgrade_store.async_save(existing_records)
            
        except Exception as e:
            _LOGGER.warning("Failed to record upgrade completion: %s", e)
    
    async def get_upgrade_history(self) -> list[dict[str, Any]]:
        """Get history of previous upgrades."""
        try:
            upgrade_store = Store(self.hass, 1, f"{STORAGE_KEY}_upgrades")
            records = await upgrade_store.async_load() or []
            return records
        except Exception as e:
            _LOGGER.error("Failed to get upgrade history: %s", e)
            return []
    
    def get_version_info(self) -> dict[str, Any]:
        """Get comprehensive version information."""
        return self._version_info.to_dict()