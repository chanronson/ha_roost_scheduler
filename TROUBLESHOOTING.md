# Roost Scheduler Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Roost Scheduler integration.

## Quick Diagnostics

### Health Check Service

Use the built-in diagnostics service to check system health:

```yaml
service: roost_scheduler.run_diagnostics
data:
  include_performance: true
  include_entity_states: true
```

This will generate a comprehensive report including:
- Integration status and version
- Entity compatibility and states
- Presence detection status
- Buffer system status
- Recent errors and warnings
- Performance metrics

### Debug Mode

Enable temporary debug mode for detailed logging:

```yaml
service: roost_scheduler.enable_debug_mode
data:
  duration_minutes: 30
```

This enables comprehensive logging for 30 minutes, then automatically returns to normal logging.

## Common Issues

### 1. Manager Initialization Failures

**Symptoms:**
- Integration fails to load during Home Assistant startup
- Error messages about manager initialization in logs
- Services not available or partially working
- Configuration not persisting across restarts

**Common Error Messages:**
```
TypeError: PresenceManager.__init__() takes 2 positional arguments but 3 were given
TypeError: BufferManager.__init__() takes 2 positional arguments but 3 were given
Failed to initialize PresenceManager: [error details]
Failed to initialize BufferManager: [error details]
Storage service initialization failed
Configuration migration failed
```

**Diagnosis Steps:**

1. **Check Integration Status**
   ```yaml
   # In Developer Tools → Services
   # Look for roost_scheduler services
   # If missing, integration failed to load
   ```

2. **Review Startup Logs**
   ```yaml
   # Check Home Assistant logs for:
   # - Manager initialization errors
   # - Storage service failures
   # - Configuration migration issues
   ```

3. **Run Diagnostic Service**
   ```yaml
   service: roost_scheduler.run_diagnostics
   data:
     include_manager_status: true
     include_storage_status: true
   ```

**Solutions by Error Type:**

| Error Type | Cause | Solution |
|------------|-------|----------|
| Constructor TypeError | Version mismatch or incomplete upgrade | Restart HA, check for partial installation |
| Storage initialization failed | Permissions or disk space issues | Check HA storage permissions and available space |
| Configuration migration failed | Corrupted config or version conflict | Reset configuration or restore from backup |
| Manager not found in entry data | Incomplete setup or initialization failure | Remove and re-add integration |

**Recovery Steps:**

```yaml
# 1. Quick recovery - restart Home Assistant
# This resolves most temporary initialization issues

# 2. Reset manager configuration
service: roost_scheduler.reset_manager_configuration
data:
  preserve_schedules: true
  reset_presence: false  # Keep presence settings
  reset_buffer: false    # Keep buffer settings

# 3. Force configuration migration
service: roost_scheduler.force_configuration_migration
data:
  backup_existing: true
  
# 4. Complete reset (last resort)
service: roost_scheduler.reset_configuration
data:
  preserve_schedules: true
  create_backup: true
```

### 2. Configuration Storage Issues

**Symptoms:**
- Settings don't persist after restart
- Configuration appears to reset to defaults
- Migration warnings in logs
- Storage validation errors

**Diagnosis Steps:**

1. **Check Storage Files**
   ```bash
   # Look for storage files in .storage directory
   ls -la .storage/roost_scheduler*
   
   # Check file permissions and sizes
   ```

2. **Validate Configuration**
   ```yaml
   service: roost_scheduler.validate_configuration
   data:
     repair_if_possible: true
     detailed_report: true
   ```

3. **Test Storage Operations**
   ```yaml
   service: roost_scheduler.test_storage_operations
   data:
     test_read: true
     test_write: true
     test_migration: true
   ```

**Common Storage Issues:**

| Issue | Cause | Solution |
|-------|-------|----------|
| Permission denied | HA user lacks write permissions | Fix file permissions on .storage directory |
| Disk full | Insufficient storage space | Free up disk space |
| Corrupted data | File system errors or power loss | Restore from backup or reset configuration |
| Version mismatch | Incomplete upgrade process | Force migration or clean reinstall |

### 3. Schedules Not Applying

**Symptoms:**
- Schedule shows in card but temperature doesn't change
- No service calls visible in logbook
- Entity remains at manual temperature

