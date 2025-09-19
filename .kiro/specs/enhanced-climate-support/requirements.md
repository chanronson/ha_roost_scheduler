# Enhanced Climate Entity Support - Requirements Document

## Introduction

This specification addresses the need to support climate entities that use different attribute names for temperature reporting, specifically entities that use `current_temperature` instead of `temperature`. This is common with Zigbee2MQTT (Z2M) climate devices and other integrations that follow different naming conventions.

## Requirements

### Requirement 1: Flexible Temperature Attribute Detection

**User Story:** As a user with Zigbee2MQTT climate devices, I want the scheduler to recognize my thermostats that use `current_temperature` instead of `temperature`, so that I can schedule them alongside my other climate entities.

#### Acceptance Criteria

1. WHEN the system evaluates a climate entity THEN it SHALL check for temperature attributes in the following priority order:
   - `temperature` (current standard)
   - `current_temperature` (Z2M and other integrations)
   - `current_temp` (alternative naming)

2. WHEN a climate entity has multiple temperature attributes THEN the system SHALL use the first available attribute from the priority list

3. WHEN a climate entity has none of the recognized temperature attributes THEN the system SHALL mark it as incompatible with clear reasoning

4. WHEN the system finds a valid temperature attribute THEN it SHALL store the attribute name for consistent future access

### Requirement 2: Enhanced Entity Discovery and Validation

**User Story:** As a user setting up the integration, I want all my compatible climate entities to appear in the setup wizard regardless of their temperature attribute naming, so that I don't have to manually configure each one.

#### Acceptance Criteria

1. WHEN the config flow scans for climate entities THEN it SHALL use the flexible temperature detection logic

2. WHEN validating climate entities THEN the system SHALL accept entities with any of the supported temperature attribute names

3. WHEN an entity uses a non-standard temperature attribute THEN the system SHALL log this information for debugging purposes

4. WHEN displaying entities in the setup UI THEN the system SHALL show additional information about detected temperature attributes

### Requirement 3: Backward Compatibility

**User Story:** As an existing user with standard climate entities, I want the enhanced support to not affect my current setup, so that my existing schedules continue to work without changes.

#### Acceptance Criteria

1. WHEN the system encounters entities with the standard `temperature` attribute THEN it SHALL continue to work exactly as before

2. WHEN loading existing schedule data THEN the system SHALL maintain compatibility with previously configured entities

3. WHEN migrating to the enhanced version THEN existing entity configurations SHALL be preserved

4. WHEN both old and new attribute types are present THEN the system SHALL handle them seamlessly in the same installation

### Requirement 4: Buffer System Compatibility

**User Story:** As a user with mixed climate entity types, I want the buffer system to work correctly with all my entities regardless of their temperature attribute naming, so that manual changes are properly detected and respected.

#### Acceptance Criteria

1. WHEN the buffer system reads current values THEN it SHALL use the correct temperature attribute for each entity

2. WHEN comparing target vs current temperatures THEN the system SHALL use the entity-specific temperature attribute

3. WHEN detecting manual changes THEN the system SHALL monitor the correct temperature attribute for each entity type

4. WHEN logging buffer decisions THEN the system SHALL include information about which temperature attribute was used

### Requirement 5: Service Integration Enhancement

**User Story:** As a user controlling schedules via services, I want the apply_slot and apply_grid_now services to work with all supported climate entity types, so that I can automate my mixed thermostat setup.

#### Acceptance Criteria

1. WHEN services apply schedule values THEN they SHALL work with entities using any supported temperature attribute

2. WHEN services validate entity compatibility THEN they SHALL use the enhanced detection logic

3. WHEN services report current values THEN they SHALL use the correct temperature attribute for each entity

4. WHEN service calls fail due to attribute issues THEN they SHALL provide clear error messages indicating the problem

### Requirement 6: Frontend Card Compatibility

**User Story:** As a user viewing schedules in the Lovelace card, I want to see current temperatures correctly displayed for all my climate entities, so that I can monitor the status of my mixed thermostat setup.

#### Acceptance Criteria

1. WHEN the card displays current temperatures THEN it SHALL use the correct temperature attribute for each entity

2. WHEN the card shows temperature differences THEN it SHALL calculate them using the appropriate attribute

3. WHEN the card updates in real-time THEN it SHALL monitor the correct temperature attribute for each entity type

4. WHEN the card encounters unsupported entities THEN it SHALL display helpful error messages

### Requirement 7: Diagnostic and Troubleshooting Support

**User Story:** As a user troubleshooting climate entity issues, I want clear diagnostic information about which temperature attributes are being used, so that I can understand and resolve any problems.

#### Acceptance Criteria

1. WHEN running diagnostics THEN the system SHALL report the temperature attribute used for each entity

2. WHEN logging debug information THEN the system SHALL include temperature attribute details

3. WHEN entity validation fails THEN the system SHALL provide specific information about missing or incompatible attributes

4. WHEN the system detects attribute inconsistencies THEN it SHALL log warnings with remediation suggestions

### Requirement 8: Configuration Migration and Upgrade

**User Story:** As a user upgrading from a previous version, I want the system to automatically detect and configure the correct temperature attributes for my entities, so that I don't need to reconfigure everything manually.

#### Acceptance Criteria

1. WHEN upgrading from a previous version THEN the system SHALL re-evaluate all climate entities with the enhanced detection

2. WHEN new temperature attributes are detected THEN the system SHALL update entity configurations automatically

3. WHEN migration encounters issues THEN the system SHALL provide clear error messages and fallback options

4. WHEN migration completes THEN the system SHALL log a summary of changes made to entity configurations