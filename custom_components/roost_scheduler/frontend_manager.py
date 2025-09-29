"""
Frontend Resource Manager for Roost Scheduler.

Handles registration and loading of frontend resources (JavaScript, CSS) with Home Assistant's frontend system.
Provides resource verification, error handling, and retry logic for failed registrations.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from homeassistant.core import HomeAssistant
from homeassistant.components import frontend
from homeassistant.const import __version__ as ha_version

try:
    from .const import DOMAIN
except ImportError:
    # Fallback for testing
    DOMAIN = "roost_scheduler"

_LOGGER = logging.getLogger(__name__)


@dataclass
class FrontendResourceConfig:
    """Configuration for frontend resource registration."""
    card_js_path: str
    card_css_path: Optional[str] = None
    resource_version: str = "1.0.0"
    fallback_enabled: bool = True
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class ResourceRegistrationResult:
    """Result of resource registration attempt."""
    success: bool
    resource_path: str
    error_message: Optional[str] = None
    retry_count: int = 0
    fallback_used: bool = False


class FrontendResourceManager:
    """Manages frontend resource registration for Roost Scheduler card."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the frontend resource manager."""
        self.hass = hass
        self._registered_resources: List[str] = []
        self._registration_results: List[ResourceRegistrationResult] = []
        
        # Default configuration
        self._config = FrontendResourceConfig(
            card_js_path="/hacsfiles/roost-scheduler-card/roost-scheduler-card.js",
            card_css_path=None,  # No CSS file currently
            resource_version="0.3.0",
            fallback_enabled=True,
            retry_attempts=3,
            retry_delay=1.0
        )
    
    async def register_frontend_resources(self) -> Dict[str, Any]:
        """
        Register frontend resources with Home Assistant.
        
        Returns:
            Dict containing registration status and results.
        """
        _LOGGER.info("Starting frontend resource registration for Roost Scheduler")
        
        registration_status = {
            "success": False,
            "resources_registered": [],
            "resources_failed": [],
            "warnings": [],
            "ha_version": ha_version,
            "frontend_available": self._is_frontend_available()
        }
        
        try:
            # Verify frontend availability
            if not registration_status["frontend_available"]:
                error_msg = "Home Assistant frontend component not available"
                _LOGGER.error(error_msg)
                registration_status["resources_failed"].append({
                    "resource": "frontend_check",
                    "error": error_msg
                })
                return registration_status
            
            # Verify resource availability before registration
            resource_check = await self.verify_resource_availability()
            if not resource_check["js_available"]:
                error_msg = f"JavaScript resource not found: {self._config.card_js_path}"
                _LOGGER.error(error_msg)
                registration_status["resources_failed"].append({
                    "resource": self._config.card_js_path,
                    "error": error_msg
                })
                
                # Try fallback if enabled
                if self._config.fallback_enabled:
                    fallback_result = await self._try_fallback_registration()
                    if fallback_result.success:
                        registration_status["resources_registered"].append({
                            "resource": fallback_result.resource_path,
                            "fallback_used": True
                        })
                        registration_status["warnings"].append("Using fallback resource path")
                    else:
                        registration_status["resources_failed"].append({
                            "resource": "fallback",
                            "error": fallback_result.error_message
                        })
                
                if not registration_status["resources_registered"]:
                    return registration_status
            
            # Register JavaScript resource
            js_result = await self._register_js_resource()
            if js_result.success:
                registration_status["resources_registered"].append({
                    "resource": js_result.resource_path,
                    "retry_count": js_result.retry_count,
                    "fallback_used": js_result.fallback_used
                })
                self._registered_resources.append(js_result.resource_path)
            else:
                registration_status["resources_failed"].append({
                    "resource": js_result.resource_path,
                    "error": js_result.error_message,
                    "retry_count": js_result.retry_count
                })
            
            # Register CSS resource if configured
            if self._config.card_css_path:
                css_result = await self._register_css_resource()
                if css_result.success:
                    registration_status["resources_registered"].append({
                        "resource": css_result.resource_path,
                        "retry_count": css_result.retry_count
                    })
                    self._registered_resources.append(css_result.resource_path)
                else:
                    registration_status["resources_failed"].append({
                        "resource": css_result.resource_path,
                        "error": css_result.error_message,
                        "retry_count": css_result.retry_count
                    })
                    # CSS failure is not critical
                    registration_status["warnings"].append("CSS resource registration failed - continuing without styles")
            
            # Determine overall success
            registration_status["success"] = len(registration_status["resources_registered"]) > 0
            
            if registration_status["success"]:
                _LOGGER.info("Frontend resource registration completed successfully. Registered: %s", 
                           [r["resource"] for r in registration_status["resources_registered"]])
            else:
                _LOGGER.error("Frontend resource registration failed completely")
            
            return registration_status
            
        except Exception as e:
            error_msg = f"Unexpected error during frontend resource registration: {str(e)}"
            _LOGGER.error(error_msg, exc_info=True)
            registration_status["resources_failed"].append({
                "resource": "registration_process",
                "error": error_msg
            })
            return registration_status
    
    async def verify_resource_availability(self) -> Dict[str, Any]:
        """
        Verify that frontend resources exist and are accessible.
        
        Returns:
            Dict containing availability status for each resource type.
        """
        _LOGGER.debug("Verifying frontend resource availability")
        
        availability_status = {
            "js_available": False,
            "css_available": False,
            "js_path": self._config.card_js_path,
            "css_path": self._config.card_css_path,
            "js_size": None,
            "css_size": None,
            "errors": []
        }
        
        try:
            # Check JavaScript file
            js_full_path = self._get_full_resource_path(self._config.card_js_path)
            if js_full_path and os.path.isfile(js_full_path):
                availability_status["js_available"] = True
                availability_status["js_size"] = os.path.getsize(js_full_path)
                _LOGGER.debug("JavaScript resource found: %s (%d bytes)", 
                            js_full_path, availability_status["js_size"])
            else:
                error_msg = f"JavaScript resource not found: {js_full_path or self._config.card_js_path}"
                availability_status["errors"].append(error_msg)
                _LOGGER.warning(error_msg)
            
            # Check CSS file if configured
            if self._config.card_css_path:
                css_full_path = self._get_full_resource_path(self._config.card_css_path)
                if css_full_path and os.path.isfile(css_full_path):
                    availability_status["css_available"] = True
                    availability_status["css_size"] = os.path.getsize(css_full_path)
                    _LOGGER.debug("CSS resource found: %s (%d bytes)", 
                                css_full_path, availability_status["css_size"])
                else:
                    error_msg = f"CSS resource not found: {css_full_path or self._config.card_css_path}"
                    availability_status["errors"].append(error_msg)
                    _LOGGER.warning(error_msg)
            else:
                availability_status["css_available"] = True  # Not required
            
        except Exception as e:
            error_msg = f"Error verifying resource availability: {str(e)}"
            availability_status["errors"].append(error_msg)
            _LOGGER.error(error_msg, exc_info=True)
        
        return availability_status
    
    async def handle_resource_loading_errors(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle resource loading errors with fallback strategies.
        
        Args:
            error_info: Dictionary containing error details
            
        Returns:
            Dict containing recovery actions taken and results.
        """
        _LOGGER.info("Handling resource loading errors: %s", error_info)
        
        recovery_result = {
            "recovery_attempted": False,
            "recovery_successful": False,
            "actions_taken": [],
            "fallback_used": False,
            "manual_steps_required": []
        }
        
        try:
            # Attempt resource verification first
            availability = await self.verify_resource_availability()
            
            if not availability["js_available"]:
                recovery_result["recovery_attempted"] = True
                
                # Try alternative resource paths
                alternative_paths = [
                    "/local/roost-scheduler-card/roost-scheduler-card.js",
                    f"/local/community/{DOMAIN}/roost-scheduler-card.js",
                    "/hacsfiles/roost-scheduler-card/dist/roost-scheduler-card.js"
                ]
                
                for alt_path in alternative_paths:
                    _LOGGER.debug("Trying alternative resource path: %s", alt_path)
                    full_path = self._get_full_resource_path(alt_path)
                    if full_path and os.path.isfile(full_path):
                        # Update configuration and retry registration
                        self._config.card_js_path = alt_path
                        retry_result = await self._register_js_resource()
                        if retry_result.success:
                            recovery_result["recovery_successful"] = True
                            recovery_result["fallback_used"] = True
                            recovery_result["actions_taken"].append(f"Used alternative path: {alt_path}")
                            _LOGGER.info("Successfully recovered using alternative path: %s", alt_path)
                            break
                        else:
                            recovery_result["actions_taken"].append(f"Failed alternative path: {alt_path}")
                
                # If still not successful, provide manual steps
                if not recovery_result["recovery_successful"]:
                    recovery_result["manual_steps_required"] = [
                        "Verify that the Roost Scheduler card files are properly installed",
                        "Check HACS installation and ensure the frontend resources are downloaded",
                        "Manually copy roost-scheduler-card.js to /config/www/roost-scheduler-card/",
                        "Restart Home Assistant after fixing resource files"
                    ]
            
        except Exception as e:
            error_msg = f"Error during resource loading error handling: {str(e)}"
            recovery_result["actions_taken"].append(error_msg)
            _LOGGER.error(error_msg, exc_info=True)
        
        return recovery_result
    
    def get_registration_status(self) -> Dict[str, Any]:
        """
        Get current registration status and diagnostics.
        
        Returns:
            Dict containing current registration status and diagnostics.
        """
        return {
            "registered_resources": self._registered_resources.copy(),
            "registration_results": [
                {
                    "success": result.success,
                    "resource_path": result.resource_path,
                    "error_message": result.error_message,
                    "retry_count": result.retry_count,
                    "fallback_used": result.fallback_used
                }
                for result in self._registration_results
            ],
            "frontend_available": self._is_frontend_available(),
            "ha_version": ha_version,
            "config": {
                "card_js_path": self._config.card_js_path,
                "card_css_path": self._config.card_css_path,
                "resource_version": self._config.resource_version,
                "fallback_enabled": self._config.fallback_enabled,
                "retry_attempts": self._config.retry_attempts
            }
        }
    
    async def _register_js_resource(self) -> ResourceRegistrationResult:
        """Register JavaScript resource with retry logic."""
        return await self._register_resource_with_retry(
            self._config.card_js_path,
            self._register_single_js_resource
        )
    
    async def _register_css_resource(self) -> ResourceRegistrationResult:
        """Register CSS resource with retry logic."""
        return await self._register_resource_with_retry(
            self._config.card_css_path,
            self._register_single_css_resource
        )
    
    async def _register_resource_with_retry(
        self, 
        resource_path: str, 
        register_func
    ) -> ResourceRegistrationResult:
        """Register a resource with retry logic."""
        result = ResourceRegistrationResult(
            success=False,
            resource_path=resource_path
        )
        
        for attempt in range(self._config.retry_attempts):
            try:
                await register_func(resource_path)
                result.success = True
                result.retry_count = attempt
                _LOGGER.debug("Successfully registered resource %s on attempt %d", 
                            resource_path, attempt + 1)
                break
                
            except Exception as e:
                result.error_message = str(e)
                result.retry_count = attempt + 1
                
                if attempt < self._config.retry_attempts - 1:
                    _LOGGER.warning("Failed to register resource %s on attempt %d: %s. Retrying...", 
                                  resource_path, attempt + 1, str(e))
                    await asyncio.sleep(self._config.retry_delay)
                else:
                    _LOGGER.error("Failed to register resource %s after %d attempts: %s", 
                                resource_path, self._config.retry_attempts, str(e))
        
        self._registration_results.append(result)
        return result
    
    async def _register_single_js_resource(self, resource_path: str) -> None:
        """Register a single JavaScript resource."""
        try:
            # Use Home Assistant's frontend.add_extra_js_url for custom cards
            frontend.add_extra_js_url(self.hass, resource_path)
            _LOGGER.debug("Registered JavaScript resource: %s", resource_path)
            
        except Exception as e:
            _LOGGER.error("Failed to register JavaScript resource %s: %s", resource_path, str(e))
            raise
    
    async def _register_single_css_resource(self, resource_path: str) -> None:
        """Register a single CSS resource."""
        try:
            # Use Home Assistant's frontend API for CSS resources
            # Note: CSS registration might not be available in all HA versions
            if hasattr(frontend, 'add_extra_css_url'):
                frontend.add_extra_css_url(self.hass, resource_path)
                _LOGGER.debug("Registered CSS resource: %s", resource_path)
            else:
                _LOGGER.warning("CSS resource registration not supported in this Home Assistant version")
                raise NotImplementedError("CSS resource registration not supported")
            
        except Exception as e:
            _LOGGER.error("Failed to register CSS resource %s: %s", resource_path, str(e))
            raise
    
    async def _try_fallback_registration(self) -> ResourceRegistrationResult:
        """Try fallback resource registration strategies."""
        fallback_paths = [
            "/local/roost-scheduler-card/roost-scheduler-card.js",
            f"/local/community/{DOMAIN}/roost-scheduler-card.js",
            "/hacsfiles/roost-scheduler-card/dist/roost-scheduler-card.js"
        ]
        
        for fallback_path in fallback_paths:
            _LOGGER.debug("Trying fallback resource path: %s", fallback_path)
            
            # Check if fallback resource exists
            full_path = self._get_full_resource_path(fallback_path)
            if full_path and os.path.isfile(full_path):
                try:
                    await self._register_single_js_resource(fallback_path)
                    return ResourceRegistrationResult(
                        success=True,
                        resource_path=fallback_path,
                        fallback_used=True
                    )
                except Exception as e:
                    _LOGGER.debug("Fallback path %s failed: %s", fallback_path, str(e))
                    continue
        
        return ResourceRegistrationResult(
            success=False,
            resource_path="fallback",
            error_message="No working fallback paths found"
        )
    
    def _is_frontend_available(self) -> bool:
        """Check if Home Assistant frontend component is available."""
        try:
            return "frontend" in self.hass.config.components
        except Exception as e:
            _LOGGER.warning("Error checking frontend availability: %s", str(e))
            return False
    
    def _get_full_resource_path(self, resource_path: str) -> Optional[str]:
        """Convert resource URL path to full filesystem path."""
        try:
            if resource_path.startswith("/hacsfiles/"):
                # HACS files are typically in config/www/community/
                relative_path = resource_path.replace("/hacsfiles/", "")
                return os.path.join(self.hass.config.config_dir, "www", "community", relative_path)
            elif resource_path.startswith("/local/"):
                # Local files are in config/www/
                relative_path = resource_path.replace("/local/", "")
                return os.path.join(self.hass.config.config_dir, "www", relative_path)
            else:
                _LOGGER.warning("Unknown resource path format: %s", resource_path)
                return None
                
        except Exception as e:
            _LOGGER.error("Error converting resource path %s: %s", resource_path, str(e))
            return None