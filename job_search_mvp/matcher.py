#!/usr/bin/env python3
"""
First matcher prototype for the Job Search Automation MVP.

Input:
  - one copied job description as a .txt file
  - v0.1 YAML files from the starter package

Output:
  - job_standardized.yaml
  - match_result.yaml

This prototype is intentionally deterministic and local. It does not scrape websites,
call an LLM, or generate CV text. It tests the core data model assumption:
explicit job requirements can be preserved and matched to evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .paths import resolve_data_dir

try:
    import yaml  # type: ignore
except ModuleNotFoundError:
    yaml = None


EXPLICIT_TERM_CATALOG: Dict[str, List[str]] = {
    "languages": [
        "C++", "C#", "C", "Python", "Java", "Bash", "Perl", "Fortran", "MATLAB", "Matlab",
        "Simulink", "SQL", "JavaScript", "TypeScript"
    ],
    "tools": [
        "Jira", "Git", "Gerrit", "Jenkins", "Bitbucket", "GitHub", "GitHub Copilot",
        "Microsoft Copilot", "VolvoGPT", "Volvo GPT", "VS Code", "Eclipse", "Cygwin",
        "Vector", "Vector DaVinci", "DaVinci", "DaVinci Developer", "CANoe", "CANalyzer",
        "SystemWeaver", "AUTOSAR", "Raspberry Pi", "Arduino"
    ],
    "methods": [
        "CI/CD", "Agile", "Scrum", "SAFe", "PI Planning", "DevOps", "V-model", "Waterfall",
        "requirements analysis", "root cause analysis", "test automation", "unit testing",
        "model-based development", "model-based programming"
    ],
    "standards": [
        "ISO 26262", "DNV", "SIL", "ASIL", "certified development process"
    ],
    "verification": [
        "V&V", "verification and validation", "SIL", "HIL", "PIL", "MIL", "Hardware-in-the-Loop",
        "Software-in-the-Loop", "Model-in-the-Loop", "Google Test", "Google Mock", "smoke testing",
        "simulation", "validation", "verification", "testing"
    ],
    "domains": [
        "embedded", "embedded systems", "real-time", "safety-critical", "autonomous", "automotive",
        "heavy vehicles", "telecom", "radio base", "distributed systems", "control systems",
        "industrial", "marine", "AI-assisted development", "developer productivity", "machine learning",
        "computer vision", "automation", "AI in verification and validation"
    ],
}

ROLE_ARCHETYPES: List[Tuple[str, List[str]]] = [
    ("Embedded Software Engineer", ["embedded", "autosar", "c++", "real-time", "vector", "sil", "hil"]),
    ("AI Engineering Enablement Lead", ["ai-assisted", "developer productivity", "copilot", "ai adoption", "ai enablement"]),
    ("Verification and Validation Engineer", ["verification", "validation", "sil", "hil", "test automation", "google test"]),
    ("Systems Engineer", ["systems engineer", "system integration", "requirements", "architecture"]),
    ("Technical Lead", ["technical lead", "lead engineer", "architecture", "mentoring", "cross-functional"]),
    ("Software Engineer", ["software engineer", "developer", "programming", "implementation"]),
]

GENERIC_LOW_SIGNAL_TERMS = {
    "automotive",
    "industrial",
    "automation",
    "testing",
    "verification",
    "validation",
    "agile",
    "scrum",
    "devops",
}

HIGH_SIGNAL_TERMS = {
    "c++",
    "c",
    "python",
    "matlab",
    "simulink",
    "autosar",
    "vector",
    "davinci",
    "iso 26262",
    "sil",
    "hil",
    "ci/cd",
    "jenkins",
    "git",
    "gerrit",
    "machine learning",
    "computer vision",
    "ai-assisted development",
}

LOW_FIT_TITLE_PATTERNS = [
    "ap/ar",
    "redovisning",
    "accounting",
    "accountant",
    "interior component designer",
    "samverkansledare",
    "incident manager",
    "application security architect",
    "data analysis engineer",
    "power electronics",
    "electrical system architect",
    "electronics engineer",
    "clay modeller",
    "compliance professional",
]

OFF_DIRECTION_PATTERNS = [
    "electrical",
    "electronics",
    "power electronics",
    "compliance",
    "data analysis",
    "analyst",
    "clay modeller",
]

SOFTWARE_DIRECTION_SIGNALS = [
    "software engineer",
    "embedded",
    "verification",
    "validation",
    "developer productivity",
    "ai-assisted development",
    "machine learning",
    "computer vision",
    "technical lead",
    "devops",
    "ci/cd",
]

CANONICAL_SECTION_HEADERS: Dict[str, List[str]] = {
    "job_description": [
        "job description",
        "position description",
        "role description",
        "about the role",
        "responsibilities",
        "arbetsbeskrivning",
        "uppdragsbeskrivning",
        "uppdraget",
        "arbetsuppgifter",
        "om rollen",
    ],
    "requirements_must_have": [
        "requirements",
        "must have",
        "required",
        "mandatory",
        "qualifications",
        "minimum requirements",
        "krav",
        "obligatoriska krav",
        "skallkrav",
        "måste ha",
    ],
    "requirements_nice_to_have": [
        "nice to have",
        "preferred",
        "desirable",
        "plus",
        "bonus",
        "meriterande",
        "önskvärt",
        "bra att ha",
    ],
}

MUST_HAVE_MARKERS = [
    "requirements",
    "must have",
    "required",
    "mandatory",
    "minimum requirements",
    "qualifications",
    "krav",
    "obligatoriska krav",
    "skallkrav",
    "måste",
]

NICE_TO_HAVE_MARKERS = [
    "desirable",
    "nice to have",
    "nice",
    "meriterande",
    "plus",
    "preferred",
    "önskvärt",
    "bra att ha",
]

SWEDISH_LANGUAGE_MARKERS = [
    "arbetsuppgifter",
    "krav",
    "meriterande",
    "erfarenhet av",
    "vi söker",
    "göteborg",
    "ansökan",
    "uppdragsbeskrivning",
]

ENGLISH_LANGUAGE_MARKERS = [
    "job description",
    "requirements",
    "qualifications",
    "nice to have",
    "about the role",
    "we are looking for",
    "application",
]

SWEDISH_MUST_HAVE_MARKERS = [
    "krav",
    "obligatoriska krav",
    "skallkrav",
    "måste",
]

SWEDISH_NICE_TO_HAVE_MARKERS = [
    "meriterande",
    "önskvärt",
    "bra att ha",
]

ENGLISH_MUST_HAVE_MARKERS = [
    "requirements",
    "must have",
    "required",
    "mandatory",
    "minimum requirements",
    "qualifications",
]

ENGLISH_NICE_TO_HAVE_MARKERS = [
    "desirable",
    "nice to have",
    "nice",
    "plus",
    "preferred",
]

POSTING_CHROME_MARKERS = [
    "publicerad den",
    "roll",
    "senioritetsnivå",
    "distansarbete",
    "uppdragsperiod",
    "ansökningstiden löper ut",
    "antal ansökningar",
    "ansök",
]

DESCRIPTION_SECTION_MARKERS = [
    "uppdragsbeskrivning",
    "job description",
    "about the role",
    "key responsibilities",
    "required experience",
    "requirements",
    "qualifications",
]


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML/JSON for the prototype.

    PyYAML is preferred. When PyYAML is not installed, the data files in this
    package are still valid JSON-compatible YAML, so json.loads works. For older
    package versions that used handwritten YAML, keep the small fallback parsers.
    """
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if path.name == "experience_database.yaml":
        return parse_experience_database_fallback(text)
    if path.name == "tool_aliases.yaml":
        return parse_tool_aliases_fallback(text)
    if path.name == "career_preferences.yaml":
        return parse_career_preferences_fallback(text)
    raise RuntimeError(
        f"Cannot read {path.name} without PyYAML. Install it with: "
        "python -m pip install pyyaml"
    )


