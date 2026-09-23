"""
Basic tests to verify the core module structure and imports.
"""

import sys
from pathlib import Path

# Add parent directory to path for package imports
parent_path = str(Path(__file__).parent.parent)
if parent_path not in sys.path:
    sys.path.insert(0, parent_path)


def test_imports():
    """Test that all core modules can be imported."""
    print("Testing imports...")
    
    # Test models
    from src.models import (
        UIElement,
        WindowSnapshot,
        Action,
        ActionType,
        DecisionRequest,
        DecisionResponse,
        StepRecord,
        OrchestratorState,
    )
    print("✓ Models imported successfully")
    
    # Test body
    from src.body.driver import Body, FakeBody
    print("✓ Body module imported successfully")
    
    # Test serializer
    from src.serializer.tree_parser import TreeParser
    print("✓ Serializer module imported successfully")
    
    # Test backend
    from src.backend.client import DecisionBackend, create_backend
    print("✓ Backend module imported successfully")
    
    # Test gates
    from src.gates.evaluator import GateEvaluator
    print("✓ Gates module imported successfully")
    
    # Test planner
    from src.planner.cortex import PlannerCortex
    print("✓ Planner module imported successfully")
    
    # Test orchestrator
    from src.orchestrator.loop import OrchestratorLoop, LoopConfig
    print("✓ Orchestrator module imported successfully")
    
    # Test trace
    from src.trace.writer import TraceWriter
    print("✓ Trace module imported successfully")


def test_fake_body():
    """Test FakeBody basic functionality."""
    print("\nTesting FakeBody...")
    
    from src.body.driver import FakeBody
    import asyncio
    
    async def test():
        body = FakeBody()
        
        # Test reading window
        snapshot = await body.read_frontmost_window()
        assert snapshot is not None
        assert snapshot.window_id == "fake-window"
        assert len(snapshot.elements) > 0
        print("✓ FakeBody.read_frontmost_window() works")
        
        # Test acting
        from src.models import Action, ActionType
        action = Action(element_id="e0", action_type=ActionType.CLICK)
        success = await body.act(action)
        assert success == True
        print("✓ FakeBody.act() works")
        
        # Test action logging
        actions = body.get_actions_log()
        assert len(actions) == 1
        print("✓ FakeBody action logging works")
    
    asyncio.run(test())


def test_tree_parser():
    """Test TreeParser basic functionality."""
    print("\nTesting TreeParser...")
    
    from src.serializer.tree_parser import TreeParser
    from src.models import UIElement
    
    # Create some test elements
    elements = [
        UIElement(
            element_id="test0",
            role="button",
            label="Click Me",
            enabled=True,
            visible=True,
        ),
        UIElement(
            element_id="test1", 
            role="textfield",
            label="Username",
            enabled=True,
            visible=True,
        ),
    ]
    
    parser = TreeParser()
    serialized = parser.serialize_tree(elements)
    
    assert len(serialized) == 2
    assert serialized[0].description.startswith("e0")
    print("✓ TreeParser.serialize_tree() works")
    
    # Test serialization to string
    state_string = parser.serialize_to_string(serialized)
    assert "e0" in state_string
    assert "button" in state_string
    print("✓ TreeParser.serialize_to_string() works")


def test_gate_evaluator():
    """Test GateEvaluator basic functionality."""
    print("\nTesting GateEvaluator...")
    
    from src.gates.evaluator import GateEvaluator
    from src.models import ChoiceResponse, GateResult
    
    evaluator = GateEvaluator()
    
    # Test confidence gate
    choice_response = ChoiceResponse(
        chosen_option="e0",
        confidence=0.8,
        probabilities={"e0": 0.8, "e1": 0.2},
    )
    
    result = evaluator.evaluate_confidence_gate(choice_response)
    assert result.passed == True
    print("✓ GateEvaluator.evaluate_confidence_gate() works")
    
    # Test with low confidence
    choice_response_low = ChoiceResponse(
        chosen_option="e0",
        confidence=0.5,
        probabilities={"e0": 0.5, "e1": 0.5},
    )
    
    result = evaluator.evaluate_confidence_gate(choice_response_low)
    assert result.passed == False
    print("✓ GateEvaluator confidence threshold works")


def test_trace_writer():
    """Test TraceWriter basic functionality."""
    print("\nTesting TraceWriter...")
    
    from src.trace.writer import TraceWriter
    from pathlib import Path
    import tempfile
    
    # Use a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_traces.sqlite"
        screenshot_dir = Path(tmpdir) / "screenshots"
        
        writer = TraceWriter(db_path=db_path, screenshot_dir=screenshot_dir)
        
        # Test starting a run
        run_id = writer.start_run(
            task="Test task",
            backend_model="kev-latest",
            planner_model="gpt-4o-mini",
        )
        assert run_id > 0
        print("✓ TraceWriter.start_run() works")
        
        # Test getting run
        run_data = writer.get_run(run_id)
        assert run_data is not None
        assert run_data["task"] == "Test task"
        print("✓ TraceWriter.get_run() works")
        
        # Test ending run
        writer.end_run(run_id, successful=True, total_cost=0.0)
        print("✓ TraceWriter.end_run() works")


if __name__ == "__main__":
    try:
        test_imports()
        test_fake_body()
        test_tree_parser()
        test_gate_evaluator()
        test_trace_writer()
        
        print("\n" + "="*50)
        print("✓ All basic tests passed!")
        print("="*50)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)