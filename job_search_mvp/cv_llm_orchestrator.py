#!/usr/bin/env python3
"""LLM orchestration for CV steps 1-6 with deterministic fallback."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

from . import cv_draft_generator, cv_llm_routing


def _norm(x: Any) -> str:
    return " ".join(str(x or "").lower().split())


def _parse_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(raw[start : end + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("LLM output is not a valid JSON object")


def _call_openai_json(*, api_key: str, model: str, temperature: float, system_prompt: str, user_prompt: str, timeout_sec: int = 60) -> Dict[str, Any]:
    payload = {
        "model": model,
        "temperature": temperature,
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
    data = json.loads(raw)
    content = ((data.get("choices") or [{}])[0].get("message", {}) or {}).get("content", "")
    if not content:
        raise RuntimeError("Empty LLM response content")
    return _parse_json_object(content)


def _fallback_step_1(job_std: Dict[str, Any]) -> Dict[str, Any]:
    root = job_std.get("job_standardized", job_std)
    ja = root.get("job_analysis", {}) or {}
    explicit = root.get("explicit_terms", {}) or {}
    title = root.get("identity", {}).get("original_title", "")
    keywords: List[str] = []
    for key in ["languages", "tools", "methods", "standards", "verification", "domains"]:
        for item in explicit.get(key, []) or []:
            if item and item not in keywords:
                keywords.append(str(item))
    return {
        "role_archetype": ja.get("role_archetype", "Software Engineer"),
        "seniority_level": ja.get("seniority", "senior"),
        "primary_technical_focus_areas": (ja.get("primary_technical_focus") or [])[:6],
        "secondary_focus_areas": (ja.get("secondary_technical_focus") or [])[:6],
        "leadership_expectations": ja.get("leadership_expectations", []),
        "critical_keywords": keywords[:16],
        "not_focused_on": [f"work outside '{title}' target scope"] if title else [],
    }


def _fallback_step_2(step1: Dict[str, Any]) -> Dict[str, Any]:
    archetype = _norm(step1.get("role_archetype", ""))
    if "verification" in archetype:
        primary, secondary = "verification_validation_engineer", "technical_lead"
    elif "embedded" in archetype:
        primary, secondary = "embedded_software_engineer", "technical_lead"
    elif "technical lead" in archetype:
        primary, secondary = "technical_lead", "embedded_software_engineer"
    else:
        primary, secondary = "software_engineer", "technical_lead"
    return {
        "primary_persona_id": primary,
        "primary_confidence": "Medium",
        "secondary_persona_id": secondary,
        "secondary_confidence": "Low",
        "reasoning": [
            f"Primary aligned to role_archetype={step1.get('role_archetype','unknown')}",
            "Secondary chosen as adjacent persona for blended positioning.",
        ],
    }


def _fallback_step_4(strategy: Dict[str, Any]) -> Dict[str, Any]:
    plan = []
    for role in strategy.get("cv_strategy", {}).get("experience_plan", []) or []:
        bullets = role.get("evidence_to_use", []) or []
        plan.append(
            {
                "role_group_id": role.get("role_group_id"),
                "blocks_used": sorted({b.get("block_id") for b in bullets if isinstance(b, dict) and b.get("block_id")}),
                "emphasis_notes": "Weighted by selected evidence priority from strategy.",
                "bullet_priority": "high" if len(bullets) >= 4 else "medium",
            }
        )
    return {"selected_role_groups_ordered": [r.get("role_group_id") for r in plan], "role_group_plan": plan}


def _fallback_step_5(strategy: Dict[str, Any], employee: Dict[str, Any]) -> Dict[str, Any]:
    text, evidence = cv_draft_generator.build_summary(employee, strategy)
    return {"adapted_professional_summary": text, "evidence_links": evidence}


def _fallback_step_6(strategy: Dict[str, Any]) -> Dict[str, Any]:
    exp = cv_draft_generator.build_experience(strategy)
    roles = []
    for role in exp:
        roles.append(
            {
                "role_group_id": role.get("role_group_id"),
                "role_header": role.get("role_header"),
                "bullets": [b.get("text", "") for b in (role.get("bullets") or [])[:6]],
            }
        )
    return {"experience_sections": roles}


def _fallback_step_7(strategy: Dict[str, Any]) -> Dict[str, Any]:
    return {"tech_competence": cv_draft_generator.build_tech_competence(strategy)}


def _enforce_size_budgets(step: str, result: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    budgets = ((policy.get("cv_generation_policy", {}) or {}).get("size_budgets", {}) or {})
    if step == "summary_adaptation":
        txt = str(result.get("adapted_professional_summary", "")).strip()
        max_words = int(budgets.get("professional_summary_max_words", 85))
        words = txt.split()
        if len(words) > max_words:
            txt = " ".join(words[:max_words]).rstrip(",;:.") + "."
        result["adapted_professional_summary"] = txt
    elif step == "experience_generation":
        roles = result.get("experience_sections", [])
        if isinstance(roles, list):
            max_top = int(budgets.get("experience_max_bullets_per_top_role", 6))
            max_support = int(budgets.get("experience_max_bullets_per_support_role", 4))
            max_words = int(budgets.get("experience_max_words_per_bullet", 34))
            for i, role in enumerate(roles):
                if not isinstance(role, dict):
                    continue
                bullets = role.get("bullets", []) or []
                max_b = max_top if i < 2 else max_support
                clipped = []
                for b in bullets[:max_b]:
                    txt = str(b or "").strip()
                    w = txt.split()
                    if len(w) > max_words:
                        txt = " ".join(w[:max_words]).rstrip(",;:.") + "."
                    clipped.append(txt)
                role["bullets"] = clipped
            result["experience_sections"] = roles
    elif step == "tech_competence_generation":
        tech = result.get("tech_competence", {})
        if isinstance(tech, dict):
            max_items = int(budgets.get("tech_competence_max_items_per_column", 10))
            for col in ["Programming", "Knowledge", "Soft Skills"]:
                items = tech.get(col, []) or []
                if isinstance(items, list):
                    tech[col] = [str(x) for x in items[:max_items] if str(x).strip()]
            result["tech_competence"] = tech
    return result


def _job_context(job_std: Dict[str, Any], strategy: Dict[str, Any]) -> Dict[str, Any]:
    root = job_std.get("job_standardized", job_std)
    return {
        "job_id": root.get("job_id"),
        "title": (root.get("identity") or {}).get("original_title"),
        "normalized_title": (root.get("identity") or {}).get("normalized_title"),
        "summary": (root.get("summary") or {}).get("short_summary"),
        "job_analysis": root.get("job_analysis", {}),
        "mandatory_terms": (strategy.get("cv_strategy", {}) or {}).get("mandatory_cv_terms", []),
    }


def _prompt_for_step(step: str, ctx: Dict[str, Any], prev: Dict[str, Any], strategy: Dict[str, Any], max_output_tokens: int) -> Tuple[str, str]:
    system = "You are a senior CV strategist. Return strict JSON only. Do not invent experience."
    if step == "job_understanding":
        user = (
            f"Analyze this job context and extract key signals in JSON. Output keys: role_archetype, seniority_level, "
            f"primary_technical_focus_areas, secondary_focus_areas, leadership_expectations, critical_keywords, not_focused_on. "
            f"Keep concise. Max output tokens target={max_output_tokens}. Context:\n{json.dumps(ctx, ensure_ascii=False)}"
        )
        return system, user
    if step == "persona_selection":
        user = (
            "Select primary and secondary persona ids and confidence based on prior job understanding. "
            "Output keys: primary_persona_id, primary_confidence, secondary_persona_id, secondary_confidence, reasoning.\n"
            f"job_understanding={json.dumps(prev.get('job_understanding', {}), ensure_ascii=False)}"
        )
        return system, user
    if step == "experience_weighting":
        slim = strategy.get("cv_strategy", {}).get("experience_plan", [])
        user = (
            "Weight role groups and blocks from strategy. Output keys: selected_role_groups_ordered, role_group_plan "
            "(each item: role_group_id, blocks_used, emphasis_notes, bullet_priority). "
            f"persona={json.dumps(prev.get('persona_selection', {}), ensure_ascii=False)} "
            f"experience_plan={json.dumps(slim, ensure_ascii=False)}"
        )
        return system, user
    if step == "summary_adaptation":
        user = (
            "Adapt professional summary for target role using evidence only. "
            "Output key: adapted_professional_summary. Keep 2-3 sentences, no buzzwords.\n"
            f"context={json.dumps(ctx, ensure_ascii=False)}\n"
            f"persona={json.dumps(prev.get('persona_selection', {}), ensure_ascii=False)}\n"
            f"weighting={json.dumps(prev.get('experience_weighting', {}), ensure_ascii=False)}"
        )
        return system, user
    if step == "experience_generation":
        user = (
            "Generate experience sections. Output key: experience_sections (list of role_group_id, role_header, bullets). "
            "Each role should have 4-6 bullets for top roles, concise and factual.\n"
            f"weighting={json.dumps(prev.get('experience_weighting', {}), ensure_ascii=False)}\n"
            f"strategy_experience_plan={json.dumps(strategy.get('cv_strategy', {}).get('experience_plan', []), ensure_ascii=False)}"
        )
        return system, user
    if step == "tech_competence_generation":
        user = (
            "Generate tech competence in exactly 3 columns: Programming, Knowledge, Soft Skills. "
            "Output key: tech_competence with those 3 keys and list values only. Max 10 items per column. "
            "Use only items supported by strategy terms/evidence.\n"
            f"context={json.dumps(ctx, ensure_ascii=False)}\n"
            f"mandatory_terms={json.dumps(strategy.get('cv_strategy', {}).get('mandatory_cv_terms', []), ensure_ascii=False)}\n"
            f"strategy_tech={json.dumps(strategy.get('cv_strategy', {}).get('tech_competence_inclusion', {}), ensure_ascii=False)}"
        )
        return system, user
    return system, "{}"


def run_steps_1_to_6(*, strategy: Dict[str, Any], job_std: Dict[str, Any], employee: Dict[str, Any], policy: Dict[str, Any], api_key: str | None = None) -> Dict[str, Any]:
    api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
    ctx = _job_context(job_std, strategy)
    out: Dict[str, Any] = {"llm_enabled": bool(api_key), "steps": {}}

    exec_cfg = ((policy.get("cv_generation_policy", {}) or {}).get("llm_execution", {}) or {})
    max_calls = int(exec_cfg.get("max_calls_per_job", 8))
    max_retries = int(exec_cfg.get("max_retries_per_step", 1))
    retry_compact = bool(exec_cfg.get("retry_with_compact_output", True))
    calls_used = 0

    step_names = [
        "job_understanding",
        "persona_selection",
        "experience_weighting",
        "summary_adaptation",
        "experience_generation",
        "tech_competence_generation",
    ]
    for step in step_names:
        out["steps"].setdefault(step, {})
        cfg = cv_llm_routing.routed_step_config(policy, step=step, retry_count=0)
        if api_key:
            last_err = ""
            llm_done = False
            retries = max(0, max_retries)
            for attempt in range(retries + 1):
                if calls_used >= max_calls:
                    last_err = f"LLM call budget reached ({max_calls}/{max_calls})"
                    break
                try:
                    route = cv_llm_routing.routed_step_config(
                        policy,
                        step=step,
                        retry_count=attempt,
                        force_compact=(retry_compact and attempt > 0),
                    )
                    sys_p, usr_p = _prompt_for_step(step, ctx, out["steps"], strategy, int(route.get("max_output_tokens", 400)))
                    result = _call_openai_json(
                        api_key=api_key,
                        model=str(route["model"]),
                        temperature=float(route["temperature"]),
                        system_prompt=sys_p,
                        user_prompt=usr_p,
                    )
                    calls_used += 1
                    result = _enforce_size_budgets(step, result, policy)
                    out["steps"][step] = {"source": "llm", "route": route, "attempt": attempt + 1, "result": result}
                    llm_done = True
                    break
                except Exception as exc:
                    calls_used += 1
                    last_err = str(exc)
            if llm_done:
                continue
            out["steps"][step] = {"source": "fallback_after_llm_error", "route": cfg, "error": last_err}
        # deterministic fallback
        if step == "job_understanding":
            result = _fallback_step_1(job_std)
        elif step == "persona_selection":
            result = _fallback_step_2(out["steps"].get("job_understanding", {}).get("result", _fallback_step_1(job_std)))
        elif step == "experience_weighting":
            result = _fallback_step_4(strategy)
        elif step == "summary_adaptation":
            result = _fallback_step_5(strategy, employee)
        elif step == "experience_generation":
            result = _fallback_step_6(strategy)
        else:
            result = _fallback_step_7(strategy)
        result = _enforce_size_budgets(step, result, policy)
        out["steps"][step]["result"] = result
        out["steps"][step]["source"] = out["steps"][step].get("source", "fallback")

    out["usage"] = {
        "llm_calls_used": calls_used,
        "llm_calls_budget": max_calls,
        "llm_enabled": bool(api_key),
    }
    return out
