# Requirements Document

## Introduction

The Roost Scheduler is a HACS-compatible Home Assistant custom integration that provides a grid-based scheduling interface with intelligent buffering and presence-aware automation. The system includes both a backend custom component and a frontend Lovelace card, offering users a visual way to create and manage schedules for climate entities with Home/Away modes while avoiding conflicts with manual adjustments.

## Requirements

### Requirement 1: Grid-Based Schedule Management

**User Story:** As a Home Assistant user, I want to create and manage schedules using a visual grid interface, so that I can easily set different temperature targets for different times and days of the week.

#### Acceptance Criteria

1. WHEN the user opens the Lovelace card THEN the system SHALL display a 7-day grid with configurable time resolution (15, 30, or 60 minutes)
2. WHEN the user clicks and drags on the grid THEN the system SHALL allow setting temperature targets for selected time slots
3. WHEN the user selects a time slot THEN the system SHALL display current target value and allow modification
4. WHEN the user changes the grid resolution THEN the system SHALL migrate existing schedules with preview before applying changes
5. IF schedules exist for the selected entity THEN the system SHALL display them visually on the grid with appropriate color coding

### Requirement 2: Intelligent Buffering System

**User Story:** As a user who manually adjusts thermostats, I want the scheduler to avoid overriding my recent manual changes, so that I don't experience a "tug-of-war" between the schedule and my immediate needs.

#### Acceptance Criteria

1. WHEN a scheduled transition is due THEN the system SHALL check if current value is within tolerance (default 2.0°C) and skip if already satisfied
2. WHEN a manual change occurred within buffer time (default 15 minutes) AND current value is within tolerance of manual value THEN the system SHALL suppress the scheduled change
3. WHEN buffer conditions are not met THEN the system SHALL apply the scheduled target value
4. IF the user configures per-slot buffer overrides THEN the system SHALL use slot-specific buffer settings instead of global defaults
5. WHEN the user triggers "Force apply now" THEN the system SHALL bypass all buffer logic and immediately apply the schedule

### Requirement 3: Presence-Aware Scheduling

**User Story:** As a homeowner, I want different schedules for when I'm home versus away, so that I can save energy when nobody is present while maintaining comfort when occupied.

#### Acceptance Criteria

1. WHEN the system evaluates presence THEN it SHALL use the configured rule (default: anyone_home) to determine Home/Away mode
2. WHEN any configured presence entity indicates 'home' AND rule is "anyone_home" THEN the system SHALL activate Home mode schedules
3. WHEN all configured presence entities indicate 'away' OR are stale beyond timeout (default 10 minutes) THEN the system SHALL activate Away mode schedules
4. IF override boolean helpers are set (roost_force_home/roost_force_away) THEN the system SHALL use override state regardless of presence entities
5. WHEN presence mode changes THEN the system SHALL immediately evaluate and apply appropriate schedule for current time slot

### Requirement 4: Configuration and Onboarding

**User Story:** As a new user, I want a guided setup process that helps me configure entities and optionally adds the scheduler card to my dashboard, so that I can start using the scheduler without complex manual configuration.

#### Acceptance Criteria

1. WHEN the integration is first installed THEN the system SHALL present a config flow for initial setup
2. WHEN the user completes entity selection THEN the system SHALL offer to add the Lovelace card to a selected dashboard view
3. IF the user chooses to add the card THEN the system SHALL present available dashboards and views for selection
4. WHEN the user confirms card placement THEN the system SHALL programmatically add the card with preview and confirmation
5. WHEN setup is complete THEN the system SHALL create default storage structure with user's selected configuration

### Requirement 5: Data Persistence and Backup

**User Story:** As a user with complex schedules, I want my schedule data to be safely stored and backed up, so that I don't lose my configuration if something goes wrong.

#### Acceptance Criteria

1. WHEN schedules are created or modified THEN the system SHALL persist data to Home Assistant storage at `.storage/roost_scheduler`
2. WHEN export is requested THEN the system SHALL create a JSON backup file in `/config/roost_scheduler_backups/` with timestamp
3. WHEN import is requested THEN the system SHALL validate JSON format and migrate data with version compatibility checks
4. IF automatic nightly backup is enabled THEN the system SHALL create backup files at configured time
5. WHEN storage corruption is detected THEN the system SHALL attempt recovery from most recent backup and notify user

### Requirement 6: Service Integration

**User Story:** As an advanced Home Assistant user, I want to integrate the scheduler with automations and scripts, so that I can trigger schedule changes programmatically.

#### Acceptance Criteria

1. WHEN the integration loads THEN the system SHALL register `scheduler.apply_slot` service for manual slot application
2. WHEN the integration loads THEN the system SHALL register `scheduler.apply_grid_now` service for immediate full schedule application
3. WHEN `apply_slot` service is called with valid parameters THEN the system SHALL apply the specified slot configuration immediately
4. WHEN `apply_grid_now` service is called THEN the system SHALL evaluate current time and presence, then apply appropriate schedule values
5. IF service calls include buffer override parameters THEN the system SHALL use provided values instead of configured defaults

### Requirement 7: Lovelace Card Integration

**User Story:** As a Home Assistant dashboard user, I want a dedicated card that integrates seamlessly with the Lovelace UI, so that I can manage schedules directly from my dashboard.

#### Acceptance Criteria

1. WHEN the card is added to a dashboard THEN it SHALL appear in the card picker as "Roost Scheduler Card"
2. WHEN the card loads THEN it SHALL display the current schedule grid with proper entity state reflection
3. WHEN the user interacts with the card THEN changes SHALL be immediately reflected in the backend storage
4. WHEN multiple cards exist for the same entity THEN they SHALL stay synchronized with real-time updates
5. IF the card cannot connect to the backend THEN it SHALL display appropriate error messages and retry mechanisms

### Requirement 8: HACS Compatibility

**User Story:** As a Home Assistant user who uses HACS, I want the integration to be fully compatible with HACS installation and update processes, so that I can manage it like other custom integrations.

#### Acceptance Criteria

1. WHEN installed via HACS THEN the integration SHALL follow all HACS repository structure requirements
2. WHEN HACS checks for updates THEN the system SHALL provide proper version information and changelog
3. WHEN updated via HACS THEN existing configuration and schedules SHALL be preserved with automatic migration if needed
4. IF the integration includes breaking changes THEN it SHALL provide clear migration instructions in the release notes
5. WHEN uninstalled THEN the system SHALL provide option to preserve or remove schedule data