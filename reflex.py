#!/usr/bin/env python3
"""
Reflex Arc CLI - Command-line interface for the desktop automation agent.

Usage:
    source .venv/bin/activate
    python reflex.py run "Task description"
    python reflex.py test
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path for package imports
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator.loop import run_task, LoopConfig
from src.body.driver import FakeBody


async def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python reflex.py <command> [args]")
        print("Commands:")
        print("  run <task>  - Execute a task")
        print("  test        - Run a simple test with FakeBody")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "run":
        if len(sys.argv) < 3:
            print("Usage: python reflex.py run <task> [options]")
            print("Options:")
            print("  --no-record    Disable screen recording")
            print("  --no-gif       Disable GIF conversion")
            print("  --keep N       Keep N most recent recordings")
            sys.exit(1)
        
        # Parse task and options
        task_parts = []
        no_record = False
        no_gif = False
        keep_recordings = None
        
        for arg in sys.argv[2:]:
            if arg == "--no-record":
                no_record = True
            elif arg == "--no-gif":
                no_gif = True
            elif arg.startswith("--keep"):
                try:
                    keep_recordings = int(arg.split("=")[1])
                except:
                    print("Error: --keep requires a number (e.g., --keep=20)")
                    sys.exit(1)
            else:
                task_parts.append(arg)
        
        task = " ".join(task_parts)
        
        # Load configuration from environment
        config = LoopConfig(
            backend_type="kev",  # Can be overridden with env var
            max_steps=40,
            max_time_seconds=120,
            record_screen=not no_record,  # Override with CLI flag
            create_gif=not no_gif,  # Override with CLI flag
            max_recordings=keep_recordings if keep_recordings else 10,  # Override with CLI flag
        )
        
        # Run the task
        result = await run_task(task, config=config)
        
        if result["success"]:
            print(f"\n✓ Task completed successfully")
            print(f"  Steps: {result['steps']}")
            print(f"  Run ID: {result['run_id']}")
        else:
            print(f"\n✗ Task failed: {result['error']}")
            print(f"  Steps completed: {result['steps']}")
            sys.exit(1)
    
    elif command == "test":
        print("Running test with FakeBody and real kev backend...")
        
        # Create a simple test with FakeBody
        fake_body = FakeBody()
        
        # Use real kev backend for testing
        config = LoopConfig(
            backend_type="kev",  # Use real kev backend
            max_steps=2,
            max_time_seconds=30,
        )
        
        result = await run_task("Test task", body=fake_body, config=config)
        
        if result["success"]:
            print(f"\n✓ Test passed")
            print(f"  Actions logged: {len(fake_body.get_actions_log())}")
        else:
            print(f"\n✗ Test failed: {result['error']}")
            sys.exit(1)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())