def write_yaml(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        if yaml is not None:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=110)
        else:
            # JSON is valid YAML 1.2 and keeps this prototype dependency-free.
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")




def normalize_url_for_id(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    remove_prefixes = ("utm_",)
    remove_exact = {"fbclid", "gclid", "mc_cid", "mc_eid"}
    clean_query = [(k, v) for k, v in query if not k.startswith(remove_prefixes) and k not in remove_exact]
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), urllib.parse.urlencode(clean_query), "")
    )


def make_job_id(job_text: str, source_url: str | None = None) -> str:
    if source_url:
        key = "url:" + normalize_url_for_id(source_url)
    else:
        body = re.sub(r"\s+", " ", job_text.lower()).strip()
        key = "content:" + body[:5000]
    return "job_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]

def parse_scalar(line: str) -> str:
    return line.split(":", 1)[1].strip().strip("'\"")


def parse_experience_database_fallback(text: str) -> Dict[str, Any]:
    role_groups: List[Dict[str, Any]] = []
    current_rg: Dict[str, Any] | None = None
    current_block: Dict[str, Any] | None = None
    current_list_key: str | None = None
    current_ev: Dict[str, Any] | None = None
    in_evidence = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped.startswith("- role_group_id:"):
            current_rg = {"role_group_id": stripped.split(":", 1)[1].strip(), "blocks": []}
            role_groups.append(current_rg)
            current_block = None
            in_evidence = False
        elif current_rg is not None and indent == 6 and any(stripped.startswith(k + ":") for k in ["company", "display_role_title", "time_range", "role_group_type"]):
            k = stripped.split(":", 1)[0]
            current_rg[k] = parse_scalar(stripped)
        elif current_rg is not None and indent == 6 and stripped.startswith("recency_rank:"):
            try:
                current_rg["recency_rank"] = int(parse_scalar(stripped))
            except ValueError:
                current_rg["recency_rank"] = 99
        elif stripped.startswith("- block_id:"):
            current_block = {"block_id": stripped.split(":", 1)[1].strip(), "evidence_items": []}
            if current_rg is not None:
                current_rg.setdefault("blocks", []).append(current_block)
            current_list_key = None
            current_ev = None
            in_evidence = False
        elif current_block is not None and indent == 10 and any(stripped.startswith(k + ":") for k in ["role_title", "block_type", "narrative_weight", "seniority"]):
            k = stripped.split(":", 1)[0]
            current_block[k] = parse_scalar(stripped)
        elif current_block is not None and indent == 10 and stripped in ["domains:", "industries:", "languages:", "tools:", "processes_standards:", "verification_validation:", "skills:", "languages_or_modeling:"]:
            current_list_key = stripped[:-1]
            current_block.setdefault(current_list_key, [])
            in_evidence = False
        elif current_block is not None and current_list_key and indent >= 12 and stripped.startswith("- ") and not in_evidence:
            current_block.setdefault(current_list_key, []).append(stripped[2:].strip())
        elif current_block is not None and stripped == "evidence_items:":
            in_evidence = True
            current_list_key = None
        elif current_block is not None and in_evidence and stripped.startswith("- evidence_id:"):
            current_ev = {"evidence_id": stripped.split(":", 1)[1].strip(), "tags": []}
            current_block.setdefault("evidence_items", []).append(current_ev)
        elif current_ev is not None and in_evidence and stripped.startswith("text:"):
            current_ev["text"] = parse_scalar(stripped)
        elif current_ev is not None and in_evidence and stripped.startswith("type:"):
            current_ev["type"] = parse_scalar(stripped)
        elif current_ev is not None and in_evidence and stripped.startswith("- "):
            current_ev.setdefault("tags", []).append(stripped[2:].strip())
    return {"experience_database": {"employee_id": "norberto_munoz", "role_groups": role_groups}}


