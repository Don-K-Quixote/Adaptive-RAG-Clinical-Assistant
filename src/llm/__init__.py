"""
LLM Provider Module for Adaptive RAG Clinical Assistant.

This module provides a unified interface for both cloud (OpenAI) and local (Ollama)
LLM providers, enabling seamless switching between deployment modes.

Quick Start:
    # Using factory (recommended)
    from src.llm import LLMFactory, get_llm

    # Create from config
    llm = LLMFactory.create({"provider": "ollama", "model": "llama3.1"})

    # Quick creation
    llm = get_llm("ollama", "biomistral")

    # Generate response
    response = llm.generate(
        prompt="What is RECIST 1.1?",
        system_prompt="You are a clinical trials expert."
    )

Available Providers:
    - openai: GPT-4, GPT-4-Turbo, GPT-3.5-Turbo (requires API key)
    - ollama: Llama 3.1, Mistral, BioMistral, Gemma 2, Phi-3, LLaVA (local)

Available Models (Ollama - verified):
    - llama3.1:8b        - Best general performance
    - mistral:7b         - Fast and efficient
    - biomistral         - Medical domain fine-tuned
    - gemma2:9b          - Strong reasoning
    - phi3:mini          - Compact and fast
    - llava:7b           - Vision-language model
"""

from .base import LLMProvider, LLMResponse
from .factory import LLMFactory, get_llm
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

__all__ = [
    # Base classes
    "LLMProvider",
    "LLMResponse",
    # Provider implementations
    "OpenAIProvider",
    "OllamaProvider",
    # Factory and convenience functions
    "LLMFactory",
    "get_llm",
]

__version__ = "1.0.0"
