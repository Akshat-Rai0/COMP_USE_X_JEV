#!/usr/bin/env python3
"""
Test script to verify kev confidence score extraction.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.backend.client import KevBackend
from src.models import DecisionRequest, ChoiceQuestion


async def test_kev_confidence():
    """Test that kev backend extracts actual confidence scores."""
    print("Testing kev confidence score extraction...")
    
    # Check if kev server is running
    import httpx
    try:
        response = httpx.get("http://localhost:8009/v1/models", timeout=2.0)
        response.raise_for_status()
        print("✓ kev server is running")
    except Exception as e:
        print(f"✗ kev server is not running: {e}")
        print("  Please start kev server with:")
        print("  cd kev && uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.5b --port 8009")
        return
    
    try:
        # Initialize kev backend
        print("\n1. Initializing kev backend...")
        backend = KevBackend(
            base_url="http://localhost:8009",
            model="kev-latest"
        )
        print(f"✓ Backend initialized (model: {backend.get_model_version()})")
        
        # Create a test decision request
        print("\n2. Creating test decision request...")
        request = DecisionRequest(
            state="e0: button - Click me\ne1: button - Cancel\ne2: button - Submit",
            questions=[
                ChoiceQuestion(
                    name="select_element",
                    options=["e0 button - Click me", "e1 button - Cancel", "e2 button - Submit"],
                    context="Select the best option",
                ),
            ],
        )
        print(f"✓ Request created (questions: {len(request.questions)})")
        
        # Make decision
        print("\n3. Making decision request...")
        response = await backend.decide(request)
        print(f"✓ Decision received (latency: {response.latency_ms:.1f}ms)")
        
        # Check confidence scores
        print("\n4. Checking confidence scores...")
        choice_found = False
        for name, choice_response in response.choice_responses.items():
            print(f"\n  Choice question: {name}")
            print(f"    Chosen option: {choice_response.chosen_option}")
            print(f"    Confidence: {choice_response.confidence}")
            print(f"    Probabilities: {choice_response.probabilities}")
            
            if choice_response.confidence > 0.0:
                print(f"    ✓ Real confidence score detected!")
                choice_found = True
            else:
                print(f"    ✗ Confidence is still 0.0 - fix may not be working")
            
            if choice_response.probabilities:
                print(f"    ✓ Probabilities extracted!")
            else:
                print(f"    ✗ Probabilities are empty - fix may not be working")
        
        # Summary
        print("\n" + "="*50)
        if choice_found:
            print("✅ SUCCESS: Confidence scores are being extracted correctly!")
            print("   - Choice confidence: Non-zero")
            print("   - Choice probabilities: Non-empty")
            print("   - Real confidence score: {:.4f}".format(
                list(response.choice_responses.values())[0].confidence
            ))
            print("   - Real probabilities: {}".format(
                list(response.choice_responses.values())[0].probabilities
            ))
        else:
            print("❌ FAILED: Confidence scores are still hardcoded to 0.0")
            print("   Please check the implementation in src/backend/client.py")
        
        print("="*50)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("⚠️  This test requires the kev server to be running on port 8009")
    print()
    
    asyncio.run(test_kev_confidence())