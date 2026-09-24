#!/usr/bin/env python3
"""
Debug script to examine Cua Driver window information.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cua_driver import CuaDriver, ListWindowsInput


async def debug_cua_windows():
    """Debug Cua Driver window information."""
    print("Debugging Cua Driver window information...")
    
    try:
        # Initialize Cua Driver
        print("\n1. Initializing Cua Driver...")
        driver = CuaDriver.create()
        print("✓ Cua Driver initialized")
        
        # List windows
        print("\n2. Listing windows...")
        result = await driver.list_windows(ListWindowsInput(pid=None, on_screen_only=True))
        
        print(f"✓ Windows received")
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
        
        # Check if result has windows attribute
        print("\n4. Checking for windows data...")
        if hasattr(result, 'windows'):
            windows = result.windows
            print(f"  ✓ windows: {len(windows)} windows found")
            for i, window in enumerate(windows[:3]):  # Show first 3
                print(f"    Window {i}: {window}")
                print(f"      Type: {type(window)}")
                print(f"      Attributes: {dir(window)}")
        
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
    asyncio.run(debug_cua_windows())