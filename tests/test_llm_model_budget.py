import pytest

from job_search_mvp.standardization.llm_standardizer import BUDGET_OPENAI_MODEL, enforce_budget_openai_model


def test_budget_model_allows_gpt_35_turbo():
    assert BUDGET_OPENAI_MODEL == "gpt-3.5-turbo"
    assert enforce_budget_openai_model("gpt-3.5-turbo") == "gpt-3.5-turbo"


def test_budget_model_rejects_other_models():
    with pytest.raises(RuntimeError, match="Only gpt-3.5-turbo is allowed"):
        enforce_budget_openai_model("gpt-5.5")
