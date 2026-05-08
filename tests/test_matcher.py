from job_search_mvp import matcher
from job_search_mvp.paths import DATA_DIR, PROJECT_ROOT

FIXTURE_JOB = PROJECT_ROOT / "tests" / "fixtures" / "jobs" / "sample_job_embedded.txt"


def test_sample_job_matching_stays_stable():
    job_text = FIXTURE_JOB.read_text(encoding="utf-8")
    experience_db = matcher.load_yaml(DATA_DIR / "experience_database.yaml")
    aliases = matcher.load_aliases(matcher.load_yaml(DATA_DIR / "tool_aliases.yaml"))
    prefs = matcher.load_yaml(DATA_DIR / "career_preferences.yaml")

    job_standardized = matcher.standardize_job(job_text)
    evidence_index = matcher.build_evidence_index(experience_db)
    match_result = matcher.match_job(job_standardized, evidence_index, aliases, prefs)

    job_root = job_standardized["job_standardized"]
    match_root = match_result["match_result"]

    assert job_root["job_id"] == "job_42428d56ca"
    assert job_root["identity"]["normalized_title"] == "Embedded Software Engineer"
    assert job_root["explicit_terms"]["languages"] == ["C++", "C", "Python", "MATLAB", "Simulink"]
    assert "AUTOSAR" in job_root["explicit_terms"]["tools"]
    assert match_root["overall_score"] == 83
    assert match_root["score_breakdown"]["role_fit"] == 90
    assert match_root["decision"]["recommended_status"] == "keep"


def test_matcher_preserves_explicit_terms_and_uses_aliases():
    job_text = "Senior Engineer\nMust have CI/CD experience for a Gothenburg role."
    experience_db = {
        "experience_database": {
            "role_groups": [
                {
                    "role_group_id": "TEST_ROLE",
                    "company": "Example",
                    "display_role_title": "Build Engineer",
                    "time_range": "2020-2024",
                    "recency_rank": 1,
                    "role_group_type": "recent",
                    "blocks": [
                        {
                            "block_id": "TEST_BLOCK",
                            "tools": ["Jenkins"],
                            "evidence_items": [
                                {
                                    "evidence_id": "TEST_EVIDENCE",
                                    "text": "Built and maintained Jenkins automation for shared delivery pipelines.",
                                    "tags": ["Jenkins", "automation"],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    }
    aliases = matcher.load_aliases(
        {
            "tool_aliases": {
                "CI/CD": {
                    "exact_terms": ["CI/CD"],
                    "supporting_terms": ["Jenkins"],
                }
            }
        }
    )
    prefs = {
        "career_preferences": {
            "scoring_weights": {
                "expertise_fit": 0.4,
                "growth_fit": 0.3,
                "interest_fit": 0.2,
                "practical_fit": 0.1,
            }
        }
    }

    job_standardized = matcher.standardize_job(job_text)
    match_result = matcher.match_job(
        job_standardized,
        matcher.build_evidence_index(experience_db),
        aliases,
        prefs,
    )

    assert "CI/CD" in job_standardized["job_standardized"]["explicit_terms"]["methods"]
    matches = match_result["match_result"]["matched_evidence"]["explicit_term_matches"]
    assert any(
        item["job_term"] == "CI/CD" and item["match_type"] == "alias/supporting"
        for item in matches
    )


def test_standardize_job_extracts_swedish_requirements_sections():
    job_text = """
Uppdragsbeskrivning:
Vi söker en embedded utvecklare för ett team i Göteborg.

Krav:
- Minst 5 års erfarenhet av C++
- Erfarenhet av AUTOSAR och Git

Meriterande:
- Erfarenhet av Python
- Kunskap om CI/CD
""".strip()

    job_standardized = matcher.standardize_job(job_text)
    root = job_standardized["job_standardized"]
    req = root["normalized_requirements"]

    assert root["language"]["original"] == "Swedish"
    assert req["must_have"] == [
        "Minst 5 års erfarenhet av C++",
        "Erfarenhet av AUTOSAR och Git",
    ]
    assert req["nice_to_have"] == [
        "Erfarenhet av Python",
        "Kunskap om CI/CD",
    ]
