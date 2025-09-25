#!/usr/bin/env python3
"""
Quick test to verify the buffer configuration fix works.
"""

import sys
import os

# Add the custom_components directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

from roost_scheduler.config_flow import RoostSchedulerConfigFlow

async def test_buffer_validation_fix():
    """Test that the buffer validation fix works correctly."""
    
    # Create a mock config flow instance
    config_flow = RoostSchedulerConfigFlow()
    
    print("Testing buffer validation fix...")
    
    # Test 1: Integer value (should work)
    errors = await config_flow._validate_buffer_settings(True, 15, 2.0)
    assert not errors, f"Integer value failed: {errors}"
    print("✅ Integer value (15) - PASS")
    
    # Test 2: Float value that's a whole number (should work after fix)
    errors = await config_flow._validate_buffer_settings(True, 15.0, 2.0)
    assert not errors, f"Whole number float failed: {errors}"
    print("✅ Whole number float (15.0) - PASS")
    
    # Test 3: Float value that's not a whole number (should fail)
    errors = await config_flow._validate_buffer_settings(True, 15.5, 2.0)
    assert "buffer_time_minutes" in errors, f"Non-whole float should fail: {errors}"
    print("✅ Non-whole float (15.5) - FAIL (as expected)")
    
    # Test 4: Negative value (should fail)
    errors = await config_flow._validate_buffer_settings(True, -1, 2.0)
    assert "buffer_time_minutes" in errors, f"Negative value should fail: {errors}"
    print("✅ Negative value (-1) - FAIL (as expected)")
    
    # Test 5: Value too large (should fail)
    errors = await config_flow._validate_buffer_settings(True, 1441, 2.0)
    assert "buffer_time_minutes" in errors, f"Too large value should fail: {errors}"
    print("✅ Too large value (1441) - FAIL (as expected)")
    
    # Test 6: String value (should fail)
    errors = await config_flow._validate_buffer_settings(True, "15", 2.0)
    assert "buffer_time_minutes" in errors, f"String value should fail: {errors}"
    print("✅ String value ('15') - FAIL (as expected)")
    
    print("\n🎉 All tests passed! The buffer validation fix is working correctly.")
    print("\nThe fix handles:")
    print("- Integer values (15) ✅")
    print("- Whole number floats (15.0) ✅ (converts to int)")
    print("- Non-whole floats (15.5) ❌ (rejects)")
    print("- Invalid ranges ❌ (rejects)")
    print("- Invalid types ❌ (rejects)")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_buffer_validation_fix())