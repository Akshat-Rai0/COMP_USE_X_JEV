#!/usr/bin/env python3
"""
Debug script to examine Cua Driver element attributes.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cua_driver import CuaDriver, ListWindowsInput, GetWindowStateInput


async def debug_element_attributes():
    """Debug Cua Driver element attributes."""
    print("Debugging Cua Driver element attributes...")
    
    try:
        # Initialize Cua Driver
        print("\n1. Initializing Cua Driver...")
        driver = CuaDriver.create()
        print("✓ Cua Driver initialized")
        
        # Get window list
        print("\n2. Getting window list...")
        windows_result = await driver.list_windows(ListWindowsInput(pid=None, on_screen_only=True))
        
        if not windows_result.windows:
            print("⚠️  No windows found")
            return
        
        # Get frontmost window
        frontmost_window = max(windows_result.windows, key=lambda w: w.z_index)
        print(f"✓ Frontmost window: {frontmost_window.app_name} (PID: {frontmost_window.pid}, Window ID: {frontmost_window.window_id})")
        
        # Get window state
        print("\n3. Getting window state...")
        screenshot_path = Path.cwd() / "runs" / "element_debug_screenshot.png"
        screenshot_path.parent.mkdir(exist_ok=True)
        
        window_result = await driver.get_window_state(
            GetWindowStateInput(
                pid=frontmost_window.pid,
                window_id=frontmost_window.window_id,
                session="debug-session",
                query=None,
                include_accessibility_tree=True,
                include_screenshot=True,
                screenshot_out_file=str(screenshot_path),
                max_elements=10,
                max_depth=5,
                max_dimension=1000
            )
        )
        
        print(f"✓ Window state received")
        print(f"  Elements: {len(window_result.elements)}")
        print(f"  Degraded: {window_result.degraded}")
        
        if window_result.elements:
            print("\n4. Examining first element attributes...")
            first_elem = window_result.elements[0]
            print(f"  Type: {type(first_elem)}")
            print(f"  Attributes: {dir(first_elem)}")
            
            print("\n5. Examining element properties...")
            for attr in dir(first_elem):
                if not attr.startswith('_'):
                    try:
                        value = getattr(first_elem, attr)
                        if not callable(value):
                            print(f"  {attr}: {type(value)} = {value}")
                    except Exception as e:
                        print(f"  {attr}: Error accessing - {e}")
        
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
    asyncio.run(debug_element_attributes())