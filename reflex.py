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
        print("Running test with FakeBody...")
        
        # Create a simple test with FakeBody
        fake_body = FakeBody()
        
        # For testing, we'll use a mock backend to avoid kev server API issues
        from src.backend.client import DecisionBackend, DecisionResponse, ChoiceResponse, NoulResponse
        import time
        
        class MockBackend(DecisionBackend):
            async def decide(self, request):
                # Mock decision response
                return DecisionResponse(
                    choice_responses={
                        "select_element": ChoiceResponse(
                            chosen_option="e0",
                            confidence=0.9,
                            probabilities={"e0": 0.9, "e1": 0.1},
                        )
                    },
                    noul_responses={
                        "goal_reached": NoulResponse(
                            answer=False,
                            confidence=0.9,
                            probability_true=0.1,
                        ),
                        "error_visible": NoulResponse(
                            answer=False,
                            confidence=0.9,
                            probability_true=0.1,
                        ),
                    },
                    model_version="mock-1.0",
                    latency_ms=50.0,
                )
            
            def get_model_version(self):
                return "mock-1.0"
        
        # Monkey-patch the backend creation for testing
        import src.orchestrator.loop as loop_module
        original_create = loop_module.create_backend
        
        def mock_create(backend_type, **kwargs):
            return MockBackend()
        
        loop_module.create_backend = mock_create
        
        try:
            config = LoopConfig(
                backend_type="mock",  # Use mock backend for testing
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
        finally:
            # Restore original function
            loop_module.create_backend = original_create
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())