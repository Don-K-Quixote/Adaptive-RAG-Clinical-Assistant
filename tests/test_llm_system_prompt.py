"""Tests that SYSTEM_PROMPT is correctly forwarded by both LLM providers."""

from unittest.mock import MagicMock

from src.llm.ollama_provider import OllamaProvider
from src.llm.openai_provider import OpenAIProvider

SYSTEM = "You must answer only from context."
PROMPT = "What is RECIST?"


class TestOpenAIProviderSystemPrompt:
    def _make_mock_client(self) -> MagicMock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        mock_response.usage.total_tokens = 10
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_system_prompt_sent_as_first_message(self):
        provider = OpenAIProvider(model="gpt-4o-mini", api_key="test-key")
        provider._client = self._make_mock_client()

        provider.generate(prompt=PROMPT, system_prompt=SYSTEM)

        messages = provider._client.chat.completions.create.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SYSTEM

    def test_empty_system_prompt_omits_system_message(self):
        provider = OpenAIProvider(model="gpt-4o-mini", api_key="test-key")
        provider._client = self._make_mock_client()

        provider.generate(prompt=PROMPT, system_prompt="")

        messages = provider._client.chat.completions.create.call_args.kwargs["messages"]
        roles = [m["role"] for m in messages]
        assert "system" not in roles


class TestOllamaProviderSystemPrompt:
    def _make_mock_client(self) -> MagicMock:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"content": "ok"}}
        return mock_client

    def test_system_prompt_sent_as_first_message(self):
        provider = OllamaProvider(model="llama3.1:8b")
        provider._client = self._make_mock_client()

        provider.generate(prompt=PROMPT, system_prompt=SYSTEM)

        messages = provider._client.chat.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SYSTEM

    def test_empty_system_prompt_omits_system_message(self):
        provider = OllamaProvider(model="llama3.1:8b")
        provider._client = self._make_mock_client()

        provider.generate(prompt=PROMPT, system_prompt="")

        messages = provider._client.chat.call_args.kwargs["messages"]
        roles = [m["role"] for m in messages]
        assert "system" not in roles
