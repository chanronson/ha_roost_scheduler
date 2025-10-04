"""Automatic domain fixing service for Roost Scheduler integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .domain_consistency_checker import DomainConsistencyChecker, ConsistencyResult, FixResult
except ImportError:
    from domain_consistency_checker import DomainConsistencyChecker, ConsistencyResult, FixResult

_LOGGER = logging.getLogger(__name__)


@dataclass
class DomainMismatchDetection:
    """Result of domain mismatch detection."""
    
    mismatch_detected: bool
    mismatched_files: List[str]
    expected_domain: Optional[str]
    actual_domains: Dict[str, Optional[str]]
    severity: str  # 'critical', 'warning', 'info'
    fix_recommended: bool
    fix_description: str


@dataclass
class AutoFixResult:
    """Result of automatic domain fixing operation."""
    
    success: bool
    detection_result: DomainMismatchDetection
    fix_result: Optional[FixResult]
    verification_passed: bool
    error_message: Optional[str]
    recommendations: List[str]


class DomainFixer:
    """Service for automatic domain mismatch detection and fixing."""
    
    def __init__(self, integration_path: str) -> None:
        """Initialize the domain fixer.
        
        Args:
            integration_path: Path to the integration directory
        """
        self.integration_path = Path(integration_path)
        self.checker = DomainConsistencyChecker(integration_path)
        
    async def detect_domain_mismatch(self) -> DomainMismatchDetection:
        """Detect domain mismatches across integration files.
        
        Returns:
            DomainMismatchDetection with detailed analysis
        """
        try:
            # Get consistency validation result
            consistency_result = await self.checker.validate_consistency()
            
            # Analyze the results
            mismatched_files = []
            actual_domains = {
                'manifest.json': consistency_result.manifest_domain,
                'const.py': consistency_result.const_domain,
                'config_flow.py': consistency_result.config_flow_domain
            }
            
            # Determine expected domain (priority: manifest > const > config_flow)
            expected_domain = None
            for domain in [consistency_result.manifest_domain, consistency_result.const_domain, consistency_result.config_flow_domain]:
                if domain and self.checker._is_valid_domain_format(domain):
                    expected_domain = domain
                    break
            
            # Check for mismatches
            mismatch_detected = not consistency_result.consistent
            
            if mismatch_detected:
                # Identify which files have mismatches
                for file_name, domain in actual_domains.items():
                    if expected_domain and domain and domain != expected_domain:
                        mismatched_files.append(file_name)
                    elif domain is None:
                        mismatched_files.append(f"{file_name} (missing domain)")
            
            # Determine severity
            severity = self._determine_severity(consistency_result, mismatched_files)
            
            # Determine if fix is recommended
            fix_recommended = mismatch_detected and expected_domain is not None
            
            # Generate fix description
            fix_description = self._generate_fix_description(
                mismatch_detected, expected_domain, mismatched_files
            )
            
            return DomainMismatchDetection(
                mismatch_detected=mismatch_detected,
                mismatched_files=mismatched_files,
                expected_domain=expected_domain,
                actual_domains=actual_domains,
                severity=severity,
                fix_recommended=fix_recommended,
                fix_description=fix_description
            )
            
        except Exception as e:
            _LOGGER.error("Error detecting domain mismatch: %s", e)
            return DomainMismatchDetection(
                mismatch_detected=True,
                mismatched_files=[],
                expected_domain=None,
                actual_domains={},
                severity='critical',
                fix_recommended=False,
                fix_description=f"Error during detection: {e}"
            )
    
    async def apply_automatic_fix(self, detection_result: Optional[DomainMismatchDetection] = None) -> AutoFixResult:
        """Apply automatic domain consistency fixing.
        
        Args:
            detection_result: Optional pre-computed detection result
            
        Returns:
            AutoFixResult with details of the fixing operation
        """
        try:
            # Get detection result if not provided
            if detection_result is None:
                detection_result = await self.detect_domain_mismatch()
            
            # Check if fix is needed and recommended
            if not detection_result.mismatch_detected:
                return AutoFixResult(
                    success=True,
                    detection_result=detection_result,
                    fix_result=None,
                    verification_passed=True,
                    error_message=None,
                    recommendations=["No domain mismatch detected - no fix needed"]
                )
            
            if not detection_result.fix_recommended:
                return AutoFixResult(
                    success=False,
                    detection_result=detection_result,
                    fix_result=None,
                    verification_passed=False,
                    error_message="Automatic fix not recommended for this type of mismatch",
                    recommendations=[
                        "Manual intervention required",
                        "Check domain configuration in all files",
                        "Ensure domain follows valid format"
                    ]
                )
            
            # Apply fixes using the domain consistency checker
            fix_result = await self.checker.fix_inconsistencies()
            
            # Verify the fix
            verification_passed = await self._verify_fix()
            
            # Generate recommendations
            recommendations = self._generate_post_fix_recommendations(
                fix_result, verification_passed
            )
            
            return AutoFixResult(
                success=fix_result.success and verification_passed,
                detection_result=detection_result,
                fix_result=fix_result,
                verification_passed=verification_passed,
                error_message=None if fix_result.success else "Fix operation failed",
                recommendations=recommendations
            )
            
        except Exception as e:
            _LOGGER.error("Error applying automatic fix: %s", e)
            return AutoFixResult(
                success=False,
                detection_result=detection_result or DomainMismatchDetection(
                    mismatch_detected=True,
                    mismatched_files=[],
                    expected_domain=None,
                    actual_domains={},
                    severity='critical',
                    fix_recommended=False,
                    fix_description="Error during fixing"
                ),
                fix_result=None,
                verification_passed=False,
                error_message=f"Unexpected error during fix: {e}",
                recommendations=["Manual intervention required"]
            )
    
    async def verify_fix_effectiveness(self) -> bool:
        """Verify that domain consistency has been restored.
        
        Returns:
            True if domain is now consistent across all files
        """
        return await self._verify_fix()
    
    async def get_fix_recommendations(self, detection_result: Optional[DomainMismatchDetection] = None) -> List[str]:
        """Get recommendations for fixing domain issues.
        
        Args:
            detection_result: Optional pre-computed detection result
            
        Returns:
            List of recommendations for fixing domain issues
        """
        if detection_result is None:
            detection_result = await self.detect_domain_mismatch()
        
        recommendations = []
        
        if not detection_result.mismatch_detected:
            recommendations.append("Domain configuration is consistent - no action needed")
            return recommendations
        
        if detection_result.fix_recommended:
            recommendations.extend([
                "Automatic fix is available and recommended",
                f"Expected domain: {detection_result.expected_domain}",
                "Run automatic fix to resolve inconsistencies"
            ])
        else:
            recommendations.extend([
                "Manual intervention required",
                "Check domain configuration in all files:",
            ])
            
            for file_name, domain in detection_result.actual_domains.items():
                if domain:
                    recommendations.append(f"  - {file_name}: {domain}")
                else:
                    recommendations.append(f"  - {file_name}: <missing>")
        
        # Add specific recommendations based on mismatched files
        if 'manifest.json' in detection_result.mismatched_files:
            recommendations.append("Update domain field in manifest.json")
        
        if 'const.py' in detection_result.mismatched_files:
            recommendations.append("Update DOMAIN constant in const.py")
        
        if 'config_flow.py' in detection_result.mismatched_files:
            recommendations.append("Ensure config flow class uses correct domain")
        
        return recommendations
    
    def _determine_severity(self, consistency_result: ConsistencyResult, mismatched_files: List[str]) -> str:
        """Determine the severity of domain mismatch.
        
        Args:
            consistency_result: Consistency validation result
            mismatched_files: List of files with mismatches
            
        Returns:
            Severity level: 'critical', 'warning', or 'info'
        """
        # Critical if manifest.json or const.py have issues
        critical_files = ['manifest.json', 'const.py']
        if any(f for f in mismatched_files if any(cf in f for cf in critical_files)):
            return 'critical'
        
        # Critical if no domain found anywhere
        if not any([consistency_result.manifest_domain, consistency_result.const_domain]):
            return 'critical'
        
        # Warning if only config_flow.py has issues
        if mismatched_files and all('config_flow.py' in f for f in mismatched_files):
            return 'warning'
        
        # Info if only minor inconsistencies
        return 'info'
    
    def _generate_fix_description(self, mismatch_detected: bool, expected_domain: Optional[str], mismatched_files: List[str]) -> str:
        """Generate description of what the fix will do.
        
        Args:
            mismatch_detected: Whether mismatch was detected
            expected_domain: The expected domain value
            mismatched_files: List of files with mismatches
            
        Returns:
            Description of the fix operation
        """
        if not mismatch_detected:
            return "No fix needed - domain is consistent"
        
        if not expected_domain:
            return "Cannot determine correct domain - manual intervention required"
        
        if not mismatched_files:
            return "Domain inconsistency detected but specific files unclear"
        
        fix_actions = []
        for file_name in mismatched_files:
            if 'manifest.json' in file_name:
                fix_actions.append(f"Update manifest.json domain to '{expected_domain}'")
            elif 'const.py' in file_name:
                fix_actions.append(f"Update const.py DOMAIN constant to '{expected_domain}'")
            elif 'config_flow.py' in file_name:
                fix_actions.append(f"Ensure config_flow.py uses domain '{expected_domain}'")
        
        return "Automatic fix will: " + "; ".join(fix_actions)
    
    async def _verify_fix(self) -> bool:
        """Verify that the fix was successful.
        
        Returns:
            True if domain is now consistent
        """
        try:
            consistency_result = await self.checker.validate_consistency()
            return consistency_result.consistent
        except Exception as e:
            _LOGGER.error("Error verifying fix: %s", e)
            return False
    
    def _generate_post_fix_recommendations(self, fix_result: Optional[FixResult], verification_passed: bool) -> List[str]:
        """Generate recommendations after fix attempt.
        
        Args:
            fix_result: Result of the fix operation
            verification_passed: Whether verification passed
            
        Returns:
            List of post-fix recommendations
        """
        recommendations = []
        
        if fix_result and fix_result.success and verification_passed:
            recommendations.extend([
                "Domain consistency successfully restored",
                "Integration should now load properly",
                "Consider restarting Home Assistant to ensure changes take effect"
            ])
        elif fix_result and fix_result.success and not verification_passed:
            recommendations.extend([
                "Fix was applied but verification failed",
                "Manual verification recommended",
                "Check all files for correct domain configuration"
            ])
        elif fix_result and not fix_result.success:
            recommendations.extend([
                "Automatic fix failed",
                "Manual intervention required",
                "Check error messages for specific issues"
            ])
            
            if fix_result.errors:
                recommendations.append("Errors encountered:")
                recommendations.extend([f"  - {error}" for error in fix_result.errors])
        else:
            recommendations.extend([
                "Fix operation incomplete",
                "Manual verification and correction needed"
            ])
        
        return recommendations


class DomainFixingService:
    """High-level service for domain fixing operations."""
    
    def __init__(self, integration_path: str) -> None:
        """Initialize the domain fixing service.
        
        Args:
            integration_path: Path to the integration directory
        """
        self.fixer = DomainFixer(integration_path)
    
    async def run_full_domain_fix(self) -> AutoFixResult:
        """Run complete domain detection and fixing process.
        
        Returns:
            AutoFixResult with complete operation details
        """
        _LOGGER.info("Starting full domain consistency check and fix")
        
        try:
            # Step 1: Detect issues
            detection_result = await self.fixer.detect_domain_mismatch()
            _LOGGER.info("Domain mismatch detection completed: %s", 
                        "mismatch detected" if detection_result.mismatch_detected else "no issues found")
            
            # Step 2: Apply fix if needed
            fix_result = await self.fixer.apply_automatic_fix(detection_result)
            
            # Step 3: Log results
            if fix_result.success:
                _LOGGER.info("Domain fixing completed successfully")
            else:
                _LOGGER.warning("Domain fixing failed or not applicable: %s", fix_result.error_message)
            
            return fix_result
            
        except Exception as e:
            _LOGGER.error("Error during full domain fix: %s", e)
            return AutoFixResult(
                success=False,
                detection_result=DomainMismatchDetection(
                    mismatch_detected=True,
                    mismatched_files=[],
                    expected_domain=None,
                    actual_domains={},
                    severity='critical',
                    fix_recommended=False,
                    fix_description="Error during operation"
                ),
                fix_result=None,
                verification_passed=False,
                error_message=f"Unexpected error: {e}",
                recommendations=["Manual intervention required"]
            )
    
    async def get_domain_status_report(self) -> Dict[str, Any]:
        """Get comprehensive domain status report.
        
        Returns:
            Dictionary with domain status information
        """
        try:
            detection_result = await self.fixer.detect_domain_mismatch()
            recommendations = await self.fixer.get_fix_recommendations(detection_result)
            
            return {
                "consistent": not detection_result.mismatch_detected,
                "severity": detection_result.severity,
                "expected_domain": detection_result.expected_domain,
                "actual_domains": detection_result.actual_domains,
                "mismatched_files": detection_result.mismatched_files,
                "fix_recommended": detection_result.fix_recommended,
                "fix_description": detection_result.fix_description,
                "recommendations": recommendations
            }
            
        except Exception as e:
            _LOGGER.error("Error generating domain status report: %s", e)
            return {
                "consistent": False,
                "severity": "critical",
                "error": str(e),
                "recommendations": ["Manual verification required"]
            }