"""Domain consistency checker for Roost Scheduler integration."""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class ConsistencyResult:
    """Result of domain consistency validation."""
    
    consistent: bool
    manifest_domain: Optional[str]
    const_domain: Optional[str]
    config_flow_domain: Optional[str]
    issues: List[str]
    warnings: List[str]
    recommendations: List[str]


@dataclass
class FixResult:
    """Result of domain consistency fixing."""
    
    success: bool
    fixes_applied: List[str]
    errors: List[str]
    warnings: List[str]
    backup_created: bool


class DomainConsistencyChecker:
    """Checks and fixes domain consistency across integration files."""
    
    def __init__(self, integration_path: str) -> None:
        """Initialize the domain consistency checker.
        
        Args:
            integration_path: Path to the integration directory
        """
        self.integration_path = Path(integration_path)
        self._manifest_path = self.integration_path / "manifest.json"
        self._const_path = self.integration_path / "const.py"
        self._config_flow_path = self.integration_path / "config_flow.py"
        
    async def check_manifest_domain(self) -> Optional[str]:
        """Extract domain from manifest.json.
        
        Returns:
            Domain from manifest.json or None if not found/invalid
        """
        try:
            if not self._manifest_path.exists():
                _LOGGER.warning("manifest.json not found at %s", self._manifest_path)
                return None
                
            with open(self._manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = json.load(f)
                
            domain = manifest_data.get("domain")
            if not domain:
                _LOGGER.warning("No domain field found in manifest.json")
                return None
                
            if not isinstance(domain, str) or not domain.strip():
                _LOGGER.warning("Invalid domain in manifest.json: %s", domain)
                return None
                
            return domain.strip()
            
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse manifest.json: %s", e)
            return None
        except Exception as e:
            _LOGGER.error("Error reading manifest.json: %s", e)
            return None
    
    async def check_const_domain(self) -> Optional[str]:
        """Extract domain from const.py.
        
        Returns:
            Domain from const.py DOMAIN constant or None if not found
        """
        try:
            if not self._const_path.exists():
                _LOGGER.warning("const.py not found at %s", self._const_path)
                return None
                
            with open(self._const_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for DOMAIN = "value" pattern
            domain_patterns = [
                r'^DOMAIN\s*=\s*["\']([^"\']+)["\']',  # DOMAIN = "value"
                r'^DOMAIN\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)',  # DOMAIN = variable
            ]
            
            for pattern in domain_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                if matches:
                    domain = matches[0].strip()
                    if domain:
                        return domain
            
            _LOGGER.warning("No DOMAIN constant found in const.py")
            return None
            
        except Exception as e:
            _LOGGER.error("Error reading const.py: %s", e)
            return None
    
    async def check_config_flow_domain(self) -> Optional[str]:
        """Extract domain from config_flow.py.
        
        Returns:
            Domain from config flow class or None if not found
        """
        try:
            if not self._config_flow_path.exists():
                _LOGGER.warning("config_flow.py not found at %s", self._config_flow_path)
                return None
                
            with open(self._config_flow_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for class with domain=DOMAIN pattern
            patterns = [
                r'class\s+\w+\s*\([^)]*domain\s*=\s*["\']([^"\']+)["\'][^)]*\)',  # domain="value"
                r'domain\s*=\s*["\']([^"\']+)["\']',  # domain = "value"
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
                if matches:
                    if isinstance(matches[0], str) and matches[0]:
                        return matches[0].strip()
            
            # Also check for imports from .const import DOMAIN and class definition with domain=DOMAIN
            if 'from .const import' in content and 'DOMAIN' in content:
                # Look for class definition with domain=DOMAIN
                domain_class_pattern = r'class\s+\w+\s*\([^)]*domain\s*=\s*DOMAIN[^)]*\)'
                if re.search(domain_class_pattern, content, re.MULTILINE | re.DOTALL):
                    const_domain = await self.check_const_domain()
                    if const_domain:
                        return const_domain
            
            _LOGGER.warning("No domain configuration found in config_flow.py")
            return None
            
        except Exception as e:
            _LOGGER.error("Error reading config_flow.py: %s", e)
            return None
    
    async def validate_consistency(self) -> ConsistencyResult:
        """Validate domain consistency across all files.
        
        Returns:
            ConsistencyResult with validation details
        """
        issues = []
        warnings = []
        recommendations = []
        
        # Extract domains from all files
        manifest_domain = await self.check_manifest_domain()
        const_domain = await self.check_const_domain()
        config_flow_domain = await self.check_config_flow_domain()
        
        # Check if any domains were found
        domains_found = [d for d in [manifest_domain, const_domain, config_flow_domain] if d is not None]
        
        if not domains_found:
            issues.append("No domain configuration found in any file")
            return ConsistencyResult(
                consistent=False,
                manifest_domain=manifest_domain,
                const_domain=const_domain,
                config_flow_domain=config_flow_domain,
                issues=issues,
                warnings=warnings,
                recommendations=["Ensure domain is properly configured in manifest.json and const.py"]
            )
        
        # Check for missing domains
        if manifest_domain is None:
            issues.append("Domain not found in manifest.json")
        if const_domain is None:
            issues.append("DOMAIN constant not found in const.py")
        if config_flow_domain is None:
            warnings.append("Domain configuration not clearly found in config_flow.py")
        
        # Check consistency between found domains
        unique_domains = set(domains_found)
        
        if len(unique_domains) > 1:
            issues.append(f"Domain mismatch detected: {dict(zip(['manifest', 'const', 'config_flow'], [manifest_domain, const_domain, config_flow_domain]))}")
            recommendations.append("Ensure all files use the same domain identifier")
        
        # Validate domain format
        for domain_name, domain_value in [
            ("manifest", manifest_domain),
            ("const", const_domain),
            ("config_flow", config_flow_domain)
        ]:
            if domain_value and not self._is_valid_domain_format(domain_value):
                issues.append(f"Invalid domain format in {domain_name}: {domain_value}")
                recommendations.append("Domain should contain only lowercase letters, numbers, and underscores")
        
        # Check for common issues
        if manifest_domain and const_domain and manifest_domain != const_domain:
            issues.append(f"Manifest domain '{manifest_domain}' does not match const domain '{const_domain}'")
        
        consistent = len(issues) == 0 and len(unique_domains) <= 1
        
        if consistent and len(warnings) == 0:
            recommendations.append("Domain configuration is consistent across all files")
        
        return ConsistencyResult(
            consistent=consistent,
            manifest_domain=manifest_domain,
            const_domain=const_domain,
            config_flow_domain=config_flow_domain,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations
        )
    
    async def fix_inconsistencies(self) -> FixResult:
        """Automatically fix domain inconsistencies.
        
        Returns:
            FixResult with details of fixes applied
        """
        fixes_applied = []
        errors = []
        warnings = []
        backup_created = False
        
        try:
            # First validate current state
            consistency_result = await self.validate_consistency()
            
            if consistency_result.consistent:
                return FixResult(
                    success=True,
                    fixes_applied=["No fixes needed - domain is already consistent"],
                    errors=[],
                    warnings=[],
                    backup_created=False
                )
            
            # Create backup before making changes
            try:
                await self._create_backup()
                backup_created = True
                fixes_applied.append("Created backup of original files")
            except Exception as e:
                warnings.append(f"Could not create backup: {e}")
            
            # Determine the correct domain to use
            correct_domain = self._determine_correct_domain(consistency_result)
            
            if not correct_domain:
                errors.append("Could not determine correct domain to use for fixing")
                return FixResult(
                    success=False,
                    fixes_applied=fixes_applied,
                    errors=errors,
                    warnings=warnings,
                    backup_created=backup_created
                )
            
            # Fix manifest.json if needed
            if consistency_result.manifest_domain != correct_domain:
                try:
                    await self._fix_manifest_domain(correct_domain)
                    fixes_applied.append(f"Updated manifest.json domain to '{correct_domain}'")
                except Exception as e:
                    errors.append(f"Failed to fix manifest.json: {e}")
            
            # Fix const.py if needed
            if consistency_result.const_domain != correct_domain:
                try:
                    await self._fix_const_domain(correct_domain)
                    fixes_applied.append(f"Updated const.py DOMAIN to '{correct_domain}'")
                except Exception as e:
                    errors.append(f"Failed to fix const.py: {e}")
            
            # Verify fixes
            verification_result = await self.validate_consistency()
            success = verification_result.consistent and len(errors) == 0
            
            if success:
                fixes_applied.append("Domain consistency successfully restored")
            else:
                errors.append("Some fixes failed - manual intervention may be required")
            
            return FixResult(
                success=success,
                fixes_applied=fixes_applied,
                errors=errors,
                warnings=warnings,
                backup_created=backup_created
            )
            
        except Exception as e:
            errors.append(f"Unexpected error during fixing: {e}")
            return FixResult(
                success=False,
                fixes_applied=fixes_applied,
                errors=errors,
                warnings=warnings,
                backup_created=backup_created
            )
    
    def _is_valid_domain_format(self, domain: str) -> bool:
        """Check if domain follows valid format.
        
        Args:
            domain: Domain string to validate
            
        Returns:
            True if domain format is valid
        """
        if not domain or not isinstance(domain, str):
            return False
        
        # Domain should be lowercase, contain only letters, numbers, and underscores
        # Should not start with number or underscore
        pattern = r'^[a-z][a-z0-9_]*$'
        return bool(re.match(pattern, domain))
    
    def _determine_correct_domain(self, consistency_result: ConsistencyResult) -> Optional[str]:
        """Determine the correct domain to use for fixing.
        
        Args:
            consistency_result: Current consistency validation result
            
        Returns:
            The domain that should be used, or None if cannot determine
        """
        # Priority: manifest.json > const.py > config_flow.py
        domains = [
            consistency_result.manifest_domain,
            consistency_result.const_domain,
            consistency_result.config_flow_domain
        ]
        
        # Use the first valid domain found
        for domain in domains:
            if domain and self._is_valid_domain_format(domain):
                return domain
        
        # If no valid domain found, use the first non-None domain
        for domain in domains:
            if domain:
                return domain
        
        return None
    
    async def _create_backup(self) -> None:
        """Create backup of files before modification."""
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.integration_path / f"backup_{timestamp}"
        backup_dir.mkdir(exist_ok=True)
        
        files_to_backup = [
            self._manifest_path,
            self._const_path,
            self._config_flow_path
        ]
        
        for file_path in files_to_backup:
            if file_path.exists():
                backup_path = backup_dir / file_path.name
                shutil.copy2(file_path, backup_path)
                _LOGGER.info("Created backup: %s", backup_path)
    
    async def _fix_manifest_domain(self, correct_domain: str) -> None:
        """Fix domain in manifest.json.
        
        Args:
            correct_domain: The correct domain to set
        """
        if not self._manifest_path.exists():
            raise FileNotFoundError(f"manifest.json not found at {self._manifest_path}")
        
        with open(self._manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        
        manifest_data["domain"] = correct_domain
        
        with open(self._manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
        
        _LOGGER.info("Updated manifest.json domain to '%s'", correct_domain)
    
    async def _fix_const_domain(self, correct_domain: str) -> None:
        """Fix DOMAIN constant in const.py.
        
        Args:
            correct_domain: The correct domain to set
        """
        if not self._const_path.exists():
            raise FileNotFoundError(f"const.py not found at {self._const_path}")
        
        with open(self._const_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace DOMAIN constant
        patterns = [
            (r'^DOMAIN\s*=\s*["\'][^"\']*["\']', f'DOMAIN = "{correct_domain}"'),
            (r'^DOMAIN\s*=\s*[^"\'\n]+', f'DOMAIN = "{correct_domain}"'),
        ]
        
        updated = False
        for pattern, replacement in patterns:
            new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            if new_content != content:
                content = new_content
                updated = True
                break
        
        if not updated:
            # If no existing DOMAIN found, add it at the top after imports
            lines = content.split('\n')
            insert_index = 0
            
            # Find a good place to insert (after imports and docstring)
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('"""') and not line.startswith('from') and not line.startswith('import'):
                    insert_index = i
                    break
            
            lines.insert(insert_index, f'DOMAIN = "{correct_domain}"')
            content = '\n'.join(lines)
        
        with open(self._const_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        _LOGGER.info("Updated const.py DOMAIN to '%s'", correct_domain)