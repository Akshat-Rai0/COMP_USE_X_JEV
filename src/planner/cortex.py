"""
Planner Cortex - LLM-based high-level planning and text generation.

This module handles:
- Creating task plans when escalated from the fast decision model
- Generating text input for TYPE actions
- Replanning when the fast model gets stuck
- Analyzing screenshots for visual context
"""

import os
import base64
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.models import (
    WindowSnapshot,
    Action,
    ActionType,
    UIElement,
)


@dataclass
class Plan:
    """A high-level plan for completing a task."""
    steps: List[str]
    reasoning: str
    estimated_steps: int


@dataclass
class TextGeneration:
    """Generated text for a TYPE action."""
    text: str
    confidence: float
    reasoning: str


class PlannerCortex:
    """LLM-based planner for high-level reasoning and text generation."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the planner cortex.
        
        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            model: Model to use (defaults to PLANNER_MODEL env var)
            base_url: API base URL (defaults to OPENROUTER_BASE_URL env var)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required for PlannerCortex")
        
        self.model = model or os.getenv("PLANNER_MODEL", "openai/gpt-4o-mini")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        
        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://reflex-ai.dev",  # Required by OpenRouter
                "X-Title": "Reflex Arc",
            }
        )
    
    async def make_plan(
        self,
        task: str,
        current_context: str,
        screenshot_path: Optional[Path] = None,
    ) -> Plan:
        """
        Create a high-level plan for completing the task.
        
        Args:
            task: The task description
            current_context: Current state/context description
            screenshot_path: Optional screenshot for visual context
            
        Returns:
            Plan with steps and reasoning
        """
        messages = [
            {
                "role": "system",
                "content": "You are a task planning assistant for desktop automation. Break down tasks into clear, actionable steps."
            },
            {
                "role": "user",
                "content": self._create_plan_prompt(task, current_context, screenshot_path),
            }
        ]
        
        # Add screenshot if provided
        if screenshot_path and screenshot_path.exists():
            messages[1]["content"] = [
                {"type": "text", "text": messages[1]["content"]},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._encode_image(screenshot_path),
                    }
                }
            ]
        
        response = await self._call_llm(messages)
        
        # Parse the response (simplified - would need robust parsing)
        return self._parse_plan_response(response)
    
    async def pick_element(
        self,
        task: str,
        elements: List[UIElement],
        screenshot_path: Optional[Path] = None,
    ) -> Optional[str]:
        """
        Pick the best element to act on when the fast model is unsure.
        
        Args:
            task: Current task context
            elements: Available UI elements
            screenshot_path: Optional screenshot for visual context
            
        Returns:
            Element ID of the best choice, or None if unclear
        """
        elements_str = self._format_elements(elements)
        
        messages = [
            {
                "role": "system",
                "content": "You are a UI element selection assistant. Choose the best element to interact with based on the task."
            },
            {
                "role": "user",
                "content": f"Task: {task}\n\nAvailable elements:\n{elements_str}\n\nWhich element should be interacted with? Respond with just the element ID (e.g., 'e12')."
            }
        ]
        
        # Add screenshot if provided
        if screenshot_path and screenshot_path.exists():
            messages[1]["content"] = [
                {"type": "text", "text": messages[1]["content"]},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._encode_image(screenshot_path),
                    }
                }
            ]
        
        response = await self._call_llm(messages)
        
        # Extract element ID from response
        for elem in elements:
            if elem.element_id in response:
                return elem.element_id
        
        return None
    
    async def write_text(
        self,
        task: str,
        field_label: str,
        current_value: Optional[str] = None,
        screenshot_path: Optional[Path] = None,
    ) -> TextGeneration:
        """
        Generate text for a TYPE action.
        
        Args:
            task: Current task context
            field_label: Label of the text field
            current_value: Current value in the field (if any)
            screenshot_path: Optional screenshot for context
            
        Returns:
            Generated text with confidence
        """
        messages = [
            {
                "role": "system",
                "content": "You are a text generation assistant for desktop automation. Generate appropriate text for form fields based on task context."
            },
            {
                "role": "user",
                "content": self._create_text_prompt(task, field_label, current_value),
            }
        ]
        
        # Add screenshot if provided
        if screenshot_path and screenshot_path.exists():
            messages[1]["content"] = [
                {"type": "text", "text": messages[1]["content"]},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._encode_image(screenshot_path),
                    }
                }
            ]
        
        response = await self._call_llm(messages)
        
        return TextGeneration(
            text=response.strip(),
            confidence=0.8,  # LLM confidence is not calibrated
            reasoning="Generated based on task context and field label",
        )
    
    async def replan(
        self,
        task: str,
        current_context: str,
        failure_reason: str,
        screenshot_path: Optional[Path] = None,
    ) -> Plan:
        """
        Replan when the current approach isn't working.
        
        Args:
            task: Original task
            current_context: Current state/context
            failure_reason: Why the current approach failed
            screenshot_path: Optional screenshot for context
            
        Returns:
            Updated plan
        """
        messages = [
            {
                "role": "system",
                "content": "You are a task planning assistant. When a plan fails, analyze why and create a revised approach."
            },
            {
                "role": "user",
                "content": f"Task: {task}\n\nCurrent context: {current_context}\n\nFailure reason: {failure_reason}\n\nCreate a revised plan to complete the task."
            }
        ]
        
        # Add screenshot if provided
        if screenshot_path and screenshot_path.exists():
            messages[1]["content"] = [
                {"type": "text", "text": messages[1]["content"]},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": self._encode_image(screenshot_path),
                    }
                }
            ]
        
        response = await self._call_llm(messages)
        
        return self._parse_plan_response(response)
    
    def _create_plan_prompt(
        self,
        task: str,
        current_context: str,
        screenshot_path: Optional[Path],
    ) -> str:
        """Create a prompt for plan generation."""
        prompt = f"Task: {task}\n\n"
        prompt += f"Current context: {current_context}\n\n"
        prompt += "Break this task down into clear, actionable steps. "
        prompt += "Each step should be something that can be accomplished by clicking or typing in a desktop application. "
        prompt += "Format your response as a numbered list of steps, followed by your reasoning."
        
        if screenshot_path:
            prompt += "\n\nA screenshot of the current state is also provided for visual context."
        
        return prompt
    
    def _create_text_prompt(
        self,
        task: str,
        field_label: str,
        current_value: Optional[str],
    ) -> str:
        """Create a prompt for text generation."""
        prompt = f"Task: {task}\n\n"
        prompt += f"Field label: {field_label}\n"
        
        if current_value:
            prompt += f"Current value: {current_value}\n"
        
        prompt += "\nGenerate appropriate text to enter in this field. "
        prompt += "Consider the task context and what would be a reasonable value. "
        prompt += "Respond with just the text, no explanation."
        
        return prompt
    
    def _format_elements(self, elements: List[UIElement]) -> str:
        """Format UI elements for the prompt."""
        lines = []
        for elem in elements:
            line = f"{elem.element_id}: {elem.role}"
            if elem.label:
                line += f" - {elem.label}"
            if elem.value:
                line += f" (value: {elem.value})"
            lines.append(line)
        return "\n".join(lines)
    
    def _encode_image(self, image_path: Path) -> str:
        """Encode an image to base64 for API transmission."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    async def _call_llm(self, messages: List[Dict[str, Any]]) -> str:
        """Call the LLM API and return the response text."""
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000,
                }
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"LLM API call failed: {e}")
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    def _parse_plan_response(self, response: str) -> Plan:
        """Parse the LLM response into a Plan object."""
        # This is a simplified parser - production would need robust parsing
        lines = response.strip().split("\n")
        
        steps = []
        reasoning = ""
        
        in_steps = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for numbered steps
            if line[0].isdigit() and line[1] in ".)":
                in_steps = True
                step_text = line[2:].strip()
                if step_text:
                    steps.append(step_text)
            elif in_steps:
                # Continue collecting steps until we hit reasoning
                if line.lower().startswith("reasoning") or line.lower().startswith("because"):
                    in_steps = False
                    reasoning = line
                else:
                    steps.append(line)
            else:
                reasoning += line + " "
        
        if not steps:
            # Fallback: treat the whole response as reasoning and create a single step
            reasoning = response
            steps = ["Complete the task as described"]
        
        return Plan(
            steps=steps,
            reasoning=reasoning.strip(),
            estimated_steps=len(steps),
        )
    
    async def shutdown(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()