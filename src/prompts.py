"""
Adaptive Prompt Generation
===========================

Generates persona-aware and query-type-aware prompts for response generation.

The prompt system adapts based on:
1. User expertise level (Novice → Executive)
2. Query type (Definition, Procedure, Compliance, etc.)
3. Response configuration (tables, color coding, length)
"""

from langchain_core.documents import Document

from .config import RESPONSE_COLORS
from .personas import ResponseConfig, UserType
from .query_classifier import QueryType
from .utils import format_source_reference

# System-level anti-hallucination instruction passed to every LLM call.
SYSTEM_PROMPT = (
    "You are a clinical trials document assistant. "
    "You answer questions strictly based on the document context provided by the user. "
    "Never fabricate information, invent citations, or draw on knowledge outside the provided context. "
    "If the document context does not contain enough information to answer a question fully, "
    "say so explicitly and describe what is missing rather than guessing."
)

# Grounding instruction embedded inside every user prompt, immediately before the question.
_GROUNDING_INSTRUCTION = """GROUNDING REQUIREMENT:
Answer using ONLY the information in the CONTEXT FROM DOCUMENT section above. \
Do not use prior knowledge, external sources, or infer facts not explicitly stated in the context. \
If the context does not contain sufficient information to fully answer the question, \
explicitly state what is not covered rather than speculating."""


