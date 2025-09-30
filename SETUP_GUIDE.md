# Roost Scheduler Setup Guide

This guide will walk you through setting up the Roost Scheduler integration in Home Assistant.

## Prerequisites

- Home Assistant 2023.1.0 or later (recommended: 2024.1.0+)
- HACS (Home Assistant Community Store) installed
- At least one climate entity (thermostat) in your Home Assistant setup
- Optional: Device tracker or person entities for presence detection

## Installation

### Method 1: HACS Installation (Recommended)

1. **Add Custom Repository**
   - Open HACS in Home Assistant
   - Go to "Integrations"
   - Click the three dots menu → "Custom repositories"
   - Add repository URL: `https://github.com/user/roost-scheduler`
   - Category: "Integration"
   - Click "Add"

2. **Install Integration**
   - Search for "Roost Scheduler" in HACS
   - Click "Download"
   - Restart Home Assistant

3. **Install Frontend Card**
   - The Lovelace card will be automatically available after installation
   - No additional steps needed for the card

### Method 2: Manual Installation

1. **Download Files**
   - Download the latest release from GitHub
   - Extract the `custom_components/roost_scheduler` folder
   - Copy to your Home Assistant `custom_components` directory

2. **Install Frontend Card**
   - Copy the `www/roost-scheduler-card` folder to your `www` directory
   - Add the card resource in Lovelace resources

3. **Restart Home Assistant**

## Initial Setup

### 1. Add Integration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"Roost Scheduler"**
4. Click to add the integration

### 2. Configuration Wizard

The setup wizard will guide you through:

1. **Entity Selection**
   - Select climate entities to schedule
   - Choose supported entities (climate, input_number, number domains)

2. **Presence Configuration**
   - Select presence entities (device_tracker, person)
   - Choose presence rule:
     - `anyone_home`: Home when any selected entity is home
     - `everyone_home`: Home only when all selected entities are home
   - Set presence timeout (default: 10 minutes)
   - **Note**: Presence configuration is automatically saved to persistent storage and will be preserved across Home Assistant restarts

3. **Buffer Settings**
   - Configure global buffer time (default: 15 minutes)
   - Set temperature tolerance (default: 2.0°C)
   - These prevent conflicts with manual adjustments
   - **Note**: Buffer configuration is automatically saved to persistent storage and will be preserved across Home Assistant restarts

4. **Dashboard Integration**
   - The integration automatically registers the Roost Scheduler card with Home Assistant's frontend
   - After successful setup, a Roost Scheduler card is automatically added to your default dashboard
   - The card will also be available in the dashboard card picker for manual addition to other dashboards
   - If automatic card installation fails, you'll receive instructions for manual installation

### 3. Verify Installation

After setup, you should see:
- New services under **Developer Tools** → **Services**:
  - `roost_scheduler.apply_slot`
  - `roost_scheduler.apply_grid_now`
  - `roost_scheduler.migrate_resolution`
- Storage files created in `.storage/roost_scheduler`
- Roost Scheduler card automatically added to your default dashboard
- Card available in Lovelace card picker for adding to additional dashboards
- Success message with link to view your new dashboard card

**Configuration Persistence**: All manager configurations (presence settings, buffer settings) are automatically saved to Home Assistant's storage system and will persist across restarts. If you're upgrading from an older version, your existing configuration will be automatically migrated to the new storage format.

## Basic Configuration

### Climate Entity Requirements

Supported climate entity features:
- **Required**: `temperature` attribute or `set_temperature` service
- **Optional**: `target_temp_high`/`target_temp_low` for dual setpoint systems
- **Attributes**: `min_temp`, `max_temp` for validation

### Presence Entity Setup

For optimal presence detection:

1. **Device Trackers**
   - Ensure device trackers are reliable and update frequently
   - Consider using multiple trackers per person for redundancy

2. **Person Entities**
   - Configure person entities with multiple device trackers
   - Person entities provide better presence logic than individual trackers

3. **Override Entities** (Optional)
   - Create `input_boolean.roost_force_home` for manual home override
   - Create `input_boolean.roost_force_away` for manual away override

### Buffer Configuration

The buffer system prevents "tug-of-war" between manual and scheduled changes:

- **Time Buffer**: Prevents schedule changes for X minutes after manual adjustment
- **Value Tolerance**: Skips schedule application if current value is close enough
- **Per-Slot Overrides**: Individual slots can have custom buffer settings

## Creating Your First Schedule

### Using the Lovelace Card

1. **Access Your Card**
   - After setup, the Roost Scheduler card is automatically added to your default dashboard
   - Navigate to your dashboard to find the new card
   - If you need to add the card to other dashboards:
     - Edit dashboard
     - Add card → Search "Roost Scheduler"
     - Configure entity and display options

2. **Manual Card Installation (Fallback)**
   - If automatic installation fails, you can manually add the card:
     - Go to **Settings** → **Dashboards** → **Resources**
     - Add resource: `/roost-scheduler-card/roost-scheduler-card.js` (type: JavaScript Module)
     - Edit your dashboard and add the custom card

2. **Create Schedule Slots**
   - Click and drag on the grid to select time periods
   - Set target temperature for selected slots
   - Different schedules for Home and Away modes

3. **Advanced Features**
   - Copy/paste schedule slots
   - Bulk edit multiple slots
   - Change time resolution (15, 30, or 60 minutes)

### Using Services

You can also control schedules via services:

```yaml
# Apply specific schedule slot
service: roost_scheduler.apply_slot
data:
  entity_id: climate.living_room
  day: monday
  time: "08:00-09:30"
  force: false

# Apply current schedule immediately
service: roost_scheduler.apply_grid_now
data:
  entity_id: climate.living_room
  force: true
```

