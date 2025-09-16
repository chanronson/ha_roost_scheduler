"""Storage service for the Roost Scheduler integration."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import ScheduleData

_LOGGER = logging.getLogger(__name__)


class StorageService:
    """Handles data persistence for the Roost Scheduler integration."""
    
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the storage service."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        self._schedule_data: Optional[Dict[str, Any]] = None
        self._backup_dir = Path(hass.config.config_dir) / "roost_scheduler_backups"
    
    async def load_schedules(self) -> Optional[Dict[str, Any]]:
        """Load schedule data from storage."""
        try:
            data = await self._store.async_load()
            if data:
                self._schedule_data = data
                _LOGGER.debug("Loaded schedule data for entry %s", self.entry_id)
                return data
            else:
                _LOGGER.info("No existing schedule data found for entry %s", self.entry_id)
                return None
        except Exception as e:
            _LOGGER.error("Error loading schedule data: %s", e)
            # Attempt recovery from backup
            return await self._attempt_recovery()
    
    async def save_schedules(self, schedules: Dict[str, Any]) -> None:
        """Save schedule data to storage."""
        try:
            # Update metadata
            if "metadata" not in schedules:
                schedules["metadata"] = {}
            
            schedules["metadata"]["last_modified"] = datetime.now().isoformat()
            
            # Save to storage
            await self._store.async_save(schedules)
            self._schedule_data = schedules
            
            _LOGGER.debug("Saved schedule data for entry %s", self.entry_id)
        except Exception as e:
            _LOGGER.error("Error saving schedule data: %s", e)
            raise
    
    async def export_backup(self, path: Optional[str] = None) -> str:
        """Export schedule data to a backup file."""
        if not self._schedule_data:
            await self.load_schedules()
        
        if not self._schedule_data:
            raise ValueError("No schedule data to export")
        
        # Ensure backup directory exists
        self._backup_dir.mkdir(exist_ok=True)
        
        # Generate filename if not provided
        if not path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"roost_scheduler_backup_{self.entry_id}_{timestamp}.json"
            path = str(self._backup_dir / filename)
        
        # Export data
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._schedule_data, f, indent=2, ensure_ascii=False)
            
            _LOGGER.info("Exported backup to %s", path)
            return path
        except Exception as e:
            _LOGGER.error("Error exporting backup: %s", e)
            raise
    
    async def import_backup(self, file_path: str) -> bool:
        """Import schedule data from a backup file."""
        try:
            if not os.path.exists(file_path):
                _LOGGER.error("Backup file not found: %s", file_path)
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate data structure
            if not self._validate_backup_data(data):
                _LOGGER.error("Invalid backup data structure")
                return False
            
            # Perform version migration if needed
            migrated_data = await self._migrate_data(data)
            
            # Save imported data
            await self.save_schedules(migrated_data)
            
            _LOGGER.info("Successfully imported backup from %s", file_path)
            return True
        except Exception as e:
            _LOGGER.error("Error importing backup: %s", e)
            return False
    
    async def create_nightly_backup(self) -> Optional[str]:
        """Create an automatic nightly backup."""
        try:
            if not self._schedule_data:
                await self.load_schedules()
            
            if not self._schedule_data:
                _LOGGER.debug("No data to backup")
                return None
            
            # Create backup with nightly prefix
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"nightly_backup_{self.entry_id}_{timestamp}.json"
            path = str(self._backup_dir / filename)
            
            # Only create if doesn't exist (one per day)
            if os.path.exists(path):
                _LOGGER.debug("Nightly backup already exists for today")
                return path
            
            backup_path = await self.export_backup(path)
            
            # Clean up old nightly backups (keep last 7 days)
            await self._cleanup_old_backups()
            
            return backup_path
        except Exception as e:
            _LOGGER.error("Error creating nightly backup: %s", e)
            return None
    
    def _validate_backup_data(self, data: Dict[str, Any]) -> bool:
        """Validate backup data structure."""
        required_keys = ["version", "schedules"]
        
        for key in required_keys:
            if key not in data:
                _LOGGER.error("Missing required key in backup: %s", key)
                return False
        
        # Validate schedules structure
        schedules = data.get("schedules", {})
        if not isinstance(schedules, dict):
            return False
        
        return True
    
    async def _migrate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate data from older versions if needed."""
        current_version = data.get("version", "0.1.0")
        
        # Add migration logic here as versions evolve
        if current_version != "0.3.0":
            _LOGGER.info("Migrating data from version %s to 0.3.0", current_version)
            data["version"] = "0.3.0"
            
            # Add any necessary migration steps here
        
        return data
    
    async def _attempt_recovery(self) -> Optional[Dict[str, Any]]:
        """Attempt to recover from the most recent backup."""
        if not self._backup_dir.exists():
            return None
        
        # Find most recent backup
        backup_files = list(self._backup_dir.glob(f"*{self.entry_id}*.json"))
        if not backup_files:
            return None
        
        # Sort by modification time, newest first
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for backup_file in backup_files:
            try:
                _LOGGER.info("Attempting recovery from %s", backup_file)
                if await self.import_backup(str(backup_file)):
                    return self._schedule_data
            except Exception as e:
                _LOGGER.error("Recovery failed for %s: %s", backup_file, e)
                continue
        
        _LOGGER.error("All recovery attempts failed")
        return None
    
    async def _cleanup_old_backups(self) -> None:
        """Clean up old nightly backups, keeping only the last 7 days."""
        try:
            if not self._backup_dir.exists():
                return
            
            nightly_files = list(self._backup_dir.glob(f"nightly_backup_{self.entry_id}_*.json"))
            
            # Sort by modification time, newest first
            nightly_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove files beyond the 7 most recent
            for old_file in nightly_files[7:]:
                try:
                    old_file.unlink()
                    _LOGGER.debug("Removed old backup: %s", old_file)
                except Exception as e:
                    _LOGGER.error("Error removing old backup %s: %s", old_file, e)
        except Exception as e:
            _LOGGER.error("Error during backup cleanup: %s", e)