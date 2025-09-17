# Implementation Plan

- [x] 1. Set up project structure and core interfaces
  - Create Home Assistant custom component directory structure
  - Define core Python interfaces and data models for schedule management
  - Set up basic integration entry point with proper HA integration patterns
  - git add and git commit to allow for rollback
  - _Requirements: 4.1, 8.1_

- [x] 2. Implement data models and storage foundation
  - [x] 2.1 Create core data model classes and validation
    - Write Python dataclasses for ScheduleSlot, EntityState, BufferConfig
    - Implement JSON serialization/deserialization methods
    - Add validation methods for schedule data integrity
    - git add and git commit to allow for rollback
    - _Requirements: 5.1, 5.5_

  - [x] 2.2 Implement storage service with HA storage integration
    - Create StorageService class using Home Assistant's storage API
    - Implement load_schedules() and save_schedules() methods
    - Add error handling for corrupted or missing storage files
    - Write unit tests for storage operations
    - git add and git commit to allow for rollback
    - _Requirements: 5.1, 5.2, 5.5_

  - [x] 2.3 Add backup and export functionality
    - Implement export_backup() method to create JSON snapshots
    - Create import_backup() with validation and migration support
    - Add automatic nightly backup functionality with configurable timing
    - Write tests for backup/restore operations
    - git add and git commit to allow for rollback
    - _Requirements: 5.2, 5.3, 5.4_

- [x] 3. Implement presence management system
  - [x] 3.1 Create presence manager with entity monitoring
    - Write PresenceManager class with entity state tracking
    - Implement evaluate_presence_entities() using configured rule logic
    - Add timeout detection for stale device trackers
    - git add and git commit to allow for rollback
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 3.2 Add presence override and template support
    - Implement override boolean helper support (force_home/force_away)
    - Add custom Jinja template evaluation for advanced presence rules
    - Create mode change callback system for real-time updates
    - Write comprehensive unit tests for all presence scenarios
    - git add and git commit to allow for rollback
    - _Requirements: 3.4, 3.5_

- [x] 4. Implement intelligent buffering system
  - [x] 4.1 Create buffer manager with suppression algorithm
    - Write BufferManager class with should_suppress_change() logic
    - Implement manual change tracking with timestamps
    - Add tolerance checking for current vs target values
    - git add and git commit to allow for rollback
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 4.2 Add per-slot buffer override support
    - Implement get_buffer_config() with slot-specific overrides
    - Create buffer configuration validation and defaults
    - Add force-apply bypass mechanism
    - Write unit tests covering all buffer scenarios including edge cases
    - git add and git commit to allow for rollback
    - _Requirements: 2.4, 2.5_

- [x] 5. Implement core schedule management
  - [x] 5.1 Create schedule manager with evaluation logic
    - Write ScheduleManager class with time slot evaluation
    - Implement evaluate_current_slot() for current time and presence mode
    - Add schedule grid generation for frontend consumption
    - git add and git commit to allow for rollback
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 5.2 Add schedule application and service integration
    - Implement apply_schedule() with buffer manager integration
    - Create update_slot() for individual schedule modifications
    - Add proper error handling for unavailable entities and service failures
    - Write integration tests with mock Home Assistant services
    - git add and git commit to allow for rollback
    - _Requirements: 1.4, 1.5, 6.3, 6.4_

- [x] 6. Implement config flow and onboarding
  - [x] 6.1 Create basic config flow with entity selection
    - Write ConfigFlow class following HA patterns
    - Implement entity discovery and selection UI
    - Add validation for selected entities and their capabilities
    - git add and git commit to allow for rollback
    - _Requirements: 4.1, 4.2_

  - [x] 6.2 Add Lovelace card installation option
    - Implement dashboard and view discovery
    - Create card installation preview and confirmation
    - Add programmatic card addition using Lovelace storage API
    - Write tests for card installation process
    - git add and git commit to allow for rollback
    - _Requirements: 4.3, 4.4, 4.5_