## Advanced Configuration

### Custom Presence Rules

For complex presence logic, you can use Jinja templates:

```yaml
# In configuration.yaml or via UI
presence_template: >
  {{ is_state('person.user1', 'home') or 
     is_state('person.user2', 'home') or
     is_state('input_boolean.vacation_mode', 'off') }}
```

### Buffer Overrides

Configure per-slot buffer settings for fine control:

```yaml
# Example slot with custom buffer
buffer_override:
  time_minutes: 5      # Shorter buffer time
  value_delta: 0.5     # Tighter tolerance
  enabled: true
```

### Automation Integration

Integrate with Home Assistant automations:

```yaml
# Automation to apply schedules on presence change
automation:
  - alias: "Apply Schedule on Arrival"
    trigger:
      - platform: state
        entity_id: person.user
        to: "home"
    action:
      - service: roost_scheduler.apply_grid_now
        data:
          entity_id: climate.living_room
          force: false
```

## Troubleshooting

### Common Issues

1. **Schedules Not Applying**
   - Check entity availability in Developer Tools → States
   - Verify presence detection is working correctly
   - Check buffer settings aren't too restrictive
   - Enable debug logging for detailed information

2. **Presence Detection Issues**
   - Verify presence entities are updating
   - Check presence timeout settings
   - Test with override entities
   - Review presence rule configuration

3. **Card Not Loading**
   - Verify HACS installation completed successfully
   - Check browser console for JavaScript errors
   - Clear browser cache and refresh
   - Ensure card resource is properly loaded
   - If automatic card installation failed, try manual installation (see Manual Card Installation section)

### Debug Logging

Enable debug logging for troubleshooting:

```yaml
# In configuration.yaml
logger:
  default: info
  logs:
    custom_components.roost_scheduler: debug
```

Or use the built-in debug service:

```yaml
service: roost_scheduler.enable_debug_mode
data:
  duration_minutes: 30
```

### Performance Monitoring

Monitor integration performance:

```yaml
# Enable performance logging
service: roost_scheduler.update_logging_config
data:
  performance_monitoring: true
  log_to_file: true
```

## Data Management

### Backup and Export

The integration automatically creates nightly backups in `/config/roost_scheduler_backups/`.

Manual backup:
```yaml
service: roost_scheduler.export_backup
data:
  filename: "my_schedules_backup.json"
```

### Import and Migration

Import schedules from backup:
```yaml
service: roost_scheduler.import_backup
data:
  file_path: "/config/roost_scheduler_backups/backup_20250917.json"
```

### Resolution Migration

Change schedule time resolution:
```yaml
service: roost_scheduler.migrate_resolution
data:
  resolution_minutes: 15  # Change from 30 to 15 minutes
  preview: true          # Preview changes first
```

## Best Practices

### Schedule Design

1. **Start Simple**: Begin with basic home/away schedules
2. **Use Reasonable Buffers**: 15-minute buffer works well for most use cases
3. **Test Presence Logic**: Verify presence detection before relying on it
4. **Plan for Exceptions**: Use override entities for special situations

### Performance Optimization

1. **Limit Tracked Entities**: Only track entities you actively schedule
2. **Reasonable Resolution**: 30-minute resolution is sufficient for most homes
3. **Monitor Logs**: Watch for performance warnings in logs
4. **Regular Maintenance**: Review and clean up unused schedules

### Security Considerations

1. **Access Control**: Limit dashboard access to trusted users
2. **Service Permissions**: Be cautious with automation service calls
3. **Data Privacy**: Schedule data is stored locally in Home Assistant

## Support and Community

- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Join community discussions
- **Documentation**: Check GitHub wiki for additional guides
- **Updates**: Follow releases for new features and fixes

## Configuration Migration for Existing Users

### Upgrading from Previous Versions

If you're upgrading from a version prior to 0.3.0, your configuration will be automatically migrated:

1. **Automatic Migration**: The integration will detect your existing configuration and migrate it to the new storage format
2. **Backup Creation**: A backup of your original configuration is created before migration
3. **Validation**: The migration process validates all settings and fixes any inconsistencies
4. **Fallback**: If migration fails, the system falls back to default settings and logs the issue

**What Gets Migrated:**
- Presence entity configurations
- Presence detection rules and timeouts
- Buffer settings (global and entity-specific)
- Schedule data and entity tracking

**Migration Process:**
```yaml
# The migration happens automatically during startup
# You can monitor the process in the logs:
# "Migration completed from version X.X.X to Y.Y.Y"
# "Presence configuration migrated successfully"
# "Buffer configuration migrated successfully"
```

**Troubleshooting Migration Issues:**
If migration fails, check the logs for specific error messages and use the diagnostic service:

```yaml
service: roost_scheduler.run_diagnostics
data:
  include_migration_status: true
```

### Migration from Other Schedulers

If migrating from other scheduling solutions:

1. **Export Existing Schedules**: Use your current scheduler's export feature
2. **Plan Migration**: Map existing schedules to Roost Scheduler format
3. **Test in Parallel**: Run both systems briefly to verify behavior
4. **Gradual Transition**: Migrate one entity at a time
5. **Backup Everything**: Keep backups of both old and new configurations

## Next Steps

After basic setup:

1. **Explore Advanced Features**: Try copy/paste, bulk edit, templates
2. **Integrate with Automations**: Connect schedules to other HA automations
3. **Monitor Performance**: Use built-in monitoring tools
4. **Customize Interface**: Adjust card settings for your preferences
5. **Share Feedback**: Help improve the integration with feedback and suggestions