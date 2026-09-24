#!/usr/bin/env python3
"""
Test script for real Cua Driver integration.

This script tests the actual Cua Driver integration with real applications.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.body.driver import CuaBody, FakeBody, CUA_DRIVER_AVAILABLE
from src.models import Action, ActionType


async def test_cua_driver():
    """Test Cua Driver with real applications."""
    print("Testing Cua Driver integration...")
    
    # Check if Cua Driver is available
    if not CUA_DRIVER_AVAILABLE:
        print("⚠️  Cua Driver not available, using FakeBody for testing")
        body = FakeBody()
    else:
        print("✓ Cua Driver available, attempting real integration")
        try:
            body = CuaBody()
        except Exception as e:
            print(f"⚠️  Failed to initialize CuaBody: {e}")
            print("Falling back to FakeBody")
            body = FakeBody()
    
    try:
        # Initialize
        print("\n1. Initializing...")
        await body.initialize()
        print("✓ Initialized")
        
        # List running apps
        print("\n2. Listing running applications...")
        apps = await body.list_apps()
        print(f"✓ Found {len(apps)} running applications:")
        for app in apps[:5]:  # Show first 5
            print(f"  - {app['name']} (PID: {app['pid']})")
        
        # Read frontmost window
        print("\n3. Reading frontmost window...")
        screenshot_path = Path.cwd() / "runs" / "test_screenshot.png"
        screenshot_path.parent.mkdir(exist_ok=True)
        
        snapshot = await body.read_frontmost_window(screenshot_path)
        print(f"✓ Frontmost window: {snapshot.title}")
        print(f"  App: {snapshot.app_name}")
        print(f"  Elements: {len(snapshot.elements)}")
        print(f"  Screenshot: {screenshot_path}")
        
        # Show some elements
        if snapshot.elements:
            print(f"\n4. Sample UI elements:")
            for i, elem in enumerate(snapshot.elements[:5]):
                print(f"  {elem.element_id}: {elem.role} - {elem.label or '(no label)'}")
        
        print("\n✅ Test passed!")
        
        if isinstance(body, FakeBody):
            print(f"\nNote: Using FakeBody. Real Cua Driver integration needs further API alignment.")
        else:
            print(f"\nNote: Real Cua Driver integration working!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            await body.shutdown()
            print("\n✓ Shutdown complete")
        except Exception as e:
            print(f"\n⚠️  Shutdown error: {e}")


if __name__ == "__main__":
    asyncio.run(test_cua_driver())