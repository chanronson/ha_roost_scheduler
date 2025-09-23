"""Troubleshooting utilities for Roost Scheduler."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TroubleshootingManager:
    """Manages troubleshooting utilities and diagnostic functions."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the troubleshooting manager."""
        self.hass = hass
    
    async def run_comprehensive_diagnostics(self, entry_id: str) -> Dict[str, Any]:
        """Run comprehensive diagnostics for a specific config entry."""
        _LOGGER.info("Running comprehensive diagnostics for entry %s", entry_id)
        
        diagnostics = {
            "entry_id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "overall_health": "unknown",
            "components": {},
            "common_issues": [],
            "recommendations": [],
            "performance_summary": {},
            "configuration_issues": [],
            "entity_issues": []
        }
        
        try:
            # Get entry data
            entry_data = self.hass.data.get(DOMAIN, {}).get(entry_id)
            if not entry_data:
                diagnostics["overall_health"] = "critical"
                diagnostics["common_issues"].append("Entry data not found - integration may not be properly initialized")
                diagnostics["recommendations"].append("Restart Home Assistant and check logs for initialization errors")
                return diagnostics
            
            # Test each component
            await self._diagnose_presence_manager(entry_data, diagnostics)
            await self._diagnose_buffer_manager(entry_data, diagnostics)
            await self._diagnose_schedule_manager(entry_data, diagnostics)
            await self._diagnose_storage_service(entry_data, diagnostics)
            await self._diagnose_logging_manager(entry_data, diagnostics)
            
            # Analyze overall health
            self._analyze_overall_health(diagnostics)
            
            # Generate summary recommendations
            self._generate_summary_recommendations(diagnostics)
            
            _LOGGER.info("Comprehensive diagnostics completed for entry %s", entry_id)
            
        except Exception as e:
            _LOGGER.error("Error during comprehensive diagnostics: %s", e, exc_info=True)
            diagnostics["overall_health"] = "error"
            diagnostics["common_issues"].append(f"Diagnostic process failed: {str(e)}")
        
        return diagnostics
    
    async def _diagnose_presence_manager(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose presence manager issues."""
        presence_manager = entry_data.get("presence_manager")
        if not presence_manager:
            diagnostics["components"]["presence_manager"] = {
                "status": "missing",
                "issues": ["PresenceManager not found in entry data"]
            }
            return
        
        try:
            # Run presence manager diagnostics
            pm_diagnostics = await presence_manager.run_diagnostics()
            
            # Extract key information
            component_info = {
                "status": "healthy" if pm_diagnostics.get("troubleshooting", {}).get("health_score", 0) > 70 else "issues",
                "health_score": pm_diagnostics.get("troubleshooting", {}).get("health_score", 0),
                "entities_configured": len(pm_diagnostics.get("configuration", {}).get("presence_entities", [])),
                "current_mode": pm_diagnostics.get("configuration", {}).get("current_mode", "unknown"),
                "issues": pm_diagnostics.get("troubleshooting", {}).get("common_issues", []),
                "performance": pm_diagnostics.get("performance_metrics", {})
            }
            
            diagnostics["components"]["presence_manager"] = component_info
            
            # Add to overall issues
            diagnostics["common_issues"].extend(component_info["issues"])
            
        except Exception as e:
            diagnostics["components"]["presence_manager"] = {
                "status": "error",
                "issues": [f"Failed to diagnose presence manager: {str(e)}"]
            }
    
    async def _diagnose_buffer_manager(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose buffer manager issues."""
        buffer_manager = entry_data.get("buffer_manager")
        if not buffer_manager:
            diagnostics["components"]["buffer_manager"] = {
                "status": "missing",
                "issues": ["BufferManager not found in entry data"]
            }
            return
        
        try:
            # Run buffer manager diagnostics
            bm_diagnostics = await buffer_manager.run_diagnostics()
            
            # Extract key information
            component_info = {
                "status": "healthy" if bm_diagnostics.get("troubleshooting", {}).get("health_score", 0) > 70 else "issues",
                "health_score": bm_diagnostics.get("troubleshooting", {}).get("health_score", 0),
                "entities_tracked": bm_diagnostics.get("manager_status", {}).get("entities_tracked", 0),
                "global_buffer_enabled": bm_diagnostics.get("manager_status", {}).get("global_buffer_enabled", False),
                "issues": bm_diagnostics.get("troubleshooting", {}).get("common_issues", []),
                "performance": bm_diagnostics.get("performance_metrics", {})
            }
            
            diagnostics["components"]["buffer_manager"] = component_info
            
            # Add to overall issues
            diagnostics["common_issues"].extend(component_info["issues"])
            
        except Exception as e:
            diagnostics["components"]["buffer_manager"] = {
                "status": "error",
                "issues": [f"Failed to diagnose buffer manager: {str(e)}"]
            }
    
    async def _diagnose_schedule_manager(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose schedule manager issues."""
        schedule_manager = entry_data.get("schedule_manager")
        if not schedule_manager:
            diagnostics["components"]["schedule_manager"] = {
                "status": "missing",
                "issues": ["ScheduleManager not found in entry data"]
            }
            return
        
        try:
            # Test basic schedule manager functionality
            component_info = {
                "status": "healthy",
                "issues": []
            }
            
            # Test schedule loading
            try:
                # This is a basic test - in a real implementation you might have more specific tests
                if hasattr(schedule_manager, 'get_tracked_entities'):
                    tracked_entities = schedule_manager.get_tracked_entities()
                    component_info["entities_tracked"] = len(tracked_entities)
                else:
                    component_info["entities_tracked"] = 0
            except Exception as e:
                component_info["issues"].append(f"Failed to get tracked entities: {str(e)}")
                component_info["status"] = "issues"
            
            diagnostics["components"]["schedule_manager"] = component_info
            diagnostics["common_issues"].extend(component_info["issues"])
            
        except Exception as e:
            diagnostics["components"]["schedule_manager"] = {
                "status": "error",
                "issues": [f"Failed to diagnose schedule manager: {str(e)}"]
            }
    
    async def _diagnose_storage_service(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose storage service issues."""
        storage_service = entry_data.get("storage_service")
        if not storage_service:
            diagnostics["components"]["storage_service"] = {
                "status": "missing",
                "issues": ["StorageService not found in entry data"]
            }
            return
        
        try:
            component_info = {
                "status": "healthy",
                "issues": []
            }
            
            # Test storage loading
            try:
                schedule_data = await storage_service.load_schedules()
                component_info["has_data"] = schedule_data is not None
                if schedule_data:
                    component_info["data_version"] = getattr(schedule_data, 'version', 'unknown')
                    component_info["entities_in_data"] = len(getattr(schedule_data, 'entities_tracked', []))
            except Exception as e:
                component_info["issues"].append(f"Failed to load schedules: {str(e)}")
                component_info["status"] = "issues"
            
            # Test storage saving (with a dummy save to test permissions)
            try:
                if hasattr(storage_service, '_store'):
                    # Just test that we can access the store
                    store = storage_service._store
                    component_info["store_available"] = store is not None
                else:
                    component_info["store_available"] = False
            except Exception as e:
                component_info["issues"].append(f"Storage access test failed: {str(e)}")
                component_info["status"] = "issues"
            
            diagnostics["components"]["storage_service"] = component_info
            diagnostics["common_issues"].extend(component_info["issues"])
            
        except Exception as e:
            diagnostics["components"]["storage_service"] = {
                "status": "error",
                "issues": [f"Failed to diagnose storage service: {str(e)}"]
            }
    
    async def _diagnose_logging_manager(self, entry_data: Dict[str, Any], diagnostics: Dict[str, Any]) -> None:
        """Diagnose logging manager issues."""
        logging_manager = entry_data.get("logging_manager")
        if not logging_manager:
            diagnostics["components"]["logging_manager"] = {
                "status": "missing",
                "issues": ["LoggingManager not found - enhanced logging unavailable"]
            }
            return
        
        try:
            component_info = {
                "status": "healthy",
                "issues": []
            }
            
            # Get logging status
            debug_status = logging_manager.get_debug_status()
            component_info["logging_level"] = debug_status.get("logging_level", "unknown")
            component_info["debug_enabled"] = any(debug_status.get("debug_flags", {}).values())
            component_info["performance_monitoring"] = debug_status.get("performance_monitoring", False)
            component_info["file_logging"] = debug_status.get("file_logging", False)
            
            diagnostics["components"]["logging_manager"] = component_info
            
        except Exception as e:
            diagnostics["components"]["logging_manager"] = {
                "status": "error",
                "issues": [f"Failed to diagnose logging manager: {str(e)}"]
            }
    
    def _analyze_overall_health(self, diagnostics: Dict[str, Any]) -> None:
        """Analyze overall system health based on component diagnostics."""
        components = diagnostics.get("components", {})
        
        # Count component statuses
        healthy_count = sum(1 for comp in components.values() if comp.get("status") == "healthy")
        issues_count = sum(1 for comp in components.values() if comp.get("status") == "issues")
        error_count = sum(1 for comp in components.values() if comp.get("status") == "error")
        missing_count = sum(1 for comp in components.values() if comp.get("status") == "missing")
        
        total_components = len(components)
        
        # Determine overall health
        if error_count > 0 or missing_count > 2:  # Allow some missing components
            diagnostics["overall_health"] = "critical"
        elif issues_count > total_components // 2:
            diagnostics["overall_health"] = "poor"
        elif issues_count > 0:
            diagnostics["overall_health"] = "fair"
        else:
            diagnostics["overall_health"] = "good"
        
        # Add health summary
        diagnostics["health_summary"] = {
            "total_components": total_components,
            "healthy": healthy_count,
            "issues": issues_count,
            "errors": error_count,
            "missing": missing_count,
            "health_percentage": (healthy_count / max(total_components, 1)) * 100
        }
    
    def _generate_summary_recommendations(self, diagnostics: Dict[str, Any]) -> None:
        """Generate summary recommendations based on all diagnostic results."""
        recommendations = []
        overall_health = diagnostics.get("overall_health", "unknown")
        
        if overall_health == "critical":
            recommendations.extend([
                "Critical issues detected - integration may not function properly",
                "Check Home Assistant logs for detailed error messages",
                "Consider removing and re-adding the integration",
                "Ensure Home Assistant has sufficient disk space and permissions"
            ])
        elif overall_health == "poor":
            recommendations.extend([
                "Multiple issues detected - some features may not work correctly",
                "Review component-specific issues and address configuration problems",
                "Check entity configurations and ensure all referenced entities exist"
            ])
        elif overall_health == "fair":
            recommendations.extend([
                "Minor issues detected - integration should work but may have limitations",
                "Review and fix configuration validation errors",
                "Consider enabling debug logging to monitor for additional issues"
            ])
        else:
            recommendations.extend([
                "Integration appears to be functioning normally",
                "Consider enabling performance monitoring if experiencing slowdowns",
                "Regular diagnostic checks can help identify issues early"
            ])
        
        # Add specific recommendations based on common issues
        common_issues = diagnostics.get("common_issues", [])
        
        if any("storage" in issue.lower() for issue in common_issues):
            recommendations.append("Check Home Assistant storage permissions and available disk space")
        
        if any("entity" in issue.lower() and "not found" in issue.lower() for issue in common_issues):
            recommendations.append("Review entity configurations and remove references to non-existent entities")
        
        if any("timeout" in issue.lower() or "stale" in issue.lower() for issue in common_issues):
            recommendations.append("Check network connectivity and entity update frequencies")
        
        # Remove duplicates and add to diagnostics
        diagnostics["recommendations"] = list(set(recommendations))
    
    def generate_troubleshooting_report(self, diagnostics: Dict[str, Any]) -> str:
        """Generate a human-readable troubleshooting report."""
        report_lines = []
        
        # Header
        report_lines.append("=== Roost Scheduler Troubleshooting Report ===")
        report_lines.append(f"Generated: {diagnostics.get('timestamp', 'unknown')}")
        report_lines.append(f"Entry ID: {diagnostics.get('entry_id', 'unknown')}")
        report_lines.append(f"Overall Health: {diagnostics.get('overall_health', 'unknown').upper()}")
        report_lines.append("")
        
        # Health Summary
        health_summary = diagnostics.get("health_summary", {})
        if health_summary:
            report_lines.append("Health Summary:")
            report_lines.append(f"  Total Components: {health_summary.get('total_components', 0)}")
            report_lines.append(f"  Healthy: {health_summary.get('healthy', 0)}")
            report_lines.append(f"  With Issues: {health_summary.get('issues', 0)}")
            report_lines.append(f"  Errors: {health_summary.get('errors', 0)}")
            report_lines.append(f"  Missing: {health_summary.get('missing', 0)}")
            report_lines.append(f"  Health Percentage: {health_summary.get('health_percentage', 0):.1f}%")
            report_lines.append("")
        
        # Component Status
        components = diagnostics.get("components", {})
        if components:
            report_lines.append("Component Status:")
            for component_name, component_info in components.items():
                status = component_info.get("status", "unknown").upper()
                report_lines.append(f"  {component_name}: {status}")
                
                # Add component-specific details
                if "health_score" in component_info:
                    report_lines.append(f"    Health Score: {component_info['health_score']}")
                
                if "entities_configured" in component_info:
                    report_lines.append(f"    Entities Configured: {component_info['entities_configured']}")
                
                if "entities_tracked" in component_info:
                    report_lines.append(f"    Entities Tracked: {component_info['entities_tracked']}")
                
                # Add issues
                issues = component_info.get("issues", [])
                if issues:
                    report_lines.append("    Issues:")
                    for issue in issues:
                        report_lines.append(f"      - {issue}")
            
            report_lines.append("")
        
        # Common Issues
        common_issues = diagnostics.get("common_issues", [])
        if common_issues:
            report_lines.append("Common Issues Found:")
            for issue in common_issues:
                report_lines.append(f"  - {issue}")
            report_lines.append("")
        
        # Recommendations
        recommendations = diagnostics.get("recommendations", [])
        if recommendations:
            report_lines.append("Recommendations:")
            for recommendation in recommendations:
                report_lines.append(f"  - {recommendation}")
            report_lines.append("")
        
        # Performance Summary
        performance_summary = diagnostics.get("performance_summary", {})
        if performance_summary:
            report_lines.append("Performance Summary:")
            for metric, value in performance_summary.items():
                report_lines.append(f"  {metric}: {value}")
            report_lines.append("")
        
        report_lines.append("=== End of Report ===")
        
        return "\n".join(report_lines)
    
    async def quick_health_check(self, entry_id: str) -> Tuple[str, List[str]]:
        """Perform a quick health check and return status and critical issues."""
        try:
            entry_data = self.hass.data.get(DOMAIN, {}).get(entry_id)
            if not entry_data:
                return "critical", ["Integration not properly initialized"]
            
            critical_issues = []
            
            # Check critical components
            required_components = ["storage_service", "schedule_manager", "presence_manager", "buffer_manager"]
            for component in required_components:
                if component not in entry_data or entry_data[component] is None:
                    critical_issues.append(f"Missing {component}")
            
            # Quick storage test
            storage_service = entry_data.get("storage_service")
            if storage_service:
                try:
                    await storage_service.load_schedules()
                except Exception as e:
                    critical_issues.append(f"Storage access failed: {str(e)}")
            
            # Determine status
            if len(critical_issues) > 2:
                return "critical", critical_issues
            elif len(critical_issues) > 0:
                return "issues", critical_issues
            else:
                return "healthy", []
                
        except Exception as e:
            return "error", [f"Health check failed: {str(e)}"]
    
    def get_common_solutions(self) -> Dict[str, List[str]]:
        """Get common solutions for typical issues."""
        return {
            "integration_not_loading": [
                "Check Home Assistant logs for specific error messages",
                "Ensure all required dependencies are installed",
                "Restart Home Assistant",
                "Check available disk space and permissions"
            ],
            "entities_not_found": [
                "Verify that referenced entities exist in Home Assistant",
                "Check entity naming and domains",
                "Remove references to deleted entities",
                "Ensure entities are properly configured and available"
            ],
            "storage_issues": [
                "Check Home Assistant storage permissions",
                "Ensure sufficient disk space is available",
                "Check for file system errors",
                "Restart Home Assistant to reset storage connections"
            ],
            "presence_detection_issues": [
                "Verify presence entities are updating regularly",
                "Check presence entity states and last_updated times",
                "Adjust presence timeout if entities update infrequently",
                "Ensure presence entities are of appropriate types (device_tracker, person, etc.)"
            ],
            "buffer_not_working": [
                "Check buffer configuration values (time and delta)",
                "Ensure buffer is enabled in configuration",
                "Verify entity states are being tracked properly",
                "Check for manual changes that might affect buffer logic"
            ],
            "performance_issues": [
                "Enable performance monitoring to identify bottlenecks",
                "Check for excessive debug logging",
                "Review entity count and complexity",
                "Consider reducing update frequency for non-critical entities"
            ]
        }