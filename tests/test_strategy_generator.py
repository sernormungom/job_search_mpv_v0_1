from job_search_mvp import matcher, strategy_generator
from job_search_mvp.paths import DATA_DIR, PROJECT_ROOT


def test_strategy_generator_selects_expected_role_groups_for_sample_job():
    job_text = (PROJECT_ROOT / "prototype" / "examples" / "sample_job_embedded.txt").read_text(encoding="utf-8")
    experience_db = matcher.load_yaml(DATA_DIR / "experience_database.yaml")
    aliases = matcher.load_aliases(matcher.load_yaml(DATA_DIR / "tool_aliases.yaml"))
    prefs = matcher.load_yaml(DATA_DIR / "career_preferences.yaml")

    job_standardized = matcher.standardize_job(job_text)
    match_result = matcher.match_job(
        job_standardized,
        matcher.build_evidence_index(experience_db),
        aliases,
        prefs,
    )
    policy = strategy_generator.load_yaml(DATA_DIR / "cv_generation_policy.yaml")

    strategy = strategy_generator.build_strategy(job_standardized, match_result, experience_db, policy)
    root = strategy["cv_strategy"]

    assert root["job_id"] == "job_b7c1da8f64"
    assert [rg["role_group_id"] for rg in root["selected_role_groups"]] == [
        "VOLVO_2024_2026",
        "ERICSSON_2021_2024",
        "GE_2005_2020",
    ]
    assert len(root["selected_role_groups"]) <= 3
    assert "C++" in root["mandatory_cv_terms"]
    assert root["selected_role_groups"][0]["selection_score"] == 69.6
