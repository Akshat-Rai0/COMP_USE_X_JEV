#!/usr/bin/env python3
"""
Test script for real Calculator automation using Cua Driver.

This script tests the actual Cua Driver integration with the Calculator app.
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
from src.orchestrator.loop import run_task, LoopConfig


async def test_calculator():
    """Test automation with real Calculator app."""
    print("Testing Calculator automation with Cua Driver...")
    
    if not CUA_DRIVER_AVAILABLE:
        print("⚠️  Cua Driver not available. Please install cua-driver package.")
        return
    
    try:
        # Initialize Cua Driver
        print("\n1. Initializing Cua Driver...")
        body = CuaBody()
        await body.initialize()
        print("✓ Cua Driver initialized")
        
        # List running apps to check for Calculator
        print("\n2. Checking for Calculator...")
        apps = await body.list_apps()
        calc_app = None
        for app in apps:
            if 'calculator' in app['name'].lower():
                calc_app = app
                break
        
        if calc_app:
            print(f"✓ Calculator found: {calc_app['name']}")
        else:
            print("⚠️  Calculator not running. Please open Calculator.app first.")
            print("   You can open it with: open -a Calculator")
            return
        
        # Read current Calculator state
        print("\n3. Reading Calculator state...")
        screenshot_path = Path.cwd() / "runs" / "calculator_screenshot.png"
        screenshot_path.parent.mkdir(exist_ok=True)
        
        snapshot = await body.read_frontmost_window(screenshot_path)
        print(f"✓ Frontmost window: {snapshot.title}")
        print(f"  App: {snapshot.app_name}")
        print(f"  Elements: {len(snapshot.elements)}")
        print(f"  Screenshot: {screenshot_path}")
        
        # Show some elements
        if snapshot.elements:
            print(f"\n4. Sample UI elements:")
            for i, elem in enumerate(snapshot.elements[:10]):
                print(f"  {elem.element_id}: {elem.role} - {elem.label or '(no label)'}")
        
        # Run a simple calculation task
        print("\n5. Running calculation task (6 × 7)...")
        print("Note: UI tree parsing is still in development.")
        print("For now, we'll demonstrate the basic Cua Driver integration.")
        
        # Skip the full automation for now since UI tree parsing needs development
        print("\n✅ Cua Driver integration successful!")
        print("   - Cua Driver connected and working")
        print("   - Calculator app detected")
        print("   - Desktop state captured")
        print("   - Screenshot saved")
        print("\nNext steps:")
        print("   - Implement proper UI tree parsing from Cua Driver responses")
        print("   - Add element targeting with proper window PID")
        print("   - Test actual click/type actions")
        
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
    print("⚠️  Make sure Calculator.app is open before running this test!")
    print("   You can open it with: open -a Calculator")
    print()
    
    # Run directly without prompt for automation
    asyncio.run(test_calculator())