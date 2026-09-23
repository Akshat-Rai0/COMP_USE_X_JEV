"""
Core data models for Reflex Arc.

This module defines the fundamental data structures used throughout the system:
- UI elements and window snapshots
- Decision backend requests/responses
- Step records and trace data
- Configuration and state
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of actions that can be performed on UI elements."""
    CLICK = "click"
    TYPE = "type"
    PRESS = "press"
    SCROLL = "scroll"


class QuestionType(str, Enum):
    """Types of questions that can be asked to the decision backend."""
    CHOICE = "choice"  # Which element to act on
    NOUL = "noul"     # Yes/no question
    SCORE = "score"   # Scoring/ranking question


@dataclass
class UIElement:
    """Represents a single UI element from the accessibility tree."""
    element_id: str
    role: str
    label: str
    value: Optional[str] = None
    enabled: bool = True
    visible: bool = True
    children: List['UIElement'] = field(default_factory=list)
    parent_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "element_id": self.element_id,
            "role": self.role,
            "label": self.label,
            "value": self.value,
            "enabled": self.enabled,
            "visible": self.visible,
            "parent_id": self.parent_id,
        }


@dataclass
class WindowSnapshot:
    """Snapshot of the frontmost window including UI tree and screenshot."""
    window_id: str
    title: str
    app_name: str
    elements: List[UIElement]
    screenshot_path: Optional[Path] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def get_element_by_id(self, element_id: str) -> Optional[UIElement]:
        """Find an element by its ID in the tree."""
        for element in self.elements:
            if element.element_id == element_id:
                return element
            if element.children:
                child = self._find_in_children(element.children, element_id)
                if child:
                    return child
        return None
    
    def _find_in_children(self, children: List[UIElement], element_id: str) -> Optional[UIElement]:
        """Recursively search for element in children."""
        for child in children:
            if child.element_id == element_id:
                return child
            if child.children:
                found = self._find_in_children(child.children, element_id)
                if found:
                    return found
        return None


@dataclass
class ChoiceQuestion:
    """A Choice question for the decision backend."""
    name: str
    options: List[str]  # List of element descriptions like "e12 button 'Add Reminder'"
    context: str  # Current state/task context


@dataclass
class NoulQuestion:
    """A Noul (yes/no) question for the decision backend."""
    name: str
    statement: str  # The statement to evaluate


@dataclass
class DecisionRequest:
    """Request to the decision backend."""
    state: str  # Serialized current state
    questions: List[Union[ChoiceQuestion, NoulQuestion]]


@dataclass
class ChoiceResponse:
    """Response to a Choice question."""
    chosen_option: str
    confidence: float
    probabilities: Dict[str, float]


@dataclass
class NoulResponse:
    """Response to a Noul question."""
    answer: bool
    confidence: float
    probability_true: float


@dataclass
class DecisionResponse:
    """Response from the decision backend."""
    choice_responses: Dict[str, ChoiceResponse]
    noul_responses: Dict[str, NoulResponse]
    model_version: str
    latency_ms: float


@dataclass
class Action:
    """An action to perform on a UI element."""
    element_id: str
    action_type: ActionType
    text: Optional[str] = None  # For TYPE actions
    key: Optional[str] = None   # For PRESS actions


@dataclass
class StepRecord:
    """Record of a single step in the execution trace."""
    step_number: int
    timestamp: datetime
    window_snapshot: WindowSnapshot
    decision_request: DecisionRequest
    decision_response: DecisionResponse
    action: Optional[Action] = None
    escalated: bool = False
    escalation_reason: Optional[str] = None
    human_approval_required: bool = False
    human_approval_granted: Optional[bool] = None
    error: Optional[str] = None
    latency_breakdown: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for SQLite storage."""
        return {
            "step_number": self.step_number,
            "timestamp": self.timestamp.isoformat(),
            "window_title": self.window_snapshot.title,
            "app_name": self.window_snapshot.app_name,
            "element_count": len(self.window_snapshot.elements),
            "screenshot_path": str(self.window_snapshot.screenshot_path) if self.window_snapshot.screenshot_path else None,
            "model_version": self.decision_response.model_version,
            "chosen_element": self.action.element_id if self.action else None,
            "action_type": self.action.action_type.value if self.action else None,
            "confidence": next(iter(self.decision_response.choice_responses.values())).confidence if self.decision_response.choice_responses else None,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "human_approval_required": self.human_approval_required,
            "human_approval_granted": self.human_approval_granted,
            "error": self.error,
            "latency_ms": self.decision_response.latency_ms,
        }


class GateResult(BaseModel):
    """Result of a gate evaluation."""
    passed: bool
    reason: Optional[str] = None
    confidence: Optional[float] = None
    gap: Optional[float] = None


class OrchestratorState(BaseModel):
    """State maintained by the orchestrator during execution."""
    task: str
    current_step: int = 0
    max_steps: int = 40
    max_time_seconds: int = 120
    start_time: datetime = Field(default_factory=datetime.utcnow)
    last_screen_hash: Optional[str] = None
    consecutive_same_screen_count: int = 0
    recent_failures: int = 0
    total_cost: float = 0.0
    
    def should_stop(self) -> bool:
        """Check if execution should stop based on limits."""
        if self.current_step >= self.max_steps:
            return True
        if (datetime.utcnow() - self.start_time).total_seconds() >= self.max_time_seconds:
            return True
        if self.consecutive_same_screen_count >= 3:
            return True
        return False