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
from .migration import MigrationManager

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
        self._migration_manager = MigrationManager(hass, entry_id)
    
    async def load_schedules(self) -> Optional[ScheduleData]:
        """Load schedule data from storage with migration support."""
        try:
            data = await self._store.async_load()
            if data:
                try:
                    # Perform migration if needed
                    migrated_data = await self._migration_manager.migrate_if_needed(data)
                    
                    # Validate migrated data
                    if not await self._migration_manager.validate_migrated_data(migrated_data):
                        raise CorruptedDataError("Data validation failed after migration")
                    
                    # Save migrated data if it was changed
                    if migrated_data != data:
                        await self._store.async_save(migrated_data)
                        _LOGGER.info("Saved migrated data for entry %s", self.entry_id)
                    
                    # Parse the loaded/migrated data
                    schedule_data = ScheduleData.from_dict(migrated_data)
                    self._schedule_data = schedule_data
                    _LOGGER.debug("Loaded and validated schedule data for entry %s", self.entry_id)
                    return schedule_data
                except (ValueError, TypeError) as e:
                    _LOGGER.error("Corrupted schedule data detected: %s", e)
                    raise CorruptedDataError(f"Invalid schedule data format: {e}")
            else:
                _LOGGER.info("No existing schedule data found for entry %s", self.entry_id)
                
                # Create default data for new installations
                _LOGGER.info("Creating default schedule data for new installation")
                default_data = await self._create_default_schedule_data("New installation - no existing data")
                
                if default_data is None:
                    _LOGGER.error("Failed to create default data for new installation")
                    return None
                
                return default_data
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
        """Export schedule data to a backup file with comprehensive error logging."""
        export_start_time = datetime.now()
        export_context = {
            "entry_id": self.entry_id,
            "operation": "export_backup",
            "requested_path": path
        }
        
        try:
            _LOGGER.info("Starting backup export for entry %s", self.entry_id)
            
            # Ensure we have schedule data to export
            if not self._schedule_data:
                _LOGGER.debug("No schedule data loaded, attempting to load for export")
                try:
                    await self.load_schedules()
                    export_context["data_loaded"] = True
                except Exception as load_error:
                    _LOGGER.error("Failed to load schedule data for export: %s", load_error)
                    export_context["load_error"] = str(load_error)
                    raise StorageError(f"Cannot load schedule data for export: {load_error}")
            
            if not self._schedule_data:
                _LOGGER.error("No schedule data available for export after load attempt")
                export_context["no_data_after_load"] = True
                raise StorageError("No schedule data to export")
            
            # Log data summary
            _LOGGER.debug("Exporting schedule data summary:")
            _LOGGER.debug("  - Version: %s", self._schedule_data.version)
            _LOGGER.debug("  - Entities tracked: %d", len(self._schedule_data.entities_tracked))
            _LOGGER.debug("  - Schedule modes: %s", list(self._schedule_data.schedules.keys()))
            
            export_context["data_summary"] = {
                "version": self._schedule_data.version,
                "entities_count": len(self._schedule_data.entities_tracked),
                "schedule_modes": list(self._schedule_data.schedules.keys())
            }
            
            # Ensure backup directory exists with detailed error handling
            try:
                if not self._backup_dir.exists():
                    _LOGGER.debug("Creating backup directory: %s", self._backup_dir)
                    self._backup_dir.mkdir(parents=True, exist_ok=True)
                    _LOGGER.debug("Successfully created backup directory: %s", self._backup_dir)
                
                # Verify directory is writable
                if not os.access(self._backup_dir, os.W_OK):
                    _LOGGER.error("Backup directory is not writable: %s", self._backup_dir)
                    export_context["directory_permission_error"] = "not_writable"
                    raise PermissionError(f"Backup directory is not writable: {self._backup_dir}")
                    
            except OSError as e:
                _LOGGER.error("Cannot create backup directory %s: %s (errno: %s)", 
                             self._backup_dir, e, getattr(e, 'errno', 'unknown'))
                export_context["directory_error"] = str(e)
                raise StorageError(f"Cannot create backup directory: {e}")
            
            # Generate filename if not provided
            if not path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"roost_scheduler_backup_{self.entry_id}_{timestamp}.json"
                path = str(self._backup_dir / filename)
                _LOGGER.debug("Generated backup filename: %s", filename)
            else:
                _LOGGER.debug("Using provided backup path: %s", path)
            
            export_context["final_path"] = path
            
            # Export data with comprehensive error handling
            try:
                # Use the ScheduleData's to_json method for consistent formatting
                _LOGGER.debug("Serializing schedule data to JSON")
                json_data = self._schedule_data.to_json()
                data_size = len(json_data)
                
                _LOGGER.debug("JSON serialization complete (size: %d bytes)", data_size)
                export_context["json_size"] = data_size
                
                # Write to file with error handling
                _LOGGER.debug("Writing backup data to file: %s", path)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(json_data)
                
                # Verify file was written successfully
                if os.path.exists(path):
                    written_size = os.path.getsize(path)
                    export_duration = datetime.now() - export_start_time
                    
                    _LOGGER.info("Backup export completed successfully:")
                    _LOGGER.info("  - Entry ID: %s", self.entry_id)
                    _LOGGER.info("  - File: %s", path)
                    _LOGGER.info("  - Size: %d bytes", written_size)
                    _LOGGER.info("  - Duration: %s", export_duration)
                    
                    export_context["success"] = True
                    export_context["written_size"] = written_size
                    export_context["duration"] = str(export_duration)
                    
                    if written_size != data_size:
                        _LOGGER.warning("Size mismatch in backup export: expected %d, written %d", 
                                       data_size, written_size)
                        export_context["size_mismatch"] = True
                    
                    return path
                else:
                    _LOGGER.error("Backup file was not created: %s", path)
                    export_context["file_not_created"] = True
                    raise StorageError(f"Backup file was not created: {path}")
                
            except json.JSONEncodeError as e:
                _LOGGER.error("JSON serialization failed during backup export:")
                _LOGGER.error("  - Error: %s", e)
                _LOGGER.error("  - Data version: %s", self._schedule_data.version)
                export_context["json_error"] = str(e)
                raise StorageError(f"Failed to serialize schedule data: {e}")
                
            except PermissionError as e:
                _LOGGER.error("Permission denied writing backup file %s: %s", path, e)
                export_context["permission_error"] = str(e)
                raise StorageError(f"Permission denied writing backup file: {e}")
                
            except OSError as e:
                _LOGGER.error("OS error writing backup file %s: %s (errno: %s)", 
                             path, e, getattr(e, 'errno', 'unknown'))
                export_context["os_error"] = str(e)
                raise StorageError(f"Failed to write backup file: {e}")
                
        except StorageError:
            # Re-raise StorageError as-is
            raise
        except Exception as e:
            export_duration = datetime.now() - export_start_time
            export_context["unexpected_error"] = str(e)
            export_context["error_type"] = type(e).__name__
            export_context["duration"] = str(export_duration)
            
            _LOGGER.error("Unexpected error during backup export:")
            _LOGGER.error("  - Entry ID: %s", self.entry_id)
            _LOGGER.error("  - Error: %s", e)
            _LOGGER.error("  - Error type: %s", type(e).__name__)
            _LOGGER.error("  - Duration: %s", export_duration)
            _LOGGER.error("  - Context: %s", export_context)
            
            raise StorageError(f"Failed to export backup: {e}")
    
    async def import_backup(self, file_path: str) -> bool:
        """Import schedule data from a backup file with comprehensive validation."""
        try:
            if not os.path.exists(file_path):
                _LOGGER.error("Backup file not found: %s", file_path)
                return False
            
            # Read and parse the backup file with enhanced validation
            # Read file with comprehensive error handling
            try:
                _LOGGER.debug("Reading backup file: %s", file_path)
                
                # Check file size first
                try:
                    file_size = os.path.getsize(file_path)
                    _LOGGER.debug("Backup file size: %d bytes", file_size)
                    
                    if file_size == 0:
                        _LOGGER.error("Backup file is empty: %s", file_path)
                        return False
                    elif file_size > 100 * 1024 * 1024:  # 100MB limit
                        _LOGGER.warning("Large backup file detected: %s (%d bytes)", file_path, file_size)
                except OSError as e:
                    _LOGGER.error("Cannot read file size for %s: %s", file_path, e)
                    return False
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    
                content_length = len(content)
                _LOGGER.debug("Read backup content: %d characters", content_length)
                    
                # Check if file is empty
                if not content:
                    _LOGGER.error("Backup file content is empty: %s", file_path)
                    return False
                
                # Parse JSON with detailed error handling
                try:
                    raw_data = json.loads(content)
                except json.JSONDecodeError as e:
                    _LOGGER.error("Invalid JSON in backup file %s at line %d, column %d: %s", 
                                file_path, e.lineno, e.colno, e.msg)
                    return False
                
                # Validate basic data structure with comprehensive analysis
                validation_result = self._validate_backup_data_structure(raw_data, file_path)
                if not validation_result["valid"]:
                    _LOGGER.error("Backup data structure validation failed for %s", file_path)
                    _LOGGER.error("Validation errors (%d):", len(validation_result["errors"]))
                    for error in validation_result["errors"]:
                        _LOGGER.error("  - %s", error)
                    
                    if validation_result.get("warnings"):
                        _LOGGER.warning("Validation warnings (%d):", len(validation_result["warnings"]))
                        for warning in validation_result["warnings"]:
                            _LOGGER.warning("  - %s", warning)
                    
                    # Log detailed analysis for troubleshooting
                    details = validation_result.get("details", {})
                    if "validation_score" in details:
                        _LOGGER.info("Validation score: %d/100", details["validation_score"])
                    
                    if "structure_analysis" in details:
                        analysis = details["structure_analysis"]
                        _LOGGER.debug("Structure analysis: %s", analysis)
                    
                    return False
                
                # Log validation success with details
                if validation_result.get("warnings"):
                    _LOGGER.info("Backup validation passed with %d warnings for %s", 
                               len(validation_result["warnings"]), file_path)
                    for warning in validation_result["warnings"]:
                        _LOGGER.warning("  - %s", warning)
                else:
                    _LOGGER.info("Backup validation passed successfully for %s", file_path)
                
                # Perform migration if needed
                migrated_data = await self._migration_manager.migrate_if_needed(raw_data)
                
                # Validate migrated data
                if not await self._migration_manager.validate_migrated_data(migrated_data):
                    _LOGGER.error("Backup data validation failed after migration for %s", file_path)
                    return False
                
                # Convert to ScheduleData object with additional validation
                try:
                    schedule_data = ScheduleData.from_dict(migrated_data)
                    # Perform additional validation on the created object
                    schedule_data.validate()
                except (ValueError, TypeError, AttributeError) as e:
                    _LOGGER.error("Failed to create valid ScheduleData from backup %s: %s", file_path, e)
                    return False
                
            except (OSError, UnicodeDecodeError) as e:
                _LOGGER.error("Error reading backup file %s: %s", file_path, e)
                return False
            except Exception as e:
                _LOGGER.error("Unexpected error processing backup file %s: %s", file_path, e)
                return False
            
            # Save imported data
            await self.save_schedules(schedule_data)
            
            _LOGGER.info("Successfully imported backup from %s", file_path)
            return True
        except Exception as e:
            _LOGGER.error("Unexpected error importing backup from %s: %s", file_path, e)
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
        """Attempt to recover from backups with comprehensive error handling and fallback strategies."""
        recovery_attempts = []
        
        # Check if backup directory exists
        if not self._backup_dir.exists():
            error_msg = f"Backup directory does not exist: {self._backup_dir}"
            _LOGGER.warning(error_msg)
            recovery_attempts.append({"file": "N/A", "error": error_msg, "strategy": "directory_check"})
            return await self._create_default_schedule_data("No backup directory found")
        
        # Find backup files
        try:
            backup_files = list(self._backup_dir.glob(f"*{self.entry_id}*.json"))
        except Exception as e:
            error_msg = f"Error scanning backup directory: {e}"
            _LOGGER.error(error_msg)
            recovery_attempts.append({"file": "N/A", "error": error_msg, "strategy": "directory_scan"})
            return await self._create_default_schedule_data("Cannot scan backup directory")
        
        if not backup_files:
            error_msg = f"No backup files found for entry {self.entry_id}"
            _LOGGER.warning(error_msg)
            recovery_attempts.append({"file": "N/A", "error": error_msg, "strategy": "file_search"})
            return await self._create_default_schedule_data("No backup files available")
        
        # Sort by modification time, newest first
        try:
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        except Exception as e:
            _LOGGER.warning("Error sorting backup files, using unsorted order: %s", e)
        
        _LOGGER.info("Found %d backup files for recovery attempt", len(backup_files))
        
        # Attempt recovery from each backup file
        for i, backup_file in enumerate(backup_files):
            attempt_info = {
                "file": str(backup_file),
                "strategy": f"backup_import_{i+1}",
                "error": None
            }
            
            try:
                _LOGGER.info("Recovery attempt %d/%d from %s", i+1, len(backup_files), backup_file.name)
                
                # Check file accessibility
                if not backup_file.exists():
                    attempt_info["error"] = "File no longer exists"
                    recovery_attempts.append(attempt_info)
                    continue
                
                if not backup_file.is_file():
                    attempt_info["error"] = "Path is not a regular file"
                    recovery_attempts.append(attempt_info)
                    continue
                
                # Check file size
                try:
                    file_size = backup_file.stat().st_size
                    if file_size == 0:
                        attempt_info["error"] = "File is empty"
                        recovery_attempts.append(attempt_info)
                        continue
                    elif file_size > 10 * 1024 * 1024:  # 10MB limit
                        attempt_info["error"] = f"File too large ({file_size} bytes)"
                        recovery_attempts.append(attempt_info)
                        continue
                except Exception as e:
                    attempt_info["error"] = f"Cannot read file stats: {e}"
                    recovery_attempts.append(attempt_info)
                    continue
                
                # Attempt import
                if await self.import_backup(str(backup_file)):
                    _LOGGER.info("Successfully recovered from %s (attempt %d/%d)", 
                               backup_file.name, i+1, len(backup_files))
                    
                    # Log recovery summary
                    self._log_recovery_summary(recovery_attempts, success=True, 
                                             successful_file=str(backup_file))
                    return self._schedule_data
                else:
                    attempt_info["error"] = "Import validation failed"
                    
            except PermissionError as e:
                attempt_info["error"] = f"Permission denied: {e}"
            except OSError as e:
                attempt_info["error"] = f"File system error: {e}"
            except Exception as e:
                attempt_info["error"] = f"Unexpected error: {e}"
            
            recovery_attempts.append(attempt_info)
            _LOGGER.warning("Recovery attempt %d failed for %s: %s", 
                          i+1, backup_file.name, attempt_info["error"])
        
        # All recovery attempts failed
        _LOGGER.error("All %d recovery attempts failed", len(backup_files))
        self._log_recovery_summary(recovery_attempts, success=False)
        
        # Final fallback: create default data
        _LOGGER.warning("Initiating graceful degradation with default data creation")
        default_data = await self._create_default_schedule_data("All backup recovery attempts failed")
        
        if default_data is None:
            _LOGGER.critical("Failed to create default data - integration cannot continue safely")
            raise StorageError("Complete recovery failure: cannot create default data")
        
        _LOGGER.info("Graceful degradation successful - integration will continue with default data")
        return default_data
    
    def _log_recovery_summary(self, attempts: list, success: bool, successful_file: str = None) -> None:
        """Log a summary of recovery attempts for troubleshooting."""
        _LOGGER.info("=== Backup Recovery Summary ===")
        _LOGGER.info("Total attempts: %d", len(attempts))
        _LOGGER.info("Success: %s", "Yes" if success else "No")
        
        if success and successful_file:
            _LOGGER.info("Successful file: %s", successful_file)
        
        if attempts:
            _LOGGER.info("Attempt details:")
            for i, attempt in enumerate(attempts, 1):
                _LOGGER.info("  %d. File: %s", i, attempt["file"])
                _LOGGER.info("     Strategy: %s", attempt["strategy"])
                if attempt["error"]:
                    _LOGGER.info("     Error: %s", attempt["error"])
        
        _LOGGER.info("=== End Recovery Summary ===")
    
    async def _create_default_schedule_data(self, reason: str) -> Optional[ScheduleData]:
        """Create default schedule data as a fallback recovery strategy.
        
        Args:
            reason: Reason why default data is being created
            
        Returns:
            Default ScheduleData object or None if creation fails
        """
        try:
            _LOGGER.warning("Creating default schedule data: %s", reason)
            
            # Import models here to avoid circular imports
            from .models import ScheduleData, PresenceConfig, GlobalBufferConfig
            from .version import VERSION
            
            # Create comprehensive default schedule data with all required fields
            current_time = datetime.now()
            
            # Create default presence configuration
            default_presence_config = PresenceConfig(
                entities=[],
                rule="anyone_home",
                timeout_seconds=600,
                override_entities={
                    "force_home": "input_boolean.roost_force_home",
                    "force_away": "input_boolean.roost_force_away"
                },
                custom_template=None,
                template_entities=[]
            )
            
            # Create default buffer configuration
            default_buffer_config = GlobalBufferConfig(
                time_minutes=15,
                value_delta=2.0,
                enabled=False,  # Start disabled for safety
                apply_to="climate",
                entity_overrides={}
            )
            
            # Create comprehensive default data structure
            default_data = {
                "version": VERSION,
                "entities_tracked": [],
                "presence_entities": [],
                "presence_rule": "anyone_home",
                "presence_timeout_seconds": 600,
                "buffer": {},  # Legacy buffer structure (empty)
                "ui": {
                    "resolution_minutes": 30,
                    "auto_add_card": False,
                    "theme": "default"
                },
                "schedules": {
                    "home": {},
                    "away": {}
                },
                "metadata": {
                    "created": current_time.isoformat(),
                    "last_modified": current_time.isoformat(),
                    "recovery_reason": reason,
                    "recovery_timestamp": current_time.isoformat(),
                    "default_data_version": VERSION,
                    "initialization_method": "graceful_degradation"
                },
                "presence_config": default_presence_config.to_dict(),
                "buffer_config": default_buffer_config.to_dict()
            }
            
            # Create ScheduleData object with validation
            try:
                schedule_data = ScheduleData.from_dict(default_data)
                
                # Perform additional validation to ensure data integrity
                schedule_data.validate()
                
                _LOGGER.info("Default schedule data validation passed")
                
            except Exception as validation_error:
                _LOGGER.error("Default data validation failed: %s", validation_error)
                
                # Create even more minimal fallback data if validation fails
                minimal_data = {
                    "version": VERSION,
                    "entities_tracked": [],
                    "presence_entities": [],
                    "presence_rule": "anyone_home", 
                    "presence_timeout_seconds": 600,
                    "buffer": {},
                    "ui": {},
                    "schedules": {"home": {}, "away": {}},
                    "metadata": {
                        "created": current_time.isoformat(),
                        "last_modified": current_time.isoformat(),
                        "recovery_reason": f"{reason} (validation fallback)",
                        "recovery_timestamp": current_time.isoformat(),
                        "fallback_level": "minimal"
                    }
                }
                
                schedule_data = ScheduleData.from_dict(minimal_data)
                _LOGGER.warning("Using minimal fallback data due to validation failure")
            
            # Save the default data
            await self.save_schedules(schedule_data)
            
            _LOGGER.info("Successfully created and saved default schedule data (reason: %s)", reason)
            
            # Log what was created for troubleshooting
            _LOGGER.debug("Default data summary:")
            _LOGGER.debug("  - Version: %s", schedule_data.version)
            _LOGGER.debug("  - Entities tracked: %d", len(schedule_data.entities_tracked))
            _LOGGER.debug("  - Presence entities: %d", len(schedule_data.presence_entities))
            _LOGGER.debug("  - Schedule modes: %s", list(schedule_data.schedules.keys()))
            _LOGGER.debug("  - Buffer config enabled: %s", 
                         schedule_data.buffer_config.enabled if schedule_data.buffer_config else False)
            
            return schedule_data
            
        except Exception as e:
            _LOGGER.error("Failed to create default schedule data: %s", e)
            _LOGGER.error("This is a critical error - integration may not function properly")
            
            # Last resort: return None to indicate complete failure
            # The calling code should handle this gracefully
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
    
    def _parse_backup_time(self, time_value: Any) -> tuple[int, int]:
        """Safely parse backup time handling different data types.
        
        Args:
            time_value: Time value that could be string, list, tuple, or other types
            
        Returns:
            Tuple of (hour, minute) as integers
            
        Raises:
            ValueError: If time_value cannot be parsed into valid time format
        """
        try:
            # Handle string format "HH:MM"
            if isinstance(time_value, str):
                if ':' in time_value:
                    parts = time_value.split(':')
                    if len(parts) == 2:
                        hour, minute = int(parts[0]), int(parts[1])
                        if 0 <= hour <= 23 and 0 <= minute <= 59:
                            return hour, minute
                raise ValueError(f"Invalid time string format: {time_value}")
            
            # Handle list or tuple format [hour, minute]
            elif isinstance(time_value, (list, tuple)) and len(time_value) == 2:
                hour, minute = int(time_value[0]), int(time_value[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return hour, minute
                raise ValueError(f"Invalid time values: hour={hour}, minute={minute}")
            
            # Handle dict format {"hour": X, "minute": Y}
            elif isinstance(time_value, dict):
                if "hour" in time_value and "minute" in time_value:
                    hour, minute = int(time_value["hour"]), int(time_value["minute"])
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        return hour, minute
                raise ValueError(f"Invalid time dict format: {time_value}")
            
            # Handle integer (assume minutes since midnight)
            elif isinstance(time_value, int):
                if 0 <= time_value <= 1439:  # 24*60-1 minutes in a day
                    hour, minute = divmod(time_value, 60)
                    return hour, minute
                raise ValueError(f"Invalid time integer (must be 0-1439 minutes): {time_value}")
            
            else:
                raise ValueError(f"Unsupported time format type: {type(time_value).__name__}")
                
        except (ValueError, TypeError, KeyError) as e:
            _LOGGER.error("Failed to parse backup time %s: %s", time_value, e)
            # Return default backup time (2:00 AM) on parsing failure
            _LOGGER.warning("Using default backup time 02:00 due to parsing error")
            return 2, 0
    
    def _validate_backup_data_structure(self, data: Any, file_path: str) -> Dict[str, Any]:
        """Validate the basic structure of backup data with comprehensive checks.
        
        Args:
            data: The parsed backup data to validate
            file_path: Path to the backup file for error reporting
            
        Returns:
            Dict with 'valid' boolean, 'errors' list, 'warnings' list, and 'details' dict
        """
        errors = []
        warnings = []
        details = {
            "file_path": file_path,
            "validation_timestamp": datetime.now().isoformat(),
            "data_size": len(str(data)) if data else 0,
            "structure_analysis": {}
        }
        
        try:
            # Check if data is a dictionary
            if not isinstance(data, dict):
                errors.append(f"Root data must be a dictionary, got {type(data).__name__}")
                details["structure_analysis"]["root_type"] = type(data).__name__
                return {"valid": False, "errors": errors, "warnings": warnings, "details": details}
            
            details["structure_analysis"]["root_type"] = "dict"
            details["structure_analysis"]["top_level_keys"] = list(data.keys())
            
            # Check for required top-level fields
            required_fields = ["version", "schedules"]
            optional_fields = ["entities_tracked", "presence_entities", "presence_rule", 
                             "presence_timeout_seconds", "buffer", "ui", "metadata", 
                             "presence_config", "buffer_config"]
            
            missing_required = []
            missing_optional = []
            
            for field in required_fields:
                if field not in data:
                    missing_required.append(field)
                    errors.append(f"Missing required field: {field}")
                elif data[field] is None:
                    errors.append(f"Required field '{field}' is null")
            
            for field in optional_fields:
                if field not in data:
                    missing_optional.append(field)
                    warnings.append(f"Missing optional field: {field}")
            
            details["structure_analysis"]["missing_required"] = missing_required
            details["structure_analysis"]["missing_optional"] = missing_optional
            
            # Validate version field with detailed checks
            if "version" in data:
                version = data["version"]
                details["structure_analysis"]["version"] = version
                
                if not isinstance(version, str):
                    errors.append(f"Version must be a string, got {type(version).__name__}")
                elif not version.strip():
                    errors.append("Version cannot be empty")
                else:
                    # Check version format (should be semantic versioning)
                    import re
                    version_pattern = r'^\d+\.\d+(\.\d+)?$'
                    if not re.match(version_pattern, version):
                        warnings.append(f"Version format may be invalid: {version} (expected X.Y or X.Y.Z)")
            
            # Validate schedules field with comprehensive structure analysis
            if "schedules" in data:
                schedules = data["schedules"]
                schedule_analysis = self._analyze_schedules_structure(schedules, errors, warnings)
                details["structure_analysis"]["schedules"] = schedule_analysis
            
            # Validate entities_tracked
            if "entities_tracked" in data:
                entities_analysis = self._validate_entity_list(
                    data["entities_tracked"], "entities_tracked", errors, warnings
                )
                details["structure_analysis"]["entities_tracked"] = entities_analysis
            
            # Validate presence_entities
            if "presence_entities" in data:
                presence_analysis = self._validate_entity_list(
                    data["presence_entities"], "presence_entities", errors, warnings
                )
                details["structure_analysis"]["presence_entities"] = presence_analysis
            
            # Validate presence_rule
            if "presence_rule" in data:
                rule = data["presence_rule"]
                valid_rules = {"anyone_home", "everyone_home", "custom"}
                if rule not in valid_rules:
                    errors.append(f"Invalid presence_rule: {rule} (must be one of {valid_rules})")
                details["structure_analysis"]["presence_rule"] = rule
            
            # Validate presence_timeout_seconds
            if "presence_timeout_seconds" in data:
                timeout = data["presence_timeout_seconds"]
                if not isinstance(timeout, int) or timeout < 0:
                    errors.append(f"presence_timeout_seconds must be non-negative integer, got {timeout}")
                elif timeout > 86400:  # 24 hours
                    warnings.append(f"presence_timeout_seconds is very large: {timeout} seconds")
                details["structure_analysis"]["presence_timeout_seconds"] = timeout
            
            # Validate metadata with detailed analysis
            if "metadata" in data:
                metadata = data["metadata"]
                if not isinstance(metadata, dict):
                    errors.append(f"Metadata must be a dictionary, got {type(metadata).__name__}")
                else:
                    metadata_analysis = self._analyze_metadata_structure(metadata, warnings)
                    details["structure_analysis"]["metadata"] = metadata_analysis
            
            # Validate buffer_config with detailed checks
            if "buffer_config" in data:
                buffer_config = data["buffer_config"]
                if not isinstance(buffer_config, dict):
                    errors.append(f"Buffer config must be a dictionary, got {type(buffer_config).__name__}")
                else:
                    buffer_analysis = self._analyze_buffer_config_structure(buffer_config, errors, warnings)
                    details["structure_analysis"]["buffer_config"] = buffer_analysis
            
            # Validate presence_config
            if "presence_config" in data:
                presence_config = data["presence_config"]
                if not isinstance(presence_config, dict):
                    errors.append(f"Presence config must be a dictionary, got {type(presence_config).__name__}")
                else:
                    presence_config_analysis = self._analyze_presence_config_structure(presence_config, errors, warnings)
                    details["structure_analysis"]["presence_config"] = presence_config_analysis
            
            # Check for unexpected data types in nested structures
            nested_validation_errors = []
            self._validate_nested_data_types(data, nested_validation_errors, "root")
            errors.extend(nested_validation_errors)
            
            # Calculate validation score
            total_checks = len(required_fields) + len(optional_fields) + 10  # Additional checks
            error_weight = len(errors) * 2
            warning_weight = len(warnings)
            validation_score = max(0, 100 - error_weight - warning_weight)
            details["validation_score"] = validation_score
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            details["validation_exception"] = str(e)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "details": details
        }
    
    def _analyze_schedules_structure(self, schedules: Any, errors: list, warnings: list) -> Dict[str, Any]:
        """Analyze schedules structure and return detailed information."""
        analysis = {
            "type": type(schedules).__name__,
            "modes": [],
            "total_slots": 0,
            "days_coverage": {},
            "validation_issues": []
        }
        
        if not isinstance(schedules, dict):
            errors.append(f"Schedules must be a dictionary, got {type(schedules).__name__}")
            return analysis
        
        valid_modes = {"home", "away"}
        valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        
        for mode, mode_schedules in schedules.items():
            analysis["modes"].append(mode)
            
            if mode not in valid_modes:
                warnings.append(f"Unexpected schedule mode: {mode}")
            
            if not isinstance(mode_schedules, dict):
                errors.append(f"Schedule mode '{mode}' must be a dictionary, got {type(mode_schedules).__name__}")
                continue
            
            mode_analysis = {"days": [], "slots_per_day": {}, "total_slots": 0}
            
            for day, day_schedules in mode_schedules.items():
                mode_analysis["days"].append(day)
                
                if day.lower() not in valid_days:
                    warnings.append(f"Invalid day in {mode} mode: {day}")
                
                if not isinstance(day_schedules, list):
                    errors.append(f"Day schedules for {mode}/{day} must be a list, got {type(day_schedules).__name__}")
                    continue
                
                slot_count = len(day_schedules)
                mode_analysis["slots_per_day"][day] = slot_count
                mode_analysis["total_slots"] += slot_count
                analysis["total_slots"] += slot_count
                
                # Validate individual slots
                for i, slot in enumerate(day_schedules):
                    if not isinstance(slot, dict):
                        errors.append(f"Slot {i} in {mode}/{day} must be a dictionary")
                        continue
                    
                    # Check required slot fields
                    required_slot_fields = ["start", "end", "target"]
                    for field in required_slot_fields:
                        if field not in slot:
                            errors.append(f"Slot {i} in {mode}/{day} missing required field: {field}")
            
            analysis["days_coverage"][mode] = mode_analysis
        
        return analysis
    
    def _validate_entity_list(self, entities: Any, field_name: str, errors: list, warnings: list) -> Dict[str, Any]:
        """Validate a list of entity IDs and return analysis."""
        analysis = {
            "type": type(entities).__name__,
            "count": 0,
            "valid_entities": [],
            "invalid_entities": [],
            "domains": set()
        }
        
        if not isinstance(entities, list):
            errors.append(f"{field_name} must be a list, got {type(entities).__name__}")
            return analysis
        
        analysis["count"] = len(entities)
        
        for i, entity_id in enumerate(entities):
            if not isinstance(entity_id, str):
                errors.append(f"{field_name}[{i}] must be a string, got {type(entity_id).__name__}")
                analysis["invalid_entities"].append(f"Index {i}: not a string")
                continue
            
            if not entity_id.strip():
                errors.append(f"{field_name}[{i}] cannot be empty")
                analysis["invalid_entities"].append(f"Index {i}: empty string")
                continue
            
            if '.' not in entity_id:
                errors.append(f"{field_name}[{i}] must be in format 'domain.entity': {entity_id}")
                analysis["invalid_entities"].append(f"Index {i}: invalid format")
                continue
            
            domain, entity = entity_id.split('.', 1)
            if not domain or not entity:
                errors.append(f"{field_name}[{i}] has empty domain or entity part: {entity_id}")
                analysis["invalid_entities"].append(f"Index {i}: empty parts")
                continue
            
            analysis["valid_entities"].append(entity_id)
            analysis["domains"].add(domain)
        
        analysis["domains"] = list(analysis["domains"])
        return analysis
    
    def _analyze_metadata_structure(self, metadata: Dict[str, Any], warnings: list) -> Dict[str, Any]:
        """Analyze metadata structure and return information."""
        analysis = {
            "keys": list(metadata.keys()),
            "has_timestamps": False,
            "has_version_info": False,
            "has_recovery_info": False
        }
        
        # Check for common metadata fields
        timestamp_fields = ["created", "last_modified", "created_at", "updated_at"]
        version_fields = ["version", "migration_completed", "last_migration"]
        recovery_fields = ["recovery_reason", "recovery_timestamp", "backup_metadata"]
        
        for field in timestamp_fields:
            if field in metadata:
                analysis["has_timestamps"] = True
                break
        
        for field in version_fields:
            if field in metadata:
                analysis["has_version_info"] = True
                break
        
        for field in recovery_fields:
            if field in metadata:
                analysis["has_recovery_info"] = True
                break
        
        # Validate timestamp formats
        for key, value in metadata.items():
            if "time" in key.lower() or "date" in key.lower():
                if isinstance(value, str):
                    try:
                        datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        warnings.append(f"Metadata field '{key}' appears to be a timestamp but has invalid format: {value}")
        
        return analysis
    
    def _analyze_buffer_config_structure(self, buffer_config: Dict[str, Any], errors: list, warnings: list) -> Dict[str, Any]:
        """Analyze buffer configuration structure."""
        analysis = {
            "keys": list(buffer_config.keys()),
            "has_required_fields": True,
            "field_types": {}
        }
        
        required_fields = {
            "time_minutes": int,
            "value_delta": (int, float),
            "enabled": bool,
            "apply_to": str
        }
        
        for field, expected_type in required_fields.items():
            if field not in buffer_config:
                errors.append(f"Buffer config missing required field: {field}")
                analysis["has_required_fields"] = False
            else:
                value = buffer_config[field]
                analysis["field_types"][field] = type(value).__name__
                
                if not isinstance(value, expected_type):
                    errors.append(f"Buffer config field '{field}' must be {expected_type}, got {type(value).__name__}")
                elif field == "time_minutes" and (value < 0 or value > 1440):
                    warnings.append(f"Buffer time_minutes value seems unusual: {value}")
                elif field == "value_delta" and (value < 0 or value > 50):
                    warnings.append(f"Buffer value_delta seems unusual: {value}")
        
        # Check for entity overrides
        if "entity_overrides" in buffer_config:
            overrides = buffer_config["entity_overrides"]
            if isinstance(overrides, dict):
                analysis["entity_overrides_count"] = len(overrides)
            else:
                errors.append("Buffer config entity_overrides must be a dictionary")
        
        return analysis
    
    def _analyze_presence_config_structure(self, presence_config: Dict[str, Any], errors: list, warnings: list) -> Dict[str, Any]:
        """Analyze presence configuration structure."""
        analysis = {
            "keys": list(presence_config.keys()),
            "entity_count": 0,
            "has_overrides": False
        }
        
        # Validate entities
        if "entities" in presence_config:
            entities = presence_config["entities"]
            if isinstance(entities, list):
                analysis["entity_count"] = len(entities)
                entity_analysis = self._validate_entity_list(entities, "presence_config.entities", errors, warnings)
                analysis["entity_analysis"] = entity_analysis
            else:
                errors.append("Presence config entities must be a list")
        
        # Check for override entities
        if "override_entities" in presence_config:
            overrides = presence_config["override_entities"]
            if isinstance(overrides, dict):
                analysis["has_overrides"] = True
                analysis["override_count"] = len(overrides)
            else:
                errors.append("Presence config override_entities must be a dictionary")
        
        # Validate rule
        if "rule" in presence_config:
            rule = presence_config["rule"]
            valid_rules = {"anyone_home", "everyone_home", "custom"}
            if rule not in valid_rules:
                errors.append(f"Invalid presence rule: {rule}")
            analysis["rule"] = rule
        
        return analysis
    
    def _validate_nested_data_types(self, data: Any, errors: list, path: str) -> None:
        """Recursively validate data types in nested structures.
        
        Args:
            data: Data to validate
            errors: List to append errors to
            path: Current path in the data structure for error reporting
        """
        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    # Validate key type
                    if not isinstance(key, str):
                        errors.append(f"Dictionary key at '{path}' must be string, got {type(key).__name__}")
                    
                    # Recursively validate values
                    new_path = f"{path}.{key}" if path != "root" else key
                    self._validate_nested_data_types(value, errors, new_path)
                    
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    new_path = f"{path}[{i}]"
                    self._validate_nested_data_types(item, errors, new_path)
                    
            elif isinstance(data, (str, int, float, bool)) or data is None:
                # These are valid JSON types
                pass
            else:
                # Invalid type for JSON
                errors.append(f"Invalid data type at '{path}': {type(data).__name__}")
                
        except Exception as e:
            errors.append(f"Error validating nested data at '{path}': {str(e)}")
    
    async def schedule_nightly_backup(self) -> None:
        """Schedule the nightly backup using Home Assistant's time tracking."""
        if not self._nightly_backup_enabled:
            return
        
        try:
            from homeassistant.helpers.event import async_track_time_change
            
            # Parse backup time with type safety
            hour, minute = self._parse_backup_time(self._nightly_backup_time)
            
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
    
    def get_config_entry_data(self) -> Optional[Dict[str, Any]]:
        """Get config entry data for migration purposes."""
        try:
            # Access the config entry from Home Assistant
            from homeassistant.config_entries import ConfigEntry
            from .const import DOMAIN
            
            # Find the config entry for this entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.entry_id == self.entry_id:
                    # Return both entry data and options
                    return {
                        **entry.data,
                        **entry.options
                    }
            
            _LOGGER.debug("Config entry not found for entry_id: %s", self.entry_id)
            return None
        except Exception as e:
            _LOGGER.error("Error accessing config entry data: %s", e)
            return None