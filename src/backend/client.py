"""
Decision Backend Client - Unified interface for Jev, kev, and LLM backends.

This module provides a unified DecisionBackend protocol that can be implemented
by different backends:
- JevBackend: TypeSafe's Jev API (remote)
- KevBackend: Local kev server (drop-in Jev replacement)
- LLMBackend: OpenRouter LLM wrapped to match Jev's interface
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Union, Optional
from dataclasses import dataclass

try:
    from typesafe_sdk import TypeSafeClient
    from typesafe_sdk import Choice, Noul
    TYPESAFE_SDK_AVAILABLE = True
except ImportError:
    TYPESAFE_SDK_AVAILABLE = False
    print("Warning: typesafe-sdk not installed. JevBackend will not be available.")

import httpx

from src.models import (
    DecisionRequest,
    DecisionResponse,
    ChoiceQuestion,
    NoulQuestion,
    ChoiceResponse,
    NoulResponse,
)


class DecisionBackend(ABC):
    """Abstract interface for decision backends."""
    
    @abstractmethod
    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        """
        Make a decision based on the current state.
        
        Args:
            request: Decision request with state and questions
            
        Returns:
            Decision response with answers and confidence scores
        """
        pass
    
    @abstractmethod
    def get_model_version(self) -> str:
        """Get the model version being used."""
        pass


class JevBackend(DecisionBackend):
    """TypeSafe Jev API backend."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.typesafe.ai", model: str = "jev-latest"):
        """
        Initialize Jev backend.
        
        Args:
            api_key: TypeSafe API key
            base_url: TypeSafe API base URL
            model: Jev model version to use
        """
        if not TYPESAFE_SDK_AVAILABLE:
            raise ImportError("typesafe-sdk is not installed. Install it with: pip install typesafe-sdk")
        
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = TypeSafeClient(api_key=api_key, base_url=base_url, model=model)
    
    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        """Make a decision using Jev API."""
        start_time = time.time()
        
        # Convert our questions to TypeSafe format
        questions = []
        for q in request.questions:
            if isinstance(q, ChoiceQuestion):
                questions.append(Choice(
                    name=q.name,
                    options=q.options,
                ))
            elif isinstance(q, NoulQuestion):
                questions.append(Noul(
                    name=q.name,
                    statement=q.statement,
                ))
        
        # Call TypeSafe API
        try:
            response = await self.client.system_one_async(
                state=request.state,
                questions=questions,
            )
        except Exception as e:
            raise RuntimeError(f"Jev API call failed: {e}")
        
        # Parse response
        choice_responses = {}
        noul_responses = {}
        
        for q_name, answer in response.answers.items():
            if hasattr(answer, 'chosen_option'):
                choice_responses[q_name] = ChoiceResponse(
                    chosen_option=answer.chosen_option,
                    confidence=answer.confidence,
                    probabilities=answer.probabilities if hasattr(answer, 'probabilities') else {},
                )
            elif hasattr(answer, 'answer'):
                noul_responses[q_name] = NoulResponse(
                    answer=answer.answer,
                    confidence=answer.confidence,
                    probability_true=answer.probability_true if hasattr(answer, 'probability_true') else 0.0,
                )
        
        latency_ms = (time.time() - start_time) * 1000
        
        return DecisionResponse(
            choice_responses=choice_responses,
            noul_responses=noul_responses,
            model_version=self.model,
            latency_ms=latency_ms,
        )
    
    def get_model_version(self) -> str:
        """Get the Jev model version."""
        return self.model
    
    async def shutdown(self) -> None:
        """Close the TypeSafe client."""
        # TypeSafeClient doesn't have async close, no cleanup needed
        pass


class KevBackend(DecisionBackend):
    """Local kev server backend (drop-in Jev replacement)."""
    
    def __init__(self, base_url: str = "http://localhost:8009", model: str = "kev-latest"):
        """
        Initialize kev backend.
        
        Args:
            base_url: Local kev server URL
            model: Model identifier (for version tracking)
        """
        self.base_url = base_url
        self.model = model
        
        if TYPESAFE_SDK_AVAILABLE:
            self.client = TypeSafeClient(
                api_key="local",
                base_url=base_url,
                model=model,
            )
        else:
            raise ImportError("typesafe-sdk is required for KevBackend")
    
    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        """Make a decision using local kev server via TypeSafe SDK."""
        start_time = time.time()
        
        # Convert our request to TypeSafe SDK format
        questions = {}
        
        for q in request.questions:
            if isinstance(q, ChoiceQuestion):
                # Convert ChoiceQuestion to TypeSafe Choice format
                # TypeSafe Choice requires criteria to be a dict with string keys and None values
                criteria = {str(option): None for option in q.options}
                questions[q.name] = Choice(
                    criteria=criteria,
                    instructions=q.context or "Select the best option",
                )
            elif isinstance(q, NoulQuestion):
                # Convert NoulQuestion to TypeSafe Noul format
                questions[q.name] = Noul(instructions=q.statement or "Answer yes or no")
        
        # Call kev server via TypeSafe SDK
        try:
            response = self.client.system_one(
                state=request.state,
                questions=questions,
            )
        except Exception as e:
            raise RuntimeError(f"kev server call failed: {e}")
        
        # Parse response
        choice_responses = {}
        noul_responses = {}
        
        # TypeSafe SDK returns answers in .choices and .nouls
        for name, choice_answer in response.choices.items():
            choice_responses[name] = ChoiceResponse(
                chosen_option=choice_answer.choice,
                confidence=choice_answer.confidence,  # Extract actual confidence from response
                probabilities=choice_answer.probabilities,  # Extract actual probabilities from response
            )
        
        for name, noul_answer in response.nouls.items():
            # NoulAnswer only has 'noul' (float), derive probability_true from it
            # noul is likely 0.0 for false, 1.0 for true
            probability_true = float(noul_answer.noul)
            
            noul_responses[name] = NoulResponse(
                answer=noul_answer.noul >= 0.5,  # Convert to boolean
                confidence=0.5,  # Noul doesn't provide confidence, use neutral value
                probability_true=probability_true,  # Derive from noul value
            )
        
        latency_ms = (time.time() - start_time) * 1000
        
        return DecisionResponse(
            choice_responses=choice_responses,
            noul_responses=noul_responses,
            model_version=self.model,
            latency_ms=latency_ms,
        )
    
    def get_model_version(self) -> str:
        """Get the kev model version."""
        return self.model
    
    async def shutdown(self) -> None:
        """Close the TypeSafe client."""
        # TypeSafeClient doesn't have async close, no cleanup needed
        pass