**Diagnosis Steps:**

1. **Check Entity State**
   ```yaml
   # In Developer Tools → States
   # Look for your climate entity
   climate.living_room:
     state: "heat"
     attributes:
       temperature: 20.0
       target_temp_high: null
       target_temp_low: null
   ```

2. **Verify Schedule Slot**
   ```yaml
   service: roost_scheduler.get_current_slot
   data:
     entity_id: climate.living_room
   ```

3. **Check Buffer Status**
   ```yaml
   service: roost_scheduler.get_buffer_status
   data:
     entity_id: climate.living_room
   ```

**Common Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Entity unavailable | Check entity in HA, restart if needed |
| Buffer suppression | Adjust buffer settings or use force apply |
| No active schedule slot | Verify schedule exists for current time/day |
| Presence mode mismatch | Check presence detection settings |
| Service call failures | Check entity supports set_temperature service |

**Buffer-Related Issues:**

```yaml
# Check if buffer is suppressing changes
# Look for these log messages:
# "Suppressing change for climate.living_room: current 20.1 within tolerance 2.0 of target 20.0"
# "Schedule application suppressed by buffer logic"

# Solutions:
# 1. Reduce buffer tolerance
service: roost_scheduler.update_buffer_config
data:
  entity_id: climate.living_room
  value_delta: 0.5  # Reduce from 2.0 to 0.5

# 2. Force apply schedule
service: roost_scheduler.apply_grid_now
data:
  entity_id: climate.living_room
  force: true

# 3. Disable buffer temporarily
service: roost_scheduler.update_buffer_config
data:
  entity_id: climate.living_room
  enabled: false
```

### 2. Presence Detection Issues

**Symptoms:**
- Wrong Home/Away mode detected
- Mode doesn't change when leaving/arriving
- Schedules apply for wrong mode

**Diagnosis Steps:**

1. **Check Presence Entities**
   ```yaml
   # Check each presence entity state
   device_tracker.phone:
     state: "home"  # Should be "home" or "not_home"
     last_updated: "2025-09-17T10:30:00"
   
   person.user:
     state: "home"
     last_updated: "2025-09-17T10:25:00"
   ```

2. **Test Presence Evaluation**
   ```yaml
   service: roost_scheduler.evaluate_presence
   data:
     debug: true
   ```

3. **Check Override Entities**
   ```yaml
   input_boolean.roost_force_home:
     state: "off"  # Should be "off" unless intentionally overriding
   
   input_boolean.roost_force_away:
     state: "off"
   ```

**Common Causes & Solutions:**

| Issue | Cause | Solution |
|-------|-------|----------|
| Stale entities | Device tracker not updating | Check device tracker integration, reduce timeout |
| Wrong rule | Presence rule doesn't match needs | Change from "anyone_home" to "everyone_home" or vice versa |
| Override stuck | Override entity left on | Turn off override entities |
| Template errors | Custom presence template has errors | Check template syntax in Developer Tools |

**Presence Configuration Examples:**

```yaml
# For single person household
presence_rule: "anyone_home"
presence_entities:
  - device_tracker.phone
  - person.user

# For multi-person household (home when anyone is home)
presence_rule: "anyone_home"
presence_entities:
  - person.user1
  - person.user2

# For multi-person household (away only when everyone is away)
presence_rule: "anyone_home"  # This is correct for this scenario
presence_entities:
  - person.user1
  - person.user2

# For strict presence (home only when everyone is home)
presence_rule: "everyone_home"
presence_entities:
  - person.user1
  - person.user2
```

### 3. Dashboard Integration Issues

**Symptoms:**
- Card not automatically added to dashboard after setup
- Card not appearing in dashboard card picker
- Frontend resource registration failures
- Setup completion shows errors about dashboard integration

**Diagnosis Steps:**

1. **Check Frontend Resource Registration**
   ```yaml
   service: roost_scheduler.run_diagnostics
   data:
     include_frontend_status: true
   ```

2. **Verify Card Resource Loading**
   - Check browser console for resource loading errors
   - Look for 404 errors for `/roost-scheduler-card/roost-scheduler-card.js`
   - Verify resource is registered in **Settings** → **Dashboards** → **Resources**

