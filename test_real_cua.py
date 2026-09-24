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

from body.driver import CuaBody
from models import Action, ActionType


async def test_cua_driver():
    """Test Cua Driver with real applications."""
    print("Testing Cua Driver integration...")
    
    try:
        # Initialize Cua Driver
        print("\n1. Initializing Cua Driver...")
        body = CuaBody()
        await body.initialize()
        print("✓ Cua Driver initialized")
        
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
        
        # Test with Calculator if available
        print("\n5. Checking for Calculator...")
        calc_app = None
        for app in apps:
            if 'calculator' in app['name'].lower():
                calc_app = app
                break
        
        if calc_app:
            print(f"✓ Calculator found: {calc_app['name']}")
        else:
            print("  Calculator not running. Please open Calculator.app to test interactions.")
        
        print("\n✅ Cua Driver integration test passed!")
        print(f"\nNext steps:")
        print(f"1. Open Calculator.app")
        print(f"2. Run: source .venv/bin/activate && python test_real_cua.py")
        print(f"3. The script will show real UI elements from Calculator")
        
    except Exception as e:
        print(f"\n✗ Cua Driver test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            await body.shutdown()
            print("\n✓ Cua Driver shut down")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_cua_driver())