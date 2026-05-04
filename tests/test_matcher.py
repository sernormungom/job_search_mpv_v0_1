from job_search_mvp import matcher
from job_search_mvp.paths import DATA_DIR, PROJECT_ROOT


def test_sample_job_matching_stays_stable():
    job_text = (PROJECT_ROOT / "prototype" / "examples" / "sample_job_embedded.txt").read_text(encoding="utf-8")
    experience_db = matcher.load_yaml(DATA_DIR / "experience_database.yaml")
    aliases = matcher.load_aliases(matcher.load_yaml(DATA_DIR / "tool_aliases.yaml"))
    prefs = matcher.load_yaml(DATA_DIR / "career_preferences.yaml")

    job_standardized = matcher.standardize_job(job_text)
    evidence_index = matcher.build_evidence_index(experience_db)
    match_result = matcher.match_job(job_standardized, evidence_index, aliases, prefs)

    job_root = job_standardized["job_standardized"]
    match_root = match_result["match_result"]

    assert job_root["job_id"] == "job_b7c1da8f64"
    assert job_root["identity"]["normalized_title"] == "Embedded Software Engineer"
    assert job_root["explicit_terms"]["languages"] == ["C++", "C"]
    assert "AUTOSAR" in job_root["explicit_terms"]["tools"]
    assert match_root["overall_score"] == 79
    assert match_root["decision"]["recommended_status"] == "keep"
