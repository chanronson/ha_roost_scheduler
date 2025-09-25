#!/usr/bin/env python3
"""
Script to fix invalid buffer configuration in Roost Scheduler.
Run this script to reset buffer configuration to safe defaults.
"""

import json
import os
from pathlib import Path

def fix_buffer_config():
    """Fix buffer configuration by resetting to defaults."""
    
    # Default safe values
    default_config = {
        "time_minutes": 15,  # 15 minutes (safe default)
        "value_delta": 2.0,  # 2 degrees (safe default)
        "enabled": True,
        "apply_to": "climate"
    }
    
    print("Roost Scheduler Buffer Configuration Fix")
    print("=" * 40)
    
    # Look for Home Assistant configuration directory
    ha_config_paths = [
        "/config",  # Docker/HAOS
        os.path.expanduser("~/.homeassistant"),  # Manual install
        os.path.expanduser("~/homeassistant"),  # Alternative
        "."  # Current directory
    ]
    
    ha_config_dir = None
    for path in ha_config_paths:
        if os.path.exists(os.path.join(path, "configuration.yaml")):
            ha_config_dir = path
            break
    
    if not ha_config_dir:
        print("❌ Could not find Home Assistant configuration directory")
        print("Please run this script from your Home Assistant config directory")
        return False
    
    print(f"✅ Found Home Assistant config at: {ha_config_dir}")
    
    # Look for storage files
    storage_dir = os.path.join(ha_config_dir, ".storage")
    if not os.path.exists(storage_dir):
        print("❌ Storage directory not found")
        return False
    
    # Find roost scheduler storage file
    roost_files = []
    for file in os.listdir(storage_dir):
        if "roost_scheduler" in file.lower():
            roost_files.append(file)
    
    if not roost_files:
        print("ℹ️  No Roost Scheduler storage files found")
        print("The integration may need to be reconfigured from scratch")
        return True
    
    print(f"📁 Found Roost Scheduler files: {roost_files}")
    
    # Backup and fix each file
    for filename in roost_files:
        filepath = os.path.join(storage_dir, filename)
        backup_path = f"{filepath}.backup"
        
        try:
            # Create backup
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"💾 Created backup: {backup_path}")
            
            # Fix buffer configuration
            fixed = False
            
            # Check for buffer_config in data
            if "data" in data and isinstance(data["data"], dict):
                if "buffer_config" in data["data"]:
                    old_config = data["data"]["buffer_config"]
                    print(f"🔧 Found buffer config: {old_config}")
                    
                    # Replace with safe defaults
                    data["data"]["buffer_config"] = default_config
                    fixed = True
                
                # Also check for global buffer settings
                for key in ["global_buffer", "buffer_settings"]:
                    if key in data["data"]:
                        old_config = data["data"][key]
                        print(f"🔧 Found {key}: {old_config}")
                        data["data"][key] = default_config
                        fixed = True
            
            if fixed:
                # Write fixed configuration
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)
                
                print(f"✅ Fixed buffer configuration in {filename}")
            else:
                print(f"ℹ️  No buffer configuration found in {filename}")
                
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
            # Restore backup if it exists
            if os.path.exists(backup_path):
                os.rename(backup_path, filepath)
                print(f"🔄 Restored backup for {filename}")
    
    print("\n" + "=" * 40)
    print("✅ Buffer configuration fix completed!")
    print("\nNext steps:")
    print("1. Restart Home Assistant")
    print("2. Go to Settings → Devices & Services")
    print("3. Configure Roost Scheduler with valid buffer settings:")
    print(f"   - Buffer Time: {default_config['time_minutes']} minutes (0-1440)")
    print(f"   - Buffer Delta: {default_config['value_delta']} degrees (0.1-10.0)")
    print("4. If issues persist, remove and re-add the integration")
    
    return True

if __name__ == "__main__":
    fix_buffer_config()