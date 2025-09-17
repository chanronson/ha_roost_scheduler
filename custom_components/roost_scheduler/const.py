"""Constants for the Roost Scheduler integration."""

DOMAIN = "roost_scheduler"
NAME = "Roost Scheduler"
VERSION = "0.3.0"

# Default configuration values
DEFAULT_RESOLUTION_MINUTES = 30
DEFAULT_BUFFER_TIME_MINUTES = 15
DEFAULT_BUFFER_VALUE_DELTA = 2.0
DEFAULT_PRESENCE_TIMEOUT_SECONDS = 600
DEFAULT_PRESENCE_RULE = "anyone_home"

# Storage keys
STORAGE_KEY = "roost_scheduler"
STORAGE_VERSION = 1

# Service names
SERVICE_APPLY_SLOT = "apply_slot"
SERVICE_APPLY_GRID_NOW = "apply_grid_now"
SERVICE_MIGRATE_RESOLUTION = "migrate_resolution"

# Presence modes
MODE_HOME = "home"
MODE_AWAY = "away"

# Time constants
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7

# Days of week
WEEKDAYS = [
    "monday",
    "tuesday", 
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday"
]