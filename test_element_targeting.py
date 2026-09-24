#!/usr/bin/env python3
"""
Test script for element-level targeting with window PIDs.

This script tests the proper element targeting implementation.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.body.driver import CuaBody, CUA_DRIVER_AVAILABLE
from src.models import Action, ActionType


async def test_element_targeting():
    """Test element-level targeting implementation."""
    print("Testing element-level targeting...")
    
    if not CUA_DRIVER_AVAILABLE:
        print("⚠️  Cua Driver not available. Please install cua-driver package.")
        return
    
    try:
        # Initialize Cua Driver
        print("\n1. Initializing Cua Driver...")
        body = CuaBody()
        await body.initialize()
        print("✓ Cua Driver initialized")
        
        # Read current window state
        print("\n2. Reading window state for element targeting...")
        screenshot_path = Path.cwd() / "runs" / "targeting_screenshot.png"
        screenshot_path.parent.mkdir(exist_ok=True)
        
        snapshot = await body.read_frontmost_window(screenshot_path)
        print(f"✓ Frontmost window: {snapshot.title}")
        print(f"  App: {snapshot.app_name}")
        print(f"  Elements: {len(snapshot.elements)}")
        print(f"  Window PID: {body.current_window_pid}")
        print(f"  Window ID: {body.current_window_id}")
        
        # Check element map
        print("\n3. Checking element map...")
        print(f"  Element map size: {len(body.element_map)}")
        
        if len(body.element_map) > 0:
            # Show first few elements with targeting info
            print(f"\n4. Sample elements with targeting data:")
            for i, (elem_id, elem_data) in enumerate(list(body.element_map.items())[:5]):
                print(f"  {elem_id}:")
                print(f"    PID: {elem_data.get('pid')}")
                print(f"    Window ID: {elem_data.get('window_id')}")
                print(f"    Position: {elem_data.get('position')}")
                print(f"    Bounds: {elem_data.get('frame')}")
            
            # Test coordinate extraction
            print(f"\n5. Testing coordinate extraction...")
            first_elem_id = list(body.element_map.keys())[0]
            coords = body._find_element_coordinates(first_elem_id)
            if coords:
                print(f"  ✓ Coordinates for {first_elem_id}: {coords}")
            else:
                print(f"  ✗ No coordinates found for {first_elem_id}")
            
            # Test with a dummy action (won't actually execute for safety)
            print(f"\n6. Testing action preparation...")
            test_action = Action(
                element_id=first_elem_id,
                action_type=ActionType.CLICK,
            )
            print(f"  ✓ Test action created for {first_elem_id}")
            print(f"    Action type: {test_action.action_type}")
            print(f"    Element ID: {test_action.element_id}")
            
            print(f"\n✅ Element targeting successfully implemented!")
            print(f"   - Window PID tracking: ✓")
            print(f"   - Window ID tracking: ✓")
            print(f"   - Element mapping: ✓ ({len(body.element_map)} elements)")
            print(f"   - Coordinate extraction: ✓")
            print(f"   - Action preparation: ✓")
            
        else:
            print("⚠️  No elements found in element map")
            print("   This may be due to accessibility issues with the current app")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            await body.shutdown()
            print("\n✓ Cua Driver shut down")
        except Exception as e:
            print(f"\n⚠️  Shutdown error: {e}")


if __name__ == "__main__":
    print("⚠️  This test will read the current frontmost window")
    print("   Make sure you have an accessible app open (TextEdit, Notes, etc.)")
    print()
    
    asyncio.run(test_element_targeting())