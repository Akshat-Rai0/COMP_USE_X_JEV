#!/usr/bin/env python3
"""
Debug script to examine Cua Driver window state with accessibility tree.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cua_driver import CuaDriver, GetWindowStateInput


async def debug_cua_window_state():
    """Debug Cua Driver window state with accessibility tree."""
    print("Debugging Cua Driver window state...")
    
    try:
        # Initialize Cua Driver
        print("\n1. Initializing Cua Driver...")
        driver = CuaDriver.create()
        print("✓ Cua Driver initialized")
        
        # First get list of windows to find Calculator
        print("\n2. Getting window list...")
        from cua_driver import ListWindowsInput
        windows_result = await driver.list_windows(ListWindowsInput(pid=None, on_screen_only=True))
        
        # Find Calculator window
        calc_window = None
        for window in windows_result.windows:
            if 'calculator' in window.app_name.lower():
                calc_window = window
                break
        
        if calc_window:
            print(f"✓ Found Calculator: {calc_window.app_name} (PID: {calc_window.pid}, Window ID: {calc_window.window_id})")
        else:
            print("⚠️  Calculator not found, using first window")
            calc_window = windows_result.windows[0]
            print(f"   Using: {calc_window.app_name} (PID: {calc_window.pid}, Window ID: {calc_window.window_id})")
        
        # Get window state with accessibility tree
        print("\n3. Getting window state with accessibility tree...")
        screenshot_path = Path.cwd() / "runs" / "window_debug_screenshot.png"
        screenshot_path.parent.mkdir(exist_ok=True)
        result = await driver.get_window_state(
            GetWindowStateInput(
                pid=calc_window.pid,
                window_id=calc_window.window_id,
                session="debug-session",
                query=None,
                include_accessibility_tree=True,
                include_screenshot=True,
                screenshot_out_file=str(screenshot_path),
                max_elements=100,
                max_depth=10,
                max_dimension=1000
            )
        )
        
        print(f"✓ Window state received")
        print(f"  Result type: {type(result)}")
        print(f"  Result attributes: {dir(result)}")
        
        # Examine the result structure
        print("\n3. Examining result structure...")
        for attr in dir(result):
            if not attr.startswith('_'):
                try:
                    value = getattr(result, attr)
                    if not callable(value):
                        print(f"  {attr}: {type(value)} = {value}")
                        if hasattr(value, '__dict__'):
                            print(f"    Attributes: {dir(value)}")
                except Exception as e:
                    print(f"  {attr}: Error accessing - {e}")
        
        # Check if result has accessibility tree
        print("\n4. Checking for accessibility tree...")
        if hasattr(result, 'root_element'):
            print(f"  ✓ root_element: {result.root_element}")
        
        # Check raw_json
        if hasattr(result, 'raw_json'):
            import json
            data = json.loads(result.raw_json)
            print(f"  ✓ raw_json parsed: {json.dumps(data, indent=2)}")
        
        print("\n✅ Debug complete")
        
    except Exception as e:
        print(f"\n✗ Debug failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            await driver.shutdown()
            print("\n✓ Cua Driver shut down")
        except Exception as e:
            print(f"\n⚠️  Shutdown error: {e}")


if __name__ == "__main__":
    asyncio.run(debug_cua_window_state())