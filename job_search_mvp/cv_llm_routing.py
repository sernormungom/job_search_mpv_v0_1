#!/usr/bin/env python3
"""Policy-driven LLM routing for CV generation steps."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List


DEFAULT_STEP_ORDER = [
    "job_understanding",
    "persona_selection",
    "experience_weighting",
    "summary_adaptation",
    "experience_generation",
    "tech_competence_generation",
]


@dataclass
class StepRoute:
    step: str
    model: str
    reasoning_effort: str
    max_input_tokens: int
    max_output_tokens: int
    temperature: float
    fallback_model: str
    fallback_reasoning_effort: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _deep_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _step_defaults(step: str) -> StepRoute:
    defaults: Dict[str, StepRoute] = {
        "job_understanding": StepRoute(step, "gpt-5.4-mini", "medium", 5000, 500, 0.1, "gpt-5.4-mini", "low"),
        "persona_selection": StepRoute(step, "gpt-5.4", "medium", 6000, 400, 0.1, "gpt-5.4-mini", "low"),
        "experience_weighting": StepRoute(step, "gpt-5.5", "high", 9000, 1200, 0.1, "gpt-5.4", "medium"),
        "summary_adaptation": StepRoute(step, "gpt-5.4", "medium", 7000, 350, 0.2, "gpt-5.4-mini", "low"),
        "experience_generation": StepRoute(step, "gpt-5.4", "medium", 9000, 1200, 0.2, "gpt-5.4-mini", "low"),
        "tech_competence_generation": StepRoute(step, "gpt-5.4-mini", "low", 5000, 300, 0.1, "gpt-5.4-mini", "low"),
    }
    return defaults.get(step, StepRoute(step, "gpt-5.4-mini", "low", 4000, 300, 0.1, "gpt-5.4-mini", "low"))


def load_step_route(policy: Dict[str, Any], step: str) -> StepRoute:
    base = _step_defaults(step)
    cfg = _deep_get(policy, "cv_generation_policy", "llm_routing", "steps", step, default={}) or {}
    return StepRoute(
        step=step,
        model=str(cfg.get("model", base.model)),
        reasoning_effort=str(cfg.get("reasoning_effort", base.reasoning_effort)),
        max_input_tokens=int(cfg.get("max_input_tokens", base.max_input_tokens)),
        max_output_tokens=int(cfg.get("max_output_tokens", base.max_output_tokens)),
        temperature=float(cfg.get("temperature", base.temperature)),
        fallback_model=str(cfg.get("fallback_model", base.fallback_model)),
        fallback_reasoning_effort=str(cfg.get("fallback_reasoning_effort", base.fallback_reasoning_effort)),
    )


def routed_step_config(
    policy: Dict[str, Any],
    *,
    step: str,
    retry_count: int = 0,
    force_compact: bool = False,
) -> Dict[str, Any]:
    route = load_step_route(policy, step)
    cfg = route.to_dict()
    if retry_count > 0:
        # Retry path: cheaper model and tighter budget for compression/fix pass.
        cfg["model"] = route.fallback_model
        cfg["reasoning_effort"] = route.fallback_reasoning_effort
        cfg["max_output_tokens"] = max(120, int(route.max_output_tokens * 0.65))
    if force_compact:
        cfg["max_output_tokens"] = max(120, int(cfg["max_output_tokens"] * 0.75))
    return cfg


def build_routing_plan(policy: Dict[str, Any]) -> Dict[str, Any]:
    step_order = _deep_get(policy, "cv_generation_policy", "llm_routing", "step_order", default=DEFAULT_STEP_ORDER) or DEFAULT_STEP_ORDER
    steps: List[Dict[str, Any]] = []
    total_out = 0
    for step in step_order:
        cfg = routed_step_config(policy, step=step)
        total_out += int(cfg["max_output_tokens"])
        steps.append(cfg)
    return {
        "step_order": list(step_order),
        "steps": steps,
        "estimated_total_max_output_tokens": total_out,
    }

