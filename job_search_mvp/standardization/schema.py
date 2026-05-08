"""Schema helpers for LLM standardization payloads."""

from __future__ import annotations

from typing import Any, Dict


LLM_STANDARDIZED_SCHEMA_VERSION = "job_standardized_llm_v1"


def llm_payload_template(job_id: str, source_url: str | None) -> Dict[str, Any]:
    return {
        "schema_version": LLM_STANDARDIZED_SCHEMA_VERSION,
        "job_id": job_id,
        "source": {
            "site": "verama",
            "url": source_url,
            "scraped_at": None,
        },
        "language": {
            "original": "unspecified",
            "standardized_output": "English",
            "translation_notes": [],
        },
        "identity": {
            "original_title": None,
            "normalized_title": None,
            "company": None,
            "client_or_broker": "unspecified",
            "location": {
                "city": None,
                "country": None,
                "work_mode": "unspecified",
                "remote_percentage": None,
            },
            "employment_type": "unspecified",
            "assignment_period": {
                "start": None,
                "end": None,
            },
            "application_deadline": None,
        },
        "summary": {
            "short_summary": None,
            "role_goal": None,
            "business_context": None,
        },
        "job_analysis": {
            "role_archetype": None,
            "seniority": "unspecified",
            "primary_technical_focus": [],
            "secondary_technical_focus": [],
            "leadership_expectations": [],
            "consultant_fit_notes": [],
        },
        "explicit_terms": {
            "languages": [],
            "tools": [],
            "platforms": [],
            "methods": [],
            "standards": [],
            "verification": [],
            "domains": [],
            "soft_skills": [],
        },
        "normalized_requirements": {
            "responsibilities": [],
            "must_have": [],
            "nice_to_have": [],
        },
        "tags": {
            "skills": [],
            "domain": [],
            "work_mode": [],
            "language_requirement": [],
            "risk_flags": [],
            "opportunity_flags": [],
        },
        "blockers": {
            "hard": [],
            "soft": [],
        },
        "llm_audit": {
            "confidence": None,
            "unsupported_or_ambiguous_fields": [],
            "source_quote_refs": [],
        },
    }

