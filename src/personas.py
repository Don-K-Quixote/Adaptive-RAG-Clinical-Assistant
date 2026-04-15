"""
Persona Detection and Response Configuration
=============================================

Implements expertise-based user personas and adaptive response configuration.

User Types:
- NOVICE: New to clinical trials, needs simplified explanations
- INTERMEDIATE: Familiar with basics, needs practical guidance
- EXPERT: Clinical trial professional, needs technical depth
- REGULATORY: Compliance-focused, needs audit-ready responses
- EXECUTIVE: Decision maker, needs concise summaries with metrics
"""

import re
from dataclasses import dataclass
from enum import Enum

from .config import RESPONSE_LENGTH_LIMITS


class UserType(Enum):
    """User expertise levels for adaptive response generation."""

    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"
    REGULATORY = "regulatory"
    EXECUTIVE = "executive"

    @property
    def description(self) -> str:
        """Human-readable description of the user type."""
        descriptions = {
            UserType.NOVICE: "New to clinical trials, needs simplified explanations",
            UserType.INTERMEDIATE: "Familiar with basics, needs practical guidance",
            UserType.EXPERT: "Clinical trial professional, needs technical depth",
            UserType.REGULATORY: "Compliance-focused, needs audit-ready responses",
            UserType.EXECUTIVE: "Decision maker, needs concise summaries",
        }
        return descriptions.get(self, "Unknown user type")


@dataclass
class ResponseConfig:
    """Configuration for adaptive response generation."""

    user_type: UserType
    query_type: str  # Will be QueryType.value

    # Content settings
    include_examples: bool = True
    include_references: bool = False  # Enabled explicitly for EXPERT and REGULATORY only
    include_definitions: bool = False

    # Formatting settings
    detail_level: str = "medium"  # low, medium, high
    use_tables: bool = False
    use_bullet_points: bool = False
    color_coding: bool = True

    # Length settings
    max_length: int = 500

    # Special features
    include_key_takeaway: bool = False
    include_executive_summary: bool = False
    include_recommendations: bool = False

    def __post_init__(self):
        """Set max_length based on user_type if not explicitly set."""
        if self.max_length == 500:  # Default value
            self.max_length = RESPONSE_LENGTH_LIMITS.get(self.user_type.value, 500)


# ==============================================================================
# USER TYPE DETECTION
# ==============================================================================

# Role keywords for detection
ROLE_KEYWORDS = {
    UserType.REGULATORY: ["regulatory", "compliance", "quality", "qa", "audit", "inspector"],
    UserType.EXECUTIVE: [
        "director",
        "vp",
        "vice president",
        "ceo",
        "coo",
        "cmo",
        "executive",
        "sponsor",
        "head of",
        "chief",
    ],
    UserType.EXPERT: [
        "senior",
        "lead",
        "principal",
        "expert",
        "investigator",
        "specialist",
        "manager",
        "physician",
        "radiologist",
        "oncologist",
    ],
    UserType.NOVICE: ["new", "intern", "trainee", "assistant", "junior", "entry"],
}


def detect_user_type(user_profile: dict) -> UserType:
    """
    Detect user expertise level from profile information.

    Args:
        user_profile: Dictionary containing:
            - role: str - User's job title/role
            - experience_years: int - Years of experience in clinical trials

    Returns:
        UserType enum value representing the detected expertise level.

    Detection Priority:
        1. Role-based keywords (regulatory, executive, expert, novice)
        2. Experience-based fallback
    """
    role = user_profile.get("role", "").lower()
    experience_years = user_profile.get("experience_years", 0)

    def has_keyword(text: str, keyword: str) -> bool:
        # Use word-boundary matching to avoid false substring hits
        # e.g. "coo" should not match inside "coordinator"
        return bool(re.search(rf"\b{re.escape(keyword)}\b", text))

    # Priority 1: Check for regulatory/compliance roles
    for keyword in ROLE_KEYWORDS[UserType.REGULATORY]:
        if has_keyword(role, keyword):
            return UserType.REGULATORY

    # Priority 2: Check for executive/leadership roles
    for keyword in ROLE_KEYWORDS[UserType.EXECUTIVE]:
        if has_keyword(role, keyword):
            return UserType.EXECUTIVE

    # Priority 3: Check for expert/senior roles
    for keyword in ROLE_KEYWORDS[UserType.EXPERT]:
        if has_keyword(role, keyword):
            return UserType.EXPERT

    # Priority 4: Check for novice/entry-level roles
    for keyword in ROLE_KEYWORDS[UserType.NOVICE]:
        if has_keyword(role, keyword):
            return UserType.NOVICE

    # Priority 5: Experience-based fallback
    if experience_years == 0:
        return UserType.NOVICE
    elif experience_years < 3:
        return UserType.INTERMEDIATE
    elif experience_years >= 5:
        return UserType.EXPERT

    # Default
    return UserType.INTERMEDIATE


def get_response_config(user_type: UserType, query_type: str) -> ResponseConfig:
    """
    Generate response configuration based on user type and query type.

    Args:
        user_type: The detected UserType
        query_type: The classified query type (QueryType.value)

    Returns:
        ResponseConfig with appropriate settings for the user/query combination.
    """
    config = ResponseConfig(user_type=user_type, query_type=query_type)

    # Configure based on user type
    if user_type == UserType.NOVICE:
        config.detail_level = "low"
        config.include_definitions = True
        config.use_bullet_points = True
        config.include_key_takeaway = True
        config.include_examples = True

    elif user_type == UserType.INTERMEDIATE:
        config.detail_level = "medium"
        config.use_tables = True
        config.include_examples = True

    elif user_type == UserType.EXPERT:
        config.detail_level = "high"
        config.use_tables = True
        config.include_references = True

    elif user_type == UserType.REGULATORY:
        config.detail_level = "high"
        config.use_tables = True
        config.include_references = True
        config.color_coding = True

    elif user_type == UserType.EXECUTIVE:
        config.detail_level = "low"
        config.include_executive_summary = True
        config.include_recommendations = True
        config.use_tables = True

    # Override based on query type (certain queries benefit from tables)
    if query_type in ["numerical", "comparison", "timeline"]:
        config.use_tables = True

    return config
