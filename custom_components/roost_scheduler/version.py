"""Version management for Roost Scheduler."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Current version - update this for releases
VERSION = "0.4.0"

# Minimum supported version for data migration
MIN_SUPPORTED_VERSION = "0.1.0"

# Version history for migration support
VERSION_HISTORY = [
    "0.1.0",  # Initial release
    "0.2.0",  # Added presence management
    "0.3.0",  # Added buffer system and HACS support
    "0.4.0",  # Added dashboard integration functionality
]


def get_version() -> str:
    """Get the current version."""
    return VERSION


def get_manifest_version() -> str | None:
    """Get version from manifest.json."""
    try:
        manifest_path = Path(__file__).parent / "manifest.json"
        with manifest_path.open() as f:
            manifest = json.load(f)
            return manifest.get("version")
    except Exception as e:
        _LOGGER.error("Failed to read manifest version: %s", e)
        return None


def is_version_supported(version: str) -> bool:
    """Check if a version is supported for migration."""
    if not version:
        return False
    
    try:
        # Simple version comparison - assumes semantic versioning
        current_parts = [int(x) for x in VERSION.split(".")]
        min_parts = [int(x) for x in MIN_SUPPORTED_VERSION.split(".")]
        version_parts = [int(x) for x in version.split(".")]
        
        # Check if version is >= minimum supported AND <= current version
        # Don't support future versions (downgrade prevention)
        version_too_old = False
        version_too_new = False
        
        # Check if version is too old
        for i in range(min(len(version_parts), len(min_parts))):
            if version_parts[i] < min_parts[i]:
                version_too_old = True
                break
            elif version_parts[i] > min_parts[i]:
                break
        
        # Check if version is too new (future version)
        for i in range(min(len(version_parts), len(current_parts))):
            if version_parts[i] > current_parts[i]:
                version_too_new = True
                break
            elif version_parts[i] < current_parts[i]:
                break
        
        if version_too_old:
            _LOGGER.warning("Version %s is below minimum supported version %s", version, MIN_SUPPORTED_VERSION)
            return False
        
        if version_too_new:
            _LOGGER.warning("Version %s is newer than current version %s (downgrade not supported)", version, VERSION)
            return False
        
        return True
        
    except (ValueError, IndexError):
        _LOGGER.warning("Invalid version format: %s", version)
        return False


def get_migration_path(from_version: str) -> list[str]:
    """Get the migration path from a version to current."""
    if not is_version_supported(from_version):
        return []
    
    try:
        from_index = VERSION_HISTORY.index(from_version)
        current_index = VERSION_HISTORY.index(VERSION)
        
        if from_index >= current_index:
            return []  # No migration needed
        
        return VERSION_HISTORY[from_index + 1:current_index + 1]
    except ValueError:
        _LOGGER.warning("Version not found in history: %s", from_version)
        return []


def validate_manifest_version() -> bool:
    """Validate that manifest version matches code version."""
    manifest_version = get_manifest_version()
    if manifest_version != VERSION:
        _LOGGER.error(
            "Version mismatch: code=%s, manifest=%s", 
            VERSION, 
            manifest_version
        )
        return False
    return True


class VersionInfo:
    """Version information container."""
    
    def __init__(self) -> None:
        """Initialize version info."""
        self.current = VERSION
        self.manifest = get_manifest_version()
        self.supported_min = MIN_SUPPORTED_VERSION
        self.history = VERSION_HISTORY.copy()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current": self.current,
            "manifest": self.manifest,
            "supported_min": self.supported_min,
            "history": self.history,
            "is_valid": self.manifest == self.current,
        }
    
    def __str__(self) -> str:
        """String representation."""
        return f"RoostScheduler v{self.current}"
    
    def __repr__(self) -> str:
        """Detailed representation."""
        return f"VersionInfo(current={self.current}, manifest={self.manifest})"