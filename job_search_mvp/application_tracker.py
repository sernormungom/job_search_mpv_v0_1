#!/usr/bin/env python3
"""
Persistent application decision tracker for Job Search Automation MVP.

Why this exists
---------------
Batch outputs are disposable: if you rerun `run_job_batch.py`, review_queue.csv is
regenerated. This tracker stores human decisions, notes, lifecycle status, and CV
artifact paths in a stable CSV file so those decisions survive reruns.

Typical usage
-------------
1) Create or update tracker from a batch review queue:
   python -m jobsearch.tracking.application_tracker sync \
     --review-queue outputs/batch/review_queue.csv \
     --tracker outputs/application_tracker.csv \
     --out-review-queue outputs/batch/review_queue.tracked.csv \
     --out-html outputs/application_tracker.html

2) Mark a job for CV preparation:
   python -m jobsearch.tracking.application_tracker set-status \
     --tracker outputs/application_tracker.csv \
     --job-id job_ef3e435134 \
     --status prepare_cv \
     --notes "Strong verification and HIL/SIL fit"

3) After running run_selected_cv_pipeline.py, attach generated artifact paths:
   python -m jobsearch.tracking.application_tracker ingest-cv-report \
     --tracker outputs/application_tracker.csv \
     --cv-report outputs/selected/selected_cv_pipeline_report.csv

4) Export a human-friendly HTML tracker:
   python -m jobsearch.tracking.application_tracker export-html \
     --tracker outputs/application_tracker.csv \
     --out-html outputs/application_tracker.html
"""

from __future__ import annotations

import argparse
import csv
import html
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

DEFAULT_TRACKER = "outputs/application_tracker.csv"
DEFAULT_TRACKER_HTML = "outputs/application_tracker.html"

VALID_STATUSES = [
    "new",
    "keep",
    "maybe",
    "reject",
    "prepare_cv",
    "cv_ready",
    "applied",
    "archived",
]

TRACKER_FIELDS = [
    "job_id",
    "status",
    "priority",
    "title",
    "normalized_title",
    "company",
    "city",
    "work_mode",
    "source_url",
    "input_file",
    "overall_score",
    "expertise_fit",
    "role_fit",
    "tool_fit",
    "domain_fit",
    "growth_fit",
    "interest_fit",
    "practical_fit",
    "risk_score",
    "recommended_status",
    "matched_terms",
    "suggested_role_groups",
    "hard_blockers",
    "soft_risks",
    "match_reason",
    "user_notes",
    "decision_reason",
    "first_seen_at",
    "last_seen_at",
    "last_status_change_at",
    "applied_at",
    "cv_strategy_path",
    "cv_draft_yaml_path",
    "cv_draft_txt_path",
    "mpya_cv_html_path",
]

