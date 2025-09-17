# Roost Scheduler

## What is Roost Scheduler?

Roost Scheduler is a comprehensive Home Assistant integration that provides intelligent, presence-aware climate scheduling with a visual grid interface. It's designed to eliminate the "tug-of-war" between automated schedules and manual adjustments while providing an intuitive way to manage complex heating and cooling schedules.

## Key Features

### 🗓️ Visual Grid Scheduling
- Interactive 7-day grid interface
- Configurable time resolution (15, 30, or 60 minutes)
- Click-and-drag schedule creation
- Real-time visual feedback

### 🧠 Intelligent Buffering
- Automatic conflict resolution with manual adjustments
- Configurable tolerance and timing parameters
- Per-slot buffer overrides
- Force-apply bypass for immediate control

### 🏠 Presence-Aware Automation
- Automatic Home/Away mode switching
- Support for multiple presence entities
- Configurable presence rules and timeouts
- Manual override capabilities

### 💾 Robust Data Management
- Automatic nightly backups
- Export/import functionality
- Version migration support
- Corruption recovery

### 🔧 Service Integration
- Home Assistant service calls
- Automation and script integration
- Programmatic schedule control
- Event-driven updates

## Installation Requirements

- Home Assistant 2023.1.0 or newer
- HACS (Home Assistant Community Store)
- Climate entities to schedule

## What gets installed?

This integration installs:
1. **Custom Component**: Backend scheduling logic and Home Assistant integration
2. **Lovelace Card**: Frontend grid interface for schedule management
3. **Services**: `apply_slot` and `apply_grid_now` for automation integration
4. **Storage**: Persistent schedule data with backup capabilities

## First Steps After Installation

1. **Add Integration**: Go to Settings > Devices & Services > Add Integration
2. **Select Entities**: Choose climate entities to schedule during setup
3. **Configure Presence**: Select device trackers or presence entities
4. **Install Card**: Optionally add the Lovelace card to your dashboard
5. **Create Schedules**: Use the grid interface to set up your heating/cooling schedules

## Support and Documentation

- **Full Documentation**: Available in the repository README
- **Issue Tracking**: Report bugs and request features on GitHub
- **Community Support**: Home Assistant Community forums

This integration follows Home Assistant best practices and is actively maintained with regular updates and improvements.