def parse_tool_aliases_fallback(text: str) -> Dict[str, Any]:
    aliases: Dict[str, Dict[str, List[str]]] = {}
    current_key = None
    current_section = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 2 and stripped.endswith(":"):
            current_key = stripped[:-1]
            aliases[current_key] = {"exact_terms": [], "supporting_terms": []}
        elif current_key and indent == 4 and stripped in ["exact_terms:", "supporting_terms:"]:
            current_section = stripped[:-1]
        elif current_key and current_section and stripped.startswith("- "):
            aliases[current_key][current_section].append(stripped[2:].strip())
    return {"tool_aliases": aliases}


def parse_career_preferences_fallback(text: str) -> Dict[str, Any]:
    # Conservative defaults matching the v0.1 design.
    return {"career_preferences": {"scoring_weights": {"expertise_fit": 0.40, "growth_fit": 0.30, "interest_fit": 0.20, "practical_fit": 0.10}, "growth_focus": {"primary": ["AI-assisted development", "AI in verification and validation", "machine learning development", "AI for developer productivity", "computer vision"]}, "ai_growth_bias": {"reward_signals": ["tooling ownership", "process transformation", "first-time AI adoption", "regulated-context AI", "AI-assisted verification and validation"]}, "work_preferences": {"role_shape": {"preferred": ["technical delivery", "cross-team influence", "innovation leadership", "process ownership", "mentoring"], "avoid": ["pure administration", "generic project coordination without technical substance"]}}, "target_roles": {"avoid": ["pure people manager", "low-seniority maintenance-only role", "role with no technical growth"]}}}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def term_in_text(term: str, text: str) -> bool:
    # Handles punctuation-heavy terms like C++, CI/CD, C#, V&V.
    if not term:
        return False
    escaped = re.escape(term.lower())
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.lower()) is not None


def find_terms(text: str, terms: Iterable[str]) -> List[str]:
    found = []
    for term in terms:
        if term_in_text(term, text):
            found.append(term)
    # preserve order but deduplicate case-insensitively
    seen = set()
    out = []
    for t in found:
        key = t.lower()
        if key not in seen:
            out.append(t)
            seen.add(key)
    return out


def flatten_values(value: Any) -> List[str]:
    out: List[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, list):
        for item in value:
            out.extend(flatten_values(item))
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(flatten_values(item))
    return out


