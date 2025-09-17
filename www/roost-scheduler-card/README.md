# Roost Scheduler Card

A Lovelace card for the Roost Scheduler Home Assistant integration, providing a visual grid interface for managing climate schedules with presence-aware automation.

## Development

### Prerequisites

- Node.js 18+ and npm
- Home Assistant with Roost Scheduler integration installed

### Setup

```bash
cd www/roost-scheduler-card
npm install
```

### Build

```bash
# Development build with watch
npm run dev

# Production build
npm run build
```

### Testing

```bash
# Run tests
npm test

# Run linting
npm run lint
```

### Installation

1. Build the card: `npm run build`
2. Copy `dist/roost-scheduler-card.js` to your Home Assistant `www` folder
3. Add the card resource in Home Assistant:
   - Go to Configuration → Lovelace Dashboards → Resources
   - Add `/local/roost-scheduler-card.js` as a JavaScript Module

### Usage

Add the card to your Lovelace dashboard:

```yaml
type: custom:roost-scheduler-card
entity: climate.living_room
name: Living Room Schedule
show_header: true
resolution_minutes: 30
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `entity` | string | **Required** | Climate entity to control |
| `name` | string | Entity name | Card title |
| `show_header` | boolean | `true` | Show card header |
| `resolution_minutes` | number | `30` | Time resolution (15, 30, or 60) |

## Features

- Visual grid interface for schedule management
- Home/Away mode support
- Real-time synchronization with backend
- Configurable time resolution
- Responsive design

## Development Status

This card is part of the Roost Scheduler integration development. Current implementation includes:

- ✅ Basic card structure and registration
- ✅ Configuration interface
- ✅ Home Assistant integration
- ⏳ Grid interface (next task)
- ⏳ Real-time updates (future task)