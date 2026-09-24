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
            print("Usage: python reflex.py run <task>")
            sys.exit(1)
        
        task = " ".join(sys.argv[2:])
        
        # Load configuration from environment
        config = LoopConfig(
            backend_type="kev",  # Can be overridden with env var
            max_steps=40,
            max_time_seconds=120,
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