3. **Check Dashboard Integration Status**
   ```yaml
   service: roost_scheduler.get_dashboard_integration_status
   data:
     check_card_availability: true
     check_dashboard_access: true
   ```

**Common Causes & Solutions:**

| Issue | Cause | Solution |
|-------|-------|----------|
| Resource registration failed | Missing card files or permissions | Reinstall integration, check file permissions |
| Card not in picker | Frontend registration incomplete | Restart HA, manually register resource |
| Dashboard access denied | Insufficient permissions | Check user permissions for dashboard editing |
| Card installation failed | Dashboard configuration locked | Manually add card to dashboard |

**Manual Card Installation Steps:**

If automatic installation fails, follow these steps:

1. **Register Frontend Resource**
   ```yaml
   # Go to Settings → Dashboards → Resources
   # Add new resource:
   # URL: /roost-scheduler-card/roost-scheduler-card.js
   # Type: JavaScript Module
   ```

2. **Add Card to Dashboard**
   ```yaml
   # Edit your dashboard
   # Click "Add Card"
   # Search for "Roost Scheduler"
   # Configure with your climate entity
   ```

3. **Verify Card Configuration**
   ```yaml
   # Minimal working configuration:
   type: custom:roost-scheduler-card
   entity: climate.your_entity
   title: "Schedule"
   ```

**Dashboard Integration Recovery:**

```yaml
# Force frontend resource re-registration
service: roost_scheduler.register_frontend_resources
data:
  force_reload: true
  verify_installation: true

# Retry automatic card installation
service: roost_scheduler.install_dashboard_card
data:
  dashboard_id: "default"
  force_install: true

# Check integration status after recovery
service: roost_scheduler.run_diagnostics
data:
  include_dashboard_status: true
```

### 4. Lovelace Card Issues

**Symptoms:**
- Card doesn't load or shows error
- Grid doesn't display correctly
- Changes don't save
- Real-time updates not working

**Diagnosis Steps:**

1. **Check Browser Console**
   - Open Developer Tools (F12)
   - Look for JavaScript errors in Console tab
   - Check Network tab for failed requests

2. **Verify Card Installation**
   ```yaml
   # Check if card resource is loaded
   # In Lovelace → Raw Config Editor
   resources:
     - url: /roost-scheduler-card/roost-scheduler-card.js
       type: module
   ```

3. **Test WebSocket Connection**
   ```yaml
   # In browser console:
   # Check if WebSocket messages are being received
   # Look for "roost_scheduler" message types
   ```

**Common Solutions:**

| Issue | Solution |
|-------|----------|
| Card not found | Reinstall via HACS, clear browser cache |
| JavaScript errors | Update to latest version, check browser compatibility |
| WebSocket issues | Restart HA, check network connectivity |
| Grid not responsive | Check entity configuration, verify schedule data |
| Changes not saving | Check HA permissions, verify storage is writable |

**Card Configuration Troubleshooting:**

```yaml
# Minimal working card configuration
type: custom:roost-scheduler-card
entity: climate.living_room
title: "Living Room Schedule"

# Full configuration with all options
type: custom:roost-scheduler-card
entity: climate.living_room
title: "Living Room Schedule"
show_mode_selector: true
show_current_temp: true
show_target_temp: true
resolution_minutes: 30
height: 400
theme: default
```

### 5. Performance Issues

**Symptoms:**
- Slow response times
- High CPU usage
- Memory leaks
- Delayed schedule applications

**Diagnosis:**

1. **Enable Performance Monitoring**
   ```yaml
   service: roost_scheduler.update_logging_config
   data:
     performance_monitoring: true
     log_to_file: true
   ```

2. **Check System Resources**
   - Monitor HA system resources in Settings → System
   - Check for other integrations causing issues
   - Review HA logs for performance warnings

**Optimization Steps:**

