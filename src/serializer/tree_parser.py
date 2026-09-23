"""
Tree Parser - Converts UI element trees into the format required by Jev/kev.

This module handles:
- Flattening hierarchical UI trees into numbered elements
- Pruning to the 255-element limit required by Choice questions
- Ranking elements by importance for the decision model
- Serializing elements into the format: "e12 button 'Add Reminder'"
"""

import hashlib
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from src.models import UIElement


@dataclass
class SerializedElement:
    """A serialized UI element in the format expected by Jev/kev."""
    element_id: str
    description: str  # e.g., "e12 button 'Add Reminder'"
    original_element: UIElement
    importance_score: float = 0.0


class TreeParser:
    """Parser for converting UI trees into decision-backend format."""
    
    MAX_ELEMENTS = 255  # Hard limit from Jev/kev Choice questions
    
    def __init__(self):
        """Initialize the tree parser."""
        self.element_counter = 0
    
    def serialize_tree(self, elements: List[UIElement]) -> List[SerializedElement]:
        """
        Convert a UI tree into serialized elements for the decision backend.
        
        Args:
            elements: List of root UI elements
            
        Returns:
            List of serialized elements, pruned to MAX_ELEMENTS
        """
        self.element_counter = 0
        serialized = []
        
        # First pass: serialize all elements with importance scoring
        for element in elements:
            self._serialize_element_recursive(element, serialized, depth=0)
        
        # Second pass: rank by importance and prune if necessary
        if len(serialized) > self.MAX_ELEMENTS:
            serialized = self._prune_by_importance(serialized)
        
        # Re-index after pruning
        for i, elem in enumerate(serialized):
            elem.element_id = f"e{i}"
        
        return serialized
    
    def _serialize_element_recursive(
        self,
        element: UIElement,
        serialized: List[SerializedElement],
        depth: int = 0,
    ) -> None:
        """
        Recursively serialize an element and its children.
        
        Args:
            element: The UI element to serialize
            serialized: List to append serialized elements to
            depth: Current depth in the tree (for importance scoring)
        """
        # Skip invisible or disabled elements
        if not element.visible or not element.enabled:
            return
        
        # Create description
        description = self._create_description(element, self.element_counter)
        
        # Calculate importance score
        importance = self._calculate_importance(element, depth)
        
        # Create serialized element
        serialized_elem = SerializedElement(
            element_id=f"e{self.element_counter}",
            description=description,
            original_element=element,
            importance_score=importance,
        )
        
        serialized.append(serialized_elem)
        self.element_counter += 1
        
        # Recursively serialize children
        for child in element.children:
            self._serialize_element_recursive(child, serialized, depth + 1)
    
    def _create_description(self, element: UIElement, index: int) -> str:
        """
        Create a human-readable description for the element.
        
        Format: "e{index} {role} '{label}'"
        Examples: "e12 button 'Add Reminder'", "e5 textfield 'Username'"
        
        Args:
            element: The UI element
            index: The element's index
            
        Returns:
            Description string
        """
        label = element.label or element.value or ""
        label = label.replace("'", "\\'")  # Escape quotes
        
        description = f"e{index} {element.role}"
        if label:
            description += f" '{label}'"
        
        return description
    
    def _calculate_importance(self, element: UIElement, depth: int) -> float:
        """
        Calculate an importance score for an element.
        
        Higher scores indicate more important elements that should be
        preserved during pruning.
        
        Scoring factors:
        - Interactive elements (buttons, textfields) score higher
        - Elements with labels score higher
        - Shallower depth scores higher
        - Large elements score higher (more likely to be containers)
        
        Args:
            element: The UI element
            depth: Depth in the tree
            
        Returns:
            Importance score (0.0 to 1.0)
        """
        score = 0.0
        
        # Interactive roles get higher scores
        interactive_roles = {"button", "textfield", "link", "checkbox", "radiobutton"}
        if element.role.lower() in interactive_roles:
            score += 0.5
        
        # Elements with labels get higher scores
        if element.label:
            score += 0.3
        
        # Depth penalty (deeper elements are less important)
        score += max(0, 0.5 - (depth * 0.1))
        
        # Elements with children (containers) get moderate scores
        if element.children:
            score += 0.2
        
        # Normalize to 0-1 range
        return min(1.0, max(0.0, score))
    
    def _prune_by_importance(self, serialized: List[SerializedElement]) -> List[SerializedElement]:
        """
        Prune elements to MAX_ELEMENTS based on importance scores.
        
        Args:
            serialized: List of serialized elements
            
        Returns:
            Pruned list with at most MAX_ELEMENTS elements
        """
        # Sort by importance score (descending)
        sorted_elements = sorted(
            serialized,
            key=lambda x: x.importance_score,
            reverse=True
        )
        
        # Keep top MAX_ELEMENTS
        pruned = sorted_elements[:self.MAX_ELEMENTS]
        
        # Sort back by original element_id to maintain order
        pruned.sort(key=lambda x: int(x.element_id[1:]))
        
        return pruned
    
    def serialize_to_string(self, serialized: List[SerializedElement]) -> str:
        """
        Convert serialized elements to a single string for the decision backend.
        
        Each element on its own line:
        e0 button 'Add Reminder'
        e1 textfield 'Task name'
        e2 button 'Cancel'
        
        Args:
            serialized: List of serialized elements
            
        Returns:
            String representation
        """
        lines = [elem.description for elem in serialized]
        return "\n".join(lines)
    
    def compute_screen_hash(self, elements: List[UIElement]) -> str:
        """
        Compute a hash of the screen state for loop detection.
        
        This is used to detect when the screen hasn't changed between steps,
        which can indicate infinite loops.
        
        Args:
            elements: List of UI elements
            
        Returns:
            Hash string
        """
        # Create a canonical string representation
        elements_str = ""
        for elem in elements:
            elements_str += f"{elem.role}:{elem.label}:{elem.value}:{elem.enabled}:{elem.visible}"
        
        # Compute hash
        return hashlib.sha256(elements_str.encode()).hexdigest()[:16]


class TreeParserError(Exception):
    """Exception raised for tree parsing errors."""
    pass