class LLMBackend(DecisionBackend):
    """OpenRouter LLM backend wrapped to match Jev's interface."""
    
    def __init__(self, api_key: str, model: str = "openai/gpt-4o-mini", base_url: str = "https://openrouter.ai/api/v1"):
        """
        Initialize LLM backend.
        
        Args:
            api_key: OpenRouter API key
            model: OpenRouter model to use
            base_url: OpenRouter API base URL
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            timeout=60.0,
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        """Make a decision using OpenRouter LLM with structured output."""
        start_time = time.time()
        
        # Convert questions to a prompt for the LLM
        prompt = self._create_prompt(request)
        
        # Call OpenRouter API
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a UI decision assistant. Answer questions about UI elements accurately."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                }
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"OpenRouter API call failed: {e}")
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        # Parse the LLM response (this is simplified - would need robust parsing)
        choice_responses = {}
        noul_responses = {}
        
        for q in request.questions:
            if isinstance(q, ChoiceQuestion):
                # This is a placeholder - actual implementation would parse LLM response
                choice_responses[q.name] = ChoiceResponse(
                    chosen_option=q.options[0] if q.options else "",
                    confidence=0.5,  # LLM doesn't provide calibrated confidence
                    probabilities={opt: 1.0/len(q.options) for opt in q.options} if q.options else {},
                )
            elif isinstance(q, NoulQuestion):
                # This is a placeholder - actual implementation would parse LLM response
                noul_responses[q.name] = NoulResponse(
                    answer=True,  # Placeholder
                    confidence=0.5,
                    probability_true=0.5,
                )
        
        latency_ms = (time.time() - start_time) * 1000
        
        return DecisionResponse(
            choice_responses=choice_responses,
            noul_responses=noul_responses,
            model_version=self.model,
            latency_ms=latency_ms,
        )
    
    def _create_prompt(self, request: DecisionRequest) -> str:
        """Create a prompt for the LLM from the decision request."""
        prompt = f"Current state:\n{request.state}\n\n"
        
        for q in request.questions:
            if isinstance(q, ChoiceQuestion):
                prompt += f"Question: {q.name}\n"
                prompt += f"Options: {', '.join(q.options)}\n"
                prompt += "Choose the best option.\n\n"
            elif isinstance(q, NoulQuestion):
                prompt += f"Question: {q.name}\n"
                prompt += f"Statement: {q.statement}\n"
                prompt += "Answer yes or no.\n\n"
        
        return prompt
    
    def get_model_version(self) -> str:
        """Get the LLM model version."""
        return self.model
    
    async def shutdown(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()


def create_backend(backend_type: str, **kwargs) -> DecisionBackend:
    """
    Factory function to create a decision backend.
    
    Args:
        backend_type: Type of backend ("jev", "kev", or "llm")
        **kwargs: Backend-specific configuration
        
    Returns:
        Configured decision backend instance
    """
    if backend_type == "jev":
        api_key = kwargs.get("api_key") or os.getenv("TYPESAFE_API_KEY")
        base_url = kwargs.get("base_url", os.getenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai"))
        model = kwargs.get("model", os.getenv("JEV_MODEL_VERSION", "jev-latest"))
        
        if not api_key:
            raise ValueError("TYPESAFE_API_KEY is required for Jev backend")
        
        return JevBackend(api_key=api_key, base_url=base_url, model=model)
    
    elif backend_type == "kev":
        base_url = kwargs.get("base_url", os.getenv("KEV_BASE_URL", "http://localhost:8009"))
        model = kwargs.get("model", os.getenv("KEV_MODEL", "kev-latest"))
        
        return KevBackend(base_url=base_url, model=model)
    
    elif backend_type == "llm":
        api_key = kwargs.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        base_url = kwargs.get("base_url", os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
        model = kwargs.get("model", os.getenv("PLANNER_MODEL", "openai/gpt-4o-mini"))
        
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for LLM backend")
        
        return LLMBackend(api_key=api_key, base_url=base_url, model=model)
    
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")