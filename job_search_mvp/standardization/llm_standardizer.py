#!/usr/bin/env python3
"""LLM-backed standardizer with deterministic fallback."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from .. import matcher
from ..paths import resolve_data_dir
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .validation import merge_explicit_terms, validate_payload


HEADER_FIELD_RE = re.compile(r"^\s*([A-Za-z /]+)\s*:\s*(.*?)\s*$")
BUDGET_OPENAI_MODEL = "gpt-3.5-turbo"
HYBRID_CONFIDENCE_THRESHOLD = 0.55


@dataclass
class LLMStandardizationResult:
    job_standardized: Dict[str, Any]
    llm_raw: Dict[str, Any] | None
    validation_report: Dict[str, Any]
    used_fallback: bool


def deterministic_confidence_report(job_standardized: Dict[str, Any]) -> Dict[str, Any]:
    root = job_standardized.get("job_standardized", job_standardized)
    identity = root.get("identity", {}) or {}
    normalized_requirements = root.get("normalized_requirements", {}) or {}
    must_have = normalized_requirements.get("must_have", []) or []
    nice_to_have = normalized_requirements.get("nice_to_have", []) or []
    explicit_terms = root.get("explicit_terms", {}) or {}

    signals = 0
    penalties = 0
    reasons: list[str] = []

    title = (identity.get("original_title") or "").strip().lower()
    if title and title not in {"unspecified role", "full job description", "hem", "uppdragsannonser"}:
        signals += 1
    else:
        penalties += 1
        reasons.append("title_weak")

    if len(must_have) >= 2:
        signals += 2
    elif len(must_have) == 1:
        signals += 1
        reasons.append("must_have_sparse")
    else:
        penalties += 2
        reasons.append("must_have_missing")

    if len(nice_to_have) >= 1:
        signals += 1
    else:
        penalties += 1
        reasons.append("nice_to_have_missing")

    explicit_term_count = sum(len(v or []) for v in explicit_terms.values() if isinstance(v, list))
    if explicit_term_count >= 4:
        signals += 1
    else:
        penalties += 1
        reasons.append("explicit_terms_sparse")

    denom = max(1, signals + penalties)
    score = signals / denom
    return {
        "score": round(score, 3),
        "signals": signals,
        "penalties": penalties,
        "reasons": reasons,
        "threshold": HYBRID_CONFIDENCE_THRESHOLD,
        "is_low_confidence": score < HYBRID_CONFIDENCE_THRESHOLD,
    }


def enforce_budget_openai_model(model: str) -> str:
    requested = (model or "").strip()
    if requested != BUDGET_OPENAI_MODEL:
        raise RuntimeError(
            f"Only {BUDGET_OPENAI_MODEL} is allowed for OpenAI API calls in this project; "
            f"got {requested or '<empty>'}."
        )
    return BUDGET_OPENAI_MODEL


def parse_job_file(path: Path) -> Tuple[Dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    metadata: Dict[str, str] = {}
    body_lines = []
    in_body = False
    for line in text.splitlines():
        if line.strip().lower() == "full job description":
            in_body = True
            continue
        if in_body:
            body_lines.append(line)
            continue
        m = HEADER_FIELD_RE.match(line)
        if m:
            key = m.group(1).strip().lower().replace(" ", "_").replace("/", "_")
            metadata[key] = m.group(2).strip()
    if not body_lines:
        body_lines = text.splitlines()
    body = "\n".join(body_lines).strip()
    return metadata, body


def parse_json_object(text: str) -> Dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        parsed = json.loads(raw[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("LLM output is not valid JSON object")


def call_openai_chat(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    timeout_sec: int = 60,
) -> Dict[str, Any]:
    model = enforce_budget_openai_model(model)
    payload = {
        "model": model,
        "temperature": 1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI HTTPError {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI network error: {exc}") from exc

    response = json.loads(raw)
    choices = response.get("choices", [])
    if not choices:
        raise RuntimeError("OpenAI response has no choices")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("OpenAI response content is empty")
    return parse_json_object(content)


def canonical_from_llm(
    *,
    deterministic: Dict[str, Any],
    llm_payload: Dict[str, Any],
    metadata: Dict[str, str],
) -> Dict[str, Any]:
    root = deterministic["job_standardized"]
    llm_identity = llm_payload.get("identity", {}) or {}
    llm_location = llm_identity.get("location", {}) or {}
    llm_analysis = llm_payload.get("job_analysis", {}) or {}
    llm_summary = llm_payload.get("summary", {}) or {}
    llm_requirements = llm_payload.get("normalized_requirements", {}) or {}
    llm_blockers = llm_payload.get("blockers", {}) or {}

    root["identity"]["original_title"] = llm_identity.get("original_title") or root["identity"].get("original_title")
    root["identity"]["normalized_title"] = llm_identity.get("normalized_title") or root["identity"].get("normalized_title")
    root["identity"]["company"] = llm_identity.get("company") or metadata.get("company_client") or root["identity"].get("company")
    root["identity"]["location"]["city"] = llm_location.get("city") or root["identity"]["location"].get("city")
    root["identity"]["location"]["country"] = llm_location.get("country") or root["identity"]["location"].get("country")
    root["identity"]["location"]["work_mode"] = llm_location.get("work_mode") or root["identity"]["location"].get("work_mode")
    root["identity"]["employment_type"] = llm_identity.get("employment_type") or root["identity"].get("employment_type")

    root["summary"]["short_summary"] = llm_summary.get("short_summary") or root["summary"].get("short_summary")

    root["job_analysis"]["role_archetype"] = llm_analysis.get("role_archetype") or root["job_analysis"].get("role_archetype")
    root["job_analysis"]["seniority"] = llm_analysis.get("seniority") or root["job_analysis"].get("seniority")
    root["job_analysis"]["primary_technical_focus"] = llm_analysis.get("primary_technical_focus") or root["job_analysis"].get("primary_technical_focus")
    root["job_analysis"]["secondary_technical_focus"] = llm_analysis.get("secondary_technical_focus") or root["job_analysis"].get("secondary_technical_focus")
    root["job_analysis"]["leadership_expectations"] = llm_analysis.get("leadership_expectations") or root["job_analysis"].get("leadership_expectations")

    merged_terms = merge_explicit_terms(
        llm_payload.get("explicit_terms", {}) or {},
        root.get("explicit_terms", {}) or {},
    )
    root["explicit_terms"] = merged_terms

    root["normalized_requirements"]["must_have"] = llm_requirements.get("must_have") or root["normalized_requirements"].get("must_have")
    root["normalized_requirements"]["nice_to_have"] = llm_requirements.get("nice_to_have") or root["normalized_requirements"].get("nice_to_have")
    responsibilities = llm_requirements.get("responsibilities", [])
    if responsibilities:
        root["normalized_requirements"]["responsibilities"] = responsibilities

    root["blockers"]["hard"] = llm_blockers.get("hard") or root["blockers"].get("hard", [])
    root["blockers"]["soft"] = llm_blockers.get("soft") or root["blockers"].get("soft", [])

    root["llm_enrichment"] = {
        "schema_version": llm_payload.get("schema_version", "job_standardized_llm_v1"),
        "language": llm_payload.get("language", {}),
        "identity_extra": {
            "client_or_broker": llm_identity.get("client_or_broker"),
            "assignment_period": llm_identity.get("assignment_period"),
            "application_deadline": llm_identity.get("application_deadline"),
            "remote_percentage": llm_location.get("remote_percentage"),
        },
        "summary_extra": {
            "role_goal": llm_summary.get("role_goal"),
            "business_context": llm_summary.get("business_context"),
        },
        "tags": llm_payload.get("tags", {}),
        "audit": llm_payload.get("llm_audit", {}),
        "standardized_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    return deterministic


def standardize_job_with_mode(
    *,
    job_text: str,
    source_url: str | None,
    metadata: Dict[str, str],
    mode: str,
    provider: str,
    model: str,
    timeout_sec: int = 60,
) -> LLMStandardizationResult:
    deterministic = matcher.standardize_job(job_text, source_url=source_url)
    deterministic_terms = deterministic["job_standardized"].get("explicit_terms", {})
    job_id = deterministic["job_standardized"]["job_id"]
    confidence = deterministic_confidence_report(deterministic)
    core_language = (
        (deterministic.get("job_standardized", {}).get("language", {}) or {}).get("original", "") or ""
    ).strip().lower()
    force_llm_for_language = core_language == "swedish"

    if mode == "deterministic":
        return LLMStandardizationResult(
            job_standardized=deterministic,
            llm_raw=None,
            validation_report={
                "mode": "deterministic",
                "used_fallback": False,
                "errors": [],
                "warnings": [],
                "deterministic_confidence": confidence,
            },
            used_fallback=False,
        )

    if mode == "hybrid" and not confidence["is_low_confidence"] and not force_llm_for_language:
        return LLMStandardizationResult(
            job_standardized=deterministic,
            llm_raw=None,
            validation_report={
                "mode": mode,
                "used_fallback": False,
                "errors": [],
                "warnings": ["LLM skipped: deterministic confidence is high enough."],
                "deterministic_confidence": confidence,
                "language_override": {
                    "core_language": core_language or "unknown",
                    "forced_llm": False,
                },
            },
            used_fallback=False,
        )

    if provider != "openai":
        raise RuntimeError(f"Unsupported LLM provider: {provider}")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        if mode == "hybrid":
            return LLMStandardizationResult(
                job_standardized=deterministic,
                llm_raw=None,
                validation_report={
                    "mode": mode,
                    "used_fallback": True,
                    "errors": ["OPENAI_API_KEY is not set"],
                    "warnings": [],
                    "deterministic_confidence": confidence,
                    "language_override": {
                        "core_language": core_language or "unknown",
                        "forced_llm": bool(force_llm_for_language),
                    },
                },
                used_fallback=True,
            )
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = enforce_budget_openai_model(model)

    user_prompt = build_user_prompt(
        job_id=job_id,
        source_url=source_url,
        known_metadata=metadata,
        deterministic_explicit_terms=deterministic_terms,
        cleaned_job_text=job_text,
    )

    llm_raw = call_openai_chat(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        api_key=api_key,
        timeout_sec=timeout_sec,
    )
    ok, errors, warnings = validate_payload(
        llm_raw,
        expected_job_id=job_id,
        expected_source_url=source_url,
    )
    if not ok:
        if mode == "hybrid":
            return LLMStandardizationResult(
                job_standardized=deterministic,
                llm_raw=llm_raw,
                validation_report={
                    "mode": mode,
                    "used_fallback": True,
                    "errors": errors,
                    "warnings": warnings,
                    "deterministic_confidence": confidence,
                    "language_override": {
                        "core_language": core_language or "unknown",
                        "forced_llm": bool(force_llm_for_language),
                    },
                },
                used_fallback=True,
            )
        raise RuntimeError("LLM payload validation failed: " + "; ".join(errors))

    canonical = canonical_from_llm(deterministic=deterministic, llm_payload=llm_raw, metadata=metadata)
    return LLMStandardizationResult(
        job_standardized=canonical,
        llm_raw=llm_raw,
        validation_report={
            "mode": mode,
            "used_fallback": False,
            "errors": errors,
            "warnings": warnings,
            "deterministic_confidence": confidence,
            "language_override": {
                "core_language": core_language or "unknown",
                "forced_llm": bool(force_llm_for_language),
            },
        },
        used_fallback=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM standardize one job text file")
    parser.add_argument("--job", required=True, help="Path to job .txt file")
    parser.add_argument("--out-dir", default="outputs/standardized", help="Output directory")
    parser.add_argument("--source-url", default=None, help="Optional source URL override")
    parser.add_argument("--mode", choices=["llm", "hybrid", "deterministic"], default="hybrid")
    parser.add_argument("--provider", default=os.getenv("JOBSEARCH_LLM_PROVIDER", "openai"))
    parser.add_argument(
        "--model",
        default=os.getenv("JOBSEARCH_LLM_MODEL", BUDGET_OPENAI_MODEL),
        help=f"OpenAI model for LLM mode. Only {BUDGET_OPENAI_MODEL} is allowed for cost control.",
    )
    parser.add_argument("--timeout-sec", type=int, default=60)
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()

    _ = resolve_data_dir(args.data_dir)
    job_path = Path(args.job)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata, job_body = parse_job_file(job_path)
    source_url = args.source_url or metadata.get("source_url")
    result = standardize_job_with_mode(
        job_text=job_body,
        source_url=source_url,
        metadata=metadata,
        mode=args.mode,
        provider=args.provider,
        model=args.model,
        timeout_sec=args.timeout_sec,
    )

    job_id = result.job_standardized["job_standardized"]["job_id"]
    matcher.write_yaml(out_dir / f"{job_id}.job_standardized.yaml", result.job_standardized)
    matcher.write_yaml(out_dir / f"{job_id}.job_standardized.validation.yaml", result.validation_report)
    if result.llm_raw is not None:
        matcher.write_yaml(out_dir / f"{job_id}.job_standardized.llm_raw.yaml", result.llm_raw)

    print(f"Wrote {out_dir / f'{job_id}.job_standardized.yaml'}")
    if result.used_fallback:
        print("LLM fallback to deterministic output was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
