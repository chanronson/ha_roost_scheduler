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
from homeassistant.exceptions import HomeAssistantError

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import ScheduleData

_LOGGER = logging.getLogger(__name__)


class StorageError(HomeAssistantError):
    """Exception raised for storage-related errors."""
    pass


class CorruptedDataError(StorageError):
    """Exception raised when storage data is corrupted."""
    pass


class StorageService:
    """Handles data persistence for the Roost Scheduler integration."""
    
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the storage service."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")
        self._schedule_data: Optional[ScheduleData] = None
        self._backup_dir = Path(hass.config.config_dir) / "roost_scheduler_backups"
        self._nightly_backup_enabled = True
        self._nightly_backup_time = "02:00"  # Default backup time
    
    async def load_schedules(self) -> Optional[ScheduleData]:
        """Load schedule data from storage."""
        try:
            data = await self._store.async_load()
            if data:
                try:
                    # Validate and parse the loaded data
                    schedule_data = ScheduleData.from_dict(data)
                    self._schedule_data = schedule_data
                    _LOGGER.debug("Loaded and validated schedule data for entry %s", self.entry_id)
                    return schedule_data
                except (ValueError, TypeError) as e:
                    _LOGGER.error("Corrupted schedule data detected: %s", e)
                    raise CorruptedDataError(f"Invalid schedule data format: {e}")
            else:
                _LOGGER.info("No existing schedule data found for entry %s", self.entry_id)
                return None
        except CorruptedDataError:
            # Attempt recovery from backup for corrupted data
            _LOGGER.warning("Attempting recovery from backup due to corrupted data")
            return await self._attempt_recovery()
        except Exception as e:
            _LOGGER.error("Unexpected error loading schedule data: %s", e)
            raise StorageError(f"Failed to load schedule data: {e}")
    
    async def save_schedules(self, schedules: ScheduleData) -> None:
        """Save schedule data to storage."""
        try:
            # Validate the schedule data before saving
            schedules.validate()
            
            # Update metadata
            schedules.metadata["last_modified"] = datetime.now().isoformat()
            
            # Convert to dict for storage
            data_dict = schedules.to_dict()
            
            # Save to storage
            await self._store.async_save(data_dict)
            self._schedule_data = schedules
            
            _LOGGER.debug("Saved schedule data for entry %s", self.entry_id)
        except (ValueError, TypeError) as e:
            _LOGGER.error("Invalid schedule data: %s", e)
            raise StorageError(f"Cannot save invalid schedule data: {e}")
        except Exception as e:
            _LOGGER.error("Error saving schedule data: %s", e)
            raise StorageError(f"Failed to save schedule data: {e}")
    
    async def export_backup(self, path: Optional[str] = None) -> str:
        """Export schedule data to a backup file."""
        if not self._schedule_data:
            await self.load_schedules()
        
        if not self._schedule_data:
            raise StorageError("No schedule data to export")
        
        # Ensure backup directory exists
        try:
            self._backup_dir.mkdir(exist_ok=True)
        except OSError as e:
            raise StorageError(f"Cannot create backup directory: {e}")
        
        # Generate filename if not provided
        if not path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"roost_scheduler_backup_{self.entry_id}_{timestamp}.json"
            path = str(self._backup_dir / filename)
        
        # Export data
        try:
            # Use the ScheduleData's to_json method for consistent formatting
            json_data = self._schedule_data.to_json()
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(json_data)
            
            _LOGGER.info("Exported backup to %s", path)
            return path
        except OSError as e:
            _LOGGER.error("Error writing backup file: %s", e)
            raise StorageError(f"Failed to write backup file: {e}")
        except Exception as e:
            _LOGGER.error("Error exporting backup: %s", e)
            raise StorageError(f"Failed to export backup: {e}")
    
    async def import_backup(self, file_path: str) -> bool:
        """Import schedule data from a backup file."""
        try:
            if not os.path.exists(file_path):
                _LOGGER.error("Backup file not found: %s", file_path)
                return False
            
            # Read and parse the backup file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = f.read()
                
                # Use ScheduleData's from_json method for consistent parsing
                schedule_data = ScheduleData.from_json(json_data)
                
            except (OSError, json.JSONDecodeError) as e:
                _LOGGER.error("Error reading backup file %s: %s", file_path, e)
                return False
            except (ValueError, TypeError) as e:
                _LOGGER.error("Invalid backup data format in %s: %s", file_path, e)
                return False
            
            # Perform version migration if needed
            migrated_data = await self._migrate_schedule_data(schedule_data)
            
            # Save imported data
            await self.save_schedules(migrated_data)
            
            _LOGGER.info("Successfully imported backup from %s", file_path)
            return True
        except Exception as e:
            _LOGGER.error("Unexpected error importing backup: %s", e)
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
    
    async def _migrate_schedule_data(self, schedule_data: ScheduleData) -> ScheduleData:
        """Migrate schedule data from older versions if needed."""
        current_version = schedule_data.version
        
        # Add migration logic here as versions evolve
        if current_version != "0.3.0":
            _LOGGER.info("Migrating data from version %s to 0.3.0", current_version)
            schedule_data.version = "0.3.0"
            
            # Add any necessary migration steps here
            # For example, if we need to migrate buffer config structure:
            # if current_version == "0.2.0":
            #     schedule_data = self._migrate_from_v02_to_v03(schedule_data)
        
        return schedule_data
    
    async def _attempt_recovery(self) -> Optional[ScheduleData]:
        """Attempt to recover from the most recent backup."""
        if not self._backup_dir.exists():
            _LOGGER.warning("Backup directory does not exist, cannot attempt recovery")
            return None
        
        # Find most recent backup
        backup_files = list(self._backup_dir.glob(f"*{self.entry_id}*.json"))
        if not backup_files:
            _LOGGER.warning("No backup files found for entry %s", self.entry_id)
            return None
        
        # Sort by modification time, newest first
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for backup_file in backup_files:
            try:
                _LOGGER.info("Attempting recovery from %s", backup_file)
                if await self.import_backup(str(backup_file)):
                    _LOGGER.info("Successfully recovered from %s", backup_file)
                    return self._schedule_data
            except Exception as e:
                _LOGGER.error("Recovery failed for %s: %s", backup_file, e)
                continue
        
        _LOGGER.error("All recovery attempts failed")
        return None
    
    def configure_nightly_backup(self, enabled: bool, backup_time: str = "02:00") -> None:
        """Configure automatic nightly backup settings."""
        self._nightly_backup_enabled = enabled
        self._nightly_backup_time = backup_time
        _LOGGER.info("Nightly backup configured: enabled=%s, time=%s", enabled, backup_time)
    
    def is_nightly_backup_enabled(self) -> bool:
        """Check if nightly backup is enabled."""
        return self._nightly_backup_enabled
    
    def get_nightly_backup_time(self) -> str:
        """Get the configured nightly backup time."""
        return self._nightly_backup_time
    
    async def schedule_nightly_backup(self) -> None:
        """Schedule the nightly backup using Home Assistant's time tracking."""
        if not self._nightly_backup_enabled:
            return
        
        try:
            from homeassistant.helpers.event import async_track_time_change
            
            # Parse backup time
            hour, minute = map(int, self._nightly_backup_time.split(':'))
            
            # Schedule the backup
            async_track_time_change(
                self.hass,
                self._scheduled_backup_callback,
                hour=hour,
                minute=minute,
                second=0
            )
            
            _LOGGER.info("Scheduled nightly backup at %s", self._nightly_backup_time)
        except Exception as e:
            _LOGGER.error("Error scheduling nightly backup: %s", e)
    
    async def _scheduled_backup_callback(self, now) -> None:
        """Callback for scheduled nightly backup."""
        try:
            backup_path = await self.create_nightly_backup()
            if backup_path:
                _LOGGER.info("Scheduled backup completed: %s", backup_path)
            else:
                _LOGGER.debug("Scheduled backup skipped (no data)")
        except Exception as e:
            _LOGGER.error("Error during scheduled backup: %s", e)
    
    async def get_backup_info(self) -> Dict[str, Any]:
        """Get information about available backups."""
        if not self._backup_dir.exists():
            return {"backups": [], "total_size": 0}
        
        backups = []
        total_size = 0
        
        try:
            backup_files = list(self._backup_dir.glob(f"*{self.entry_id}*.json"))
            
            for backup_file in backup_files:
                try:
                    stat = backup_file.stat()
                    backups.append({
                        "filename": backup_file.name,
                        "path": str(backup_file),
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "type": "nightly" if "nightly_backup" in backup_file.name else "manual"
                    })
                    total_size += stat.st_size
                except Exception as e:
                    _LOGGER.warning("Error reading backup file %s: %s", backup_file, e)
            
            # Sort by creation time, newest first
            backups.sort(key=lambda x: x["created"], reverse=True)
            
            return {
                "backups": backups,
                "total_size": total_size,
                "backup_dir": str(self._backup_dir)
            }
        except Exception as e:
            _LOGGER.error("Error getting backup info: %s", e)
            return {"backups": [], "total_size": 0, "error": str(e)}
    
    async def delete_backup(self, filename: str) -> bool:
        """Delete a specific backup file."""
        try:
            backup_path = self._backup_dir / filename
            
            # Security check - ensure file is in backup directory and has correct pattern
            if not backup_path.exists():
                _LOGGER.error("Backup file not found: %s", filename)
                return False
            
            if not backup_path.is_relative_to(self._backup_dir):
                _LOGGER.error("Security violation: backup file outside backup directory")
                return False
            
            if self.entry_id not in filename or not filename.endswith('.json'):
                _LOGGER.error("Invalid backup filename format: %s", filename)
                return False
            
            backup_path.unlink()
            _LOGGER.info("Deleted backup file: %s", filename)
            return True
        except Exception as e:
            _LOGGER.error("Error deleting backup %s: %s", filename, e)
            return False
    
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