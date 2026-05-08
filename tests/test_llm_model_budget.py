import pytest

from job_search_mvp.standardization.llm_standardizer import (
    BUDGET_OPENAI_MODEL,
    enforce_budget_openai_model,
    standardize_job_with_mode,
)


def test_budget_model_allows_gpt_35_turbo():
    assert BUDGET_OPENAI_MODEL == "gpt-3.5-turbo"
    assert enforce_budget_openai_model("gpt-3.5-turbo") == "gpt-3.5-turbo"


def test_budget_model_rejects_other_models():
    with pytest.raises(RuntimeError, match="Only gpt-3.5-turbo is allowed"):
        enforce_budget_openai_model("gpt-5.5")


def test_hybrid_mode_skips_llm_when_deterministic_confidence_is_high(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text = """
Job Description:
We are looking for an embedded software engineer.

Requirements:
- 5+ years of C++ development
- Experience with AUTOSAR and Git

Nice to have:
- Python
""".strip()

    result = standardize_job_with_mode(
        job_text=text,
        source_url=None,
        metadata={},
        mode="hybrid",
        provider="openai",
        model=BUDGET_OPENAI_MODEL,
    )

    assert result.used_fallback is False
    assert result.llm_raw is None
    assert "LLM skipped" in " ".join(result.validation_report.get("warnings", []))
    assert result.validation_report["deterministic_confidence"]["is_low_confidence"] is False


def test_hybrid_mode_uses_deterministic_fallback_when_low_confidence_and_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text = "Role\nJoin us."

    result = standardize_job_with_mode(
        job_text=text,
        source_url=None,
        metadata={},
        mode="hybrid",
        provider="openai",
        model=BUDGET_OPENAI_MODEL,
    )

    assert result.used_fallback is True
    assert result.llm_raw is None
    assert result.validation_report["deterministic_confidence"]["is_low_confidence"] is True
    assert "OPENAI_API_KEY is not set" in result.validation_report.get("errors", [])
