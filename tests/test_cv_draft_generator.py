from job_search_mvp import cv_draft_generator, matcher, strategy_generator
from job_search_mvp.paths import DATA_DIR


def test_cv_draft_does_not_surface_unsupported_job_tools():
    job_text = (
        "Senior Software Engineer\n"
        "Must have C++ and Java experience for an embedded role in Gothenburg.\n"
        "Experience with CI/CD is also required."
    )
    experience_db = matcher.load_yaml(DATA_DIR / "experience_database.yaml")
    aliases = matcher.load_aliases(matcher.load_yaml(DATA_DIR / "tool_aliases.yaml"))
    prefs = matcher.load_yaml(DATA_DIR / "career_preferences.yaml")
    policy = strategy_generator.load_yaml(DATA_DIR / "cv_generation_policy.yaml")
    employee = cv_draft_generator.load_yaml(DATA_DIR / "employee_profile.yaml")

    job_standardized = matcher.standardize_job(job_text)
    match_result = matcher.match_job(
        job_standardized,
        matcher.build_evidence_index(experience_db),
        aliases,
        prefs,
    )
    strategy = strategy_generator.build_strategy(job_standardized, match_result, experience_db, policy)
    draft = cv_draft_generator.generate_draft(strategy, employee, job_standardized)
    root = draft["cv_draft"]

    assert "Java" in strategy["cv_strategy"]["mandatory_cv_terms"]
    assert "Java" in strategy["cv_strategy"]["validation"]["missing_supported_mandatory_terms_in_selected_roles"]

    rendered = cv_draft_generator.render_text(draft)
    tech_terms = sum(root["sections"]["tech_competence"].values(), [])
    assert "Java" not in tech_terms
    assert "Java" not in root["sections"]["professional_summary"]["text"]
    assert "Mandatory terms not surfaced: Java" in rendered