```yaml
# 1. Reduce tracked entities
# Only track entities you actively schedule
entities_tracked:
  - climate.living_room  # Remove unused entities
  # - climate.bedroom    # Comment out if not used

# 2. Increase schedule resolution
# Use 30 or 60 minutes instead of 15
service: roost_scheduler.migrate_resolution
data:
  resolution_minutes: 30

# 3. Optimize buffer settings
# Reduce buffer check frequency
buffer:
  global:
    time_minutes: 30      # Increase from 15
    value_delta: 3.0      # Increase tolerance
    
# 4. Limit presence entities
# Use fewer, more reliable presence entities
presence_entities:
  - person.user          # Use person instead of multiple device trackers
  # - device_tracker.phone  # Remove redundant trackers
```

### 6. Data and Storage Issues

**Symptoms:**
- Schedules disappear after restart
- Import/export failures
- Corruption errors in logs
- Migration issues

**Diagnosis:**

1. **Check Storage Files**
   ```bash
   # Check if storage files exist and are readable
   ls -la .storage/roost_scheduler*
   
   # Check file permissions
   # Files should be readable/writable by HA user
   ```

2. **Validate Schedule Data**
   ```yaml
   service: roost_scheduler.validate_schedules
   data:
     repair_if_possible: true
   ```

**Recovery Steps:**

```yaml
# 1. Restore from automatic backup
service: roost_scheduler.import_backup
data:
  file_path: "/config/roost_scheduler_backups/backup_20250917.json"

# 2. Reset to defaults (last resort)
service: roost_scheduler.reset_configuration
data:
  preserve_schedules: true  # Keep schedules, reset other settings
  
# 3. Manual data recovery
# Check .storage/roost_scheduler for corrupted files
# Look for .backup files that might be recoverable
```

## Advanced Troubleshooting

### Configuration Validation and Repair

**Comprehensive Configuration Diagnostics:**

```yaml
# Run full configuration validation
service: roost_scheduler.validate_configuration
data:
  check_presence_config: true
  check_buffer_config: true
  check_entity_references: true
  check_storage_integrity: true
  repair_if_possible: true
  generate_report: true
```

**Configuration Repair Procedures:**

```yaml
# 1. Repair presence configuration
service: roost_scheduler.repair_presence_configuration
data:
  remove_invalid_entities: true
  reset_invalid_rules: true
  fix_timeout_values: true

# 2. Repair buffer configuration  
service: roost_scheduler.repair_buffer_configuration
data:
  reset_invalid_values: true
  remove_orphaned_overrides: true
  validate_entity_references: true

# 3. Repair storage consistency
service: roost_scheduler.repair_storage_consistency
data:
  fix_version_mismatches: true
  remove_corrupted_data: true
  rebuild_indexes: true
```

**Manager-Specific Diagnostics:**

```yaml
# Presence Manager diagnostics
service: roost_scheduler.diagnose_presence_manager
data:
  test_entity_states: true
  test_rule_evaluation: true
  test_timeout_logic: true
  test_override_entities: true

# Buffer Manager diagnostics  
service: roost_scheduler.diagnose_buffer_manager
data:
  test_buffer_logic: true
  test_entity_tracking: true
  test_configuration_persistence: true
  analyze_suppression_patterns: true

# Storage Service diagnostics
service: roost_scheduler.diagnose_storage_service
data:
  test_read_operations: true
  test_write_operations: true
  test_migration_capability: true
  check_data_integrity: true
```

**Configuration Issue Detection:**

The diagnostic system automatically detects these common configuration issues:

| Issue Type | Detection Method | Auto-Repair Available |
|------------|------------------|----------------------|
| Invalid entity references | Entity state lookup | Yes - removes invalid entities |
| Corrupted presence rules | Rule validation | Yes - resets to default |
| Buffer value out of range | Value range checking | Yes - clamps to valid range |
| Storage version mismatch | Version comparison | Yes - triggers migration |
| Missing required fields | Schema validation | Yes - adds default values |
| Circular dependencies | Dependency analysis | Yes - breaks circular refs |

### Debug Logging Analysis

**Enable Comprehensive Logging:**

```yaml
# In configuration.yaml
logger:
  default: warning
  logs:
    custom_components.roost_scheduler: debug
    custom_components.roost_scheduler.schedule_manager: debug
    custom_components.roost_scheduler.presence_manager: debug
    custom_components.roost_scheduler.buffer_manager: debug
    custom_components.roost_scheduler.storage: debug
    custom_components.roost_scheduler.config_validator: debug
```