class ResponseStyler:
    """
    Generates adaptive prompts based on user persona and query type.

    Creates tailored prompts that instruct the LLM to adapt its response
    style, complexity, and formatting based on the user's expertise level
    and the type of question being asked.
    """

    # User type instruction templates
    USER_TYPE_INSTRUCTIONS = {
        UserType.NOVICE: """
AUDIENCE: Novice user (new to clinical trials)

REQUIREMENTS:
- Use simple, non-technical language throughout
- Define ALL medical/clinical terms in parentheses when first used
- Use bullet points for clarity and easy scanning
- Include a "📌 Key Takeaway" summary at the end (2-3 sentences)
- Avoid jargon; if unavoidable, explain immediately after using
- Use analogies to everyday concepts where helpful
- Keep sentences short and direct
""",
        UserType.INTERMEDIATE: """
AUDIENCE: Intermediate user (familiar with clinical trial basics)

REQUIREMENTS:
- Use standard clinical trial terminology without excessive explanation
- Provide practical, actionable guidance
- Include specific examples where relevant
- Balance technical accuracy with readability
- Reference relevant sections/pages when citing the document
- Assume familiarity with terms like: protocol, endpoint, IRB, CRF
""",
        UserType.EXPERT: """
AUDIENCE: Expert user (clinical trial professional)

REQUIREMENTS:
- Use precise medical and regulatory terminology
- Provide comprehensive, detailed analysis
- Include nuances, edge cases, and exceptions
- Reference specific regulations when relevant (21 CFR Part 11, ICH-GCP E6(R2))
- Discuss implications, rationale, and potential issues
- Assume familiarity with RECIST, GCP, regulatory submissions
- Include cross-references to related document sections
""",
        UserType.REGULATORY: """
AUDIENCE: Regulatory affairs professional / QA / Compliance

REQUIREMENTS:
- Focus on compliance and regulatory requirements
- Cite specific regulations and guidance documents
- Highlight audit/inspection considerations
- Use formal, precise language suitable for regulatory documents
- Emphasize documentation requirements and traceability
- Note any gaps or areas requiring additional documentation
- Reference: FDA guidance, EMA guidelines, ICH-GCP as applicable
""",
        UserType.EXECUTIVE: """
AUDIENCE: Executive / Decision maker / Sponsor

REQUIREMENTS:
- Start with an executive summary (2-3 sentences maximum)
- Focus on business impact, risks, and key decisions
- Use metrics and quantifiable information where available
- Be concise and action-oriented
- End with clear recommendations or next steps
- Avoid technical details unless directly relevant to decisions
- Highlight timeline and resource implications
""",
    }

    # Query type formatting instructions
    QUERY_TYPE_INSTRUCTIONS = {
        QueryType.DEFINITION: """
FORMAT FOR DEFINITION QUERY:
- Start with a clear, one-sentence definition
- Then expand with context and relevance
- Include examples if helpful
""",
        QueryType.PROCEDURE: """
FORMAT FOR PROCEDURE QUERY:
- Use numbered steps (1., 2., 3., ...)
- Include important considerations or warnings at each step
- Note any prerequisites or dependencies
- Highlight common mistakes to avoid
""",
        QueryType.COMPLIANCE: """
FORMAT FOR COMPLIANCE QUERY:
- Cite specific regulations and guidance documents
- Clearly state requirements vs. recommendations
- Highlight audit/inspection considerations
- Note documentation requirements
""",
        QueryType.COMPARISON: """
FORMAT FOR COMPARISON QUERY:
- Use a comparison table with clear headers
- Highlight key differences in separate rows
- Include a summary of when to use each option
""",
        QueryType.NUMERICAL: """
FORMAT FOR NUMERICAL QUERY:
- Lead with the specific number/value immediately
- Then provide context and source
- Include any relevant ranges or thresholds
""",
        QueryType.TIMELINE: """
FORMAT FOR TIMELINE QUERY:
- Present information chronologically
- Include specific timeframes and durations
- Note any dependencies or critical paths
- Highlight deadlines or time-sensitive items
""",
        QueryType.SAFETY: """
FORMAT FOR SAFETY QUERY:
- Use severity classification where applicable
- List by frequency or importance
- Clearly distinguish between different severity levels
- Include reporting requirements if relevant
""",
        QueryType.ELIGIBILITY: """
FORMAT FOR ELIGIBILITY QUERY:
- Separate inclusion and exclusion criteria clearly
- Use checklist format (✓ / ✗)
- Note any clarifications or edge cases
- Include relevant measurement thresholds
""",
        QueryType.COMPLEX: """
FORMAT FOR COMPLEX QUERY:
- Break down into logical components
- Address each part systematically
- Provide cross-references between related parts
- Summarize key points at the end
""",
    }

    @classmethod
    def generate_prompt(cls, context: str, query: str, config: ResponseConfig) -> str:
        """
        Generate an adaptive prompt based on configuration.

        Args:
            context: Retrieved document context
            query: User's question
            config: ResponseConfig with user type and settings

        Returns:
            Complete prompt string for LLM
        """
        # Build prompt components
        user_instructions = cls.USER_TYPE_INSTRUCTIONS.get(
            config.user_type, cls.USER_TYPE_INSTRUCTIONS[UserType.INTERMEDIATE]
        )

        query_type = (
            QueryType(config.query_type)
            if isinstance(config.query_type, str)
            else config.query_type
        )
        query_instructions = cls.QUERY_TYPE_INSTRUCTIONS.get(
            query_type, cls.QUERY_TYPE_INSTRUCTIONS[QueryType.DEFINITION]
        )

        # Build formatting instructions
        formatting = []

        if config.use_tables:
            formatting.append("- Use Markdown tables for structured data")

        if config.use_bullet_points:
            formatting.append("- Use bullet points for lists and key points")

        if config.color_coding:
            formatting.append(f"""
- Use HTML color coding for emphasis:
  * <span style="color:{RESPONSE_COLORS["critical"]}">**CRITICAL:**</span> for safety-critical information
  * <span style="color:{RESPONSE_COLORS["warning"]}">**⚠️ WARNING:**</span> for important warnings
  * <span style="color:{RESPONSE_COLORS["positive"]}">**✓ COMPLIANT:**</span> for compliance confirmations
""")

        formatting.append(f"- Target response length: ~{config.max_length} words")

        if config.include_references:
            formatting.append(
                "- When referencing specific information, cite the source number "
                "(e.g., 'According to [Source 2]...' or 'As stated in [Source 1]...')"
            )

        if config.include_key_takeaway:
            formatting.append("- Include a '📌 Key Takeaway' section at the end")

        if config.include_executive_summary:
            formatting.append("- Start with a brief executive summary (2-3 sentences)")

        if config.include_recommendations:
            formatting.append("- End with clear recommendations or next steps")

        formatting_text = "\n".join(formatting) if formatting else ""

        # Assemble complete prompt
        prompt = f"""You are an AI assistant helping with clinical trial documentation.

{user_instructions}

{query_instructions}

ADDITIONAL FORMATTING:
{formatting_text}

CONTEXT FROM DOCUMENT:
{context}

{_GROUNDING_INSTRUCTION}

QUESTION: {query}

ANSWER:"""

        return prompt


def build_adaptive_prompt(documents: list[Document], query: str, config: ResponseConfig) -> str:
    """
    Build an adaptive prompt from retrieved documents.

    Convenience function that formats document context and generates
    the complete adaptive prompt.

    Args:
        documents: List of retrieved Document objects
        query: User's question
        config: ResponseConfig with user type and settings

    Returns:
        Complete prompt string for LLM
    """
    # Format context from documents with source attribution
    context_parts = []
    for i, doc in enumerate(documents, 1):
        source_ref = format_source_reference(doc, index=i)
        context_parts.append(f"{source_ref}\n{doc.page_content}")

    context = "\n\n---\n\n".join(context_parts)

    return ResponseStyler.generate_prompt(context, query, config)
