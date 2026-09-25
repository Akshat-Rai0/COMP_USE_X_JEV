#!/usr/bin/env python3
"""
Test script for screen recording and GIF conversion functionality.
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
from src.orchestrator.loop import LoopConfig
from src.utils.gif_converter import convert_frames_to_gif, cleanup_frames


async def test_recording():
    """Test screen recording functionality."""
    print("Testing screen recording...")
    
    if not CUA_DRIVER_AVAILABLE:
        print("⚠️  Cua Driver not available. Please install cua-driver package.")
        return
    
    try:
        # Initialize CuaBody
        print("\n1. Initializing CuaBody...")
        body = CuaBody()
        await body.initialize()
        print("✓ CuaBody initialized")
        
        # Start recording
        print("\n2. Starting recording...")
        run_id = 999  # Test run ID
        body.start_recording(run_id)
        print("✓ Recording started")
        
        # Capture some frames
        print("\n3. Capturing test frames...")
        for i in range(5):
            frame_path = await body.capture_action_frame(f"test_{i}")
            if frame_path:
                print(f"  ✓ Frame {i+1} captured: {frame_path.name}")
            else:
                print(f"  ✗ Frame {i+1} capture failed")
            await asyncio.sleep(0.5)  # Small delay between frames
        
        # Stop recording
        print("\n4. Stopping recording...")
        frames_dir = body.stop_recording()
        print(f"✓ Recording stopped")
        print(f"  Frames directory: {frames_dir}")
        
        # Get captured frames
        frame_paths = body.get_recording_frames()
        print(f"  Total frames captured: {len(frame_paths)}")
        
        # Convert to GIF
        if frame_paths:
            print("\n5. Converting frames to GIF...")
            gif_dir = Path.cwd() / "runs" / "gifs"
            gif_dir.mkdir(parents=True, exist_ok=True)
            
            gif_path = gif_dir / f"test_recording.gif"
            result_path = convert_frames_to_gif(
                frame_paths,
                gif_path,
                duration=0.5,
                loop=True,
                fps=2
            )
            
            if result_path:
                print(f"✓ GIF created successfully: {result_path}")
                print(f"  File size: {result_path.stat().st_size / 1024:.1f} KB")
            else:
                print("✗ GIF creation failed")
        else:
            print("⚠️  No frames to convert")
        
        # Cleanup frames
        print("\n6. Cleaning up frames...")
        deleted = cleanup_frames(frame_paths)
        print(f"✓ Deleted {deleted} frame files")
        
        print("\n✅ Recording test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            await body.shutdown()
            print("\n✓ CuaBody shut down")
        except Exception as e:
            print(f"\n⚠️  Shutdown error: {e}")


if __name__ == "__main__":
    print("⚠️  This test will capture screenshots and create a GIF")
    print("   Make sure you have Cua Driver installed and configured")
    print()
    
    asyncio.run(test_recording())