"""
Orchestrator Loop - Main execution loop implementing the 5-step process.

This module implements the core execution loop:
1. Look - Read the screen via Body
2. Describe - Serialize UI tree via TreeParser
3. Decide - Query decision backend
4. Act - Perform action via Body (if gates pass)
5. Check - Verify action succeeded via Noul questions

The loop handles escalation to the planner LLM when gates fail,
manages human approval for risky actions, and logs everything to the trace.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from src.models import (
    WindowSnapshot,
    DecisionRequest,
    DecisionResponse,
    ChoiceQuestion,
    NoulQuestion,
    Action,
    ActionType,
    StepRecord,
    OrchestratorState,
    GateResult,
)
from src.body.driver import Body, CuaBody, FakeBody
from src.serializer.tree_parser import TreeParser
from src.backend.client import DecisionBackend, create_backend
from src.gates.evaluator import GateEvaluator
from src.planner.cortex import PlannerCortex
from src.trace.writer import TraceWriter
from src.utils.gif_converter import convert_frames_to_gif, cleanup_frames


@dataclass
class LoopConfig:
    """Configuration for the orchestrator loop."""
    backend_type: str = "kev"  # "kev", "jev", or "llm"
    max_steps: int = 40
    max_time_seconds: int = 120
    confidence_gate: float = 0.70
    min_gap: float = 0.15
    screenshot_dir: Optional[Path] = None
    trace_db_path: Optional[Path] = None
    # Screen recording configuration
    record_screen: bool = True  # Always enabled by default
    create_gif: bool = True   # Convert recording to GIF
    max_recordings: int = 10  # Keep only most recent N recordings
    capture_idle: bool = False  # Hybrid: skip idle time


class OrchestratorLoop:
    """Main orchestrator loop for executing tasks."""
    
    def __init__(
        self,
        body: Body,
        config: Optional[LoopConfig] = None,
    ):
        """
        Initialize the orchestrator loop.
        
        Args:
            body: Body implementation for desktop interaction
            config: Loop configuration
        """
        self.config = config or LoopConfig()
        self.body = body
        
        # Initialize components
        self.tree_parser = TreeParser()
        self.gate_evaluator = GateEvaluator(
            confidence_gate=self.config.confidence_gate,
            min_gap=self.config.min_gap,
        )
        self.trace_writer = TraceWriter(
            db_path=self.config.trace_db_path,
            screenshot_dir=self.config.screenshot_dir,
        )
        
        # Initialize backends
        self.decision_backend = create_backend(
            backend_type=self.config.backend_type,
        )
        
        # Initialize planner (optional, only used on escalation)
        self.planner: Optional[PlannerCortex] = None
        try:
            self.planner = PlannerCortex()
        except ValueError as e:
            print(f"Warning: Planner not available: {e}")
        
        # Current state
        self.current_run_id: Optional[int] = None
        self.state: Optional[OrchestratorState] = None
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """
        Execute a task using the 5-step loop.
        
        Args:
            task: Task description
            
        Returns:
            Execution results
        """
        # Initialize state
        self.state = OrchestratorState(
            task=task,
            max_steps=self.config.max_steps,
            max_time_seconds=self.config.max_time_seconds,
        )
        
        # Start trace
        self.current_run_id = self.trace_writer.start_run(
            task=task,
            backend_model=self.decision_backend.get_model_version(),
            planner_model=self.planner.model if self.planner else "none",
        )
        
        print(f"Starting task: {task}")
        print(f"Run ID: {self.current_run_id}")
        
        # Start screen recording if enabled
        if self.config.record_screen and isinstance(self.body, CuaBody):
            self.body.start_recording(self.current_run_id)
        
        try:
            # Main execution loop
            while not self.state.should_stop():
                await self._execute_step()
                
                # Check if we should continue
                if self._should_stop_early():
                    break
            
            # Mark run as successful
            self.trace_writer.end_run(
                run_id=self.current_run_id,
                successful=True,
                total_cost=self.state.total_cost,
            )
            
            print(f"Task completed successfully in {self.state.current_step} steps")
            
            return {
                "success": True,
                "steps": self.state.current_step,
                "run_id": self.current_run_id,
            }
            
        except Exception as e:
            # Mark run as failed
            self.trace_writer.end_run(
                run_id=self.current_run_id,
                successful=False,
                error_message=str(e),
                total_cost=self.state.total_cost,
            )
            
            print(f"Task failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "steps": self.state.current_step,
                "run_id": self.current_run_id,
            }
        finally:
            # Stop recording and convert to GIF if enabled
            if self.config.record_screen and isinstance(self.body, CuaBody):
                frames_dir = self.body.stop_recording()
                if frames_dir and self.config.create_gif:
                    try:
                        # Get captured frames
                        frame_paths = self.body.get_recording_frames()
                        
                        if frame_paths:
                            # Create GIF
                            gif_dir = Path.cwd() / "runs" / "gifs"
                            gif_dir.mkdir(parents=True, exist_ok=True)
                            
                            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                            gif_path = gif_dir / f"run_{self.current_run_id}_{timestamp}.gif"
                            
                            print(f"Converting {len(frame_paths)} frames to GIF...")
                            result_path = convert_frames_to_gif(
                                frame_paths,
                                gif_path,
                                duration=0.5,
                                loop=True,
                                fps=2
                            )
                            
                            if result_path:
                                # Update trace with GIF path
                                self.trace_writer.update_run_gif(self.current_run_id, result_path)
                                print(f"✓ GIF created: {result_path}")
                                
                                # Cleanup old recordings
                                self.trace_writer.cleanup_old_recordings(self.config.max_recordings)
                                
                                # Cleanup frame files
                                cleanup_frames(frame_paths)
                            else:
                                print("⚠️  GIF creation failed")
                    except Exception as e:
                        print(f"⚠️  GIF conversion failed: {e}")
    
    async def _execute_step(self) -> None:
        """Execute a single step of the 5-step process."""
        self.state.current_step += 1
        step_number = self.state.current_step
        
        print(f"\n--- Step {step_number} ---")
        
        # Step 1: Look - Read the screen
        screenshot_path = self._get_screenshot_path(step_number)
        window_snapshot = await self.body.read_frontmost_window(screenshot_path)
        
        # Compute screen hash for loop detection
        screen_hash = self.tree_parser.compute_screen_hash(window_snapshot.elements)
        
        # Step 2: Describe - Serialize UI tree
        serialized_elements = self.tree_parser.serialize_tree(window_snapshot.elements)
        state_string = self.tree_parser.serialize_to_string(serialized_elements)
        
        print(f"Screen: {window_snapshot.title} ({len(window_snapshot.elements)} elements)")
        
        # Step 3: Decide - Query decision backend
        decision_request = self._create_decision_request(
            state_string,
            window_snapshot,
        )
        
        decision_response = await self.decision_backend.decide(decision_request)
        
        print(f"Decision latency: {decision_response.latency_ms:.1f}ms")
        
        # Step 4: Evaluate gates
        action = self._create_action_from_decision(decision_response, serialized_elements)
        gate_results = self.gate_evaluator.evaluate_all_gates(
            choice_response=next(iter(decision_response.choice_responses.values())),
            action=action,
            element_label=self._get_element_label(action, window_snapshot),
            state=self.state,
            current_screen_hash=screen_hash,
        )
        
        should_escalate, escalation_reason = self.gate_evaluator.should_escalate(gate_results)
        requires_human_approval = self.gate_evaluator.requires_human_approval(gate_results)
        
        # Step 5: Act or escalate
        step_record = StepRecord(
            step_number=step_number,
            timestamp=datetime.utcnow(),
            window_snapshot=window_snapshot,
            decision_request=decision_request,
            decision_response=decision_response,
            action=action,
            escalated=should_escalate,
            escalation_reason=escalation_reason,
            human_approval_required=requires_human_approval,
        )
        
        if should_escalate:
            print(f"Escalating to planner: {escalation_reason}")
            await self._handle_escalation(step_record, window_snapshot)
        elif requires_human_approval:
            print(f"Human approval required for risky action")
            approved = await self._request_human_approval(action, window_snapshot)
            step_record.human_approval_granted = approved
            
            if approved:
                print("Human approved - executing action")
                await self._execute_action(action, window_snapshot)
            else:
                print("Human rejected - skipping action")
        else:
            print(f"Executing action: {action.action_type.value} on {action.element_id}")
            await self._execute_action(action, window_snapshot)
        
        # Write step to trace
        self.trace_writer.write_step(self.current_run_id, step_record)
    
    def _create_decision_request(
        self,
        state_string: str,
        window_snapshot: WindowSnapshot,
    ) -> DecisionRequest:
        """Create a decision request for the backend."""
        # Create a Choice question for element selection
        # This is simplified - would need proper element extraction
        choice_question = ChoiceQuestion(
            name="select_element",
            options=state_string.split("\n")[:10],  # First 10 elements as options
            context=f"Task: {self.state.task}\nCurrent window: {window_snapshot.title}",
        )
        
        # Create Noul questions for verification
        noul_questions = [
            NoulQuestion(
                name="goal_reached",
                statement=f"The task '{self.state.task}' has been completed",
            ),
            NoulQuestion(
                name="error_visible",
                statement="An error message or dialog is visible on screen",
            ),
        ]
        
        return DecisionRequest(
            state=state_string,
            questions=[choice_question] + noul_questions,
        )
    
    def _create_action_from_decision(
        self,
        decision_response: DecisionResponse,
        serialized_elements,
    ) -> Action:
        """Create an action from the decision response."""
        # Get the choice response for element selection
        choice_response = next(iter(decision_response.choice_responses.values()))
        
        # Extract element ID from chosen option
        chosen_option = choice_response.chosen_option
        element_id = chosen_option.split()[0] if chosen_option else "e0"
        
        return Action(
            element_id=element_id,
            action_type=ActionType.CLICK,  # Default to click
        )
    
    def _get_element_label(self, action: Action, window_snapshot: WindowSnapshot) -> Optional[str]:
        """Get the label of an element for risk evaluation."""
        element = window_snapshot.get_element_by_id(action.element_id)
        return element.label if element else None
    
    async def _execute_action(self, action: Action, window_snapshot: WindowSnapshot) -> bool:
        """Execute an action and return success status."""
        try:
            # Capture frame before action if recording is enabled
            if self.config.record_screen and isinstance(self.body, CuaBody):
                await self.body.capture_action_frame("before_action")
            
            success = await self.body.act(action)
            
            # Capture frame after action if recording is enabled
            if self.config.record_screen and isinstance(self.body, CuaBody):
                await self.body.capture_action_frame("after_action")
            
            if not success:
                self.state.recent_failures += 1
            else:
                self.state.recent_failures = 0
            
            return success
        except Exception as e:
            print(f"Action failed: {e}")
            self.state.recent_failures += 1
            return False
    
    async def _handle_escalation(
        self,
        step_record: StepRecord,
        window_snapshot: WindowSnapshot,
    ) -> None:
        """Handle escalation to the planner LLM."""
        if not self.planner:
            print("Planner not available - stopping execution")
            self.state.current_step = self.state.max_steps  # Force stop
            return
        
        try:
            # Ask planner to pick an element
            chosen_element = await self.planner.pick_element(
                task=self.state.task,
                elements=window_snapshot.elements,
                screenshot_path=window_snapshot.screenshot_path,
            )
            
            if chosen_element:
                # Update action with planner's choice
                step_record.action = Action(
                    element_id=chosen_element,
                    action_type=ActionType.CLICK,
                )
                
                # Execute the planner's choice
                await self._execute_action(step_record.action, window_snapshot)
            else:
                print("Planner could not determine an element - stopping")
                self.state.current_step = self.state.max_steps
                
        except Exception as e:
            print(f"Planner escalation failed: {e}")
            step_record.error = str(e)
    
    async def _request_human_approval(
        self,
        action: Action,
        window_snapshot: WindowSnapshot,
    ) -> bool:
        """Request human approval for a risky action."""
        # In a real implementation, this would show a UI dialog
        # For now, we'll use console input
        print(f"\n⚠️  RISKY ACTION REQUIRES APPROVAL")
        print(f"Action: {action.action_type.value} on {action.element_id}")
        print(f"Window: {window_snapshot.title}")
        
        response = input("Approve? (y/n): ").strip().lower()
        return response == 'y'
    
    def _should_stop_early(self) -> bool:
        """Check if we should stop execution early."""
        # Check Noul responses for goal completion
        # This is simplified - would need proper response checking
        return False
    
    def _get_screenshot_path(self, step_number: int) -> Path:
        """Get the path for a screenshot."""
        if self.config.screenshot_dir:
            return self.config.screenshot_dir / f"step_{step_number:04d}.png"
        return Path.cwd() / "runs" / f"step_{step_number:04d}.png"
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        await self.body.shutdown()
        
        if hasattr(self.decision_backend, 'shutdown'):
            await self.decision_backend.shutdown()
        
        if self.planner:
            await self.planner.shutdown()


async def run_task(
    task: str,
    body: Optional[Body] = None,
    config: Optional[LoopConfig] = None,
) -> Dict[str, Any]:
    """
    Convenience function to run a task.
    
    Args:
        task: Task description
        body: Body implementation (defaults to CuaBody)
        config: Loop configuration
        
    Returns:
        Execution results
    """
    if body is None:
        body = CuaBody()
    
    orchestrator = OrchestratorLoop(body, config)
    
    try:
        return await orchestrator.execute_task(task)
    finally:
        await orchestrator.shutdown()