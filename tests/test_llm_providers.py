#!/usr/bin/env python3
"""
Test script for LLM providers.

Run this to verify your Ollama setup is working correctly.

Usage:
    python tests/test_llm_providers.py
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm import LLMFactory, OllamaProvider, get_llm


def test_ollama_availability():
    """Test if Ollama is running and models are available."""
    print("=" * 60)
    print("Testing Ollama Availability")
    print("=" * 60)

    provider = OllamaProvider()

    if not provider.is_available():
        print("❌ Ollama is not available!")
        print("   Make sure Ollama is running: ollama serve")
        return False

    print("✅ Ollama is running")

    # List available models
    models = provider.list_available_models()
    print(f"\n📦 Downloaded models ({len(models)}):")
    for model in models:
        print(f"   - {model}")

    return True


def test_model_inference(model_name: str):
    """Test inference with a specific model."""
    print(f"\n{'=' * 60}")
    print(f"Testing Model: {model_name}")
    print("=" * 60)

    try:
        llm = get_llm("ollama", model_name)

        # Check availability
        if not llm.is_available():
            print(f"❌ Model '{model_name}' not available")
            return False

        print(f"✅ Model loaded: {llm.get_model_info()['model']}")

        # Test generation
        prompt = "In one sentence, what is RECIST 1.1?"
        system_prompt = "You are a clinical trials expert. Be concise."

        print(f"\n📝 Prompt: {prompt}")
        print("⏳ Generating response...")

        response = llm.generate_with_metadata(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=100
        )

        print(f"\n✅ Response ({response.latency_ms:.0f}ms):")
        print(f"   {response.content[:200]}...")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_model_comparison():
    """Compare responses from different models."""
    print(f"\n{'=' * 60}")
    print("Model Comparison Test")
    print("=" * 60)

    models_to_test = [
        "llama3.1:8b",
        "mistral:7b",
        "adrienbrault/biomistral-7b:Q4_K_M",
    ]

    prompt = "What are target lesions in RECIST 1.1? (1-2 sentences)"
    system_prompt = "You are a clinical imaging expert. Be precise and concise."

    results = []

    for model in models_to_test:
        try:
            llm = get_llm("ollama", model)
            if not llm.is_available():
                print(f"⚠️  {model}: Not available, skipping")
                continue

            start = time.time()
            response = llm.generate(prompt, system_prompt, max_tokens=100)
            latency = (time.time() - start) * 1000

            results.append({
                "model": model,
                "response": response[:150],
                "latency_ms": latency
            })

            print(f"\n📊 {model} ({latency:.0f}ms):")
            print(f"   {response[:150]}...")

        except Exception as e:
            print(f"❌ {model}: {e}")

    return results


def test_factory_methods():
    """Test LLMFactory convenience methods."""
    print(f"\n{'=' * 60}")
    print("Testing Factory Methods")
    print("=" * 60)

    # Test create_for_medical
    print("\n1. create_for_medical(local=True):")
    try:
        llm = LLMFactory.create_for_medical(local=True)
        print(f"   ✅ Created: {llm.get_model_info()['model']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test get_recommended_models
    print("\n2. get_recommended_models():")
    recommendations = OllamaProvider.get_recommended_models()
    for use_case, info in recommendations.items():
        print(f"   {use_case}: {info['model']} - {info['reason']}")

    # Test get_available_providers
    print("\n3. get_available_providers():")
    status = LLMFactory.get_available_providers()
    for provider, info in status.items():
        available = "✅" if info.get("available") else "❌"
        print(f"   {available} {provider}: {info.get('default_model', 'N/A')}")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LLM Provider Test Suite")
    print("=" * 60)

    # Test 1: Ollama availability
    if not test_ollama_availability():
        print("\n⚠️  Ollama not running. Start with: ollama serve")
        sys.exit(1)

    # Test 2: Individual model inference
    test_model_inference("llama3.1:8b")

    # Test 3: Model comparison
    test_model_comparison()

    # Test 4: Factory methods
    test_factory_methods()

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