def build_evidence_index(experience_db: Dict[str, Any]) -> List[Dict[str, Any]]:
    index: List[Dict[str, Any]] = []
    root = experience_db.get("experience_database", experience_db)
    for rg in root.get("role_groups", []):
        rg_terms = flatten_values({k: v for k, v in rg.items() if k != "blocks"})
        for block in rg.get("blocks", []):
            block_terms = flatten_values({k: v for k, v in block.items() if k != "evidence_items"})
            evidence_texts = []
            evidence_ids = []
            evidence_tags = []
            for ev in block.get("evidence_items", []):
                evidence_ids.append(ev.get("evidence_id"))
                evidence_texts.append(ev.get("text", ""))
                evidence_tags.extend(ev.get("tags", []))
            searchable_terms = rg_terms + block_terms + evidence_texts + evidence_tags
            index.append(
                {
                    "role_group_id": rg.get("role_group_id"),
                    "company": rg.get("company"),
                    "display_role_title": rg.get("display_role_title"),
                    "time_range": rg.get("time_range"),
                    "recency_rank": rg.get("recency_rank", 99),
                    "role_group_type": rg.get("role_group_type"),
                    "block_id": block.get("block_id"),
                    "block_type": block.get("block_type"),
                    "evidence_ids": [e for e in evidence_ids if e],
                    "searchable_text": normalize(" | ".join(str(x) for x in searchable_terms if x)),
                    "raw_terms": searchable_terms,
                }
            )
    return index


def load_aliases(alias_data: Dict[str, Any]) -> Dict[str, List[str]]:
    aliases = {}
    for key, val in alias_data.get("tool_aliases", alias_data).items():
        terms = [key]
        terms.extend(val.get("exact_terms", []) or [])
        terms.extend(val.get("supporting_terms", []) or [])
        aliases[key] = list(dict.fromkeys([t for t in terms if t]))
    return aliases


