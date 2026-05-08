"""Validation and merge helpers for LLM-standardized payloads."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


REQUIRED_TOP_LEVEL_KEYS = [
    "schema_version",
    "job_id",
    "source",
    "language",
    "identity",
    "summary",
    "job_analysis",
    "explicit_terms",
    "normalized_requirements",
    "blockers",
    "llm_audit",
]


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x not in [None, ""]]
    return [str(value)]


def _merge_terms(existing: List[str], extra: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in existing + extra:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def validate_payload(
    payload: Dict[str, Any],
    *,
    expected_job_id: str,
    expected_source_url: str | None,
) -> Tuple[bool, List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in payload:
            errors.append(f"Missing top-level key: {key}")

    if payload.get("job_id") and str(payload.get("job_id")) != expected_job_id:
        errors.append(f"job_id mismatch: expected {expected_job_id}, got {payload.get('job_id')}")

    source = payload.get("source", {})
    source_url = source.get("url") if isinstance(source, dict) else None
    if expected_source_url and source_url and str(source_url) != expected_source_url:
        warnings.append("source.url from LLM does not match source URL from file header")

    explicit_terms = payload.get("explicit_terms", {})
    if not isinstance(explicit_terms, dict):
        errors.append("explicit_terms must be an object")

    blockers = payload.get("blockers", {})
    if not isinstance(blockers, dict):
        errors.append("blockers must be an object")
    else:
        for key in ["hard", "soft"]:
            if key not in blockers:
                errors.append(f"blockers missing key: {key}")

    return (len(errors) == 0), errors, warnings


def merge_explicit_terms(
    llm_terms: Dict[str, Any],
    deterministic_terms: Dict[str, Any],
) -> Dict[str, List[str]]:
    keys = set(deterministic_terms.keys()) | set(llm_terms.keys())
    merged: Dict[str, List[str]] = {}
    for key in sorted(keys):
        merged[key] = _merge_terms(
            _as_list(deterministic_terms.get(key, [])),
            _as_list(llm_terms.get(key, [])),
        )
    return merged