- [x] 7. Implement Home Assistant service registration
  - [x] 7.1 Register scheduler services with HA
    - Create scheduler.apply_slot service with parameter validation
    - Implement scheduler.apply_grid_now service for immediate application
    - Add proper service documentation and examples
    - git add and git commit to allow for rollback
    - _Requirements: 6.1, 6.2_

  - [x] 7.2 Add service parameter handling and validation
    - Implement service call parameter parsing and validation
    - Add buffer override support in service calls
    - Create comprehensive error handling for invalid service parameters
    - Write integration tests for all service scenarios
    - git add and git commit to allow for rollback
    - _Requirements: 6.3, 6.4, 6.5_

- [x] 8. Create Lovelace card foundation
  - [x] 8.1 Set up card project structure and build system
    - Create JavaScript/TypeScript project structure for the card
    - Set up build system with bundling and minification
    - Implement basic card registration with Home Assistant
    - git add and git commit to allow for rollback
    - _Requirements: 7.1, 7.2_

  - [x] 8.2 Implement basic card rendering and configuration
    - Create card configuration schema and validation
    - Implement basic card rendering with entity selection
    - Add card picker integration and metadata
    - Write basic frontend tests for card loading
    - git add and git commit to allow for rollback
    - _Requirements: 7.1, 7.3_

- [x] 9. Implement grid interface and interactions
  - [x] 9.1 Create visual grid component
    - Implement time/day grid rendering with configurable resolution
    - Add visual indicators for current schedule values
    - Create responsive design for different screen sizes
    - git add and git commit to allow for rollback
    - _Requirements: 1.1, 1.2_

  - [x] 9.2 Add grid interaction functionality
    - Implement click-and-drag selection for time slots
    - Add value editing with validation and range checking
    - Create visual feedback for user interactions
    - Write frontend tests for all interaction scenarios
    - git add and git commit to allow for rollback
    - _Requirements: 1.2, 1.3, 1.4_

- [x] 10. Implement real-time synchronization
  - [x] 10.1 Add WebSocket communication for live updates
    - Implement WebSocket connection management
    - Create real-time state synchronization between card and backend
    - Add connection status indicators and error handling
    - git add and git commit to allow for rollback
    - _Requirements: 7.3, 7.4_

  - [x] 10.2 Add schedule change propagation
    - Implement immediate schedule updates from card to backend
    - Create conflict resolution for concurrent edits
    - Add optimistic UI updates with rollback on errors
    - Write integration tests for real-time synchronization
    - git add and git commit to allow for rollback
    - _Requirements: 7.3, 7.4, 7.5_

- [x] 11. Implement resolution migration and advanced features
  - [x] 11.1 Add schedule resolution migration
    - Create migration logic for changing time resolution
    - Implement preview system for resolution changes
    - Add user confirmation before applying migrations
    - git add and git commit to allow for rollback
    - _Requirements: 1.4_

  - [x] 11.2 Add advanced grid features
    - Implement copy/paste functionality for schedule slots
    - Add bulk edit operations for multiple slots
    - Create schedule templates and quick-apply options
    - Write comprehensive tests for advanced features
    - git add and git commit to allow for rollback
    - _Requirements: 1.3, 1.5_

- [-] 12. Implement HACS integration and packaging
  - [x] 12.1 Set up HACS repository structure
    - Create proper HACS manifest and repository structure
    - Add version management and release automation
    - Implement proper dependency declarations
    - git add and git commit to allow for rollback
    - _Requirements: 8.1, 8.2_

  - [-] 12.2 Add migration and upgrade handling
    - Create version migration system for breaking changes
    - Implement data preservation during updates
    - Add uninstall cleanup with data preservation options
    - Write tests for upgrade scenarios
    - git add and git commit to allow for rollback
    - _Requirements: 8.3, 8.4, 8.5_

- [ ] 13. Integration testing and final wiring
  - [ ] 13.1 Create comprehensive integration tests
    - Write end-to-end tests covering complete user workflows
    - Test presence-based mode switching with real scenarios
    - Validate buffer system behavior under various conditions
    - git add and git commit to allow for rollback
    - _Requirements: All requirements validation_

  - [ ] 13.2 Final system integration and polish
    - Integrate all components with proper error handling
    - Add comprehensive logging and debugging support
    - Create user documentation and setup guides
    - Perform final testing and bug fixes
    - git add and git commit to allow for rollback
    - _Requirements: All requirements final validation_