def infer_title(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip(" \t#-*:")
        if len(cleaned) >= 6 and len(cleaned) <= 120:
            return cleaned
    return "Unspecified role"


def infer_location(text: str) -> Dict[str, str | None]:
    low = text.lower()
    city = None
    if "gothenburg" in low or "göteborg" in low:
        city = "Gothenburg"
    elif "stockholm" in low:
        city = "Stockholm"
    elif "malmö" in low or "malmo" in low:
        city = "Malmö"
    work_mode = "unspecified"
    if "hybrid" in low or "hybrid" in low:
        work_mode = "hybrid"
    elif "remote" in low or "distans" in low:
        work_mode = "remote"
    elif "onsite" in low or "on-site" in low or "på plats" in low:
        work_mode = "onsite"
    return {"city": city, "country": "Sweden" if city else None, "work_mode": work_mode}


def infer_seniority(text: str) -> str:
    low = text.lower()
    if any(x in low for x in ["principal", "staff engineer"]):
        return "staff/principal"
    if any(x in low for x in ["senior", "lead", "experienced", "erfaren"]):
        return "senior"
    if any(x in low for x in ["junior", "graduate", "entry level"]):
        return "junior"
    return "unspecified"


def infer_role_archetype(text: str) -> str:
    low = text.lower()
    best = ("Software Engineer", 0)
    for label, terms in ROLE_ARCHETYPES:
        score = sum(1 for t in terms if t in low)
        if score > best[1]:
            best = (label, score)
    return best[0]


def infer_language(text: str) -> str:
    low = text.lower()
    swedish_hits = sum(1 for marker in SWEDISH_LANGUAGE_MARKERS if marker in low)
    english_hits = sum(1 for marker in ENGLISH_LANGUAGE_MARKERS if marker in low)
    if swedish_hits > english_hits:
        return "Swedish"
    if english_hits > swedish_hits:
        return "English"
    return "English/unspecified"


def _core_content_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    low_lines = [line.lower() for line in lines]
    start_idx = 0
    for i, line in enumerate(low_lines):
        if any(marker in line for marker in DESCRIPTION_SECTION_MARKERS):
            start_idx = i + 1
            break

    kept: List[str] = []
    for line in low_lines[start_idx:]:
        if any(marker in line for marker in POSTING_CHROME_MARKERS):
            continue
        kept.append(line)

    if not kept:
        kept = low_lines
    return "\n".join(kept)


def infer_content_language(text: str) -> str:
    core = _core_content_text(text)
    swedish_hits = sum(1 for marker in SWEDISH_LANGUAGE_MARKERS if marker in core)
    english_hits = sum(1 for marker in ENGLISH_LANGUAGE_MARKERS if marker in core)
    if swedish_hits > english_hits:
        return "Swedish"
    if english_hits > swedish_hits:
        return "English"
    return "English/unspecified"


def requirement_markers_for_language(language: str) -> Tuple[List[str], List[str]]:
    low = language.lower()
    if low == "swedish":
        must = SWEDISH_MUST_HAVE_MARKERS + MUST_HAVE_MARKERS
        nice = SWEDISH_NICE_TO_HAVE_MARKERS + NICE_TO_HAVE_MARKERS
        return list(dict.fromkeys(must)), list(dict.fromkeys(nice))
    if low == "english":
        must = ENGLISH_MUST_HAVE_MARKERS + MUST_HAVE_MARKERS
        nice = ENGLISH_NICE_TO_HAVE_MARKERS + NICE_TO_HAVE_MARKERS
        return list(dict.fromkeys(must)), list(dict.fromkeys(nice))
    return MUST_HAVE_MARKERS, NICE_TO_HAVE_MARKERS


def normalize_header(text: str) -> str:
    low = text.lower().strip(" \t:-*#")
    low = re.sub(r"[^\w\såäö/+-]", " ", low)
    return re.sub(r"\s+", " ", low).strip()


def header_to_canonical(line: str) -> str | None:
    candidate = normalize_header(line)
    if not candidate:
        return None
    for canonical, headers in CANONICAL_SECTION_HEADERS.items():
        for header in headers:
            h = normalize_header(header)
            if candidate == h or candidate.startswith(h + " "):
                return canonical
    return None


def extract_canonical_sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {key: [] for key in CANONICAL_SECTION_HEADERS.keys()}
    active: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header = header_to_canonical(line)
        if header is not None:
            active = header
            continue
        if active is None:
            continue
        cleaned = line.strip(" -•\t")
        if len(cleaned) > 2:
            sections[active].append(cleaned)
    return sections


def standardize_job(job_text: str, source_url: str | None = None) -> Dict[str, Any]:
    explicit = {cat: find_terms(job_text, terms) for cat, terms in EXPLICIT_TERM_CATALOG.items()}
    role_archetype = infer_role_archetype(job_text)
    title = infer_title(job_text)
    short_summary = " ".join([s.strip() for s in re.split(r"(?<=[.!?])\s+", job_text.strip())[:3]])
    detected_language = infer_content_language(job_text)
    must_markers, nice_markers = requirement_markers_for_language(detected_language)
    canonical_sections = extract_canonical_sections(job_text)
    must_have = dedupe_lines(
        canonical_sections.get("requirements_must_have", [])
        + extract_requirement_lines(job_text, must_markers)
    )
    nice_to_have = dedupe_lines(
        canonical_sections.get("requirements_nice_to_have", [])
        + extract_requirement_lines(job_text, nice_markers)
    )
    job_description_lines = dedupe_lines(canonical_sections.get("job_description", []))
    job_description = " ".join(job_description_lines).strip()
    if not job_description:
        job_description = short_summary[:1200]
    return {
        "job_standardized": {
            "job_id": make_job_id(job_text, source_url),
            "source": {
                "site": "manual_input",
                "url": source_url,
                "scraped_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
            "language": {
                "original": detected_language,
                "standardized_output": "English",
            },
            "identity": {
                "original_title": title,
                "normalized_title": role_archetype,
                "company": None,
                "location": infer_location(job_text),
                "employment_type": "unspecified",
            },
            "summary": {"short_summary": short_summary[:700]},
            "job_description": job_description[:1200],
            "job_analysis": {
                "role_archetype": role_archetype,
                "seniority": infer_seniority(job_text),
                "primary_technical_focus": infer_primary_focus(explicit, role_archetype),
                "secondary_technical_focus": infer_secondary_focus(explicit),
                "leadership_expectations": infer_leadership(job_text),
                "de_emphasized_or_not_required": [],
            },
            "explicit_terms": explicit,
            "normalized_requirements": {
                "must_have": must_have[:8],
                "nice_to_have": nice_to_have[:8],
            },
            "blockers": infer_blockers(job_text),
            "raw_text_excerpt": job_text[:1800],
        }
    }


def infer_primary_focus(explicit: Dict[str, List[str]], role_archetype: str) -> List[str]:
    focus = []
    if "Embedded" in role_archetype:
        focus.append("embedded software development")
    if explicit.get("verification"):
        focus.append("verification and validation")
    if any(t.lower() in ["ai-assisted development", "machine learning", "computer vision"] for t in explicit.get("domains", [])):
        focus.append("AI-enabled engineering")
    return focus or [role_archetype]


def infer_secondary_focus(explicit: Dict[str, List[str]]) -> List[str]:
    out = []
    for cat in ["methods", "standards", "tools", "domains"]:
        out.extend(explicit.get(cat, [])[:5])
    return list(dict.fromkeys(out))[:12]


def infer_leadership(text: str) -> List[str]:
    low = text.lower()
    signals = []
    mapping = {
        "technical ownership": ["ownership", "own", "ansvar"],
        "cross-functional collaboration": ["cross-functional", "collaborate", "samarbeta"],
        "mentoring": ["mentor", "coach", "coaching"],
        "team leadership": ["lead team", "team lead", "manage team", "people manager"],
        "stakeholder coordination": ["stakeholder", "customer", "product owner"],
    }
    for label, terms in mapping.items():
        if any(t in low for t in terms):
            signals.append(label)
    return signals or ["not explicitly stated"]


def extract_requirement_lines(text: str, markers: List[str]) -> List[str]:
    lines = [l.strip(" -•\t") for l in text.splitlines()]
    selected = []
    active = False
    for line in lines:
        if not line:
            continue
        low = line.lower()
        marker_hit = any(m in low for m in markers)
        is_header_like = low.endswith(":") or (len(line) <= 60 and line == line.strip())
        if marker_hit and (is_header_like or active):
            active = True
            if len(line) > 15 and not low.endswith(":"):
                selected.append(line)
            continue
        if active:
            if re.match(r"^[A-ZÅÄÖ][A-Za-zÅÄÖåäö ]{2,}:$", line) and len(selected) > 0:
                active = False
                continue
            if len(line) > 8:
                selected.append(line)
        if len(selected) >= 8:
            break
    return selected[:8]


def dedupe_lines(lines: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for line in lines:
        cleaned = line.strip()
        if len(cleaned) <= 2:
            continue
        key = normalize(cleaned)
        if key in seen:
            continue
        out.append(cleaned)
        seen.add(key)
    return out


def infer_blockers(text: str) -> Dict[str, List[str]]:
    low = text.lower()
    hard, soft = [], []
    if "fluent swedish" in low or "flytande svenska" in low or "svenska är ett krav" in low:
        hard.append("fluent Swedish required")
    elif "swedish" in low or "svenska" in low:
        soft.append("Swedish may be preferred")
    if "onsite" in low and "gothenburg" not in low and "göteborg" not in low:
        soft.append("onsite location may need confirmation")
    return {"hard": hard, "soft": soft}


def match_job(job: Dict[str, Any], evidence_index: List[Dict[str, Any]], aliases: Dict[str, List[str]], prefs: Dict[str, Any]) -> Dict[str, Any]:
    js = job["job_standardized"]
    explicit_terms: Dict[str, List[str]] = js["explicit_terms"]
    term_categories: Dict[str, str] = {}
    for category, terms in explicit_terms.items():
        for term in terms:
            term_categories.setdefault(term, category)
    all_job_terms = list(dict.fromkeys([term for terms in explicit_terms.values() for term in terms]))

    matched_tools = []
    role_group_scores: Dict[str, float] = {}
    block_hits: Dict[str, Dict[str, Any]] = {}

    for term in all_job_terms:
        alias_terms = aliases.get(term, [term])
        # Also allow catalog term itself to match alias keys that mention it.
        for alias_key, expanded in aliases.items():
            if term.lower() == alias_key.lower() or any(term.lower() == e.lower() for e in expanded):
                alias_terms = list(dict.fromkeys(alias_terms + expanded))
        for block in evidence_index:
            exact = term_in_text(term, block["searchable_text"])
            support = any(term_in_text(a, block["searchable_text"]) for a in alias_terms if a.lower() != term.lower())
            if exact or support:
                weight = 1.0 if exact else 0.7
                # Recent evidence gets a small boost; foundational keeps a small bonus.
                recency_bonus = max(0.0, (5 - float(block.get("recency_rank", 5))) * 0.05)
                foundational_bonus = 0.08 if block.get("role_group_type") == "foundational" else 0.0
                score = weight + recency_bonus + foundational_bonus
                role_group_scores[block["role_group_id"]] = role_group_scores.get(block["role_group_id"], 0) + score
                block_hits.setdefault(block["block_id"], {"block": block, "terms": [], "evidence_ids": block["evidence_ids"]})
                block_hits[block["block_id"]]["terms"].append({"job_term": term, "match_type": "exact" if exact else "alias/supporting"})
                matched_tools.append(
                    {
                        "job_term": term,
                        "match_type": "exact" if exact else "alias/supporting",
                        "matched_block_id": block["block_id"],
                        "role_group_id": block["role_group_id"],
                        "evidence_ids": block["evidence_ids"][:3],
                    }
                )

    unique_matched_terms = {m["job_term"].lower(): m for m in matched_tools}
    total_term_weight = sum(term_weight(term, term_categories.get(term, "")) for term in all_job_terms) or 1.0
    matched_term_weight = 0.0
    for lower_term, match in unique_matched_terms.items():
        category = term_categories.get(match["job_term"], "")
        quality = 1.0 if match.get("match_type") == "exact" else 0.75
        matched_term_weight += term_weight(lower_term, category) * quality
    tool_fit = round(100 * min(1.0, matched_term_weight / total_term_weight))

    domain_terms = explicit_terms.get("domains", [])
    domain_matches = sorted({m["job_term"] for m in matched_tools if m["job_term"] in domain_terms})
    if domain_terms:
        domain_total = sum(term_weight(term, "domains") for term in domain_terms) or 1.0
        domain_matched = sum(term_weight(term, "domains") for term in domain_matches)
        domain_fit = round(100 * min(1.0, domain_matched / domain_total))
    else:
        domain_fit = 50

    expertise_fit = round((tool_fit * 0.75) + (domain_fit * 0.25))
    concrete_matches = [
        match["job_term"]
        for match in unique_matched_terms.values()
        if term_categories.get(match["job_term"], "") in {"languages", "tools", "standards"}
        or match["job_term"].lower() in HIGH_SIGNAL_TERMS
    ]
    if unique_matched_terms and not concrete_matches:
        tool_fit = min(tool_fit, 58)
        expertise_fit = min(expertise_fit, 58)
    role_fit = score_role_fit(js, list(unique_matched_terms.keys()))
    growth_fit = score_growth_fit(js, prefs)
    interest_fit = score_interest_fit(js, prefs)
    practical_fit = score_practical_fit(js, prefs)
    risk_score = score_risk(js)

    overall = round(
        expertise_fit * 0.30
        + role_fit * 0.30
        + growth_fit * 0.20
        + interest_fit * 0.15
        + practical_fit * 0.05
        - risk_score * 0.35
    )
    overall = max(0, min(100, overall))

    selected_role_groups = sorted(role_group_scores.items(), key=lambda kv: kv[1], reverse=True)[:3]
    recommended_status = recommend_status(
        overall,
        role_fit,
        expertise_fit,
        interest_fit,
        js["blockers"].get("hard", []),
    )
    if js["blockers"]["hard"]:
        recommended_status = "reject"

    return {
        "match_result": {
            "job_id": js["job_id"],
            "employee_id": "norberto_munoz",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "overall_score": overall,
            "score_breakdown": {
                "expertise_fit": expertise_fit,
                "role_fit": role_fit,
                "tool_fit": tool_fit,
                "domain_fit": domain_fit,
                "growth_fit": growth_fit,
                "interest_fit": interest_fit,
                "practical_fit": practical_fit,
                "risk_score": risk_score,
            },
            "decision": {
                "recommended_status": recommended_status,
                "reason": build_reason(js, overall, expertise_fit, role_fit, risk_score, matched_tools, selected_role_groups),
            },
            "matched_evidence": {
                "explicit_term_matches": matched_tools,
                "domain_matches": domain_matches,
                "selected_role_groups": [
                    {"role_group_id": rg, "match_weight": round(score, 2)} for rg, score in selected_role_groups
                ],
                "matched_blocks": [
                    {
                        "block_id": info["block"]["block_id"],
                        "role_group_id": info["block"]["role_group_id"],
                        "matched_terms": info["terms"],
                        "evidence_ids": info["evidence_ids"][:8],
                    }
                    for info in block_hits.values()
                ],
            },
            "risks": {
                "hard_blockers": js["blockers"].get("hard", []),
                "soft_risks": js["blockers"].get("soft", []),
            },
            "recommendation_for_cv": {
                "must_surface_terms": sorted({m["job_term"] for m in matched_tools}),
                "suggested_role_groups": [rg for rg, _ in selected_role_groups],
                "notes": [
                    "Use cv_strategy.yaml before drafting CV text.",
                    "Surface explicit job tools when supported by exact or alias evidence.",
                ],
            },
        }
    }


def score_growth_fit(js: Dict[str, Any], prefs: Dict[str, Any]) -> int:
    text = normalize(json.dumps(js, ensure_ascii=False))
    cp = prefs.get("career_preferences", prefs)
    primary = cp.get("growth_focus", {}).get("primary", [])
    reward = cp.get("ai_growth_bias", {}).get("reward_signals", [])
    hits = sum(1 for t in primary + reward if t.lower() in text)
    if hits:
        return min(100, 65 + hits * 8)
    # Embedded/systems technical depth still supports growth, but not as strongly as AI-growth themes.
    if any(t in text for t in ["embedded", "software-in-the-loop", "hardware-in-the-loop", "autosar", "technical lead", "systems"]):
        return 72
    if any(t in text for t in ["verification", "validation", "automation"]):
        return 64
    return 55


def score_interest_fit(js: Dict[str, Any], prefs: Dict[str, Any]) -> int:
    text = normalize(json.dumps(js, ensure_ascii=False))
    title = normalize(js.get("identity", {}).get("original_title", ""))
    normalized_title = normalize(js.get("identity", {}).get("normalized_title", ""))
    title_text = f"{title} {normalized_title}"
    cp = prefs.get("career_preferences", prefs)
    preferred = cp.get("work_preferences", {}).get("role_shape", {}).get("preferred", [])
    avoid = cp.get("work_preferences", {}).get("role_shape", {}).get("avoid", []) + cp.get("target_roles", {}).get("avoid", [])
    score = 58 + sum(6 for t in preferred if t.lower() in text) - sum(14 for t in avoid if t.lower() in text)
    if any(pattern in title_text for pattern in OFF_DIRECTION_PATTERNS):
        score -= 26
    if any(signal in text for signal in SOFTWARE_DIRECTION_SIGNALS):
        score += 10
    if ("architect" in title_text or "lead" in title_text) and "software" not in text and "technical" not in text:
        score -= 10
    return max(0, min(100, score))


def score_practical_fit(js: Dict[str, Any], prefs: Dict[str, Any]) -> int:
    loc = js["identity"].get("location", {})
    city = (loc.get("city") or "").lower()
    mode = (loc.get("work_mode") or "").lower()
    if city == "gothenburg" and mode in ["hybrid", "remote", "unspecified"]:
        return 85
    if city == "gothenburg":
        return 80
    if mode == "remote":
        return 75
    if not city:
        return 55
    return 40


def score_risk(js: Dict[str, Any]) -> int:
    hard = len(js["blockers"].get("hard", []))
    soft = len(js["blockers"].get("soft", []))
    return min(100, hard * 70 + soft * 15)


def term_weight(term: str, category: str) -> float:
    low = term.lower()
    if low in HIGH_SIGNAL_TERMS:
        return 1.45
    if low in GENERIC_LOW_SIGNAL_TERMS:
        return 0.35
    if category in {"languages", "tools", "standards"}:
        return 1.20
    if category == "verification":
        return 0.90
    if category == "methods":
        return 0.75
    if category == "domains":
        return 0.50
    return 0.70


def score_role_fit(js: Dict[str, Any], matched_terms: List[str]) -> int:
    text = normalize(json.dumps(js, ensure_ascii=False))
    title = normalize(js.get("identity", {}).get("original_title", ""))
    normalized_title = normalize(js.get("identity", {}).get("normalized_title", ""))
    archetype = normalize(js.get("job_analysis", {}).get("role_archetype", ""))
    matched = {term.lower() for term in matched_terms}
    high_signal_hits = sum(1 for term in matched if term in HIGH_SIGNAL_TERMS)

    score = 52
    if any(t in archetype + " " + normalized_title for t in ["embedded", "software engineer", "verification", "systems engineer", "technical lead"]):
        score += 14
    if any(t in text for t in ["machine learning", "computer vision", "ai-assisted development", "developer productivity"]):
        score += 10
    if high_signal_hits:
        score += min(24, high_signal_hits * 6)
    if any(pattern in title for pattern in LOW_FIT_TITLE_PATTERNS):
        score -= 32
    if "manager" in title and "engineer" not in title and "technical" not in text:
        score -= 16
    if high_signal_hits == 0 and not any(t in text for t in ["software", "embedded", "developer", "engineer", "ai", "machine learning", "verification"]):
        score -= 20
    return max(0, min(100, score))


def recommend_status(
    overall: int,
    role_fit: int,
    expertise_fit: int,
    interest_fit: int,
    hard_blockers: List[str],
) -> str:
    if hard_blockers:
        return "reject"
    if overall >= 76 and role_fit >= 60 and expertise_fit >= 55 and interest_fit >= 50:
        return "keep"
    if overall >= 58 and role_fit >= 45 and interest_fit >= 35:
        return "maybe"
    return "reject"


def build_reason(
    js: Dict[str, Any],
    overall: int,
    expertise_fit: int,
    role_fit: int,
    risk_score: int,
    matches: List[Dict[str, Any]],
    selected: List[Tuple[str, float]],
) -> str:
    terms = sorted({m["job_term"] for m in matches}, key=lambda t: (-term_weight(t, ""), t.lower()))[:12]
    high_signal = [t for t in terms if t.lower() in HIGH_SIGNAL_TERMS]
    rg = [x[0] for x in selected]
    if terms:
        strongest = high_signal[:8] or terms[:8]
        evidence = f" Evidence: {', '.join(rg)}." if rg else ""
        risk = f" Risk score {risk_score}." if risk_score else ""
        return (
            f"Score {overall}: expertise {expertise_fit}, role fit {role_fit}."
            f" Strongest supported terms: {', '.join(strongest)}.{evidence}{risk}"
        )
    return f"Score {overall}: expertise {expertise_fit}, role fit {role_fit}; limited explicit evidence matches found."


def main() -> int:
    parser = argparse.ArgumentParser(description="First matcher prototype: job text -> standardized job + match result")
    parser.add_argument("--job", required=True, help="Path to copied job description .txt")
    parser.add_argument("--data-dir", default="data", help="Path to the data directory")
    parser.add_argument("--out-dir", default="outputs/single", help="Directory for generated YAML outputs")
    parser.add_argument("--source-url", default=None, help="Optional original job posting URL")
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    job_text = Path(args.job).read_text(encoding="utf-8")
    experience_db = load_yaml(data_dir / "experience_database.yaml")
    aliases = load_aliases(load_yaml(data_dir / "tool_aliases.yaml"))
    prefs = load_yaml(data_dir / "career_preferences.yaml")

    evidence_index = build_evidence_index(experience_db)
    job_standardized = standardize_job(job_text, source_url=args.source_url)
    match_result = match_job(job_standardized, evidence_index, aliases, prefs)

    job_id = job_standardized["job_standardized"]["job_id"]
    job_path = out_dir / f"{job_id}.job_standardized.yaml"
    match_path = out_dir / f"{job_id}.match_result.yaml"
    write_yaml(job_path, job_standardized)
    write_yaml(match_path, match_result)

    print(f"Wrote {job_path}")
    print(f"Wrote {match_path}")
    print(f"Overall score: {match_result['match_result']['overall_score']}")
    print(f"Recommendation: {match_result['match_result']['decision']['recommended_status']}")
    print(match_result["match_result"]["decision"]["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
