"""
Reflex Arc - A dual-process System 1 / System 2 macOS desktop automation agent.

This package provides the core orchestration, decision-making, and desktop
interaction capabilities for the Reflex Arc agent.
"""

from .models import (
    UIElement,
    WindowSnapshot,
    ActionType,
    QuestionType,
    ChoiceQuestion,
    NoulQuestion,
    DecisionRequest,
    DecisionResponse,
    ChoiceResponse,
    NoulResponse,
    Action,
    StepRecord,
    GateResult,
    OrchestratorState,
)

from .orchestrator.loop import (
    OrchestratorLoop,
    LoopConfig,
    run_task,
)

__version__ = "0.1.0"
__all__ = [
    # Models
    "UIElement",
    "WindowSnapshot", 
    "ActionType",
    "QuestionType",
    "ChoiceQuestion",
    "NoulQuestion",
    "DecisionRequest",
    "DecisionResponse",
    "ChoiceResponse",
    "NoulResponse",
    "Action",
    "StepRecord",
    "GateResult",
    "OrchestratorState",
    # Orchestrator
    "OrchestratorLoop",
    "LoopConfig",
    "run_task",
]