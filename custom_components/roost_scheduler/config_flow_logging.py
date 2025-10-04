"""Enhanced logging system for config flow registration and troubleshooting."""
from __future__ import annotations

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class ConfigFlowLogEntry:
    """Represents a config flow log entry."""
    timestamp: str
    level: str
    operation: str
    message: str
    details: Dict[str, Any]
    error_info: Optional[Dict[str, Any]] = None


@dataclass
class DiagnosticLogData:
    """Diagnostic log data for troubleshooting."""
    session_id: str
    entries: List[ConfigFlowLogEntry]
    summary: Dict[str, Any]


class ConfigFlowLogger:
    """Enhanced logger for config flow registration and troubleshooting."""

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize the config flow logger."""
        self.hass = hass
        self.domain = domain
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_entries: List[ConfigFlowLogEntry] = []
        self._store = Store(hass, 1, f"{domain}_config_flow_logs")
        self._max_entries = 1000  # Limit log entries to prevent memory issues

    async def log_config_flow_start(self, flow_id: str, user_input: Optional[Dict[str, Any]] = None) -> None:
        """Log the start of a config flow."""
        await self._add_log_entry(
            level="INFO",
            operation="config_flow_start",
            message=f"Config flow started with ID: {flow_id}",
            details={
                "flow_id": flow_id,
                "user_input": user_input,
                "domain": self.domain
            }
        )

    async def log_config_flow_step(self, step_id: str, flow_id: str, 
                                 user_input: Optional[Dict[str, Any]] = None,
                                 errors: Optional[Dict[str, str]] = None) -> None:
        """Log a config flow step."""
        level = "ERROR" if errors else "INFO"
        message = f"Config flow step '{step_id}' executed"
        
        if errors:
            message += f" with errors: {errors}"
        
        await self._add_log_entry(
            level=level,
            operation="config_flow_step",
            message=message,
            details={
                "step_id": step_id,
                "flow_id": flow_id,
                "user_input": user_input,
                "errors": errors,
                "domain": self.domain
            }
        )

    async def log_config_flow_error(self, error: Exception, context: str,
                                  flow_id: Optional[str] = None,
                                  additional_info: Optional[Dict[str, Any]] = None) -> None:
        """Log a config flow error with detailed information."""
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context
        }
        
        if additional_info:
            error_info.update(additional_info)
        
        await self._add_log_entry(
            level="ERROR",
            operation="config_flow_error",
            message=f"Config flow error in {context}: {str(error)}",
            details={
                "flow_id": flow_id,
                "context": context,
                "domain": self.domain
            },
            error_info=error_info
        )
        
        # Also log to standard logger for immediate visibility
        _LOGGER.error("Config flow error in %s: %s", context, str(error), exc_info=True)

    async def log_registration_attempt(self, success: bool, details: Dict[str, Any]) -> None:
        """Log a config flow registration attempt."""
        level = "INFO" if success else "ERROR"
        message = f"Config flow registration {'succeeded' if success else 'failed'}"
        
        await self._add_log_entry(
            level=level,
            operation="registration_attempt",
            message=message,
            details={
                "success": success,
                "domain": self.domain,
                **details
            }
        )

    async def log_validation_result(self, validation_type: str, success: bool,
                                  issues: List[str], details: Dict[str, Any]) -> None:
        """Log validation results."""
        level = "INFO" if success else "WARNING"
        message = f"Validation '{validation_type}' {'passed' if success else 'failed'}"
        
        if issues:
            message += f" with {len(issues)} issues"
        
        await self._add_log_entry(
            level=level,
            operation="validation_result",
            message=message,
            details={
                "validation_type": validation_type,
                "success": success,
                "issues": issues,
                "domain": self.domain,
                **details
            }
        )

    async def log_diagnostic_collection(self, diagnostic_type: str, 
                                      data: Dict[str, Any],
                                      success: bool = True) -> None:
        """Log diagnostic data collection."""
        level = "INFO" if success else "WARNING"
        message = f"Diagnostic collection '{diagnostic_type}' {'completed' if success else 'failed'}"
        
        await self._add_log_entry(
            level=level,
            operation="diagnostic_collection",
            message=message,
            details={
                "diagnostic_type": diagnostic_type,
                "success": success,
                "data_keys": list(data.keys()) if isinstance(data, dict) else [],
                "domain": self.domain
            }
        )

    async def log_fix_attempt(self, fix_type: str, success: bool,
                            before_state: Dict[str, Any],
                            after_state: Dict[str, Any],
                            error: Optional[str] = None) -> None:
        """Log automatic fix attempts."""
        level = "INFO" if success else "ERROR"
        message = f"Fix attempt '{fix_type}' {'succeeded' if success else 'failed'}"
        
        details = {
            "fix_type": fix_type,
            "success": success,
            "before_state": before_state,
            "after_state": after_state,
            "domain": self.domain
        }
        
        error_info = None
        if error:
            error_info = {"fix_error": error}
            message += f": {error}"
        
        await self._add_log_entry(
            level=level,
            operation="fix_attempt",
            message=message,
            details=details,
            error_info=error_info
        )

    async def log_integration_setup(self, phase: str, success: bool,
                                  details: Dict[str, Any],
                                  duration_ms: Optional[float] = None) -> None:
        """Log integration setup phases."""
        level = "INFO" if success else "ERROR"
        message = f"Integration setup phase '{phase}' {'completed' if success else 'failed'}"
        
        if duration_ms is not None:
            message += f" in {duration_ms:.1f}ms"
        
        await self._add_log_entry(
            level=level,
            operation="integration_setup",
            message=message,
            details={
                "phase": phase,
                "success": success,
                "duration_ms": duration_ms,
                "domain": self.domain,
                **details
            }
        )

    async def log_troubleshooting_info(self, info_type: str, data: Dict[str, Any]) -> None:
        """Log troubleshooting information."""
        await self._add_log_entry(
            level="INFO",
            operation="troubleshooting_info",
            message=f"Troubleshooting info collected: {info_type}",
            details={
                "info_type": info_type,
                "domain": self.domain,
                **data
            }
        )

    async def get_diagnostic_logs(self, limit: Optional[int] = None) -> DiagnosticLogData:
        """Get diagnostic logs for troubleshooting."""
        entries = self._log_entries
        if limit:
            entries = entries[-limit:]
        
        # Generate summary
        summary = self._generate_log_summary(entries)
        
        return DiagnosticLogData(
            session_id=self._session_id,
            entries=entries,
            summary=summary
        )

    async def export_logs_to_file(self, file_path: str) -> bool:
        """Export logs to a file for analysis."""
        try:
            diagnostic_data = await self.get_diagnostic_logs()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Config Flow Diagnostic Logs - Session: {diagnostic_data.session_id}\n")
                f.write("=" * 80 + "\n\n")
                
                # Write summary
                f.write("SUMMARY:\n")
                f.write("-" * 20 + "\n")
                for key, value in diagnostic_data.summary.items():
                    f.write(f"{key}: {value}\n")
                f.write("\n")
                
                # Write detailed logs
                f.write("DETAILED LOGS:\n")
                f.write("-" * 20 + "\n")
                for entry in diagnostic_data.entries:
                    f.write(f"[{entry.timestamp}] {entry.level} - {entry.operation}\n")
                    f.write(f"Message: {entry.message}\n")
                    f.write(f"Details: {entry.details}\n")
                    if entry.error_info:
                        f.write(f"Error Info: {entry.error_info}\n")
                    f.write("-" * 40 + "\n")
            
            _LOGGER.info("Config flow logs exported to: %s", file_path)
            return True
            
        except Exception as e:
            _LOGGER.error("Failed to export logs to file: %s", e)
            return False

    async def clear_logs(self) -> None:
        """Clear all log entries."""
        self._log_entries.clear()
        await self._store.async_save([])
        _LOGGER.info("Config flow logs cleared")

    async def save_logs(self) -> None:
        """Save logs to persistent storage."""
        try:
            # Convert log entries to serializable format
            serializable_entries = []
            for entry in self._log_entries:
                serializable_entries.append(asdict(entry))
            
            await self._store.async_save({
                "session_id": self._session_id,
                "entries": serializable_entries
            })
            
        except Exception as e:
            _LOGGER.error("Failed to save config flow logs: %s", e)

    async def load_logs(self) -> None:
        """Load logs from persistent storage."""
        try:
            data = await self._store.async_load()
            if data and "entries" in data:
                self._log_entries = []
                for entry_data in data["entries"]:
                    entry = ConfigFlowLogEntry(**entry_data)
                    self._log_entries.append(entry)
                
                if "session_id" in data:
                    self._session_id = data["session_id"]
                
                _LOGGER.debug("Loaded %d config flow log entries", len(self._log_entries))
            
        except Exception as e:
            _LOGGER.error("Failed to load config flow logs: %s", e)

    async def _add_log_entry(self, level: str, operation: str, message: str,
                           details: Dict[str, Any],
                           error_info: Optional[Dict[str, Any]] = None) -> None:
        """Add a log entry."""
        entry = ConfigFlowLogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            operation=operation,
            message=message,
            details=details,
            error_info=error_info
        )
        
        self._log_entries.append(entry)
        
        # Limit entries to prevent memory issues
        if len(self._log_entries) > self._max_entries:
            self._log_entries = self._log_entries[-self._max_entries:]
        
        # Log to standard logger as well
        log_level = getattr(logging, level, logging.INFO)
        _LOGGER.log(log_level, "[%s] %s", operation, message)

    def _generate_log_summary(self, entries: List[ConfigFlowLogEntry]) -> Dict[str, Any]:
        """Generate a summary of log entries."""
        if not entries:
            return {"total_entries": 0}
        
        summary = {
            "total_entries": len(entries),
            "session_id": self._session_id,
            "first_entry": entries[0].timestamp if entries else None,
            "last_entry": entries[-1].timestamp if entries else None,
            "levels": {},
            "operations": {},
            "errors": [],
            "domain": self.domain
        }
        
        # Count by level and operation
        for entry in entries:
            # Count levels
            summary["levels"][entry.level] = summary["levels"].get(entry.level, 0) + 1
            
            # Count operations
            summary["operations"][entry.operation] = summary["operations"].get(entry.operation, 0) + 1
            
            # Collect errors
            if entry.level == "ERROR":
                error_summary = {
                    "timestamp": entry.timestamp,
                    "operation": entry.operation,
                    "message": entry.message
                }
                if entry.error_info:
                    error_summary["error_type"] = entry.error_info.get("error_type")
                summary["errors"].append(error_summary)
        
        return summary


class ConfigFlowDiagnosticReporter:
    """Generates comprehensive diagnostic reports for config flow issues."""

    def __init__(self, logger: ConfigFlowLogger) -> None:
        """Initialize the diagnostic reporter."""
        self.logger = logger

    async def generate_comprehensive_report(self) -> str:
        """Generate a comprehensive diagnostic report."""
        diagnostic_data = await self.logger.get_diagnostic_logs()
        
        report_lines = [
            "=" * 80,
            "CONFIG FLOW DIAGNOSTIC REPORT",
            "=" * 80,
            f"Session ID: {diagnostic_data.session_id}",
            f"Domain: {self.logger.domain}",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "SUMMARY:",
            "-" * 20
        ]
        
        # Add summary information
        for key, value in diagnostic_data.summary.items():
            if isinstance(value, dict):
                report_lines.append(f"{key}:")
                for sub_key, sub_value in value.items():
                    report_lines.append(f"  {sub_key}: {sub_value}")
            elif isinstance(value, list):
                report_lines.append(f"{key}: {len(value)} items")
                for item in value[:5]:  # Show first 5 items
                    report_lines.append(f"  - {item}")
                if len(value) > 5:
                    report_lines.append(f"  ... and {len(value) - 5} more")
            else:
                report_lines.append(f"{key}: {value}")
        
        # Add error analysis
        if diagnostic_data.summary.get("errors"):
            report_lines.extend([
                "",
                "ERROR ANALYSIS:",
                "-" * 15
            ])
            
            for error in diagnostic_data.summary["errors"]:
                report_lines.append(f"• {error['timestamp']} - {error['operation']}")
                report_lines.append(f"  Message: {error['message']}")
                if error.get("error_type"):
                    report_lines.append(f"  Type: {error['error_type']}")
        
        # Add recent entries
        recent_entries = diagnostic_data.entries[-10:] if len(diagnostic_data.entries) > 10 else diagnostic_data.entries
        if recent_entries:
            report_lines.extend([
                "",
                "RECENT LOG ENTRIES:",
                "-" * 19
            ])
            
            for entry in recent_entries:
                report_lines.append(f"[{entry.timestamp}] {entry.level} - {entry.operation}")
                report_lines.append(f"  {entry.message}")
                if entry.error_info:
                    report_lines.append(f"  Error: {entry.error_info.get('error_message', 'Unknown error')}")
        
        report_lines.extend([
            "",
            "=" * 80,
            "END OF DIAGNOSTIC REPORT",
            "=" * 80
        ])
        
        return "\n".join(report_lines)

    async def generate_troubleshooting_guide(self) -> str:
        """Generate a troubleshooting guide based on logged issues."""
        diagnostic_data = await self.logger.get_diagnostic_logs()
        
        guide_lines = [
            "=" * 60,
            "CONFIG FLOW TROUBLESHOOTING GUIDE",
            "=" * 60,
            "",
            "Based on the diagnostic logs, here are recommended troubleshooting steps:",
            ""
        ]
        
        # Analyze errors and provide specific guidance
        errors = diagnostic_data.summary.get("errors", [])
        if not errors:
            guide_lines.extend([
                "✓ No errors detected in config flow logs.",
                "  The integration appears to be functioning correctly.",
                ""
            ])
        else:
            guide_lines.extend([
                f"⚠ {len(errors)} error(s) detected. Recommended actions:",
                ""
            ])
            
            # Provide specific guidance based on error types
            error_types = set()
            for error in errors:
                if error.get("error_type"):
                    error_types.add(error["error_type"])
            
            for error_type in error_types:
                guidance = self._get_error_guidance(error_type)
                if guidance:
                    guide_lines.extend([
                        f"For {error_type} errors:",
                        f"  {guidance}",
                        ""
                    ])
        
        # Add general troubleshooting steps
        guide_lines.extend([
            "GENERAL TROUBLESHOOTING STEPS:",
            "-" * 32,
            "1. Check Home Assistant logs for additional error details",
            "2. Verify integration files are present and readable",
            "3. Ensure manifest.json has config_flow: true",
            "4. Confirm domain consistency across all files",
            "5. Restart Home Assistant if configuration changes were made",
            "6. Check for conflicting integrations with the same domain",
            "",
            "For additional help, provide this diagnostic report when seeking support.",
            "",
            "=" * 60
        ])
        
        return "\n".join(guide_lines)

    def _get_error_guidance(self, error_type: str) -> str:
        """Get specific guidance for error types."""
        guidance_map = {
            "ImportError": "Check that all required dependencies are installed and importable",
            "AttributeError": "Verify that all required methods and attributes are properly defined",
            "KeyError": "Check configuration keys and ensure all required fields are present",
            "ValueError": "Validate input values and configuration parameters",
            "FileNotFoundError": "Ensure all required integration files exist",
            "PermissionError": "Check file permissions and Home Assistant access rights",
            "JSONDecodeError": "Validate JSON syntax in manifest.json and other config files",
            "ModuleNotFoundError": "Install missing Python modules or check import paths"
        }
        
        return guidance_map.get(error_type, "Review error details and check integration configuration")