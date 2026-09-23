"""
Gates Evaluator - Confidence thresholds, safety checks, and loop detection.

This module implements the gating logic that determines when to escalate
from the fast decision model to the slower planner LLM.

Escalation triggers:
- Confidence below threshold (default 0.70)
- Top-two choices gap too small (default 0.15)
- Risky actions (delete, send, buy) always require human approval
- Loop detection (same screen 3x in a row)
- Repeated failures (2x in a row)
"""

import os
from typing import List, Optional, Set
from dataclasses import dataclass

from src.models import (
    DecisionResponse,
    ChoiceResponse,
    Action,
    ActionType,
    GateResult,
    OrchestratorState,
)


class GateEvaluator:
    """Evaluates gate conditions for escalation."""
    
    # Default thresholds
    DEFAULT_CONFIDENCE_GATE = 0.70
    DEFAULT_MIN_GAP = 0.15
    DEFAULT_MAX_LOOP_COUNT = 3
    DEFAULT_MAX_FAILURES = 2
    
    # Risky action keywords
    RISKY_KEYWORDS = {
        "delete", "remove", "clear", "erase",
        "send", "submit", "post", "publish",
        "buy", "purchase", "pay", "checkout",
        "transfer", "withdraw", "export",
    }
    
    def __init__(
        self,
        confidence_gate: Optional[float] = None,
        min_gap: Optional[float] = None,
        max_loop_count: Optional[int] = None,
        max_failures: Optional[int] = None,
    ):
        """
        Initialize the gate evaluator.
        
        Args:
            confidence_gate: Minimum confidence threshold (default 0.70)
            min_gap: Minimum gap between top two choices (default 0.15)
            max_loop_count: Max consecutive same screens before escalation (default 3)
            max_failures: Max consecutive failures before escalation (default 2)
        """
        self.confidence_gate = confidence_gate or float(
            os.getenv("CONFIDENCE_GATE", self.DEFAULT_CONFIDENCE_GATE)
        )
        self.min_gap = min_gap or float(
            os.getenv("MIN_GAP", self.DEFAULT_MIN_GAP)
        )
        self.max_loop_count = max_loop_count or int(
            os.getenv("MAX_LOOP_COUNT", str(self.DEFAULT_MAX_LOOP_COUNT))
        )
        self.max_failures = max_failures or int(
            os.getenv("MAX_FAILURES", str(self.DEFAULT_MAX_FAILURES))
        )
    
    def evaluate_confidence_gate(
        self,
        choice_response: ChoiceResponse,
    ) -> GateResult:
        """
        Evaluate if confidence meets the threshold.
        
        Args:
            choice_response: Response from the decision backend
            
        Returns:
            GateResult indicating if the gate was passed
        """
        if choice_response.confidence >= self.confidence_gate:
            return GateResult(
                passed=True,
                confidence=choice_response.confidence,
            )
        
        return GateResult(
            passed=False,
            reason=f"Confidence {choice_response.confidence:.2f} below threshold {self.confidence_gate}",
            confidence=choice_response.confidence,
        )
    
    def evaluate_gap_gate(
        self,
        choice_response: ChoiceResponse,
    ) -> GateResult:
        """
        Evaluate if the gap between top two choices is sufficient.
        
        Args:
            choice_response: Response from the decision backend
            
        Returns:
            GateResult indicating if the gate was passed
        """
        if len(choice_response.probabilities) < 2:
            # Only one option, gap check passes
            return GateResult(passed=True)
        
        # Sort probabilities and get top two
        sorted_probs = sorted(
            choice_response.probabilities.values(),
            reverse=True
        )
        
        top_two_gap = sorted_probs[0] - sorted_probs[1]
        
        if top_two_gap >= self.min_gap:
            return GateResult(
                passed=True,
                gap=top_two_gap,
            )
        
        return GateResult(
            passed=False,
            reason=f"Gap {top_two_gap:.2f} below threshold {self.min_gap}",
            gap=top_two_gap,
        )
    
    def evaluate_risk_gate(
        self,
        action: Action,
        element_label: Optional[str] = None,
    ) -> GateResult:
        """
        Evaluate if an action is risky and requires human approval.
        
        Risky actions always require human approval regardless of confidence.
        
        Args:
            action: The action to evaluate
            element_label: Label of the target element (for keyword matching)
            
        Returns:
            GateResult indicating if human approval is required
        """
        # Check if action type is inherently risky
        risky_actions = {ActionType.CLICK}  # Most risky actions are clicks
        
        if action.action_type not in risky_actions:
            return GateResult(passed=True)
        
        # Check for risky keywords in element label
        if element_label:
            label_lower = element_label.lower()
            for keyword in self.RISKY_KEYWORDS:
                if keyword in label_lower:
                    return GateResult(
                        passed=False,
                        reason=f"Risky keyword '{keyword}' found in element label",
                    )
        
        # Check for risky keywords in action text (for TYPE actions)
        if action.text:
            text_lower = action.text.lower()
            for keyword in self.RISKY_KEYWORDS:
                if keyword in text_lower:
                    return GateResult(
                        passed=False,
                        reason=f"Risky keyword '{keyword}' found in action text",
                    )
        
        return GateResult(passed=True)
    
    def evaluate_loop_gate(
        self,
        state: OrchestratorState,
        current_screen_hash: str,
    ) -> GateResult:
        """
        Evaluate if we're in a loop (same screen repeated).
        
        Args:
            state: Current orchestrator state
            current_screen_hash: Hash of the current screen
            
        Returns:
            GateResult indicating if loop detection triggered
        """
        if state.last_screen_hash == current_screen_hash:
            state.consecutive_same_screen_count += 1
        else:
            state.consecutive_same_screen_count = 0
            state.last_screen_hash = current_screen_hash
        
        if state.consecutive_same_screen_count >= self.max_loop_count:
            return GateResult(
                passed=False,
                reason=f"Loop detected: same screen {state.consecutive_same_screen_count} times",
            )
        
        return GateResult(passed=True)
    
    def evaluate_failure_gate(
        self,
        state: OrchestratorState,
        action_succeeded: bool,
    ) -> GateResult:
        """
        Evaluate if we've had too many consecutive failures.
        
        Args:
            state: Current orchestrator state
            action_succeeded: Whether the last action succeeded
            
        Returns:
            GateResult indicating if failure threshold was reached
        """
        if action_succeeded:
            state.recent_failures = 0
            return GateResult(passed=True)
        
        state.recent_failures += 1
        
        if state.recent_failures >= self.max_failures:
            return GateResult(
                passed=False,
                reason=f"Too many consecutive failures: {state.recent_failures}",
            )
        
        return GateResult(passed=True)
    
    def evaluate_all_gates(
        self,
        choice_response: ChoiceResponse,
        action: Action,
        element_label: Optional[str] = None,
        state: Optional[OrchestratorState] = None,
        current_screen_hash: Optional[str] = None,
        action_succeeded: bool = True,
    ) -> List[GateResult]:
        """
        Evaluate all gates and return results.
        
        Args:
            choice_response: Response from decision backend
            action: The action to evaluate
            element_label: Label of target element
            state: Current orchestrator state (for loop/failure gates)
            current_screen_hash: Hash of current screen (for loop gate)
            action_succeeded: Whether last action succeeded (for failure gate)
            
        Returns:
            List of gate results
        """
        results = []
        
        # Confidence gate
        results.append(self.evaluate_confidence_gate(choice_response))
        
        # Gap gate
        results.append(self.evaluate_gap_gate(choice_response))
        
        # Risk gate
        results.append(self.evaluate_risk_gate(action, element_label))
        
        # Loop gate (if state provided)
        if state and current_screen_hash:
            results.append(self.evaluate_loop_gate(state, current_screen_hash))
        
        # Failure gate (if state provided)
        if state:
            results.append(self.evaluate_failure_gate(state, action_succeeded))
        
        return results
    
    def should_escalate(
        self,
        gate_results: List[GateResult],
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if escalation is needed based on gate results.
        
        Args:
            gate_results: Results from gate evaluations
            
        Returns:
            Tuple of (should_escalate, reason)
        """
        for result in gate_results:
            if not result.passed:
                return True, result.reason
        
        return False, None
    
    def requires_human_approval(
        self,
        gate_results: List[GateResult],
    ) -> bool:
        """
        Check if any gate requires human approval.
        
        Currently, only the risk gate requires human approval.
        
        Args:
            gate_results: Results from gate evaluations
            
        Returns:
            True if human approval is required
        """
        for result in gate_results:
            if not result.passed and "risky" in result.reason.lower():
                return True
        
        return False