**Key Log Messages to Look For:**

| Component | Log Pattern | Meaning |
|-----------|-------------|---------|
| Schedule Manager | `Applied schedule for climate.living_room: 20.0°C` | Successful application |
| Schedule Manager | `No active schedule slot for climate.living_room` | No schedule for current time |
| Buffer Manager | `Suppressing change for climate.living_room` | Buffer preventing change |
| Presence Manager | `Presence mode changed from away to home` | Mode change detected |
| Storage | `Migration completed from 0.2.0 to 0.3.0` | Data migration |
| **Manager Init** | `PresenceManager initialized with storage integration` | **Successful manager setup** |
| **Manager Init** | `Failed to initialize PresenceManager: TypeError` | **Constructor parameter mismatch** |
| **Manager Init** | `BufferManager configuration loaded from storage` | **Configuration persistence working** |
| **Manager Init** | `Configuration migration started for entry_id` | **Automatic migration in progress** |
| **Storage** | `Storage service initialization failed: PermissionError` | **Storage permission issues** |
| **Storage** | `Configuration validation failed: invalid presence rule` | **Configuration corruption detected** |
| **Config Validator** | `Repaired presence configuration: removed invalid entities` | **Automatic configuration repair** |
| **Config Validator** | `Buffer configuration validation passed` | **Configuration integrity confirmed** |

### Dashboard Integration Troubleshooting

**Frontend Resource Registration Issues:**

```yaml
# Check if frontend resources are properly registered
service: roost_scheduler.check_frontend_resources
data:
  verify_file_existence: true
  check_registration_status: true
  test_resource_loading: true
```

**Common Frontend Registration Errors:**

| Error Message | Cause | Solution |
|---------------|-------|----------|
| "Card file not found" | Missing JavaScript files | Reinstall integration via HACS |
| "Resource registration failed" | Frontend API unavailable | Restart Home Assistant |
| "Permission denied accessing card files" | File permission issues | Check file ownership and permissions |
| "Frontend not ready during registration" | Timing issue during startup | Enable retry logic or manual registration |

**Dashboard Card Installation Issues:**

```yaml
# Diagnose dashboard card installation problems
service: roost_scheduler.diagnose_card_installation
data:
  check_dashboard_access: true
  verify_lovelace_storage: true
  test_card_configuration: true
```

**Card Installation Recovery Procedures:**

```yaml
# 1. Reset frontend resource registration
service: roost_scheduler.reset_frontend_registration
data:
  clear_existing_registration: true
  force_re_register: true

# 2. Force dashboard card installation
service: roost_scheduler.force_card_installation
data:
  target_dashboard: "default"
  overwrite_existing: false
  use_default_config: true

# 3. Verify installation success
service: roost_scheduler.verify_dashboard_integration
data:
  check_card_in_picker: true
  check_card_on_dashboard: true
  test_card_functionality: true
```

**Manual Installation Verification:**

After manual installation, verify everything is working:

```yaml
# Test card functionality
service: roost_scheduler.test_card_functionality
data:
  entity_id: climate.your_entity
  test_schedule_display: true
  test_user_interactions: true
  test_real_time_updates: true
```

**Dashboard Integration Logs to Monitor:**

| Component | Log Message | Meaning |
|-----------|-------------|---------|
| Frontend Manager | `Frontend resources registered successfully` | Resource registration completed |
| Frontend Manager | `Card file not found: /roost-scheduler-card/roost-scheduler-card.js` | Missing card files |
| Dashboard Service | `Card added to dashboard: default` | Successful card installation |
| Dashboard Service | `Dashboard access denied for user` | Permission issues |
| Dashboard Service | `Lovelace storage not available` | Storage system issues |

### Network and WebSocket Issues

**Test WebSocket Connection:**

```javascript
// In browser console
const ws = new WebSocket('ws://your-ha-url:8123/api/websocket');
ws.onopen = () => console.log('WebSocket connected');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'roost_scheduler/schedule_updated') {
    console.log('Schedule update received:', data);
  }
};
```

**Common Network Issues:**

