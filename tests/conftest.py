"""
Shared fixtures for Adaptive RAG Clinical Assistant tests.
"""

import pytest
from langchain_core.documents import Document


@pytest.fixture
def sample_documents():
    """Create sample documents with metadata for testing."""
    return [
        Document(
            page_content="RECIST 1.1 defines complete response as disappearance of all target lesions.",
            metadata={"chunk_id": 0, "page": 1, "doc_name": "irc_charter.pdf"},
        ),
        Document(
            page_content="The imaging schedule requires baseline CT within 28 days prior to randomization.",
            metadata={"chunk_id": 1, "page": 2, "doc_name": "irc_charter.pdf"},
        ),
        Document(
            page_content="Partial response is defined as at least 30% decrease in sum of diameters.",
            metadata={"chunk_id": 2, "page": 3, "doc_name": "irc_charter.pdf"},
        ),
        Document(
            page_content="Progressive disease is at least 20% increase in sum of diameters.",
            metadata={"chunk_id": 3, "page": 4, "doc_name": "irc_charter.pdf"},
        ),
        Document(
            page_content="Stable disease is neither sufficient shrinkage nor sufficient increase.",
            metadata={"chunk_id": 4, "page": 5, "doc_name": "irc_charter.pdf"},
        ),
    ]


@pytest.fixture
def novice_profile():
    return {"role": "Research Coordinator (New)", "experience_years": 0}


@pytest.fixture
def expert_profile():
    return {"role": "Principal Investigator", "experience_years": 15}


@pytest.fixture
def regulatory_profile():
    return {"role": "Regulatory Affairs Specialist", "experience_years": 8}


@pytest.fixture
def executive_profile():
    return {"role": "VP Clinical Development", "experience_years": 20}


@pytest.fixture
def intermediate_profile():
    return {"role": "Clinical Research Coordinator", "experience_years": 4}
