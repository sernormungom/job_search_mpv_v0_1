"""Prompt builders for LLM job standardization."""

from __future__ import annotations

import json
from typing import Any, Dict

from .schema import llm_payload_template


SYSTEM_PROMPT = """You standardize job postings for a local job-search assistant.
Return only valid JSON. Do not return markdown.
Translate Swedish or mixed-language job text into English.
Do not invent facts. If data is missing, use null, empty arrays, or "unspecified".
Preserve explicit technologies, standards, tools, methods, and requirements from the source text.
Separate responsibilities, must-have requirements, and nice-to-have requirements.
Include blockers only when explicitly stated in the source text.
Do not recommend whether to apply.
"""


def build_user_prompt(
    *,
    job_id: str,
    source_url: str | None,
    known_metadata: Dict[str, Any],
    deterministic_explicit_terms: Dict[str, Any],
    cleaned_job_text: str,
) -> str:
    template = llm_payload_template(job_id, source_url)
    return (
        "Standardize this job posting to the JSON schema template.\n\n"
        f"Known metadata:\n{json.dumps(known_metadata, ensure_ascii=False, indent=2)}\n\n"
        f"Deterministic explicit terms:\n{json.dumps(deterministic_explicit_terms, ensure_ascii=False, indent=2)}\n\n"
        f"Output JSON template:\n{json.dumps(template, ensure_ascii=False, indent=2)}\n\n"
        "Source job text:\n"
        f"{cleaned_job_text}"
    )