| Issue | Cause | Solution |
|-------|-------|----------|
| Connection timeouts | Network latency | Increase timeout settings |
| Frequent disconnections | Unstable network | Check network stability |
| CORS errors | Reverse proxy config | Update proxy configuration |
| SSL certificate issues | HTTPS setup | Verify SSL configuration |

### Integration Conflicts

**Check for Conflicting Integrations:**

```yaml
# Common conflicts:
# - Other scheduling integrations
# - Climate control automations
# - Presence detection integrations

# Disable conflicting automations temporarily
automation.climate_schedule:
  state: "off"

# Check for duplicate services
# Look for other integrations providing similar services
```

### Database and History Issues

**Check Recorder Configuration:**

```yaml
# In configuration.yaml
recorder:
  include:
    domains:
      - climate
    entities:
      - roost_scheduler.*
  exclude:
    # Exclude high-frequency debug entities if needed
    entities:
      - roost_scheduler.debug_*
```

### New Error Scenarios (Version 0.3.0+)

**Manager Integration Errors:**

These errors are specific to the enhanced manager integration with storage persistence:

```yaml
# Error: Manager constructor parameter mismatch
# Log: "TypeError: PresenceManager.__init__() takes 2 positional arguments but 3 were given"
# Cause: Incomplete upgrade or version mismatch
# Solution: Restart HA, check installation integrity

# Error: Storage service not available
# Log: "Failed to initialize managers: storage_service is None"
# Cause: Storage service initialization failed
# Solution: Check storage permissions, restart HA

# Error: Configuration migration failure
# Log: "Configuration migration failed: unable to parse existing data"
# Cause: Corrupted configuration or unsupported format
# Solution: Reset configuration or restore from backup

# Error: Manager configuration validation failure
# Log: "PresenceManager configuration validation failed: invalid entities"
# Cause: Referenced entities no longer exist
# Solution: Update configuration or use repair service
```

**Storage Integration Errors:**

```yaml
# Error: Storage persistence failure
# Log: "Failed to save presence configuration: disk full"
# Cause: Insufficient disk space
# Solution: Free up storage space

# Error: Configuration loading failure
# Log: "Failed to load buffer configuration: file corrupted"
# Cause: Storage file corruption
# Solution: Restore from backup or reset configuration

# Error: Migration version conflict
# Log: "Cannot migrate from version X.X.X: unsupported version"
# Cause: Attempting to migrate from incompatible version
# Solution: Manual configuration reset required
```

**Configuration Validation Errors:**

```yaml
# Error: Entity reference validation failure
# Log: "Configuration validation failed: entity climate.nonexistent not found"
# Cause: Configuration references deleted entities
# Solution: Remove invalid entity references

# Error: Presence rule validation failure
# Log: "Invalid presence rule 'invalid_rule': must be 'anyone_home' or 'everyone_home'"
# Cause: Configuration corruption or manual editing error
# Solution: Reset presence rule to valid value

# Error: Buffer configuration validation failure
# Log: "Buffer time_minutes value 'invalid' is not a valid number"
# Cause: Invalid configuration values
# Solution: Reset buffer configuration to defaults
```

**Recovery Procedures for New Errors:**

```yaml
# For manager initialization errors:
service: roost_scheduler.reset_manager_configuration
data:
  force_reinitialize: true
  preserve_schedules: true

# For storage integration errors:
service: roost_scheduler.repair_storage_integration
data:
  check_permissions: true
  validate_files: true
  create_missing_files: true

# For configuration validation errors:
service: roost_scheduler.validate_and_repair_configuration
data:
  auto_fix_entity_references: true
  reset_invalid_values: true
  backup_before_repair: true
```

## Getting Help

### Information to Collect

When reporting issues, include:

1. **System Information**
   - Home Assistant version
   - Roost Scheduler version
   - Installation method (HACS/manual)
   - Operating system

2. **Configuration**
   - Anonymized configuration (remove personal info)
   - Entity types and domains
   - Presence setup

3. **Logs**
   - Relevant error messages
   - Debug logs (if available)
   - Timeline of issue occurrence

4. **Reproduction Steps**
   - Exact steps to reproduce
   - Expected vs actual behavior
   - Frequency of occurrence

### Diagnostic Report Generation

