# Roost Scheduler

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/user/roost-scheduler)](https://github.com/user/roost-scheduler/releases)
[![GitHub](https://img.shields.io/github/license/user/roost-scheduler)](LICENSE)

A HACS-compatible Home Assistant custom integration that provides a grid-based scheduling interface with intelligent buffering and presence-aware automation for climate entities.

## Features

- **Visual Grid Interface**: Create and manage schedules using an intuitive 7-day grid with configurable time resolution (15, 30, or 60 minutes)
- **Intelligent Buffering**: Avoid conflicts with manual adjustments through smart suppression of scheduled changes
- **Presence-Aware Scheduling**: Automatic Home/Away mode switching based on presence entities
- **Real-time Synchronization**: Live updates between multiple dashboard cards
- **Data Backup & Export**: Automatic nightly backups with manual export/import capabilities
- **Service Integration**: Programmatic control through Home Assistant services
- **HACS Compatible**: Easy installation and updates through HACS

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/user/roost-scheduler` as an Integration
6. Click "Install"
7. Restart Home Assistant
8. Go to Settings > Devices & Services
9. Click "Add Integration" and search for "Roost Scheduler"

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/user/roost-scheduler/releases)
2. Extract the contents to your `custom_components/roost_scheduler/` directory
3. Copy the `www/roost-scheduler-card/` directory to your `www/` directory
4. Restart Home Assistant
5. Add the integration through the UI

## Configuration

The integration includes a guided setup process:

1. **Entity Selection**: Choose climate entities to schedule
2. **Presence Configuration**: Select device trackers or presence entities
3. **Buffer Settings**: Configure intelligent buffering parameters
4. **Card Installation**: Optionally add the Lovelace card to your dashboard

### Manual Card Installation

If you didn't install the card during setup, add it manually:

```yaml
type: custom:roost-scheduler-card
entity: climate.living_room
title: Living Room Schedule
```

## Usage

### Creating Schedules

1. Open the Roost Scheduler card on your dashboard
2. Click and drag on the grid to select time slots
3. Set target temperatures for Home and Away modes
4. Changes are automatically saved

### Presence Modes

The scheduler supports two modes:
- **Home Mode**: Active when presence entities indicate someone is home
- **Away Mode**: Active when all presence entities indicate away or are stale

### Buffer System

The intelligent buffer system prevents "tug-of-war" scenarios:
- Skips scheduled changes if current temperature is within tolerance
- Respects recent manual adjustments for a configurable time period
- Allows per-slot buffer overrides for fine-tuned control

### Services

#### `roost_scheduler.apply_slot`
Apply a specific schedule slot immediately.

```yaml
service: roost_scheduler.apply_slot
data:
  entity_id: climate.living_room
  day: monday
  time: "08:00"
  mode: home
  force: false
```

#### `roost_scheduler.apply_grid_now`
Apply the current schedule based on time and presence.

```yaml
service: roost_scheduler.apply_grid_now
data:
  entity_id: climate.living_room
  force: false
```

## Advanced Configuration

### Buffer Settings

```yaml
# Global buffer configuration
buffer:
  time_minutes: 15      # Suppress changes for 15 minutes after manual adjustment
  value_delta: 2.0      # Skip if current temp within 2°C of target
  
# Per-slot overrides
schedules:
  home:
    monday:
      - start: "06:00"
        end: "08:00"
        target:
          temperature: 20.0
        buffer_override:
          time_minutes: 10
          value_delta: 1.0
```

### Presence Rules

- `anyone_home`: Home mode when any presence entity is home
- `everyone_home`: Home mode only when all presence entities are home
- Custom Jinja templates for advanced logic

### Override Helpers

Create boolean helpers for manual presence override:
- `input_boolean.roost_force_home`
- `input_boolean.roost_force_away`

## Troubleshooting

### Common Issues

**Card not loading**
- Ensure the card files are in `www/roost-scheduler-card/`
- Clear browser cache
- Check browser console for errors

**Schedules not applying**
- Verify climate entities are available
- Check buffer settings aren't suppressing changes
- Review presence entity states

**Data loss after restart**
- Check Home Assistant logs for storage errors
- Verify `.storage/roost_scheduler` file permissions
- Restore from backup in `/config/roost_scheduler_backups/`

### Debug Logging

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.roost_scheduler: debug
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- [Issues](https://github.com/user/roost-scheduler/issues)
- [Discussions](https://github.com/user/roost-scheduler/discussions)
- [Home Assistant Community](https://community.home-assistant.io/)