# Fields in review_queue.csv that are generated from matching and may be refreshed
# on sync without destroying user decisions.
REFRESH_FROM_REVIEW = [
    "title",
    "normalized_title",
    "company",
    "city",
    "work_mode",
    "source_url",
    "input_file",
    "overall_score",
    "expertise_fit",
    "role_fit",
    "tool_fit",
    "domain_fit",
    "growth_fit",
    "interest_fit",
    "practical_fit",
    "risk_score",
    "recommended_status",
    "matched_terms",
    "suggested_role_groups",
    "hard_blockers",
    "soft_risks",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def by_job_id(rows: Iterable[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for row in rows:
        job_id = (row.get("job_id") or "").strip()
        if job_id:
            out[job_id] = row
    return out


def normalize_status(status: str | None) -> str:
    s = (status or "").strip().lower()
    return s if s in VALID_STATUSES else "new"


def sync_tracker(review_queue: Path, tracker_path: Path) -> List[Dict[str, str]]:
    now = utc_now()
    review_rows = read_csv(review_queue)
    tracker_rows = read_csv(tracker_path)
    tracker = by_job_id(tracker_rows)

    for review in review_rows:
        job_id = (review.get("job_id") or "").strip()
        if not job_id:
            continue
        existing = tracker.get(job_id)
        if existing is None:
            existing = {field: "" for field in TRACKER_FIELDS}
            existing["job_id"] = job_id
            existing["status"] = normalize_status(review.get("review_status"))
            existing["priority"] = ""
            existing["first_seen_at"] = now
            existing["last_status_change_at"] = now
            tracker[job_id] = existing
        # Refresh machine-derived fields on every sync.
        for field in REFRESH_FROM_REVIEW:
            if field == "soft_risks":
                existing[field] = review.get(field, "")
            else:
                existing[field] = review.get(field, existing.get(field, ""))
        existing["match_reason"] = review.get("reason", existing.get("match_reason", ""))
        existing["last_seen_at"] = now
        existing["status"] = normalize_status(existing.get("status"))

    rows = sorted(
        tracker.values(),
        key=lambda r: (
            status_rank(r.get("status", "")),
            -safe_int(r.get("overall_score", "0")),
            r.get("title", ""),
        ),
    )
    write_csv(tracker_path, rows, TRACKER_FIELDS)
    return rows


def safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip() or "0"))
    except ValueError:
        return 0


def status_rank(status: str) -> int:
    order = {
        "prepare_cv": 0,
        "cv_ready": 1,
        "keep": 2,
        "maybe": 3,
        "new": 4,
        "applied": 5,
        "reject": 6,
        "archived": 7,
    }
    return order.get(normalize_status(status), 9)


def set_status(tracker_path: Path, job_id: str, status: str, notes: str = "", decision_reason: str = "", priority: str = "") -> None:
    status = normalize_status(status)
    rows = read_csv(tracker_path)
    if not rows:
        raise SystemExit(f"Tracker file not found or empty: {tracker_path}. Run sync first.")
    now = utc_now()
    found = False
    for row in rows:
        if row.get("job_id") == job_id:
            found = True
            previous = normalize_status(row.get("status"))
            row["status"] = status
            if previous != status:
                row["last_status_change_at"] = now
            if notes:
                row["user_notes"] = notes
            if decision_reason:
                row["decision_reason"] = decision_reason
            if priority:
                row["priority"] = priority
            if status == "applied" and not row.get("applied_at"):
                row["applied_at"] = now
            break
    if not found:
        raise SystemExit(f"Job id not found in tracker: {job_id}")
    write_csv(tracker_path, rows, TRACKER_FIELDS)


def ingest_cv_report(tracker_path: Path, cv_report: Path) -> None:
    rows = read_csv(tracker_path)
    report_rows = by_job_id(read_csv(cv_report))
    if not rows:
        raise SystemExit(f"Tracker file not found or empty: {tracker_path}. Run sync first.")
    if not report_rows:
        raise SystemExit(f"CV report file not found or empty: {cv_report}")
    now = utc_now()
    touched = 0
    for row in rows:
        job_id = row.get("job_id", "")
        rep = report_rows.get(job_id)
        if not rep:
            continue
        row["cv_strategy_path"] = rep.get("cv_strategy", row.get("cv_strategy_path", ""))
        row["cv_draft_yaml_path"] = rep.get("cv_draft_yaml", row.get("cv_draft_yaml_path", ""))
        row["cv_draft_txt_path"] = rep.get("cv_draft_txt", row.get("cv_draft_txt_path", ""))
        row["mpya_cv_html_path"] = rep.get("mpya_cv_html", row.get("mpya_cv_html_path", ""))
        if normalize_status(row.get("status")) in {"prepare_cv", "new", "keep", "maybe"}:
            row["status"] = "cv_ready"
            row["last_status_change_at"] = now
        touched += 1
    write_csv(tracker_path, rows, TRACKER_FIELDS)
    print(f"Updated {touched} tracker row(s) from {cv_report}")


def tracker_to_review_queue(tracker_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = []
    for row in tracker_rows:
        out.append({
            "review_status": normalize_status(row.get("status")),
            "recommended_status": row.get("recommended_status", ""),
            "overall_score": row.get("overall_score", ""),
            "expertise_fit": row.get("expertise_fit", ""),
            "role_fit": row.get("role_fit", ""),
            "tool_fit": row.get("tool_fit", ""),
            "domain_fit": row.get("domain_fit", ""),
            "growth_fit": row.get("growth_fit", ""),
            "interest_fit": row.get("interest_fit", ""),
            "practical_fit": row.get("practical_fit", ""),
            "risk_score": row.get("risk_score", ""),
            "job_id": row.get("job_id", ""),
            "input_file": row.get("input_file", ""),
            "title": row.get("title", ""),
            "normalized_title": row.get("normalized_title", ""),
            "company": row.get("company", ""),
            "city": row.get("city", ""),
            "work_mode": row.get("work_mode", ""),
            "source_url": row.get("source_url", ""),
            "matched_terms": row.get("matched_terms", ""),
            "suggested_role_groups": row.get("suggested_role_groups", ""),
            "hard_blockers": row.get("hard_blockers", ""),
            "soft_risks": row.get("soft_risks", ""),
            "reason": row.get("match_reason", ""),
        })
    return out


def write_review_queue(path: Path, tracker_rows: List[Dict[str, str]]) -> None:
    fieldnames = [
        "review_status", "recommended_status", "overall_score", "expertise_fit", "role_fit", "tool_fit", "domain_fit",
        "growth_fit", "interest_fit", "practical_fit", "risk_score", "job_id", "input_file", "title",
        "normalized_title", "company", "city", "work_mode", "source_url", "matched_terms",
        "suggested_role_groups", "hard_blockers", "soft_risks", "reason",
    ]
    write_csv(path, tracker_to_review_queue(tracker_rows), fieldnames)


def rel_link(path_text: str) -> str:
    if not path_text:
        return ""
    esc = html.escape(path_text)
    return f'<a href="{esc}">{esc}</a>'


def status_badge_class(status: str) -> str:
    status = normalize_status(status)
    return status.replace("_", "-")


def write_tracker_html(path: Path, rows: List[Dict[str, str]]) -> None:
    cards = []
    for row in rows:
        status = normalize_status(row.get("status"))
        src = row.get("source_url") or ""
        src_html = f'<a href="{html.escape(src)}" target="_blank">source</a>' if src else "manual input"
        artifacts = []
        if row.get("cv_strategy_path"):
            artifacts.append(f"Strategy: {rel_link(row['cv_strategy_path'])}")
        if row.get("cv_draft_txt_path"):
            artifacts.append(f"Draft text: {rel_link(row['cv_draft_txt_path'])}")
        if row.get("mpya_cv_html_path"):
            artifacts.append(f"MPYA HTML: {rel_link(row['mpya_cv_html_path'])}")
        artifact_html = "<br>".join(artifacts) if artifacts else "No CV artifacts yet"
        cards.append(f"""
        <article class="card {status_badge_class(status)}">
          <div class="score">{html.escape(row.get('overall_score',''))}</div>
          <div class="content">
            <div class="topline">
              <h2>{html.escape(row.get('title','Unspecified role'))}</h2>
              <span class="badge {status_badge_class(status)}">{html.escape(status)}</span>
            </div>
            <div class="meta">{html.escape(row.get('normalized_title',''))} | {html.escape(row.get('city',''))} | {html.escape(row.get('work_mode',''))} | {src_html}</div>
            <p><strong>Fit:</strong> expertise {html.escape(row.get('expertise_fit',''))} | role {html.escape(row.get('role_fit',''))} | growth {html.escape(row.get('growth_fit',''))} | risk {html.escape(row.get('risk_score',''))}</p>
            <p><strong>Matched terms:</strong> {html.escape(row.get('matched_terms',''))}</p>
            <p><strong>Suggested role groups:</strong> {html.escape(row.get('suggested_role_groups',''))}</p>
            <p><strong>Notes:</strong> {html.escape(row.get('user_notes',''))}</p>
            <p><strong>Decision reason:</strong> {html.escape(row.get('decision_reason',''))}</p>
            <p class="artifacts"><strong>Artifacts:</strong><br>{artifact_html}</p>
          </div>
          <div class="dates">
            <div><strong>First seen</strong><br>{html.escape(row.get('first_seen_at',''))}</div>
            <div><strong>Last seen</strong><br>{html.escape(row.get('last_seen_at',''))}</div>
            <div><strong>Status changed</strong><br>{html.escape(row.get('last_status_change_at',''))}</div>
          </div>
        </article>
        """)
    counts = {s: sum(1 for r in rows if normalize_status(r.get("status")) == s) for s in VALID_STATUSES}
    count_html = "".join(f'<span class="pill"><strong>{counts[s]}</strong> {html.escape(s)}</span>' for s in VALID_STATUSES if counts[s])
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Application Tracker</title>
<style>
  :root {{ --mpya:#9d1b86; --bg:#f6f6f6; --ink:#202124; --muted:#666; --line:#ddd; }}
  body {{ margin:0; font-family:Arial, Helvetica, sans-serif; background:var(--bg); color:var(--ink); }}
  header {{ background:var(--mpya); color:white; padding:26px 34px; }}
  h1 {{ margin:0 0 6px; }} header p {{ margin:0; opacity:.9; }}
  main {{ max-width:1180px; margin:24px auto 48px; padding:0 16px; }}
  .summary {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:18px; }}
  .pill {{ background:white; border:1px solid var(--line); border-radius:999px; padding:8px 12px; }}
  .card {{ display:grid; grid-template-columns:58px 1fr 190px; gap:16px; background:white; border:1px solid var(--line); border-left:8px solid #aaa; border-radius:14px; padding:16px; margin:14px 0; box-shadow:0 2px 8px rgba(0,0,0,.04); }}
  .card.prepare-cv {{ border-left-color:#1455d9; }} .card.cv-ready {{ border-left-color:#0b7a3b; }} .card.applied {{ border-left-color:#5436d5; }} .card.reject {{ border-left-color:#9b1c1c; }} .card.archived {{ opacity:.72; }}
  .score {{ background:#111; color:white; border-radius:999px; width:44px; height:44px; display:flex; align-items:center; justify-content:center; font-weight:700; }}
  .topline {{ display:flex; justify-content:space-between; align-items:start; gap:12px; }} h2 {{ margin:0; font-size:20px; }}
  .meta {{ color:var(--muted); margin:6px 0 10px; }} p {{ margin:7px 0; line-height:1.35; }}
  .badge {{ border-radius:999px; padding:6px 10px; font-size:12px; font-weight:700; text-transform:uppercase; background:#eee; }}
  .badge.prepare-cv {{ background:#dce7ff; color:#123f9f; }} .badge.cv-ready {{ background:#dff3e7; color:#07542a; }} .badge.applied {{ background:#e7e3ff; color:#3521a0; }} .badge.reject {{ background:#ffe0e0; color:#7b1111; }}
  .dates {{ font-size:12px; color:var(--muted); display:flex; flex-direction:column; gap:12px; }}
  .artifacts a {{ color:var(--mpya); }}
  @media (max-width:850px) {{ .card {{ grid-template-columns:1fr; }} .dates {{ flex-direction:row; flex-wrap:wrap; }} }}
</style>
</head>
<body>
<header><h1>Application Tracker</h1><p>Persistent decisions, notes, lifecycle status, and generated CV artifacts.</p></header>
<main><section class="summary"><span class="pill"><strong>{len(rows)}</strong> tracked jobs</span>{count_html}</section>{''.join(cards)}</main>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")


def cmd_sync(args: argparse.Namespace) -> int:
    rows = sync_tracker(Path(args.review_queue), Path(args.tracker))
    if args.out_review_queue:
        write_review_queue(Path(args.out_review_queue), rows)
    if args.out_html:
        write_tracker_html(Path(args.out_html), rows)
    print(f"Tracker synced: {args.tracker} ({len(rows)} tracked job(s))")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    set_status(Path(args.tracker), args.job_id, args.status, args.notes or "", args.reason or "", args.priority or "")
    print(f"Updated {args.job_id} -> {normalize_status(args.status)}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    ingest_cv_report(Path(args.tracker), Path(args.cv_report))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    rows = read_csv(Path(args.tracker))
    if not rows:
        raise SystemExit(f"Tracker file not found or empty: {args.tracker}")
    rows = sorted(rows, key=lambda r: (status_rank(r.get("status", "")), -safe_int(r.get("overall_score", "0"))))
    write_tracker_html(Path(args.out_html), rows)
    print(f"Wrote {args.out_html}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent application decision tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sync", help="Create/update tracker from review_queue.csv")
    p.add_argument("--review-queue", required=True)
    p.add_argument("--tracker", default=DEFAULT_TRACKER)
    p.add_argument("--out-review-queue", default="")
    p.add_argument("--out-html", default=DEFAULT_TRACKER_HTML)
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("set-status", help="Set lifecycle status for one job")
    p.add_argument("--tracker", default=DEFAULT_TRACKER)
    p.add_argument("--job-id", required=True)
    p.add_argument("--status", required=True, choices=VALID_STATUSES)
    p.add_argument("--notes", default="")
    p.add_argument("--reason", default="")
    p.add_argument("--priority", default="")
    p.set_defaults(func=cmd_set_status)

    p = sub.add_parser("ingest-cv-report", help="Attach CV artifact paths from selected_cv_pipeline_report.csv")
    p.add_argument("--tracker", default=DEFAULT_TRACKER)
    p.add_argument("--cv-report", required=True)
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("export-html", help="Render tracker as HTML")
    p.add_argument("--tracker", default=DEFAULT_TRACKER)
    p.add_argument("--out-html", default=DEFAULT_TRACKER_HTML)
    p.set_defaults(func=cmd_export)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
