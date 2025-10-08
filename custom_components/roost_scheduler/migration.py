"""Migration system for Roost Scheduler version upgrades."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import aiofiles

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


# Async file utility functions for safe file operations
async def async_read_json_file(file_path: Path) -> dict[str, Any]:
    """Safely read JSON data from a file using async I/O with comprehensive error logging."""
    operation_start = datetime.now()
    
    try:
        # Log file operation start
        _LOGGER.debug("Starting async JSON file read: %s", file_path)
        
        # Check file existence and accessibility
        if not file_path.exists():
            _LOGGER.debug("File not found during read operation: %s", file_path)
            return {}
        
        if not file_path.is_file():
            _LOGGER.error("Path is not a regular file: %s (type: %s)", 
                         file_path, "directory" if file_path.is_dir() else "other")
            raise OSError(f"Path is not a regular file: {file_path}")
        
        # Check file size for safety
        try:
            file_size = file_path.stat().st_size
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                _LOGGER.warning("Large file detected during read: %s (size: %d bytes)", file_path, file_size)
            elif file_size == 0:
                _LOGGER.warning("Empty file detected during read: %s", file_path)
                return {}
        except OSError as e:
            _LOGGER.error("Cannot read file stats for %s: %s", file_path, e)
            raise
        
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            
        # Log successful read
        operation_duration = datetime.now() - operation_start
        _LOGGER.debug("Successfully read JSON file %s (size: %d bytes, duration: %s)", 
                     file_path, len(content), operation_duration)
        
        # Parse JSON with detailed error handling
        try:
            parsed_data = json.loads(content)
            _LOGGER.debug("Successfully parsed JSON from %s (keys: %s)", 
                         file_path, list(parsed_data.keys()) if isinstance(parsed_data, dict) else "non-dict")
            return parsed_data
        except json.JSONDecodeError as e:
            _LOGGER.error("JSON parsing failed for file %s:", file_path)
            _LOGGER.error("  - Error: %s", e.msg)
            _LOGGER.error("  - Line: %d, Column: %d", e.lineno, e.colno)
            _LOGGER.error("  - Position: %d", e.pos)
            if len(content) > 0:
                # Show context around the error
                lines = content.split('\n')
                if e.lineno <= len(lines):
                    error_line = lines[e.lineno - 1] if e.lineno > 0 else ""
                    _LOGGER.error("  - Error line: %s", error_line[:100])
            raise
            
    except FileNotFoundError:
        _LOGGER.debug("File not found during async read: %s", file_path)
        return {}
    except PermissionError as e:
        operation_duration = datetime.now() - operation_start
        _LOGGER.error("Permission denied reading file %s after %s: %s", file_path, operation_duration, e)
        raise
    except UnicodeDecodeError as e:
        operation_duration = datetime.now() - operation_start
        _LOGGER.error("Unicode decode error reading file %s after %s:", file_path, operation_duration)
        _LOGGER.error("  - Encoding: %s", e.encoding)
        _LOGGER.error("  - Position: %d-%d", e.start, e.end)
        _LOGGER.error("  - Reason: %s", e.reason)
        raise
    except OSError as e:
        operation_duration = datetime.now() - operation_start
        _LOGGER.error("OS error reading file %s after %s: %s (errno: %s)", 
                     file_path, operation_duration, e, getattr(e, 'errno', 'unknown'))
        raise
    except Exception as e:
        operation_duration = datetime.now() - operation_start
        _LOGGER.error("Unexpected error reading file %s after %s: %s (type: %s)", 
                     file_path, operation_duration, e, type(e).__name__)
        raise


async def async_write_json_file(file_path: Path, data: dict[str, Any]) -> None:
    """Safely write JSON data to a file using async I/O with comprehensive error logging."""
    operation_start = datetime.now()
    
    try:
        _LOGGER.debug("Starting async JSON file write: %s", file_path)
        
        # Validate input data
        if not isinstance(data, dict):
            _LOGGER.error("Invalid data type for JSON write to %s: expected dict, got %s", 
                         file_path, type(data).__name__)
            raise TypeError(f"Data must be a dictionary, got {type(data).__name__}")
        
        # Ensure parent directory exists with detailed logging
        parent_dir = file_path.parent
        if not parent_dir.exists():
            _LOGGER.debug("Creating parent directory: %s", parent_dir)
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
                _LOGGER.debug("Successfully created parent directory: %s", parent_dir)
            except OSError as e:
                _LOGGER.error("Failed to create parent directory %s: %s (errno: %s)", 
                             parent_dir, e, getattr(e, 'errno', 'unknown'))
                raise
        
        # Serialize data with error handling
        try:
            json_content = json.dumps(data, indent=2, default=str)
            content_size = len(json_content)
            _LOGGER.debug("Serialized JSON data for %s (size: %d bytes)", file_path, content_size)
        except (TypeError, ValueError) as e:
            _LOGGER.error("JSON serialization failed for file %s: %s", file_path, e)
            _LOGGER.error("Data keys: %s", list(data.keys()) if isinstance(data, dict) else "not a dict")
            raise
        
        # Write data with proper formatting
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json_content)
        except PermissionError as e:
            _LOGGER.error("Permission denied writing to file %s: %s", file_path, e)
            raise
        except OSError as e:
            _LOGGER.error("OS error writing to file %s: %s (errno: %s)", 
                         file_path, e, getattr(e, 'errno', 'unknown'))
            raise
        
        # Verify write success
        operation_duration = datetime.now() - operation_start
        try:
            written_size = file_path.stat().st_size
            _LOGGER.debug("Successfully wrote JSON file %s (size: %d bytes, duration: %s)", 
                         file_path, written_size, operation_duration)
            
            if written_size != content_size:
                _LOGGER.warning("Size mismatch after write to %s: expected %d, actual %d", 
                               file_path, content_size, written_size)
        except OSError as e:
            _LOGGER.warning("Cannot verify file size after write to %s: %s", file_path, e)
            
    except Exception as e:
        operation_duration = datetime.now() - operation_start
        _LOGGER.error("Error writing file %s after %s: %s (type: %s)", 
                     file_path, operation_duration, e, type(e).__name__)
        raise


async def async_copy_file(src_path: Path, dst_path: Path) -> None:
    """Safely copy a file using async I/O with comprehensive error logging."""
    operation_start = datetime.now()
    
    try:
        _LOGGER.debug("Starting async file copy: %s -> %s", src_path, dst_path)
        
        # Validate source file
        if not src_path.exists():
            _LOGGER.error("Source file does not exist for copy operation: %s", src_path)
            raise FileNotFoundError(f"Source file not found: {src_path}")
        
        if not src_path.is_file():
            _LOGGER.error("Source path is not a regular file: %s", src_path)
            raise OSError(f"Source is not a regular file: {src_path}")
        
        # Check source file size and permissions
        try:
            src_stat = src_path.stat()
            src_size = src_stat.st_size
            _LOGGER.debug("Source file info: %s (size: %d bytes)", src_path, src_size)
            
            if src_size > 100 * 1024 * 1024:  # 100MB limit
                _LOGGER.warning("Large file copy operation: %s (size: %d bytes)", src_path, src_size)
        except OSError as e:
            _LOGGER.error("Cannot read source file stats %s: %s", src_path, e)
            raise
        
        # Ensure destination directory exists
        dst_parent = dst_path.parent
        if not dst_parent.exists():
            _LOGGER.debug("Creating destination directory: %s", dst_parent)
            try:
                dst_parent.mkdir(parents=True, exist_ok=True)
                _LOGGER.debug("Successfully created destination directory: %s", dst_parent)
            except OSError as e:
                _LOGGER.error("Failed to create destination directory %s: %s", dst_parent, e)
                raise
        
        # Check if destination already exists
        if dst_path.exists():
            _LOGGER.warning("Destination file already exists, will overwrite: %s", dst_path)
        
        # Perform the copy operation
        try:
            async with aiofiles.open(src_path, 'r', encoding='utf-8') as src:
                content = await src.read()
                content_size = len(content)
                _LOGGER.debug("Read source content: %d characters", content_size)
                
            async with aiofiles.open(dst_path, 'w', encoding='utf-8') as dst:
                await dst.write(content)
                _LOGGER.debug("Wrote content to destination: %s", dst_path)
                
        except PermissionError as e:
            _LOGGER.error("Permission denied during file copy %s -> %s: %s", src_path, dst_path, e)
            raise
        except UnicodeDecodeError as e:
            _LOGGER.error("Unicode decode error copying %s -> %s:", src_path, dst_path)
            _LOGGER.error("  - Encoding: %s", e.encoding)
            _LOGGER.error("  - Position: %d-%d", e.start, e.end)
            _LOGGER.error("  - Reason: %s", e.reason)
            raise
        except OSError as e:
            _LOGGER.error("OS error during file copy %s -> %s: %s (errno: %s)", 
                         src_path, dst_path, e, getattr(e, 'errno', 'unknown'))
            raise
        
        # Verify copy success
        operation_duration = datetime.now() - operation_start
        try:
            dst_stat = dst_path.stat()
            dst_size = dst_stat.st_size
            
            _LOGGER.debug("Successfully copied file %s -> %s (size: %d bytes, duration: %s)", 
                         src_path, dst_path, dst_size, operation_duration)
            
            # Verify sizes match (for text files, this should be close)
            if abs(src_size - dst_size) > src_size * 0.1:  # Allow 10% difference for encoding
                _LOGGER.warning("Significant size difference after copy %s -> %s: src=%d, dst=%d", 
                               src_path, dst_path, src_size, dst_size)
        except OSError as e:
            _LOGGER.warning("Cannot verify destination file after copy to %s: %s", dst_path, e)
            
    except Exception as e:
        operation_duration = datetime.now() - operation_start
        _LOGGER.error("Error copying file %s -> %s after %s: %s (type: %s)", 
                     src_path, dst_path, operation_duration, e, type(e).__name__)
        raise


async def async_file_exists(file_path: Path) -> bool:
    """Check if a file exists using async-safe operations."""
    try:
        # Use pathlib's exists() which is safe for async contexts
        return file_path.exists() and file_path.is_file()
    except Exception as e:
        _LOGGER.error("Error checking file existence %s: %s", file_path, e)
        return False


async def async_ensure_directory(dir_path: Path) -> None:
    """Ensure a directory exists using async-safe operations."""
    try:
        # mkdir is safe for async contexts as it's not I/O bound
        dir_path.mkdir(parents=True, exist_ok=True)
        _LOGGER.debug("Ensured directory exists: %s", dir_path)
    except Exception as e:
        _LOGGER.error("Error creating directory %s: %s", dir_path, e)
        raise


class MigrationManager:
    """Manages data migration between versions."""
    
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize migration manager."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, 1, f"{STORAGE_KEY}_{entry_id}")
        
    async def migrate_if_needed(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate data if version upgrade is detected."""
        _LOGGER.info("Starting migration check for entry %s", self.entry_id)
        
        if not data:
            _LOGGER.info("No existing data found for entry %s, no migration needed", self.entry_id)
            return data
            
        stored_version = data.get("version", "0.1.0")
        _LOGGER.info("Found existing data with version %s for entry %s", stored_version, self.entry_id)
        
        if stored_version == VERSION:
            _LOGGER.info("Data is already at current version %s for entry %s, no migration needed", 
                        VERSION, self.entry_id)
            return data
            
        if not is_version_supported(stored_version):
            _LOGGER.error(
                "Cannot migrate from unsupported version %s to %s for entry %s", 
                stored_version, 
                VERSION,
                self.entry_id
            )
            raise ValueError(f"Unsupported migration from version {stored_version} to {VERSION}")
        
        _LOGGER.info("Starting migration from version %s to %s for entry %s", 
                    stored_version, VERSION, self.entry_id)
        
        # Create backup before migration
        _LOGGER.info("Creating pre-migration backup for entry %s", self.entry_id)
        await self._create_migration_backup(data, stored_version)
        
        # Get migration path
        migration_path = get_migration_path(stored_version)
        _LOGGER.info("Migration path for entry %s: %s -> %s (steps: %s)", 
                    self.entry_id, stored_version, VERSION, migration_path)
        
        if not migration_path:
            _LOGGER.warning("No migration path found from %s to %s for entry %s, updating version only", 
                          stored_version, VERSION, self.entry_id)
            # Still update the version even if no migration path exists
            updated_data = data.copy()
            updated_data["version"] = VERSION
            
            # Add metadata about the version update
            if "metadata" not in updated_data:
                updated_data["metadata"] = {}
            
            updated_data["metadata"]["version_update"] = {
                "from_version": stored_version,
                "to_version": VERSION,
                "timestamp": datetime.now().isoformat(),
                "update_type": "direct_version_update"
            }
            
            _LOGGER.info("Updated version directly from %s to %s for entry %s", 
                        stored_version, VERSION, self.entry_id)
            return updated_data
        
        # Apply migrations in sequence
        migrated_data = data.copy()
        
        for target_version in migration_path:
            if target_version in MIGRATIONS:
                _LOGGER.info("Applying migration to version %s", target_version)
                try:
                    migrated_data = MIGRATIONS[target_version](migrated_data)
                    migrated_data["version"] = target_version
                    
                    # Update metadata for this migration step
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
                _LOGGER.info("No migration function found for version %s, updating version metadata", target_version)
                # Even without a migration function, update the version to indicate successful migration
                migrated_data["version"] = target_version
                
                # Update metadata to track version update
                if "metadata" not in migrated_data:
                    migrated_data["metadata"] = {}
                
                migrated_data["metadata"]["last_migration"] = {
                    "from_version": stored_version,
                    "to_version": target_version,
                    "timestamp": datetime.now().isoformat(),
                    "migration_id": f"{stored_version}_to_{target_version}",
                    "migration_type": "version_update_only"
                }
        
        # Ensure final version is set to current VERSION
        migrated_data["version"] = VERSION
        
        # Update final migration metadata
        if "metadata" not in migrated_data:
            migrated_data["metadata"] = {}
        
        migrated_data["metadata"]["migration_completed"] = {
            "from_version": stored_version,
            "to_version": VERSION,
            "timestamp": datetime.now().isoformat(),
            "migration_path": migration_path
        }
        
        # Log migration statistics
        await self._log_migration_statistics(stored_version, VERSION, migration_path, migrated_data)
        
        _LOGGER.info("Migration completed successfully from %s to %s for entry %s", 
                    stored_version, VERSION, self.entry_id)
        
        # Validate migrated data
        _LOGGER.info("Validating migrated data for entry %s", self.entry_id)
        validation_start_time = datetime.now()
        
        if not await self.validate_migrated_data(migrated_data):
            _LOGGER.error("Migration validation failed for entry %s after %s", 
                         self.entry_id, datetime.now() - validation_start_time)
            raise ValueError("Migration validation failed - data integrity check failed")
        
        validation_duration = datetime.now() - validation_start_time
        _LOGGER.info("Migration validation completed successfully for entry %s in %s", 
                    self.entry_id, validation_duration)
        
        return migrated_data
    
    async def _create_migration_backup(self, data: dict[str, Any], from_version: str) -> None:
        """Create a backup before migration with comprehensive error logging."""
        backup_start_time = datetime.now()
        backup_context = {
            "entry_id": self.entry_id,
            "from_version": from_version,
            "to_version": VERSION,
            "data_size": len(str(data)) if data else 0,
            "operation": "pre_migration_backup"
        }
        
        try:
            _LOGGER.info("Starting migration backup creation for entry %s (version %s -> %s)", 
                        self.entry_id, from_version, VERSION)
            
            backup_dir = Path(self.hass.config.config_dir) / "roost_scheduler_backups"
            _LOGGER.debug("Backup directory path: %s", backup_dir)
            
            # Ensure backup directory exists with detailed logging
            try:
                await async_ensure_directory(backup_dir)
                _LOGGER.debug("Backup directory ready: %s", backup_dir)
            except Exception as dir_error:
                _LOGGER.error("Failed to create backup directory %s: %s (type: %s)", 
                             backup_dir, dir_error, type(dir_error).__name__)
                backup_context["directory_error"] = str(dir_error)
                raise
            
            # Generate backup filename with detailed metadata
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"pre_migration_{from_version}_to_{VERSION}_{self.entry_id}_{timestamp}.json"
            backup_path = backup_dir / backup_filename
            
            _LOGGER.info("Creating migration backup file: %s", backup_path)
            backup_context["backup_path"] = str(backup_path)
            backup_context["backup_filename"] = backup_filename
            
            # Validate input data before backup
            if not isinstance(data, dict):
                _LOGGER.error("Invalid data type for backup: expected dict, got %s", type(data).__name__)
                backup_context["data_validation_error"] = f"Invalid type: {type(data).__name__}"
                raise TypeError(f"Backup data must be a dictionary, got {type(data).__name__}")
            
            if not data:
                _LOGGER.warning("Empty data provided for backup - creating minimal backup")
                backup_context["data_warning"] = "empty_data"
            
            # Add comprehensive backup metadata
            backup_data = data.copy()
            backup_metadata = {
                "created_at": datetime.now().isoformat(),
                "entry_id": self.entry_id,
                "source_version": from_version,
                "target_version": VERSION,
                "backup_type": "pre_migration",
                "backup_filename": backup_filename,
                "original_data_size": len(str(data)),
                "backup_context": backup_context.copy()
            }
            
            # Add data summary for troubleshooting
            if isinstance(data, dict):
                backup_metadata["data_summary"] = {
                    "top_level_keys": list(data.keys()),
                    "version": data.get("version", "unknown"),
                    "entities_count": len(data.get("entities_tracked", [])),
                    "schedules_modes": list(data.get("schedules", {}).keys())
                }
            
            backup_data["backup_metadata"] = backup_metadata
            
            # Use async file operations to write the backup
            try:
                await async_write_json_file(backup_path, backup_data)
                _LOGGER.debug("Backup file written successfully: %s", backup_path)
            except Exception as write_error:
                _LOGGER.error("Failed to write backup file %s: %s (type: %s)", 
                             backup_path, write_error, type(write_error).__name__)
                backup_context["write_error"] = str(write_error)
                raise
            
            # Verify backup file was created successfully
            backup_duration = datetime.now() - backup_start_time
            try:
                if backup_path.exists():
                    backup_size = backup_path.stat().st_size
                    _LOGGER.info("Migration backup created successfully:")
                    _LOGGER.info("  - Entry ID: %s", self.entry_id)
                    _LOGGER.info("  - File: %s", backup_path)
                    _LOGGER.info("  - Size: %d bytes", backup_size)
                    _LOGGER.info("  - Duration: %s", backup_duration)
                    _LOGGER.info("  - Version: %s -> %s", from_version, VERSION)
                    
                    backup_context["success"] = True
                    backup_context["backup_size"] = backup_size
                    backup_context["duration"] = str(backup_duration)
                else:
                    _LOGGER.error("Backup file was not created: %s", backup_path)
                    backup_context["verification_error"] = "file_not_found"
                    raise FileNotFoundError(f"Backup file was not created: {backup_path}")
                    
            except OSError as verify_error:
                _LOGGER.error("Cannot verify backup file %s: %s", backup_path, verify_error)
                backup_context["verification_error"] = str(verify_error)
                # Don't fail if we can't verify, the write might have succeeded
                
        except Exception as e:
            backup_duration = datetime.now() - backup_start_time
            backup_context["success"] = False
            backup_context["error"] = str(e)
            backup_context["error_type"] = type(e).__name__
            backup_context["duration"] = str(backup_duration)
            
            _LOGGER.error("Migration backup creation failed for entry %s:", self.entry_id)
            _LOGGER.error("  - Error: %s", e)
            _LOGGER.error("  - Error type: %s", type(e).__name__)
            _LOGGER.error("  - Duration: %s", backup_duration)
            _LOGGER.error("  - Context: %s", backup_context)
            
            # Don't fail migration if backup fails, but log the error prominently
            _LOGGER.warning("Migration will continue without backup for entry %s - this increases risk", self.entry_id)
            _LOGGER.warning("Consider manually backing up data before proceeding with migration")
    
    async def validate_migrated_data(self, data: dict[str, Any]) -> bool:
        """Validate migrated data structure with comprehensive validation and detailed error reporting."""
        validation_result = {
            "errors": [],
            "warnings": [],
            "details": {
                "validation_timestamp": datetime.now().isoformat(),
                "data_version": data.get("version", "unknown"),
                "expected_version": VERSION,
                "structure_checks": {},
                "field_analysis": {}
            }
        }
        
        try:
            # Check required top-level keys with detailed analysis
            required_keys = ["version", "entities_tracked", "schedules"]
            optional_keys = ["presence_entities", "presence_rule", "presence_timeout_seconds", 
                           "buffer", "ui", "metadata", "presence_config", "buffer_config"]
            
            missing_required = []
            missing_optional = []
            present_keys = list(data.keys())
            
            for key in required_keys:
                if key not in data:
                    missing_required.append(key)
                    validation_result["errors"].append(f"Missing required key: {key}")
            
            for key in optional_keys:
                if key not in data:
                    missing_optional.append(key)
                    validation_result["warnings"].append(f"Missing optional key: {key}")
            
            validation_result["details"]["structure_checks"] = {
                "present_keys": present_keys,
                "missing_required": missing_required,
                "missing_optional": missing_optional,
                "unexpected_keys": [k for k in present_keys if k not in required_keys + optional_keys]
            }
            
            # Validate version with detailed analysis
            actual_version = data.get("version")
            version_analysis = {
                "actual": actual_version,
                "expected": VERSION,
                "is_supported": False,
                "is_current": False
            }
            
            if actual_version == VERSION:
                version_analysis["is_current"] = True
                version_analysis["is_supported"] = True
            elif actual_version and is_version_supported(actual_version):
                version_analysis["is_supported"] = True
                _LOGGER.warning("Version %s is supported but not current (%s), accepting as valid", 
                              actual_version, VERSION)
                validation_result["warnings"].append(f"Version {actual_version} is outdated (current: {VERSION})")
            else:
                validation_result["errors"].append(f"Version mismatch: expected {VERSION}, got {actual_version}")
            
            validation_result["details"]["field_analysis"]["version"] = version_analysis
            
            # Validate entities_tracked with detailed analysis
            entities_tracked = data.get("entities_tracked")
            entities_analysis = self._analyze_entity_field(entities_tracked, "entities_tracked", validation_result)
            validation_result["details"]["field_analysis"]["entities_tracked"] = entities_analysis
            
            # Validate presence_entities if present
            if "presence_entities" in data:
                presence_entities = data.get("presence_entities")
                presence_analysis = self._analyze_entity_field(presence_entities, "presence_entities", validation_result)
                validation_result["details"]["field_analysis"]["presence_entities"] = presence_analysis
            
            # Validate schedules structure with comprehensive analysis
            schedules = data.get("schedules", {})
            schedules_analysis = self._analyze_schedules_field(schedules, validation_result)
            validation_result["details"]["field_analysis"]["schedules"] = schedules_analysis
            
            # Validate metadata with analysis
            if "metadata" in data:
                metadata = data.get("metadata")
                metadata_analysis = self._analyze_metadata_field(metadata, validation_result)
                validation_result["details"]["field_analysis"]["metadata"] = metadata_analysis
            
            # Validate presence_config if present
            if "presence_config" in data:
                presence_config = data.get("presence_config")
                presence_config_analysis = self._analyze_presence_config_field(presence_config, validation_result)
                validation_result["details"]["field_analysis"]["presence_config"] = presence_config_analysis
            
            # Validate buffer_config if present
            if "buffer_config" in data:
                buffer_config = data.get("buffer_config")
                buffer_config_analysis = self._analyze_buffer_config_field(buffer_config, validation_result)
                validation_result["details"]["field_analysis"]["buffer_config"] = buffer_config_analysis
            
            # Calculate validation score
            total_possible_points = 100
            error_penalty = len(validation_result["errors"]) * 10
            warning_penalty = len(validation_result["warnings"]) * 2
            validation_score = max(0, total_possible_points - error_penalty - warning_penalty)
            validation_result["details"]["validation_score"] = validation_score
            
            # Log comprehensive validation results
            if validation_result["errors"]:
                _LOGGER.error("Migration validation failed with %d errors and %d warnings (score: %d/100):", 
                            len(validation_result["errors"]), len(validation_result["warnings"]), validation_score)
                
                _LOGGER.error("Validation errors:")
                for error in validation_result["errors"]:
                    _LOGGER.error("  - %s", error)
                
                if validation_result["warnings"]:
                    _LOGGER.warning("Validation warnings:")
                    for warning in validation_result["warnings"]:
                        _LOGGER.warning("  - %s", warning)
                
                # Log detailed analysis for troubleshooting
                _LOGGER.debug("Detailed validation analysis: %s", validation_result["details"])
                
                return False
            else:
                if validation_result["warnings"]:
                    _LOGGER.info("Migration validation passed with %d warnings (score: %d/100)", 
                               len(validation_result["warnings"]), validation_score)
                    for warning in validation_result["warnings"]:
                        _LOGGER.warning("  - %s", warning)
                else:
                    _LOGGER.info("Migration validation passed successfully (score: %d/100)", validation_score)
                
                return True
            
        except Exception as e:
            _LOGGER.error("Error during migration validation: %s", e)
            validation_result["errors"].append(f"Validation exception: {e}")
            validation_result["details"]["validation_exception"] = str(e)
            return False
    
    def _analyze_entity_field(self, entities: Any, field_name: str, validation_result: dict) -> dict:
        """Analyze an entity list field and add validation results."""
        analysis = {
            "type": type(entities).__name__,
            "count": 0,
            "valid_entities": [],
            "invalid_entities": [],
            "domains": set()
        }
        
        if entities is None:
            validation_result["warnings"].append(f"{field_name} is None")
            return analysis
        
        if not isinstance(entities, list):
            validation_result["errors"].append(f"{field_name} must be a list, got {type(entities).__name__}")
            return analysis
        
        analysis["count"] = len(entities)
        
        for i, entity_id in enumerate(entities):
            if not isinstance(entity_id, str):
                validation_result["errors"].append(f"{field_name}[{i}] must be a string, got {type(entity_id).__name__}")
                analysis["invalid_entities"].append(f"Index {i}: not a string")
                continue
            
            if not entity_id.strip():
                validation_result["errors"].append(f"{field_name}[{i}] cannot be empty")
                analysis["invalid_entities"].append(f"Index {i}: empty string")
                continue
            
            if '.' not in entity_id:
                validation_result["errors"].append(f"{field_name}[{i}] must be in format 'domain.entity': {entity_id}")
                analysis["invalid_entities"].append(f"Index {i}: invalid format")
                continue
            
            domain, entity = entity_id.split('.', 1)
            if not domain or not entity:
                validation_result["errors"].append(f"{field_name}[{i}] has empty domain or entity part: {entity_id}")
                analysis["invalid_entities"].append(f"Index {i}: empty parts")
                continue
            
            analysis["valid_entities"].append(entity_id)
            analysis["domains"].add(domain)
        
        analysis["domains"] = list(analysis["domains"])
        return analysis
    
    def _analyze_schedules_field(self, schedules: Any, validation_result: dict) -> dict:
        """Analyze schedules field structure."""
        analysis = {
            "type": type(schedules).__name__,
            "modes": [],
            "total_slots": 0,
            "mode_analysis": {}
        }
        
        if not isinstance(schedules, dict):
            validation_result["errors"].append("schedules must be a dictionary")
            return analysis
        
        valid_modes = {"home", "away"}
        valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        
        for mode, mode_schedules in schedules.items():
            analysis["modes"].append(mode)
            
            if mode not in valid_modes:
                validation_result["warnings"].append(f"Unexpected schedule mode: {mode}")
            
            mode_analysis = {"days": [], "total_slots": 0, "slot_validation": []}
            
            if not isinstance(mode_schedules, dict):
                validation_result["errors"].append(f"Invalid schedules structure for mode {mode}: must be dict")
                analysis["mode_analysis"][mode] = mode_analysis
                continue
            
            for day, day_schedule in mode_schedules.items():
                mode_analysis["days"].append(day)
                
                if day.lower() not in valid_days:
                    validation_result["warnings"].append(f"Invalid day in {mode} mode: {day}")
                
                if not isinstance(day_schedule, list):
                    validation_result["errors"].append(f"Invalid day schedule structure for {mode}/{day}: must be list")
                    continue
                
                slot_count = len(day_schedule)
                mode_analysis["total_slots"] += slot_count
                analysis["total_slots"] += slot_count
                
                # Validate each slot
                for i, slot in enumerate(day_schedule):
                    slot_path = f"{mode}/{day}[{i}]"
                    
                    if not isinstance(slot, dict):
                        validation_result["errors"].append(f"Invalid slot structure in {slot_path}: must be dict")
                        mode_analysis["slot_validation"].append(f"{slot_path}: not a dict")
                        continue
                    
                    # Check required slot fields
                    required_slot_keys = ["start", "end", "target"]
                    missing_keys = []
                    for slot_key in required_slot_keys:
                        if slot_key not in slot:
                            missing_keys.append(slot_key)
                            validation_result["errors"].append(f"Missing slot key {slot_key} in {slot_path}")
                    
                    if missing_keys:
                        mode_analysis["slot_validation"].append(f"{slot_path}: missing {missing_keys}")
                    
                    # Validate target structure if present
                    if "target" in slot:
                        target = slot["target"]
                        if isinstance(target, dict):
                            if "domain" not in target:
                                validation_result["warnings"].append(f"Target in {slot_path} missing domain")
                            if "temperature" not in target:
                                validation_result["warnings"].append(f"Target in {slot_path} missing temperature")
                        elif isinstance(target, (int, float)):
                            validation_result["warnings"].append(f"Target in {slot_path} uses legacy numeric format")
                        else:
                            validation_result["errors"].append(f"Invalid target format in {slot_path}")
            
            analysis["mode_analysis"][mode] = mode_analysis
        
        return analysis
    
    def _analyze_metadata_field(self, metadata: Any, validation_result: dict) -> dict:
        """Analyze metadata field structure."""
        analysis = {
            "type": type(metadata).__name__,
            "keys": [],
            "has_migration_info": False,
            "has_timestamps": False
        }
        
        if not isinstance(metadata, dict):
            validation_result["errors"].append("metadata must be a dictionary")
            return analysis
        
        analysis["keys"] = list(metadata.keys())
        
        # Check for migration-related metadata
        migration_keys = ["migration_completed", "last_migration", "version_update"]
        for key in migration_keys:
            if key in metadata:
                analysis["has_migration_info"] = True
                break
        
        # Check for timestamp fields
        timestamp_keys = ["created", "last_modified", "created_at", "updated_at"]
        for key in timestamp_keys:
            if key in metadata:
                analysis["has_timestamps"] = True
                break
        
        return analysis
    
    def _analyze_presence_config_field(self, presence_config: Any, validation_result: dict) -> dict:
        """Analyze presence_config field structure."""
        analysis = {
            "type": type(presence_config).__name__,
            "keys": [],
            "entity_count": 0
        }
        
        if not isinstance(presence_config, dict):
            validation_result["errors"].append("presence_config must be a dictionary")
            return analysis
        
        analysis["keys"] = list(presence_config.keys())
        
        # Validate entities if present
        if "entities" in presence_config:
            entities = presence_config["entities"]
            if isinstance(entities, list):
                analysis["entity_count"] = len(entities)
            else:
                validation_result["errors"].append("presence_config.entities must be a list")
        
        # Validate rule if present
        if "rule" in presence_config:
            rule = presence_config["rule"]
            valid_rules = {"anyone_home", "everyone_home", "custom"}
            if rule not in valid_rules:
                validation_result["errors"].append(f"Invalid presence rule: {rule}")
        
        return analysis
    
    def _analyze_buffer_config_field(self, buffer_config: Any, validation_result: dict) -> dict:
        """Analyze buffer_config field structure."""
        analysis = {
            "type": type(buffer_config).__name__,
            "keys": [],
            "has_required_fields": True
        }
        
        if not isinstance(buffer_config, dict):
            validation_result["errors"].append("buffer_config must be a dictionary")
            return analysis
        
        analysis["keys"] = list(buffer_config.keys())
        
        # Check required fields
        required_fields = ["time_minutes", "value_delta", "enabled", "apply_to"]
        missing_fields = []
        
        for field in required_fields:
            if field not in buffer_config:
                missing_fields.append(field)
                validation_result["errors"].append(f"buffer_config missing required field: {field}")
        
        if missing_fields:
            analysis["has_required_fields"] = False
            analysis["missing_fields"] = missing_fields
        
        return analysis

    async def _log_migration_statistics(self, from_version: str, to_version: str, 
                                      migration_path: list[str], migrated_data: dict[str, Any]) -> None:
        """Log detailed migration statistics."""
        try:
            # Count data elements
            schedules = migrated_data.get("schedules", {})
            total_schedules = 0
            for mode_schedules in schedules.values():
                if isinstance(mode_schedules, dict):
                    for day_schedule in mode_schedules.values():
                        if isinstance(day_schedule, list):
                            total_schedules += len(day_schedule)
            
            entities_tracked = migrated_data.get("entities_tracked", [])
            
            # Log migration summary
            _LOGGER.info("Migration Statistics for entry %s:", self.entry_id)
            _LOGGER.info("  - Source version: %s", from_version)
            _LOGGER.info("  - Target version: %s", to_version)
            _LOGGER.info("  - Migration path: %s", " -> ".join([from_version] + migration_path))
            _LOGGER.info("  - Total schedule slots: %d", total_schedules)
            _LOGGER.info("  - Entities tracked: %d", len(entities_tracked))
            _LOGGER.info("  - Schedule modes: %s", list(schedules.keys()))
            
            # Log metadata if present
            metadata = migrated_data.get("metadata", {})
            if "migration_completed" in metadata:
                completion_info = metadata["migration_completed"]
                _LOGGER.info("  - Migration completed at: %s", completion_info.get("timestamp"))
            
            # Log presence and buffer config status
            if "presence_config" in migrated_data:
                _LOGGER.info("  - Presence configuration: Present")
            if "buffer_config" in migrated_data:
                _LOGGER.info("  - Buffer configuration: Present")
                
        except Exception as e:
            _LOGGER.error("Error logging migration statistics for entry %s: %s", self.entry_id, e)


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
            await async_ensure_directory(backup_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Backup all storage files
            storage_dir = Path(self.hass.config.config_dir) / ".storage"
            
            for storage_file in storage_dir.glob("roost_scheduler*"):
                if storage_file.is_file():
                    backup_name = f"final_backup_{storage_file.name}_{timestamp}.json"
                    backup_path = backup_dir / backup_name
                    
                    try:
                        # Use async file operations to copy the file
                        await async_copy_file(storage_file, backup_path)
                        
                        backup_locations.append(str(backup_path))
                        _LOGGER.info("Created final backup: %s", backup_path)
                    except Exception as file_error:
                        _LOGGER.error("Failed to backup file %s: %s", storage_file, file_error)
                        # Continue with other files even if one fails
                        continue
            
        except Exception as e:
            _LOGGER.error("Failed to create final backup: %s", e)
        
        return backup_locations
    
    async def _create_uninstall_info(self, info: dict[str, Any]) -> None:
        """Create uninstall information file."""
        try:
            info_path = Path(self.hass.config.config_dir) / "roost_scheduler_uninstall_info.json"
            
            # Use async file operations to write the uninstall info
            await async_write_json_file(info_path, info)
            
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
            if not await async_file_exists(backup_file):
                _LOGGER.error("Backup file not found: %s", backup_path)
                return False
            
            # Use async file operations to read the backup
            backup_data = await async_read_json_file(backup_file)
            
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