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

### 1. Schedules Not Applying

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

### 3. Lovelace Card Issues

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

### 4. Performance Issues

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

### 5. Data and Storage Issues

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
```

**Key Log Messages to Look For:**

| Component | Log Pattern | Meaning |
|-----------|-------------|---------|
| Schedule Manager | `Applied schedule for climate.living_room: 20.0°C` | Successful application |
| Schedule Manager | `No active schedule slot for climate.living_room` | No schedule for current time |
| Buffer Manager | `Suppressing change for climate.living_room` | Buffer preventing change |
| Presence Manager | `Presence mode changed from away to home` | Mode change detected |
| Storage | `Migration completed from 0.2.0 to 0.3.0` | Data migration |

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

### Monitoring Setup

```yaml
# Set up monitoring automation
automation:
  - alias: "Roost Scheduler Health Check"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: roost_scheduler.run_diagnostics
        data:
          notify_on_issues: true
          
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
```

This comprehensive troubleshooting guide should help users diagnose and resolve most issues they encounter with the Roost Scheduler integration.