```yaml
# Generate comprehensive diagnostic report
service: roost_scheduler.generate_diagnostic_report
data:
  include_logs: true
  include_config: true
  anonymize_data: true
  output_file: "/config/roost_scheduler_diagnostics.json"
```

### Community Resources

- **GitHub Issues**: Report bugs and feature requests
- **Home Assistant Community**: General discussion and help
- **Discord/Forums**: Real-time community support
- **Documentation**: Check wiki for additional guides

### Professional Support

For complex installations or custom requirements:
- Consider professional Home Assistant setup services
- Consult with home automation specialists
- Review enterprise support options if available

## Prevention and Maintenance

### Regular Maintenance Tasks

1. **Weekly**
   - Check for integration updates
   - Review error logs
   - Verify schedule accuracy

2. **Monthly**
   - Clean up old backup files
   - Review performance metrics
   - Update presence entity configurations

3. **Quarterly**
   - Full configuration backup
   - Performance optimization review
   - Security audit of access controls

### Configuration Validation and Repair Guide

**Automated Configuration Validation:**

The integration includes comprehensive configuration validation that runs automatically during startup and can be triggered manually:

```yaml
# Run comprehensive configuration validation
service: roost_scheduler.validate_configuration
data:
  check_all_components: true
  auto_repair: true
  generate_detailed_report: true
  backup_before_repair: true
```

**Manual Configuration Repair Steps:**

1. **Identify Configuration Issues:**
   ```yaml
   service: roost_scheduler.identify_configuration_issues
   data:
     check_entity_references: true
     check_value_ranges: true
     check_data_integrity: true
   ```

2. **Repair Specific Components:**
   ```yaml
   # Repair presence configuration
   service: roost_scheduler.repair_presence_configuration
   data:
     remove_invalid_entities: true
     fix_rule_conflicts: true
     update_timeout_values: true
   
   # Repair buffer configuration
   service: roost_scheduler.repair_buffer_configuration
   data:
     fix_invalid_values: true
     remove_orphaned_overrides: true
     validate_entity_mappings: true
   ```

3. **Validate Repairs:**
   ```yaml
   service: roost_scheduler.validate_repairs
   data:
     test_functionality: true
     verify_persistence: true
   ```

**Common Configuration Issues and Fixes:**

| Issue | Symptoms | Automatic Fix | Manual Fix |
|-------|----------|---------------|------------|
| Invalid entity references | Entities not found errors | Remove invalid entities | Update entity IDs |
| Corrupted presence rules | Presence detection not working | Reset to default rule | Reconfigure presence settings |
| Buffer values out of range | Buffer not working correctly | Clamp to valid range | Set appropriate values |
| Storage version mismatch | Migration errors | Trigger re-migration | Reset configuration |
| Missing configuration fields | Partial functionality | Add default values | Complete configuration |

**Configuration Backup and Restore:**

```yaml
# Create configuration backup before making changes
service: roost_scheduler.backup_configuration
data:
  include_schedules: true
  include_manager_configs: true
  backup_name: "pre_repair_backup"

# Restore from backup if repairs fail
service: roost_scheduler.restore_configuration
data:
  backup_name: "pre_repair_backup"
  validate_after_restore: true
```

### Monitoring Setup

```yaml
# Set up monitoring automation with enhanced error detection
automation:
  - alias: "Roost Scheduler Health Check"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: roost_scheduler.run_diagnostics
        data:
          notify_on_issues: true
          include_manager_status: true
          include_configuration_validation: true
          
  - alias: "Roost Scheduler Error Alert"
    trigger:
      - platform: event
        event_type: system_log_event
        event_data:
          level: ERROR
          source: custom_components.roost_scheduler
    action:
      - service: notify.admin
        data:
          message: "Roost Scheduler error: {{ trigger.event.data.message }}"
          
  - alias: "Roost Scheduler Configuration Issue Alert"
    trigger:
      - platform: event
        event_type: roost_scheduler_configuration_issue
    action:
      - service: roost_scheduler.validate_and_repair_configuration
        data:
          auto_repair: true
          notify_on_completion: true
```

This comprehensive troubleshooting guide should help users diagnose and resolve most issues they encounter with the Roost Scheduler integration.