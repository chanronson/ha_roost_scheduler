"""Setup completion feedback system for Roost Scheduler integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

@dataclass
class SetupFeedbackData:
    """Data structure for setup feedback information."""
    success: bool
    dashboard_integration_status: bool
    card_registered: bool
    card_added_to_dashboard: bool
    dashboard_id: Optional[str]
    error_messages: List[str]
    warning_messages: List[str]
    next_steps: List[str]
    troubleshooting_info: Dict[str, Any]

class SetupFeedbackManager:
    """Manages setup completion feedback and user guidance."""
    
    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the setup feedback manager."""
        self.hass = hass
        self._logger = logging.getLogger(__name__)
    
    def generate_success_message(
        self, 
        dashboard_integration_status: bool,
        card_registered: bool,
        card_added_to_dashboard: bool,
        dashboard_id: Optional[str] = None
    ) -> str:
        """Generate a success message based on setup completion status.
        
        Args:
            dashboard_integration_status: Whether dashboard integration succeeded
            card_registered: Whether the card was registered with frontend
            card_added_to_dashboard: Whether card was added to dashboard
            dashboard_id: ID of the dashboard where card was added
            
        Returns:
            Formatted success message for the user
        """
        if dashboard_integration_status and card_added_to_dashboard:
            dashboard_name = dashboard_id or "your dashboard"
            return (
                f"✅ Roost Scheduler setup completed successfully!\n\n"
                f"🎯 The Roost Scheduler card has been automatically added to {dashboard_name}. "
                f"You can now start creating and managing your heating schedules.\n\n"
                f"📍 Next steps:\n"
                f"• Navigate to your dashboard to see the new Roost Scheduler card\n"
                f"• Configure your first heating schedule\n"
                f"• Explore advanced scheduling features"
            )
        elif card_registered:
            return (
                f"✅ Roost Scheduler setup completed successfully!\n\n"
                f"📋 The Roost Scheduler card is now available in your dashboard's card picker. "
                f"You can manually add it to any dashboard.\n\n"
                f"📍 Next steps:\n"
                f"• Go to your dashboard and click 'Edit Dashboard'\n"
                f"• Click 'Add Card' and search for 'Roost Scheduler'\n"
                f"• Add the card to your preferred location"
            )
        else:
            return (
                f"✅ Roost Scheduler integration setup completed!\n\n"
                f"⚠️ Dashboard integration encountered some issues, but the core functionality is ready. "
                f"Please see the troubleshooting information below for manual setup steps."
            )
    
    def generate_error_diagnostics(
        self,
        error_messages: List[str],
        dashboard_integration_status: bool,
        card_registered: bool,
        frontend_resources_loaded: bool
    ) -> Dict[str, Any]:
        """Generate comprehensive error diagnostics for troubleshooting.
        
        Args:
            error_messages: List of error messages encountered
            dashboard_integration_status: Dashboard integration success status
            card_registered: Card registration success status  
            frontend_resources_loaded: Frontend resources loading status
            
        Returns:
            Dictionary containing diagnostic information
        """
        diagnostics = {
            "setup_status": {
                "dashboard_integration": dashboard_integration_status,
                "card_registered": card_registered,
                "frontend_resources_loaded": frontend_resources_loaded
            },
            "errors": error_messages,
            "system_info": {
                "ha_version": self.hass.config.version,
                "domain": DOMAIN
            },
            "troubleshooting_steps": []
        }
        
        # Add specific troubleshooting steps based on failure points
        if not frontend_resources_loaded:
            diagnostics["troubleshooting_steps"].extend([
                "Check that card files exist in www/roost-scheduler-card/",
                "Verify file permissions allow Home Assistant to read card files",
                "Try restarting Home Assistant to reload frontend resources"
            ])
        
        if not card_registered:
            diagnostics["troubleshooting_steps"].extend([
                "Clear browser cache and refresh the page",
                "Check browser console for JavaScript errors",
                "Verify the card is properly installed in www/roost-scheduler-card/"
            ])
        
        if not dashboard_integration_status:
            diagnostics["troubleshooting_steps"].extend([
                "Try manually adding the card through dashboard edit mode",
                "Check Lovelace configuration for any conflicts",
                "Verify dashboard permissions allow modifications"
            ])
        
        return diagnostics    
    
    def generate_next_steps_guidance(
        self,
        dashboard_integration_status: bool,
        card_registered: bool,
        card_added_to_dashboard: bool,
        dashboard_id: Optional[str] = None
    ) -> List[str]:
        """Generate next steps guidance based on setup completion status.
        
        Args:
            dashboard_integration_status: Whether dashboard integration succeeded
            card_registered: Whether the card was registered with frontend
            card_added_to_dashboard: Whether card was added to dashboard
            dashboard_id: ID of the dashboard where card was added
            
        Returns:
            List of next steps for the user
        """
        next_steps = []
        
        if dashboard_integration_status and card_added_to_dashboard:
            dashboard_name = dashboard_id or "your dashboard"
            next_steps.extend([
                f"Navigate to {dashboard_name} to access your new Roost Scheduler card",
                "Create your first heating schedule by clicking 'Add Schedule'",
                "Configure schedule parameters like temperature, time, and days",
                "Test your schedule by enabling it and monitoring the heating system",
                "Explore advanced features like presence detection and buffer management"
            ])
        elif card_registered:
            next_steps.extend([
                "Go to your dashboard and enter edit mode",
                "Click 'Add Card' and search for 'Roost Scheduler'",
                "Position the card where you want it on your dashboard",
                "Configure the card settings to match your preferences",
                "Start creating your heating schedules"
            ])
        else:
            next_steps.extend([
                "Follow the manual installation guide in the documentation",
                "Check the troubleshooting section for common issues",
                "Verify that all card files are properly installed",
                "Contact support if issues persist"
            ])
        
        # Always add general next steps
        next_steps.extend([
            "Review the setup guide for advanced configuration options",
            "Join the community forum for tips and support"
        ])
        
        return next_steps
    
    def create_setup_feedback_data(
        self,
        success: bool,
        dashboard_integration_status: bool = False,
        card_registered: bool = False,
        card_added_to_dashboard: bool = False,
        dashboard_id: Optional[str] = None,
        error_messages: Optional[List[str]] = None,
        warning_messages: Optional[List[str]] = None
    ) -> SetupFeedbackData:
        """Create comprehensive setup feedback data structure.
        
        Args:
            success: Overall setup success status
            dashboard_integration_status: Dashboard integration success status
            card_registered: Card registration success status
            card_added_to_dashboard: Whether card was added to dashboard
            dashboard_id: ID of the dashboard where card was added
            error_messages: List of error messages
            warning_messages: List of warning messages
            
        Returns:
            SetupFeedbackData object with all feedback information
        """
        error_messages = error_messages or []
        warning_messages = warning_messages or []
        
        # Generate next steps guidance
        next_steps = self.generate_next_steps_guidance(
            dashboard_integration_status,
            card_registered,
            card_added_to_dashboard,
            dashboard_id
        )
        
        # Generate troubleshooting info if there were issues
        troubleshooting_info = {}
        if not success or error_messages:
            troubleshooting_info = self.generate_error_diagnostics(
                error_messages,
                dashboard_integration_status,
                card_registered,
                True  # Assume frontend resources loaded if we got this far
            )
        
        return SetupFeedbackData(
            success=success,
            dashboard_integration_status=dashboard_integration_status,
            card_registered=card_registered,
            card_added_to_dashboard=card_added_to_dashboard,
            dashboard_id=dashboard_id,
            error_messages=error_messages,
            warning_messages=warning_messages,
            next_steps=next_steps,
            troubleshooting_info=troubleshooting_info
        )
    
    def format_feedback_for_config_flow(self, feedback_data: SetupFeedbackData) -> Dict[str, Any]:
        """Format feedback data for display in configuration flow.
        
        Args:
            feedback_data: SetupFeedbackData object with feedback information
            
        Returns:
            Dictionary formatted for configuration flow display
        """
        # Generate the main success message
        success_message = self.generate_success_message(
            feedback_data.dashboard_integration_status,
            feedback_data.card_registered,
            feedback_data.card_added_to_dashboard,
            feedback_data.dashboard_id
        )
        
        formatted_feedback = {
            "title": "Setup Complete" if feedback_data.success else "Setup Complete with Issues",
            "description": success_message,
            "next_steps": feedback_data.next_steps
        }
        
        # Add warnings if present
        if feedback_data.warning_messages:
            formatted_feedback["warnings"] = feedback_data.warning_messages
        
        # Add error information if present
        if feedback_data.error_messages:
            formatted_feedback["errors"] = feedback_data.error_messages
            formatted_feedback["troubleshooting"] = feedback_data.troubleshooting_info.get("troubleshooting_steps", [])
        
        return formatted_feedback
    
    def log_setup_completion(self, feedback_data: SetupFeedbackData) -> None:
        """Log setup completion information for diagnostics.
        
        Args:
            feedback_data: SetupFeedbackData object with feedback information
        """
        if feedback_data.success:
            self._logger.info(
                "Roost Scheduler setup completed successfully. "
                "Dashboard integration: %s, Card registered: %s, Card added: %s",
                feedback_data.dashboard_integration_status,
                feedback_data.card_registered,
                feedback_data.card_added_to_dashboard
            )
        else:
            self._logger.warning(
                "Roost Scheduler setup completed with issues. "
                "Errors: %s, Dashboard integration: %s",
                feedback_data.error_messages,
                feedback_data.dashboard_integration_status
            )
        
        # Log detailed diagnostics if there were issues
        if feedback_data.troubleshooting_info:
            self._logger.debug(
                "Setup troubleshooting info: %s",
                feedback_data.troubleshooting_info
            )