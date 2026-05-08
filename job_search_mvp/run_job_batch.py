#!/usr/bin/env python3
"""
Batch job intake and review queue builder for Job Search Automation MVP.

Input:
  - a folder of .txt job descriptions
  - v0.1 data files in the package root

Output:
  - one job_standardized.yaml per input
  - one match_result.yaml per input
  - review_queue.csv
  - review_queue.html

This script intentionally does not scrape websites. It processes copied or saved
job descriptions so the matching/review core can be tested before source adapters.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from . import matcher
from .paths import resolve_data_dir
from .standardization.llm_standardizer import BUDGET_OPENAI_MODEL, parse_job_file, standardize_job_with_mode

VERAMA_DETAIL_PATH_RE = re.compile(r"^/app/job-requests/\d+/?$")


def read_job_file(path: Path) -> Tuple[str, str | None, Dict[str, str]]:
    metadata, body = parse_job_file(path)
    source_url = metadata.get("source_url")
    return body, source_url, metadata


def is_probable_listing_page(source_url: str | None, job_text: str) -> bool:
    if not source_url:
        return False
    parsed = urlparse(source_url)
    host = (parsed.netloc or "").lower()
    if "verama.com" not in host and "eworkgroup.com" not in host:
        return False
    if VERAMA_DETAIL_PATH_RE.match(parsed.path or ""):
        return False
    low = job_text.lower()
    return "lediga uppdrag" in low or "rekommenderade" in low or "sök uppdrag" in low


def apply_file_metadata(job_standardized: Dict[str, Any], metadata: Dict[str, str]) -> Dict[str, Any]:
    js = job_standardized.get("job_standardized", {})
    identity = js.setdefault("identity", {})
    title = (metadata.get("title") or "").strip()
    company = (metadata.get("company_client") or metadata.get("company") or "").strip()
    location = (metadata.get("location") or "").strip()
    if title and identity.get("original_title") in {"Full job description", "Hem", "Uppdragsannonser", "Unspecified role"}:
        identity["original_title"] = title
    elif title and not identity.get("original_title"):
        identity["original_title"] = title
    if company and not identity.get("company"):
        identity["company"] = company
    if location and not (identity.get("location") or {}).get("city"):
        loc = identity.setdefault("location", {})
        loc["city"] = "Gothenburg" if location.lower() in {"gothenburg", "göteborg"} else location
        loc.setdefault("country", "Sweden")
    return job_standardized


def get_root(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    return data.get(key, data)


def compact_list(items: List[Any], limit: int = 8) -> str:
    clean = []
    for item in items or []:
        if isinstance(item, dict):
            item = item.get("job_term") or item.get("role_group_id") or json.dumps(item, ensure_ascii=False)
        if item is None:
            continue
        text = str(item)
        if text not in clean:
            clean.append(text)
    suffix = "" if len(clean) <= limit else f" +{len(clean) - limit} more"
    return ", ".join(clean[:limit]) + suffix


def summarize_row(input_file: Path, job_standardized: Dict[str, Any], match_result: Dict[str, Any]) -> Dict[str, str | int]:
    js = get_root(job_standardized, "job_standardized")
    mr = get_root(match_result, "match_result")
    identity = js.get("identity", {})
    loc = identity.get("location", {}) or {}
    score_breakdown = mr.get("score_breakdown", {})
    matched_terms = [m.get("job_term") for m in mr.get("matched_evidence", {}).get("explicit_term_matches", [])]
    suggested_rgs = [x.get("role_group_id") for x in mr.get("matched_evidence", {}).get("selected_role_groups", [])]
    hard = mr.get("risks", {}).get("hard_blockers", [])
    soft = mr.get("risks", {}).get("soft_risks", [])
    return {
        "review_status": "new",
        "recommended_status": mr.get("decision", {}).get("recommended_status", "review"),
        "overall_score": mr.get("overall_score", 0),
        "expertise_fit": score_breakdown.get("expertise_fit", 0),
        "role_fit": score_breakdown.get("role_fit", 0),
        "tool_fit": score_breakdown.get("tool_fit", 0),
        "domain_fit": score_breakdown.get("domain_fit", 0),
        "growth_fit": score_breakdown.get("growth_fit", 0),
        "interest_fit": score_breakdown.get("interest_fit", 0),
        "practical_fit": score_breakdown.get("practical_fit", 0),
        "risk_score": score_breakdown.get("risk_score", 0),
        "job_id": js.get("job_id", ""),
        "input_file": input_file.name,
        "title": identity.get("original_title") or identity.get("normalized_title") or "Unspecified role",
        "normalized_title": identity.get("normalized_title") or "",
        "company": identity.get("company") or "",
        "city": loc.get("city") or "",
        "work_mode": loc.get("work_mode") or "",
        "source_url": js.get("source", {}).get("url") or "",
        "matched_terms": compact_list(matched_terms, limit=12),
        "suggested_role_groups": compact_list(suggested_rgs, limit=5),
        "hard_blockers": compact_list(hard, limit=5),
        "soft_risks": compact_list(soft, limit=5),
        "reason": mr.get("decision", {}).get("reason", ""),
    }


def write_review_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "review_status", "recommended_status", "overall_score", "expertise_fit", "role_fit", "tool_fit", "domain_fit",
        "growth_fit", "interest_fit", "practical_fit", "risk_score", "job_id", "input_file", "title",
        "normalized_title", "company", "city", "work_mode", "source_url", "matched_terms",
        "suggested_role_groups", "hard_blockers", "soft_risks", "reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def status_class(status: str) -> str:
    status = (status or "").lower()
    if status == "keep":
        return "keep"
    if status == "maybe":
        return "maybe"
    if status == "reject":
        return "reject"
    return "review"


def write_review_html(path: Path, rows: List[Dict[str, Any]]) -> None:
    cards = []
    for i, row in enumerate(rows, 1):
        src = row.get("source_url") or ""
        src_html = f'<a href="{html.escape(src)}" target="_blank">source</a>' if src else "manual input"
        cards.append(f"""
        <article class="card {status_class(str(row.get('recommended_status', '')))}">
          <div class="rank">#{i}</div>
          <div class="main">
            <div class="topline">
              <h2>{html.escape(str(row.get('title', 'Unspecified role')))}</h2>
              <span class="score">{html.escape(str(row.get('overall_score', '')))}</span>
            </div>
            <div class="meta">
              {html.escape(str(row.get('normalized_title', '')))} | {html.escape(str(row.get('city', '')))} | {html.escape(str(row.get('work_mode', '')))} | {src_html}
            </div>
            <div class="badges">
              <span class="badge status">{html.escape(str(row.get('recommended_status', 'review')))}</span>
              <span class="badge">expertise {html.escape(str(row.get('expertise_fit', '')))}</span>
              <span class="badge">role {html.escape(str(row.get('role_fit', '')))}</span>
              <span class="badge">tools {html.escape(str(row.get('tool_fit', '')))}</span>
              <span class="badge">growth {html.escape(str(row.get('growth_fit', '')))}</span>
              <span class="badge">risk {html.escape(str(row.get('risk_score', '')))}</span>
            </div>
            <p><strong>Matched terms:</strong> {html.escape(str(row.get('matched_terms', '')))}</p>
            <p><strong>Suggested role groups:</strong> {html.escape(str(row.get('suggested_role_groups', '')))}</p>
            <p><strong>Risks:</strong> {html.escape(str(row.get('hard_blockers', '')))} {html.escape(str(row.get('soft_risks', '')))}</p>
            <p class="reason">{html.escape(str(row.get('reason', '')))}</p>
          </div>
          <div class="decision">
            <label>Decision</label>
            <select>
              <option>new</option><option>keep</option><option>maybe</option><option>reject</option><option>prepare_cv</option><option>applied</option><option>archived</option>
            </select>
          </div>
        </article>
        """)
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Review Queue</title>
<style>
  :root {{ --bg:#f6f6f6; --ink:#202124; --muted:#666; --line:#ddd; --keep:#0b7a3b; --maybe:#a06100; --reject:#9b1c1c; }}
  body {{ margin:0; font-family: Arial, Helvetica, sans-serif; color:var(--ink); background:var(--bg); }}
  header {{ padding:24px 32px; background:#9d1b86; color:white; }}
  header h1 {{ margin:0 0 6px 0; font-size:28px; }}
  header p {{ margin:0; opacity:.9; }}
  main {{ max-width:1120px; margin:24px auto; padding:0 16px 32px; }}
  .summary {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:18px; }}
  .pill {{ background:white; border:1px solid var(--line); border-radius:999px; padding:8px 12px; }}
  .card {{ display:grid; grid-template-columns:54px 1fr 150px; gap:16px; background:white; border:1px solid var(--line); border-left:8px solid #aaa; border-radius:14px; padding:16px; margin:14px 0; box-shadow:0 2px 8px rgba(0,0,0,.04); }}
  .card.keep {{ border-left-color:var(--keep); }} .card.maybe {{ border-left-color:var(--maybe); }} .card.reject {{ border-left-color:var(--reject); }}
  .rank {{ font-size:18px; font-weight:700; color:var(--muted); padding-top:4px; }}
  .topline {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
  h2 {{ margin:0; font-size:20px; }}
  .score {{ background:#111; color:white; border-radius:999px; padding:8px 12px; font-weight:700; min-width:32px; text-align:center; }}
  .meta {{ color:var(--muted); margin:6px 0 10px; }}
  .badges {{ display:flex; flex-wrap:wrap; gap:7px; margin:10px 0; }}
  .badge {{ border:1px solid var(--line); border-radius:999px; padding:4px 9px; font-size:12px; background:#fafafa; }}
  .status {{ font-weight:700; text-transform:uppercase; }}
  p {{ margin:7px 0; line-height:1.35; }}
  .reason {{ color:#333; }}
  .decision label {{ display:block; font-size:12px; color:var(--muted); margin-bottom:5px; }}
  select {{ width:100%; padding:7px; border-radius:8px; border:1px solid var(--line); background:white; }}
  @media (max-width: 780px) {{ .card {{ grid-template-columns:1fr; }} .decision {{ max-width:220px; }} }}
</style>
</head>
<body>
<header>
  <h1>Job Review Queue</h1>
  <p>Generated from copied job descriptions. Review status is currently visual only; edit the CSV to persist decisions.</p>
</header>
<main>
  <section class="summary">
    <div class="pill"><strong>{len(rows)}</strong> jobs processed</div>
    <div class="pill"><strong>{sum(1 for r in rows if r.get('recommended_status') == 'keep')}</strong> keep</div>
    <div class="pill"><strong>{sum(1 for r in rows if r.get('recommended_status') == 'maybe')}</strong> maybe</div>
    <div class="pill"><strong>{sum(1 for r in rows if r.get('recommended_status') == 'reject')}</strong> reject</div>
  </section>
  {''.join(cards)}
</main>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch job intake: folder of .txt jobs -> YAML outputs + review queue")
    parser.add_argument("--jobs-dir", required=True, help="Folder containing copied job descriptions as .txt files")
    parser.add_argument("--data-dir", default="data", help="Path to the data directory")
    parser.add_argument("--out-dir", default="outputs/batch", help="Directory for generated outputs")
    parser.add_argument("--standardizer", choices=["deterministic", "llm", "hybrid"], default="deterministic", help="Job standardization mode")
    parser.add_argument("--llm-provider", default="openai", help="LLM provider for --standardizer llm/hybrid")
    parser.add_argument(
        "--llm-model",
        default=os.getenv("JOBSEARCH_LLM_MODEL", BUDGET_OPENAI_MODEL),
        help=f"LLM model name for --standardizer llm/hybrid. Only {BUDGET_OPENAI_MODEL} is allowed for cost control.",
    )
    parser.add_argument("--llm-timeout-sec", type=int, default=60, help="LLM timeout in seconds")
    args = parser.parse_args()

    jobs_dir = Path(args.jobs_dir)
    data_dir = resolve_data_dir(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    job_files = sorted(jobs_dir.glob("*.txt"))
    if not job_files:
        raise SystemExit(f"No .txt files found in {jobs_dir}")

    experience_db = matcher.load_yaml(data_dir / "experience_database.yaml")
    aliases = matcher.load_aliases(matcher.load_yaml(data_dir / "tool_aliases.yaml"))
    prefs = matcher.load_yaml(data_dir / "career_preferences.yaml")
    evidence_index = matcher.build_evidence_index(experience_db)

    rows: List[Dict[str, Any]] = []
    for job_file in job_files:
        job_text, source_url, metadata = read_job_file(job_file)
        if not job_text:
            print(f"Skipping empty job file: {job_file}")
            continue
        if is_probable_listing_page(source_url, job_text):
            print(f"Skipping listing page (not a job detail): {job_file.name}")
            continue
        llm_validation = None
        llm_raw = None
        if args.standardizer == "deterministic":
            job_standardized = matcher.standardize_job(job_text, source_url=source_url)
            job_standardized = apply_file_metadata(job_standardized, metadata)
        else:
            std_result = standardize_job_with_mode(
                job_text=job_text,
                source_url=source_url,
                metadata=metadata,
                mode=args.standardizer,
                provider=args.llm_provider,
                model=args.llm_model,
                timeout_sec=args.llm_timeout_sec,
            )
            job_standardized = std_result.job_standardized
            job_standardized = apply_file_metadata(job_standardized, metadata)
            llm_validation = std_result.validation_report
            llm_raw = std_result.llm_raw
            time.sleep(10)  # Rate limit delay
        match_result = matcher.match_job(job_standardized, evidence_index, aliases, prefs)
        job_id = job_standardized["job_standardized"]["job_id"]
        matcher.write_yaml(out_dir / f"{job_id}.job_standardized.yaml", job_standardized)
        if llm_validation is not None:
            matcher.write_yaml(out_dir / f"{job_id}.job_standardized.validation.yaml", llm_validation)
        if llm_raw is not None:
            matcher.write_yaml(out_dir / f"{job_id}.job_standardized.llm_raw.yaml", llm_raw)
        matcher.write_yaml(out_dir / f"{job_id}.match_result.yaml", match_result)
        rows.append(summarize_row(job_file, job_standardized, match_result))
        print(f"Processed {job_file.name}: {job_id} score={match_result['match_result']['overall_score']} status={match_result['match_result']['decision']['recommended_status']}")

    rows.sort(key=lambda r: int(r.get("overall_score", 0)), reverse=True)
    write_review_csv(out_dir / "review_queue.csv", rows)
    write_review_html(out_dir / "review_queue.html", rows)
    print(f"Wrote {out_dir / 'review_queue.csv'}")
    print(f"Wrote {out_dir / 'review_queue.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
