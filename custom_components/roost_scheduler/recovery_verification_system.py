"""Recovery Verification System for Roost Scheduler integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .startup_validation_system import StartupValidationSystem, ComprehensiveResult
from .comprehensive_validator import ComprehensiveValidator, ComprehensiveValidationResult
from .comprehensive_error_recovery import RecoveryResult

_LOGGER = logging.getLogger(__name__)


@dataclass
class VerificationTest:
    """Represents a single verification test."""
    test_id: str
    name: str
    description: str
    category: str
    priority: int  # Higher number = higher priority
    success: bool
    duration_seconds: float
    details: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


@dataclass
class VerificationResult:
    """Result of recovery verification."""
    success: bool
    overall_status: str  # "verified", "partial", "failed"
    tests_run: int
    tests_passed: int
    tests_failed: int
    verification_tests: List[VerificationTest]
    improvement_metrics: Dict[str, Any]
    recommendations: List[str]
    duration_seconds: float


class RecoveryVerificationSystem:
    """System for verifying the effectiveness of error recovery."""

    def __init__(self, hass: HomeAssistant, domain: str = DOMAIN) -> None:
        """Initialize the recovery verification system."""
        self.hass = hass
        self.domain = domain
        
        # Initialize validation components
        self._startup_validator = StartupValidationSystem(hass)
        self._comprehensive_validator = ComprehensiveValidator(hass)
        
        # Define verification tests
        self._verification_tests = self._initialize_verification_tests()

    def _initialize_verification_tests(self) -> Dict[str, Dict[str, Any]]:
        """Initialize the verification test definitions."""
        return {
            "domain_consistency_verification": {
                "name": "Domain Consistency Verification",
                "description": "Verify that domain is consistent across all files",
                "category": "domain_consistency",
                "priority": 10,
                "test_method": self._verify_domain_consistency
            },
            "config_flow_registration_verification": {
                "name": "Config Flow Registration Verification",
                "description": "Verify that config flow can be properly registered",
                "category": "config_flow_registration",
                "priority": 9,
                "test_method": self._verify_config_flow_registration
            },
            "manifest_validation_verification": {
                "name": "Manifest Validation Verification",
                "description": "Verify that manifest.json is valid and complete",
                "category": "manifest_validation",
                "priority": 8,
                "test_method": self._verify_manifest_validation
            },
            "dependency_resolution_verification": {
                "name": "Dependency Resolution Verification",
                "description": "Verify that all dependencies can be resolved",
                "category": "dependency_resolution",
                "priority": 7,
                "test_method": self._verify_dependency_resolution
            },
            "file_system_verification": {
                "name": "File System Verification",
                "description": "Verify that all required files exist and are accessible",
                "category": "file_system",
                "priority": 6,
                "test_method": self._verify_file_system
            },
            "version_compatibility_verification": {
                "name": "Version Compatibility Verification",
                "description": "Verify version compatibility with Home Assistant",
                "category": "version_compatibility",
                "priority": 5,
                "test_method": self._verify_version_compatibility
            },
            "integration_loading_verification": {
                "name": "Integration Loading Verification",
                "description": "Verify that integration can be loaded successfully",
                "category": "integration_loading",
                "priority": 4,
                "test_method": self._verify_integration_loading
            },
            "config_flow_instantiation_verification": {
                "name": "Config Flow Instantiation Verification",
                "description": "Verify that config flow class can be instantiated",
                "category": "config_flow_instantiation",
                "priority": 3,
                "test_method": self._verify_config_flow_instantiation
            },
            "service_registration_verification": {
                "name": "Service Registration Verification",
                "description": "Verify that services can be registered properly",
                "category": "service_registration",
                "priority": 2,
                "test_method": self._verify_service_registration
            },
            "end_to_end_verification": {
                "name": "End-to-End Verification",
                "description": "Verify complete integration functionality",
                "category": "end_to_end",
                "priority": 1,
                "test_method": self._verify_end_to_end
            }
        }

    async def verify_recovery_effectiveness(
        self,
        pre_recovery_validation: ComprehensiveResult,
        pre_recovery_comprehensive: ComprehensiveValidationResult,
        recovery_result: RecoveryResult,
        config_entry: Optional[ConfigEntry] = None
    ) -> VerificationResult:
        """Verify the effectiveness of error recovery.
        
        Args:
            pre_recovery_validation: Validation result before recovery
            pre_recovery_comprehensive: Comprehensive validation result before recovery
            recovery_result: Result of the recovery process
            config_entry: Optional config entry for context
            
        Returns:
            VerificationResult with detailed verification information
        """
        verification_start_time = datetime.now()
        _LOGGER.info("Starting recovery verification for domain: %s", self.domain)
        
        try:
            # Run all verification tests
            verification_tests = []
            tests_passed = 0
            tests_failed = 0
            
            # Sort tests by priority (highest first)
            sorted_tests = sorted(
                self._verification_tests.items(),
                key=lambda x: x[1]["priority"],
                reverse=True
            )
            
            for test_id, test_config in sorted_tests:
                test_start_time = datetime.now()
                
                try:
                    _LOGGER.debug("Running verification test: %s", test_config["name"])
                    
                    # Execute the test method
                    test_method = test_config["test_method"]
                    test_result = await test_method()
                    
                    test_duration = (datetime.now() - test_start_time).total_seconds()
                    
                    verification_test = VerificationTest(
                        test_id=test_id,
                        name=test_config["name"],
                        description=test_config["description"],
                        category=test_config["category"],
                        priority=test_config["priority"],
                        success=test_result["success"],
                        duration_seconds=test_duration,
                        details=test_result.get("details", {}),
                        errors=test_result.get("errors", []),
                        warnings=test_result.get("warnings", [])
                    )
                    
                    verification_tests.append(verification_test)
                    
                    if test_result["success"]:
                        tests_passed += 1
                        _LOGGER.debug("Verification test %s passed", test_config["name"])
                    else:
                        tests_failed += 1
                        _LOGGER.warning("Verification test %s failed: %s", 
                                      test_config["name"], test_result.get("error", "Unknown error"))
                
                except Exception as e:
                    _LOGGER.error("Error running verification test %s: %s", test_config["name"], e)
                    
                    test_duration = (datetime.now() - test_start_time).total_seconds()
                    verification_tests.append(VerificationTest(
                        test_id=test_id,
                        name=test_config["name"],
                        description=test_config["description"],
                        category=test_config["category"],
                        priority=test_config["priority"],
                        success=False,
                        duration_seconds=test_duration,
                        details={},
                        errors=[f"Test execution error: {str(e)}"],
                        warnings=[]
                    ))
                    tests_failed += 1
            
            # Calculate improvement metrics
            improvement_metrics = await self._calculate_improvement_metrics(
                pre_recovery_validation, pre_recovery_comprehensive, recovery_result
            )
            
            # Determine overall verification status
            overall_status, success = self._determine_verification_status(
                tests_passed, tests_failed, improvement_metrics
            )
            
            # Generate recommendations
            recommendations = self._generate_verification_recommendations(
                verification_tests, improvement_metrics, recovery_result
            )
            
            verification_duration = (datetime.now() - verification_start_time).total_seconds()
            
            result = VerificationResult(
                success=success,
                overall_status=overall_status,
                tests_run=len(verification_tests),
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                verification_tests=verification_tests,
                improvement_metrics=improvement_metrics,
                recommendations=recommendations,
                duration_seconds=verification_duration
            )
            
            _LOGGER.info(
                "Recovery verification completed: %s (%.2fs, %d/%d tests passed)",
                overall_status, verification_duration, tests_passed, len(verification_tests)
            )
            
            return result
            
        except Exception as e:
            _LOGGER.error("Critical error during recovery verification: %s", e)
            
            verification_duration = (datetime.now() - verification_start_time).total_seconds()
            return VerificationResult(
                success=False,
                overall_status="error",
                tests_run=0,
                tests_passed=0,
                tests_failed=0,
                verification_tests=[],
                improvement_metrics={},
                recommendations=[f"Verification system error: {str(e)}"],
                duration_seconds=verification_duration
            )

    async def _verify_domain_consistency(self) -> Dict[str, Any]:
        """Verify domain consistency across all files."""
        try:
            from .domain_consistency_checker import DomainConsistencyChecker
            from pathlib import Path
            
            integration_path = Path(__file__).parent
            checker = DomainConsistencyChecker(str(integration_path))
            
            result = await checker.validate_consistency()
            
            return {
                "success": result.consistent,
                "details": {
                    "manifest_domain": result.manifest_domain,
                    "const_domain": result.const_domain,
                    "config_flow_domain": result.config_flow_domain,
                    "consistent": result.consistent
                },
                "errors": result.issues if not result.consistent else [],
                "warnings": result.warnings
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Domain consistency verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_config_flow_registration(self) -> Dict[str, Any]:
        """Verify config flow registration."""
        try:
            from .config_flow_validator import ConfigFlowValidator
            
            validator = ConfigFlowValidator(self.hass, self.domain)
            result = await validator.validate_config_flow_registration()
            
            return {
                "success": result.success,
                "details": result.diagnostic_data,
                "errors": [str(issue) for issue in result.issues if hasattr(issue, "severity") and issue.severity == "error"],
                "warnings": result.warnings
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Config flow registration verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_manifest_validation(self) -> Dict[str, Any]:
        """Verify manifest validation."""
        try:
            from .manifest_validator import ManifestValidator
            from pathlib import Path
            
            integration_path = Path(__file__).parent
            validator = ManifestValidator(self.hass, integration_path)
            
            result = await validator.validate_manifest()
            
            return {
                "success": result.valid,
                "details": {
                    "manifest_path": str(integration_path / "manifest.json"),
                    "valid": result.valid
                },
                "errors": result.issues,
                "warnings": result.warnings
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Manifest validation verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_dependency_resolution(self) -> Dict[str, Any]:
        """Verify dependency resolution."""
        try:
            from .dependency_validator import DependencyValidator
            from pathlib import Path
            
            integration_path = Path(__file__).parent
            validator = DependencyValidator(self.hass, integration_path)
            
            result = await validator.validate_dependencies()
            
            return {
                "success": result.valid,
                "details": {
                    "dependencies": result.dependencies,
                    "imports": result.imports,
                    "conflicts": result.conflicts
                },
                "errors": result.conflicts,
                "warnings": result.warnings
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Dependency resolution verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_file_system(self) -> Dict[str, Any]:
        """Verify file system integrity."""
        try:
            from .file_system_validator import FileSystemValidator
            from pathlib import Path
            
            integration_path = Path(__file__).parent
            validator = FileSystemValidator(self.hass, integration_path)
            
            result = await validator.validate_file_system()
            
            return {
                "success": result.valid,
                "details": {
                    "file_permissions": result.file_permissions,
                    "required_files_present": result.required_files_present
                },
                "errors": result.errors,
                "warnings": result.warnings
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"File system verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_version_compatibility(self) -> Dict[str, Any]:
        """Verify version compatibility."""
        try:
            from .version_compatibility_validator import VersionCompatibilityValidator
            from pathlib import Path
            
            integration_path = Path(__file__).parent
            validator = VersionCompatibilityValidator(self.hass, integration_path)
            
            result = await validator.validate_version_compatibility()
            
            return {
                "success": result.compatible,
                "details": {
                    "home_assistant": result.home_assistant,
                    "integration": result.integration,
                    "compatibility_level": result.overall_compatibility_level
                },
                "errors": [issue for issue in result.issues if "error" in issue.lower()],
                "warnings": result.warnings
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Version compatibility verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_integration_loading(self) -> Dict[str, Any]:
        """Verify integration loading."""
        try:
            # Check if integration is loaded
            integration_loaded = self.domain in self.hass.config.components
            
            # Check config entries
            config_entries = self.hass.config_entries.async_entries(self.domain)
            
            return {
                "success": integration_loaded,
                "details": {
                    "integration_loaded": integration_loaded,
                    "config_entries_count": len(config_entries),
                    "config_entries": [entry.entry_id for entry in config_entries]
                },
                "errors": [] if integration_loaded else ["Integration not loaded"],
                "warnings": []
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Integration loading verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_config_flow_instantiation(self) -> Dict[str, Any]:
        """Verify config flow instantiation."""
        try:
            # Try to import and instantiate config flow
            from . import config_flow
            
            if hasattr(config_flow, 'RoostSchedulerConfigFlow'):
                flow_class = getattr(config_flow, 'RoostSchedulerConfigFlow')
                
                # Check class attributes
                has_domain = hasattr(flow_class, 'DOMAIN') or hasattr(flow_class, 'domain')
                has_version = hasattr(flow_class, 'VERSION') or hasattr(flow_class, 'version')
                
                return {
                    "success": True,
                    "details": {
                        "config_flow_class_found": True,
                        "has_domain": has_domain,
                        "has_version": has_version,
                        "class_name": flow_class.__name__
                    },
                    "errors": [],
                    "warnings": []
                }
            else:
                return {
                    "success": False,
                    "details": {
                        "config_flow_class_found": False,
                        "available_attributes": dir(config_flow)
                    },
                    "errors": ["Config flow class not found"],
                    "warnings": []
                }
                
        except ImportError as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Config flow import failed: {str(e)}"],
                "warnings": []
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Config flow instantiation verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_service_registration(self) -> Dict[str, Any]:
        """Verify service registration."""
        try:
            # Check if services are registered
            services = self.hass.services.async_services()
            domain_services = services.get(self.domain, {})
            
            expected_services = ["apply_slot", "apply_grid_now", "migrate_resolution"]
            found_services = list(domain_services.keys())
            missing_services = [svc for svc in expected_services if svc not in found_services]
            
            return {
                "success": len(missing_services) == 0,
                "details": {
                    "expected_services": expected_services,
                    "found_services": found_services,
                    "missing_services": missing_services,
                    "total_services": len(found_services)
                },
                "errors": [f"Missing services: {missing_services}"] if missing_services else [],
                "warnings": []
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"Service registration verification failed: {str(e)}"],
                "warnings": []
            }

    async def _verify_end_to_end(self) -> Dict[str, Any]:
        """Verify end-to-end functionality."""
        try:
            # Run a comprehensive validation to ensure everything works together
            validation_result = await self._startup_validator.run_comprehensive_validation(self.domain)
            
            return {
                "success": validation_result.success,
                "details": {
                    "comprehensive_validation_success": validation_result.success,
                    "issues_count": len(validation_result.issues),
                    "warnings_count": len(validation_result.warnings),
                    "domain_consistent": validation_result.domain_consistency_result.consistent,
                    "config_flow_available": validation_result.config_flow_availability_result.success
                },
                "errors": [str(issue) for issue in validation_result.issues[:5]],  # Limit to first 5
                "warnings": validation_result.warnings[:5]  # Limit to first 5
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {},
                "errors": [f"End-to-end verification failed: {str(e)}"],
                "warnings": []
            }

    async def _calculate_improvement_metrics(
        self,
        pre_recovery_validation: ComprehensiveResult,
        pre_recovery_comprehensive: ComprehensiveValidationResult,
        recovery_result: RecoveryResult
    ) -> Dict[str, Any]:
        """Calculate improvement metrics comparing before and after recovery."""
        try:
            # Run post-recovery validation
            post_recovery_validation = await self._startup_validator.run_comprehensive_validation(self.domain)
            post_recovery_comprehensive = await self._comprehensive_validator.validate_all()
            
            # Calculate metrics
            pre_issues = len(pre_recovery_validation.issues)
            post_issues = len(post_recovery_validation.issues)
            issues_resolved = max(0, pre_issues - post_issues)
            
            pre_warnings = len(pre_recovery_validation.warnings)
            post_warnings = len(post_recovery_validation.warnings)
            warnings_resolved = max(0, pre_warnings - post_warnings)
            
            return {
                "issues_before": pre_issues,
                "issues_after": post_issues,
                "issues_resolved": issues_resolved,
                "issues_improvement_percentage": (issues_resolved / pre_issues * 100) if pre_issues > 0 else 100,
                "warnings_before": pre_warnings,
                "warnings_after": post_warnings,
                "warnings_resolved": warnings_resolved,
                "warnings_improvement_percentage": (warnings_resolved / pre_warnings * 100) if pre_warnings > 0 else 100,
                "domain_consistency_improved": (
                    not pre_recovery_validation.domain_consistency_result.consistent and
                    post_recovery_validation.domain_consistency_result.consistent
                ),
                "config_flow_availability_improved": (
                    not pre_recovery_validation.config_flow_availability_result.success and
                    post_recovery_validation.config_flow_availability_result.success
                ),
                "manifest_validation_improved": (
                    not pre_recovery_comprehensive.manifest_result.valid and
                    post_recovery_comprehensive.manifest_result.valid
                ),
                "dependency_validation_improved": (
                    not pre_recovery_comprehensive.dependency_result.valid and
                    post_recovery_comprehensive.dependency_result.valid
                ),
                "overall_validation_improved": (
                    not pre_recovery_validation.success and
                    post_recovery_validation.success
                ),
                "recovery_duration": recovery_result.duration_seconds,
                "recovery_success_rate": (recovery_result.recovered_issues / recovery_result.total_issues * 100) if recovery_result.total_issues > 0 else 100
            }
            
        except Exception as e:
            _LOGGER.error("Error calculating improvement metrics: %s", e)
            return {
                "calculation_error": str(e),
                "issues_before": len(pre_recovery_validation.issues),
                "issues_after": "unknown",
                "recovery_duration": recovery_result.duration_seconds
            }

    def _determine_verification_status(
        self,
        tests_passed: int,
        tests_failed: int,
        improvement_metrics: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """Determine the overall verification status."""
        total_tests = tests_passed + tests_failed
        
        if total_tests == 0:
            return "no_tests", False
        
        pass_percentage = (tests_passed / total_tests) * 100
        
        # Check for significant improvements
        significant_improvement = (
            improvement_metrics.get("issues_improvement_percentage", 0) > 50 or
            improvement_metrics.get("overall_validation_improved", False) or
            improvement_metrics.get("domain_consistency_improved", False) or
            improvement_metrics.get("config_flow_availability_improved", False)
        )
        
        if pass_percentage >= 90 and significant_improvement:
            return "verified", True
        elif pass_percentage >= 70 or significant_improvement:
            return "partial", True
        elif pass_percentage >= 50:
            return "limited", True
        else:
            return "failed", False

    def _generate_verification_recommendations(
        self,
        verification_tests: List[VerificationTest],
        improvement_metrics: Dict[str, Any],
        recovery_result: RecoveryResult
    ) -> List[str]:
        """Generate recommendations based on verification results."""
        recommendations = []
        
        # Analyze test results
        failed_tests = [test for test in verification_tests if not test.success]
        critical_failures = [test for test in failed_tests if test.priority >= 8]
        
        if not failed_tests:
            recommendations.append("All verification tests passed - recovery was successful")
        elif critical_failures:
            recommendations.append("Critical verification tests failed - manual intervention required")
            for test in critical_failures:
                recommendations.append(f"Address {test.name}: {test.description}")
        else:
            recommendations.append("Some verification tests failed but no critical issues detected")
        
        # Analyze improvement metrics
        issues_improvement = improvement_metrics.get("issues_improvement_percentage", 0)
        if issues_improvement >= 80:
            recommendations.append("Excellent issue resolution rate - monitor for stability")
        elif issues_improvement >= 50:
            recommendations.append("Good issue resolution rate - some issues may remain")
        elif issues_improvement > 0:
            recommendations.append("Limited issue resolution - consider additional recovery attempts")
        else:
            recommendations.append("No measurable improvement - manual troubleshooting recommended")
        
        # Recovery-specific recommendations
        if recovery_result.emergency_mode:
            recommendations.append("Integration is in emergency mode - functionality may be limited")
        
        if len(recovery_result.fallbacks_applied) > 2:
            recommendations.append("Multiple fallbacks were applied - monitor for unexpected behavior")
        
        return recommendations