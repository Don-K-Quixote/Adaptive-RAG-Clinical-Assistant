"""
Tests for persona detection logic.

Validates that user profiles are correctly classified into UserType
and that ResponseConfig is generated with appropriate settings.
"""


from src.personas import (
    UserType,
    detect_user_type,
    get_response_config,
)


class TestUserTypeDetection:
    """Verify role-based and experience-based persona detection."""

    # --- Role-based detection (priority) ---

    def test_novice_by_role(self, novice_profile):
        assert detect_user_type(novice_profile) == UserType.NOVICE

    def test_expert_by_role(self, expert_profile):
        assert detect_user_type(expert_profile) == UserType.EXPERT

    def test_regulatory_by_role(self, regulatory_profile):
        assert detect_user_type(regulatory_profile) == UserType.REGULATORY

    def test_executive_by_role(self, executive_profile):
        assert detect_user_type(executive_profile) == UserType.EXECUTIVE

    def test_regulatory_takes_priority_over_experience(self):
        """Regulatory role should be detected regardless of low experience."""
        profile = {"role": "Quality Assurance Intern", "experience_years": 0}
        # "quality" matches REGULATORY keywords
        assert detect_user_type(profile) == UserType.REGULATORY

    def test_executive_vp_detection(self):
        profile = {"role": "VP of Operations", "experience_years": 10}
        assert detect_user_type(profile) == UserType.EXECUTIVE

    def test_senior_role_detected_as_expert(self):
        profile = {"role": "Senior Data Manager", "experience_years": 3}
        assert detect_user_type(profile) == UserType.EXPERT

    # --- Experience-based fallback ---

    def test_zero_experience_no_role_match(self):
        """Unknown role with 0 experience → NOVICE."""
        profile = {"role": "Volunteer", "experience_years": 0}
        assert detect_user_type(profile) == UserType.NOVICE

    def test_low_experience_no_role_match(self):
        """Unknown role with 1-2 years → INTERMEDIATE."""
        profile = {"role": "Coordinator", "experience_years": 2}
        assert detect_user_type(profile) == UserType.INTERMEDIATE

    def test_high_experience_no_role_match(self):
        """Unknown role with 5+ years → EXPERT."""
        profile = {"role": "Consultant", "experience_years": 7}
        assert detect_user_type(profile) == UserType.EXPERT

    def test_mid_experience_no_role_match(self):
        """Unknown role with 3-4 years → INTERMEDIATE."""
        profile = {"role": "Analyst", "experience_years": 4}
        assert detect_user_type(profile) == UserType.INTERMEDIATE

    # --- Edge cases ---

    def test_empty_profile(self):
        """Empty profile should default to NOVICE (0 experience)."""
        assert detect_user_type({}) == UserType.NOVICE

    def test_missing_role(self):
        profile = {"experience_years": 10}
        assert detect_user_type(profile) == UserType.EXPERT

    def test_missing_experience(self):
        profile = {"role": "Data Manager"}
        # "manager" matches EXPERT keywords
        assert detect_user_type(profile) == UserType.EXPERT


class TestResponseConfig:
    """Verify ResponseConfig generation for different user/query combos."""

    def test_novice_gets_definitions(self):
        config = get_response_config(UserType.NOVICE, "definition")
        assert config.include_definitions is True
        assert config.include_key_takeaway is True
        assert config.detail_level == "low"

    def test_expert_gets_high_detail(self):
        config = get_response_config(UserType.EXPERT, "procedure")
        assert config.detail_level == "high"
        assert config.include_references is True

    def test_executive_gets_summary(self):
        config = get_response_config(UserType.EXECUTIVE, "timeline")
        assert config.include_executive_summary is True
        assert config.include_recommendations is True
        assert config.detail_level == "low"

    def test_regulatory_gets_references(self):
        config = get_response_config(UserType.REGULATORY, "compliance")
        assert config.include_references is True
        assert config.color_coding is True

    def test_numerical_query_forces_tables(self):
        """Numerical queries should enable tables for any user type."""
        config = get_response_config(UserType.NOVICE, "numerical")
        assert config.use_tables is True

    def test_comparison_query_forces_tables(self):
        config = get_response_config(UserType.NOVICE, "comparison")
        assert config.use_tables is True

    def test_user_type_stored_correctly(self):
        config = get_response_config(UserType.EXPERT, "safety")
        assert config.user_type == UserType.EXPERT
        assert config.query_type == "safety"
