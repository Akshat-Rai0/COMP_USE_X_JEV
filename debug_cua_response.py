#!/usr/bin/env python3
"""
Debug script to examine actual Cua Driver response format.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cua_driver import CuaDriver, GetDesktopStateInput


async def debug_cua_response():
    """Debug Cua Driver response format."""
    print("Debugging Cua Driver response format...")
    
    try:
        # Initialize Cua Driver
        print("\n1. Initializing Cua Driver...")
        driver = CuaDriver.create()
        session = "debug-session"
        print("✓ Cua Driver initialized")
        
        # Get desktop state
        print("\n2. Getting desktop state...")
        screenshot_path = Path.cwd() / "runs" / "debug_screenshot.png"
        screenshot_path.parent.mkdir(exist_ok=True)
        result = await driver.get_desktop_state(
            GetDesktopStateInput(session=session, screenshot_out_file=str(screenshot_path))
        )
        
        print(f"✓ Desktop state received")
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
        
        # Try to access common attributes
        print("\n4. Checking for common response attributes...")
        common_attrs = ['desktop', 'windows', 'screens', 'apps', 'elements', 'ui_tree', 'snapshot']
        for attr in common_attrs:
            if hasattr(result, attr):
                value = getattr(result, attr)
                print(f"  ✓ {attr}: {type(value)}")
                if isinstance(value, (list, dict)):
                    print(f"    Length/Size: {len(value)}")
                    if len(value) > 0:
                        if isinstance(value, list):
                            print(f"    First item: {value[0]}")
                        else:
                            print(f"    First key: {list(value.keys())[0]}")
        
        # Check if result has a specific structure
        print("\n5. Checking result structure details...")
        if hasattr(result, '__dict__'):
            print(f"  Result __dict__: {result.__dict__}")
        
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
    asyncio.run(debug_cua_response())