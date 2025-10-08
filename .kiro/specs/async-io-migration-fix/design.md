# Design Document

## Overview

This design addresses critical stability and data integrity issues in the Roost Scheduler integration by converting blocking I/O operations to async, fixing version migration logic, and improving backup recovery mechanisms. The solution focuses on maintaining Home Assistant's async requirements while ensuring data integrity and providing robust error recovery.

## Architecture

### Core Components to Modify

1. **Migration System** (`migration.py`)
   - Convert all file operations to async using `aiofiles`
   - Fix version update logic to properly persist version changes
   - Improve migration validation to handle edge cases

2. **Storage System** (`storage.py`)
   - Fix backup import logic to handle different data types
   - Improve data validation and type checking
   - Enhance error handling for corrupted data scenarios

3. **Version Management** (`version.py`)
   - Add validation helpers for version comparison
   - Improve version persistence mechanisms

## Components and Interfaces

### Async File Operations

**Interface Changes:**
```python
# Before (blocking)
with storage_file.open() as src, backup_path.open("w") as dst:
    dst.write(src.read())

# After (async)
async with aiofiles.open(storage_file, 'r') as src, aiofiles.open(backup_path, 'w') as dst:
    content = await src.read()
    await dst.write(content)
```

**Dependencies:**
- Add `aiofiles` to requirements for async file operations
- Use Home Assistant's `hass.async_add_executor_job()` for CPU-bound operations

### Migration System Redesign

**Version Persistence Fix:**
```python
class MigrationManager:
    async def _update_version_metadata(self, target_version: str) -> bool:
        """Properly update and persist version information."""
        # Update in-memory version
        # Persist to storage with validation
        # Verify persistence was successful
```

**Migration Validation Enhancement:**
```python
async def validate_migrated_data(self, data: dict) -> bool:
    """Enhanced validation with specific error reporting."""
    # Check version field exists and matches expected
    # Validate required data structure
    # Check data types and formats
    # Return detailed validation results
```

### Backup Recovery System

**Type-Safe Data Processing:**
```python
async def _parse_backup_time(self, time_value: Any) -> tuple[int, int]:
    """Safely parse backup time handling different data types."""
    if isinstance(time_value, str):
        return map(int, time_value.split(':'))
    elif isinstance(time_value, (list, tuple)) and len(time_value) == 2:
        return int(time_value[0]), int(time_value[1])
    else:
        raise ValueError(f"Invalid time format: {time_value}")
```

**Recovery Strategy:**
1. Attempt recovery from most recent backup
2. If parsing fails, try older backups
3. If all backups fail, initialize with safe defaults
4. Log detailed error information for each attempt

## Data Models

### Enhanced Validation Models

```python
@dataclass
class BackupMetadata:
    """Metadata for backup files with validation."""
    version: str
    timestamp: datetime
    entry_id: str
    data_format: str = "json"
    
    def validate(self) -> bool:
        """Validate backup metadata."""
        return (
            self.version and 
            isinstance(self.timestamp, datetime) and
            self.entry_id
        )

@dataclass
class MigrationResult:
    """Result of migration operation with detailed status."""
    success: bool
    source_version: str
    target_version: str
    actual_version: str
    errors: list[str]
    warnings: list[str]
```

### Data Integrity Checks

```python
class DataValidator:
    """Validates schedule data integrity."""
    
    async def validate_schedule_data(self, data: dict) -> ValidationResult:
        """Comprehensive data validation."""
        # Check required fields
        # Validate data types
        # Check version compatibility
        # Verify data consistency
```

## Error Handling

### Structured Error Reporting

```python
class MigrationError(Exception):
    """Specific migration error with context."""
    def __init__(self, message: str, source_version: str, target_version: str, details: dict = None):
        super().__init__(message)
        self.source_version = source_version
        self.target_version = target_version
        self.details = details or {}

class BackupRecoveryError(Exception):
    """Backup recovery error with file context."""
    def __init__(self, message: str, file_path: str, error_type: str):
        super().__init__(message)
        self.file_path = file_path
        self.error_type = error_type
```

### Graceful Degradation Strategy

1. **Migration Failures**: Fall back to safe defaults while preserving user data
2. **Backup Failures**: Continue with empty state but log recovery attempts
3. **Validation Failures**: Use partial data where possible, warn about missing features
4. **I/O Failures**: Retry with exponential backoff, then fail gracefully

## Testing Strategy

### Unit Tests
- Test async file operations with mocked `aiofiles`
- Test version migration logic with various version combinations
- Test backup parsing with different data formats and types
- Test error handling scenarios

### Integration Tests
- Test full migration workflow from 0.3.0 to 0.4.0
- Test backup recovery with real backup files
- Test startup sequence with various data corruption scenarios
- Test Home Assistant integration without blocking warnings

### Error Scenario Tests
- Test behavior with corrupted backup files
- Test migration with missing version information
- Test recovery when all backups are invalid
- Test async operation cancellation and cleanup

## Implementation Phases

### Phase 1: Async I/O Conversion
- Convert migration.py file operations to async
- Add aiofiles dependency
- Update error handling for async operations

### Phase 2: Version Migration Fix
- Fix version persistence logic
- Improve migration validation
- Add comprehensive logging

### Phase 3: Backup Recovery Enhancement
- Fix type handling in backup parsing
- Improve recovery strategy
- Add data validation

### Phase 4: Integration and Testing
- Comprehensive testing of all components
- Performance validation
- Home Assistant compatibility verification