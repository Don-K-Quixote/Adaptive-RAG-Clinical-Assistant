"""
Tests for adaptive prompt generation and hallucination-prevention safeguards.

Validates that every generated prompt contains the grounding instruction,
that include_references correctly emits a citation directive, and that
source references are formatted consistently via format_source_reference().
"""

import pytest
from langchain_core.documents import Document

from src.personas import ResponseConfig, UserType, get_response_config
from src.prompts import SYSTEM_PROMPT, build_adaptive_prompt
from src.query_classifier import QueryType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_docs():
    return [
        Document(
            page_content="RECIST 1.1 defines complete response as disappearance of all target lesions.",
            metadata={"chunk_id": 0, "page": 1, "doc_name": "irc_charter.pdf"},
        ),
        Document(
            page_content="Partial response is at least 30% decrease in sum of diameters.",
            metadata={"chunk_id": 1, "page": 2, "doc_name": "irc_charter.pdf"},
        ),
    ]


@pytest.fixture
def novice_config():
    return get_response_config(UserType.NOVICE, QueryType.DEFINITION.value)


@pytest.fixture
def expert_config():
    return get_response_config(UserType.EXPERT, QueryType.COMPLIANCE.value)


@pytest.fixture
def regulatory_config():
    return get_response_config(UserType.REGULATORY, QueryType.COMPLIANCE.value)


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT tests
# ---------------------------------------------------------------------------


class TestSystemPrompt:
    """Verify the system-level anti-hallucination instruction."""

    def test_system_prompt_is_non_empty(self):
        assert SYSTEM_PROMPT and len(SYSTEM_PROMPT) > 20

    def test_system_prompt_forbids_fabrication(self):
        assert "fabricat" in SYSTEM_PROMPT.lower() or "never" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_context(self):
        assert "context" in SYSTEM_PROMPT.lower()

    def test_system_prompt_instructs_to_disclose_gaps(self):
        # Should instruct the model to say when information is missing.
        lower = SYSTEM_PROMPT.lower()
        assert "missing" in lower or "not contain" in lower or "explicitly" in lower


# ---------------------------------------------------------------------------
# Grounding instruction tests
# ---------------------------------------------------------------------------


class TestGroundingInstruction:
    """Every generated prompt must contain the grounding constraint."""

    def test_grounding_present_for_novice(self, sample_docs, novice_config):
        prompt = build_adaptive_prompt(sample_docs, "What is RECIST?", novice_config)
        assert "GROUNDING REQUIREMENT" in prompt

    def test_grounding_present_for_expert(self, sample_docs, expert_config):
        prompt = build_adaptive_prompt(
            sample_docs, "Describe compliance requirements.", expert_config
        )
        assert "GROUNDING REQUIREMENT" in prompt

    def test_grounding_present_for_regulatory(self, sample_docs, regulatory_config):
        prompt = build_adaptive_prompt(
            sample_docs, "What are audit obligations?", regulatory_config
        )
        assert "GROUNDING REQUIREMENT" in prompt

    def test_grounding_only_uses_context_phrase(self, sample_docs, novice_config):
        prompt = build_adaptive_prompt(sample_docs, "What is a lesion?", novice_config)
        assert "ONLY" in prompt or "only" in prompt

    def test_grounding_positioned_after_context(self, sample_docs, novice_config):
        """Grounding instruction must appear after the CONTEXT block."""
        prompt = build_adaptive_prompt(sample_docs, "What is RECIST?", novice_config)
        context_pos = prompt.find("CONTEXT FROM DOCUMENT")
        grounding_pos = prompt.find("GROUNDING REQUIREMENT")
        question_pos = prompt.find("QUESTION:")
        assert context_pos < grounding_pos < question_pos

    def test_grounding_instructs_speculative_disclosure(self, sample_docs, novice_config):
        """Must instruct the model to disclose gaps rather than speculate."""
        prompt = build_adaptive_prompt(sample_docs, "What is a lesion?", novice_config)
        assert "speculating" in prompt or "speculate" in prompt or "explicitly state" in prompt


# ---------------------------------------------------------------------------
# include_references flag tests
# ---------------------------------------------------------------------------


class TestIncludeReferences:
    """The include_references flag must add a citation directive when True."""

    def test_citation_instruction_present_when_references_enabled(self, sample_docs):
        config = get_response_config(UserType.EXPERT, QueryType.COMPLIANCE.value)
        # expert config sets include_references=True
        assert config.include_references is True
        prompt = build_adaptive_prompt(sample_docs, "What regulations apply?", config)
        assert "[Source" in prompt or "cite the source" in prompt.lower()

    def test_citation_instruction_absent_for_novice(self, sample_docs):
        config = get_response_config(UserType.NOVICE, QueryType.DEFINITION.value)
        # novice config does not set include_references
        assert config.include_references is False
        prompt = build_adaptive_prompt(sample_docs, "What is randomization?", config)
        # Grounding still present, but no citation instruction in formatting
        assert "cite the source number" not in prompt.lower()

    def test_citation_instruction_when_manually_enabled(self, sample_docs):
        config = ResponseConfig(
            user_type=UserType.INTERMEDIATE,
            query_type=QueryType.DEFINITION.value,
            include_references=True,
        )
        prompt = build_adaptive_prompt(sample_docs, "Define endpoint.", config)
        lower = prompt.lower()
        assert "cite the source" in lower or "[source" in lower


# ---------------------------------------------------------------------------
# Source reference formatting tests
# ---------------------------------------------------------------------------


class TestSourceReferenceFormatting:
    """build_adaptive_prompt must format source tags consistently."""

    def test_source_tags_present_in_context(self, sample_docs, novice_config):
        prompt = build_adaptive_prompt(sample_docs, "What is RECIST?", novice_config)
        assert "[Source 1:" in prompt
        assert "[Source 2:" in prompt

    def test_source_tags_include_page(self, sample_docs, novice_config):
        prompt = build_adaptive_prompt(sample_docs, "What is RECIST?", novice_config)
        assert "Page 1" in prompt
        assert "Page 2" in prompt

    def test_source_tags_include_chunk(self, sample_docs, novice_config):
        prompt = build_adaptive_prompt(sample_docs, "What is RECIST?", novice_config)
        assert "Chunk 0" in prompt
        assert "Chunk 1" in prompt

    def test_empty_documents_still_builds_prompt(self, novice_config):
        """Empty document list should produce a prompt with empty context."""
        prompt = build_adaptive_prompt([], "What is RECIST?", novice_config)
        assert "QUESTION: What is RECIST?" in prompt
        assert "GROUNDING REQUIREMENT" in prompt
