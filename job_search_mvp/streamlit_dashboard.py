#!/usr/bin/env python3
"""
Streamlit review dashboard for the Job Search Automation MVP.

This UI is intentionally thin and local-first:
- Reads the latest review queue CSV
- Syncs to persistent application tracker CSV
- Lets the user inspect details and set status decisions
- Shows links to source jobs and generated CV artifacts
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:
    from . import application_tracker
    from . import matcher
except ImportError:
    # Streamlit may execute this file without package context.
    from job_search_mvp import application_tracker
    from job_search_mvp import matcher


def _find_review_queues(outputs_dir: Path) -> List[Path]:
    return sorted(outputs_dir.glob("**/review_queue.csv"), key=lambda p: p.stat().st_mtime, reverse=True)


def _read_tracker(path: Path) -> List[Dict[str, str]]:
    return application_tracker.read_csv(path)


def _write_tracker(path: Path, rows: List[Dict[str, str]]) -> None:
    application_tracker.write_csv(path, rows, application_tracker.TRACKER_FIELDS)


def _set_status_in_memory(
    rows: List[Dict[str, str]],
    job_id: str,
    status: str,
    notes: str = "",
    decision_reason: str = "",
    priority: str = "",
) -> bool:
    now = application_tracker.utc_now()
    normalized = application_tracker.normalize_status(status)
    found = False
    for row in rows:
        if row.get("job_id") != job_id:
            continue
        found = True
        previous = application_tracker.normalize_status(row.get("status"))
        row["status"] = normalized
        if previous != normalized:
            row["last_status_change_at"] = now
        if notes:
            row["user_notes"] = notes
        if decision_reason:
            row["decision_reason"] = decision_reason
        if priority:
            row["priority"] = priority
        if normalized == "applied" and not row.get("applied_at"):
            row["applied_at"] = now
        break
    return found


def _matches_filters(row: Dict[str, str], statuses: Sequence[str], query: str) -> bool:
    status = application_tracker.normalize_status(row.get("status"))
    if statuses and status not in statuses:
        return False
    if not query:
        return True
    q = query.lower().strip()
    searchable = " ".join(
        [
            row.get("title", ""),
            row.get("normalized_title", ""),
            row.get("company", ""),
            row.get("city", ""),
            row.get("matched_terms", ""),
            row.get("source_url", ""),
        ]
    ).lower()
    return q in searchable


def _tracker_summary(rows: List[Dict[str, str]]) -> Dict[str, int]:
    counts = {status: 0 for status in application_tracker.VALID_STATUSES}
    for row in rows:
        counts[application_tracker.normalize_status(row.get("status"))] += 1
    counts["total"] = len(rows)
    return counts


def _rows_for_table(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    ranked = sorted(
        rows,
        key=lambda r: (
            application_tracker.status_rank(r.get("status", "")),
            -application_tracker.safe_int(r.get("overall_score", "0")),
            r.get("title", ""),
        ),
    )
    return [
        {
            "status": application_tracker.normalize_status(row.get("status")),
            "score": row.get("overall_score", ""),
            "title": row.get("title", ""),
            "normalized_title": row.get("normalized_title", ""),
            "city": row.get("city", ""),
            "work_mode": row.get("work_mode", ""),
            "job_id": row.get("job_id", ""),
        }
        for row in ranked
    ]


def _clean_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen = set()
    for item in value:
        text = str(item).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _dedupe_texts(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        text = str(item).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _split_compact_list(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _looks_like_raw_scrape_summary(summary: str) -> bool:
    low = summary.lower()
    chrome_markers = [
        "source url:",
        "collected from:",
        "collected at:",
        "publicerad den",
        "ansökningstiden löper ut",
    ]
    return len(summary) > 520 or any(marker in low for marker in chrome_markers)


def _build_fallback_summary(context: Dict[str, Any]) -> str:
    identity = context.get("identity", {}) or {}
    location = identity.get("location", {}) or {}
    title = identity.get("normalized_title") or identity.get("original_title") or "This role"
    company = identity.get("company") or "the client"
    city = location.get("city") or ""
    work_mode = location.get("work_mode") or ""
    focus = context.get("primary_focus") or context.get("secondary_focus") or []
    responsibilities = context.get("responsibilities") or []

    place_bits = [str(bit) for bit in [city, work_mode] if bit]
    place = f" in {' / '.join(place_bits)}" if place_bits else ""
    focus_text = f", focused on {', '.join(focus[:3])}" if focus else ""
    responsibility_text = f". Main work: {responsibilities[0]}" if responsibilities else ""
    return f"{title} role for {company}{place}{focus_text}{responsibility_text}.".strip()


def _read_job_context(batch_dir: Path, job_id: str) -> Dict[str, Any]:
    job_standardized_path = batch_dir / f"{job_id}.job_standardized.yaml"
    context: Dict[str, Any] = {
        "job_id": job_id,
        "summary": "",
        "role_goal": "",
        "business_context": "",
        "job_description": "",
        "responsibilities": [],
        "must_have": [],
        "nice_to_have": [],
        "hard_blockers": [],
        "soft_blockers": [],
        "primary_focus": [],
        "secondary_focus": [],
        "language": {},
        "identity": {},
        "llm_enrichment": {},
    }
    if not job_standardized_path.exists():
        return context

    data: Dict[str, Any] = matcher.load_yaml(job_standardized_path)
    root = data.get("job_standardized", data)
    summary = root.get("summary", {}) or {}
    analysis = root.get("job_analysis", {}) or {}
    normalized = root.get("normalized_requirements", {}) or {}
    blockers = root.get("blockers", {}) or {}
    enrichment = root.get("llm_enrichment", {}) or {}
    identity = root.get("identity", {}) or {}

    context.update(
        {
            "summary": str(summary.get("short_summary") or "").strip(),
            "role_goal": str(summary.get("role_goal") or enrichment.get("summary_extra", {}).get("role_goal") or "").strip(),
            "business_context": str(
                summary.get("business_context") or enrichment.get("summary_extra", {}).get("business_context") or ""
            ).strip(),
            "job_description": str(root.get("job_description") or "").strip(),
            "responsibilities": _clean_list(normalized.get("responsibilities")),
            "must_have": _clean_list(normalized.get("must_have")),
            "nice_to_have": _clean_list(normalized.get("nice_to_have")),
            "hard_blockers": _clean_list(blockers.get("hard")),
            "soft_blockers": _clean_list(blockers.get("soft")),
            "primary_focus": _clean_list(analysis.get("primary_technical_focus")),
            "secondary_focus": _clean_list(analysis.get("secondary_technical_focus")),
            "language": root.get("language", {}) or {},
            "identity": identity,
            "llm_enrichment": enrichment,
        }
    )

    identity_extra = enrichment.get("identity_extra", {}) or {}
    if identity_extra:
        context["assignment_period"] = identity_extra.get("assignment_period") or {}
        context["application_deadline"] = identity_extra.get("application_deadline") or ""
        context["remote_percentage"] = identity_extra.get("remote_percentage")
    if _looks_like_raw_scrape_summary(context["summary"]):
        context["summary"] = ""
    if not context["summary"]:
        context["summary"] = _build_fallback_summary(context)
    return context


def _classify_requirement_fit(requirement: str, matched_terms: Sequence[str]) -> str:
    req = requirement.lower()
    matched = [term.lower() for term in matched_terms if term]
    specific_terms = [
        "ibm ace",
        "dynamics 365",
        "autosar",
        "iso 26262",
        "matlab",
        "simulink",
        "jenkins",
        "gerrit",
        "github",
        "bitbucket",
        "c++",
        "c#",
        "python",
    ]
    required_specific = [term for term in specific_terms if term in req]
    if required_specific and not any(term in matched for term in required_specific):
        return "no direct evidence"
    if any(term and term in req for term in matched):
        return "covered by matched evidence"
    if any(word in req for word in ["communication", "collaborat", "stakeholder", "swedish", "english"]):
        return "possible partial fit"
    if any(word in req for word in ["experience", "minimum", "year", "years", "documented"]):
        return "no direct evidence"
    return "needs human check"


def _build_review_brief(row: Dict[str, str], context: Dict[str, Any]) -> Dict[str, List[str] | str]:
    signals: List[str] = []
    concerns: List[str] = []
    matched_terms = _split_compact_list(row.get("matched_terms", ""))
    hard = _split_compact_list(row.get("hard_blockers", "")) + context.get("hard_blockers", [])
    soft = _split_compact_list(row.get("soft_risks", "")) + context.get("soft_blockers", [])

    expertise = application_tracker.safe_int(row.get("expertise_fit"))
    role_fit = application_tracker.safe_int(row.get("role_fit"))
    tool_fit = application_tracker.safe_int(row.get("tool_fit"))
    growth_fit = application_tracker.safe_int(row.get("growth_fit"))
    practical_fit = application_tracker.safe_int(row.get("practical_fit"))
    risk_score = application_tracker.safe_int(row.get("risk_score"))

    if matched_terms:
        signals.append("Matched evidence: " + ", ".join(matched_terms[:5]))
    if expertise >= 75:
        signals.append(f"Strong expertise score ({expertise})")
    if role_fit >= 75:
        signals.append(f"Role shape appears aligned ({role_fit})")
    if growth_fit >= 75:
        signals.append(f"Good growth score ({growth_fit})")
    if context.get("business_context"):
        signals.append(str(context["business_context"]))

    if hard:
        concerns.extend(f"Hard blocker: {item}" for item in hard[:3])
    if soft:
        concerns.extend(f"Soft risk: {item}" for item in soft[:3])
    if expertise < 50:
        concerns.append(f"Low expertise score ({expertise})")
    if tool_fit < 50:
        concerns.append(f"Weak direct tool fit ({tool_fit})")
    if practical_fit < 50:
        concerns.append(f"Practical fit may be difficult ({practical_fit})")
    if risk_score >= 20:
        concerns.append(f"Elevated risk score ({risk_score})")

    identity = context.get("identity", {}) or {}
    location = identity.get("location", {}) or {}
    work_mode = str(location.get("work_mode") or row.get("work_mode") or "").lower()
    remote_percentage = context.get("remote_percentage")
    if work_mode in {"on-site", "onsite"} or remote_percentage == 0:
        concerns.append("Onsite or 0% remote requirement")

    language_values = " ".join(str(v) for v in (context.get("language", {}) or {}).values()).lower()
    tags = context.get("llm_enrichment", {}).get("tags", {}) or {}
    language_requirements = " ".join(_clean_list(tags.get("language_requirement"))).lower()
    if "swedish" in language_values or "swedish" in language_requirements:
        concerns.append("Swedish language requirement or Swedish source context")

    direct_missing = []
    for requirement in context.get("must_have", [])[:5]:
        if _classify_requirement_fit(requirement, matched_terms) == "no direct evidence":
            direct_missing.append(requirement)
    if direct_missing:
        concerns.append("Must-have without direct matched evidence: " + direct_missing[0])

    if hard or application_tracker.normalize_status(row.get("recommended_status")) == "reject":
        decision_hint = "Likely reject unless the human reviewer sees strong external evidence."
    elif concerns and signals:
        decision_hint = "Review carefully: there are useful signals, but also concrete concerns."
    elif signals:
        decision_hint = "Promising enough for keep/maybe review."
    else:
        decision_hint = "Needs human inspection; the machine evidence is thin."

    concerns = _dedupe_texts(concerns)
    signals = _dedupe_texts(signals)

    return {
        "signals": signals[:5],
        "concerns": concerns[:8],
        "decision_hint": decision_hint,
    }


def _read_must_have_requirements(batch_dir: Path, job_id: str) -> List[str]:
    job_standardized_path = batch_dir / f"{job_id}.job_standardized.yaml"
    if not job_standardized_path.exists():
        return []
    data: Dict[str, Any] = matcher.load_yaml(job_standardized_path)
    root = data.get("job_standardized", data)
    normalized = root.get("normalized_requirements", {})
    must_have = normalized.get("must_have", [])
    if not isinstance(must_have, list):
        return []
    return [str(item).strip() for item in must_have if str(item).strip()]


def _read_job_description(batch_dir: Path, job_id: str) -> str:
    job_standardized_path = batch_dir / f"{job_id}.job_standardized.yaml"
    if not job_standardized_path.exists():
        return ""
    data: Dict[str, Any] = matcher.load_yaml(job_standardized_path)
    root = data.get("job_standardized", data)
    description = root.get("job_description", "")
    return str(description).strip() if description is not None else ""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the Streamlit dashboard.")
    parser.add_argument("--review-queue", default="", help="Path to review_queue.csv")
    parser.add_argument("--tracker", default="outputs/application_tracker.csv", help="Path to application tracker CSV")
    parser.add_argument("--outputs-dir", default="outputs", help="Outputs directory to search for review queues")
    parser.add_argument("--batch-dir", default="outputs/batch", help="Batch directory containing *.job_standardized.yaml/*.match_result.yaml")
    parser.add_argument("--data-dir", default="data", help="Data directory for CV generation pipeline")
    parser.add_argument("--selected-out-dir", default="outputs/selected", help="Output directory for selected CV artifacts")
    parser.add_argument("--tracked-review-queue", default="outputs/batch/review_queue.tracked.csv", help="Tracked review queue path generated from tracker")
    return parser


def _run_selected_cv_pipeline(tracker_path: Path, tracked_review_queue: Path, batch_dir: Path, data_dir: Path, out_dir: Path) -> tuple[bool, str]:
    rows = application_tracker.read_csv(tracker_path)
    if not rows:
        return False, f"Tracker is empty: {tracker_path}"
    application_tracker.write_review_queue(tracked_review_queue, rows)
    cmd = [
        sys.executable,
        "-m",
        "jobsearch.pipeline.run_selected_cv_pipeline",
        "--review-queue",
        str(tracked_review_queue),
        "--batch-dir",
        str(batch_dir),
        "--data-dir",
        str(data_dir),
        "--out-dir",
        str(out_dir),
    ]
    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as exc:
        return False, f"Failed to launch CV pipeline: {exc}"
    if completed.returncode != 0:
        err = (completed.stderr or "").strip() or (completed.stdout or "").strip() or "unknown error"
        return False, f"CV pipeline failed: {err}"

    report_path = out_dir / "selected_cv_pipeline_report.csv"
    if report_path.exists():
        application_tracker.ingest_cv_report(tracker_path, report_path)
        return True, f"CV pipeline complete. Tracker updated from {report_path}"
    return True, "CV pipeline ran, but no report CSV was produced."


def _run_single_job_cv_pipeline(
    tracker_path: Path,
    tracked_review_queue: Path,
    batch_dir: Path,
    data_dir: Path,
    out_dir: Path,
    job_id: str,
    notes: str = "",
    decision_reason: str = "",
    priority: str = "",
) -> tuple[bool, str]:
    tracker_rows = application_tracker.read_csv(tracker_path)
    if not tracker_rows:
        return False, f"Tracker is empty: {tracker_path}"

    # Persist selected job as prepare_cv first so ingest-cv-report can move it to cv_ready.
    ok = _set_status_in_memory(
        tracker_rows,
        job_id=job_id,
        status="prepare_cv",
        notes=notes,
        decision_reason=decision_reason,
        priority=priority,
    )
    if not ok:
        return False, f"Could not find {job_id} in tracker."
    _write_tracker(tracker_path, tracker_rows)

    review_rows = application_tracker.tracker_to_review_queue(tracker_rows)
    for review_row in review_rows:
        review_row["review_status"] = "prepare_cv" if review_row.get("job_id") == job_id else "new"
    single_queue = tracked_review_queue.with_name(f"{tracked_review_queue.stem}.{job_id}.single.csv")
    if review_rows:
        fieldnames = list(review_rows[0].keys())
        application_tracker.write_csv(single_queue, review_rows, fieldnames)
    else:
        return False, "No rows available to run CV pipeline."

    cmd = [
        sys.executable,
        "-m",
        "jobsearch.pipeline.run_selected_cv_pipeline",
        "--review-queue",
        str(single_queue),
        "--batch-dir",
        str(batch_dir),
        "--data-dir",
        str(data_dir),
        "--out-dir",
        str(out_dir),
    ]
    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as exc:
        return False, f"Failed to launch CV pipeline: {exc}"
    if completed.returncode != 0:
        err = (completed.stderr or "").strip() or (completed.stdout or "").strip() or "unknown error"
        return False, f"Single-job CV pipeline failed: {err}"

    report_path = out_dir / "selected_cv_pipeline_report.csv"
    if report_path.exists():
        application_tracker.ingest_cv_report(tracker_path, report_path)
    updated_rows = application_tracker.read_csv(tracker_path)
    updated = next((r for r in updated_rows if r.get("job_id") == job_id), None)
    if not updated:
        return True, f"Single-job CV generated for {job_id}, but tracker row refresh is missing."
    html_path = updated.get("mpya_cv_html_path", "")
    if html_path:
        return True, f"CV ready for {job_id}. MPYA HTML: {html_path}"
    return True, f"Single-job CV pipeline complete for {job_id}."


def main() -> int:
    try:
        import streamlit as st  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Streamlit is not installed. Install it with:\n"
            "  python -m pip install streamlit\n"
            "or\n"
            "  python -m pip install -e \".[ui]\""
        ) from exc

    args = _build_parser().parse_args()
    outputs_dir = Path(args.outputs_dir).resolve()
    review_queue = Path(args.review_queue).resolve() if args.review_queue else None
    tracker_path = Path(args.tracker).resolve()
    batch_dir = Path(args.batch_dir).resolve()
    data_dir = Path(args.data_dir).resolve()
    selected_out_dir = Path(args.selected_out_dir).resolve()
    tracked_review_queue = Path(args.tracked_review_queue).resolve()

    if review_queue is None:
        candidates = _find_review_queues(outputs_dir)
        if not candidates:
            raise SystemExit(f"No review_queue.csv found under {outputs_dir}")
        review_queue = candidates[0]

    st.set_page_config(page_title="Job Search MVP Dashboard", page_icon=":briefcase:", layout="wide")
    st.markdown(
        """
        <style>
          :root { --brand:#1455d9; --bg:#f4f7fc; --ink:#111827; --line:#dbe2f0; --panel:#ffffff; }
          .stApp { background: linear-gradient(170deg, #f6f9ff 0%, #edf3ff 42%, #f8fbff 100%); color: var(--ink); }
          .block-container { padding-top: 1.4rem; }
          .pill { display:inline-block; background:#eef4ff; border:1px solid #d3e1ff; border-radius:999px; padding:.2rem .6rem; margin-right:.35rem; font-size:.82rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Job Search MVP Dashboard")
    st.caption("Control center for review decisions and CV preparation")

    if st.button("Sync Tracker From Review Queue", type="primary", use_container_width=False):
        application_tracker.sync_tracker(review_queue, tracker_path)
        st.success(f"Tracker synced from {review_queue}")

    rows = _read_tracker(tracker_path)
    if not rows:
        st.warning("Tracker is empty. Click 'Sync Tracker From Review Queue' first.")
        return 0

    counts = _tracker_summary(rows)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", counts["total"])
    c2.metric("Prepare CV", counts["prepare_cv"])
    c3.metric("CV Ready", counts["cv_ready"])
    c4.metric("Keep", counts["keep"])
    c5.metric("Reject", counts["reject"])

    st.markdown(
        f"<span class='pill'>review queue: {review_queue}</span><span class='pill'>tracker: {tracker_path}</span>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 1.9], gap="large")
    with left:
        st.subheader("Filters")
        hide_reviewed = st.checkbox(
            "Hide already reviewed",
            value=True,
            help="When enabled, only jobs with status 'new' are shown.",
        )
        default_statuses = ["new"] if hide_reviewed else ["new", "keep", "maybe", "prepare_cv", "cv_ready"]
        selected_statuses = st.multiselect(
            "Status",
            options=list(application_tracker.VALID_STATUSES),
            default=default_statuses,
        )
        if hide_reviewed:
            selected_statuses = ["new"]
        search_query = st.text_input("Search", placeholder="Title, city, tags, URL...")
        filtered_rows = [r for r in rows if _matches_filters(r, selected_statuses, search_query)]
        st.caption(f"{len(filtered_rows)} jobs after filtering")

        table_rows = _rows_for_table(filtered_rows)
        st.dataframe(table_rows, use_container_width=True, hide_index=True, height=380)

        filtered_job_ids = [row.get("job_id", "") for row in filtered_rows if row.get("job_id", "")]
        if filtered_job_ids:
            current_selected_job_id = st.session_state.get("selected_job_id", "")
            if current_selected_job_id not in filtered_job_ids:
                st.session_state["selected_job_id"] = filtered_job_ids[0]
        else:
            st.session_state["selected_job_id"] = ""

        options = [f"{row['job_id']} | {row.get('title', '')[:70]}" for row in filtered_rows]
        selected_index = 0
        if options and st.session_state.get("selected_job_id"):
            for idx, row in enumerate(filtered_rows):
                if row.get("job_id") == st.session_state["selected_job_id"]:
                    selected_index = idx
                    break
        selected = st.selectbox("Select job", options=options, index=selected_index if options else None)
        if selected:
            st.session_state["selected_job_id"] = selected.split("|", 1)[0].strip()

    with right:
        if not filtered_rows:
            st.info("No jobs match current filters.")
            return 0
        selected_job_id = st.session_state.get("selected_job_id") or (selected.split("|", 1)[0].strip() if selected else filtered_rows[0]["job_id"])
        row = next((r for r in filtered_rows if r.get("job_id") == selected_job_id), filtered_rows[0])
        selected_job_id = row.get("job_id", selected_job_id)
        st.session_state["selected_job_id"] = selected_job_id

        st.subheader(row.get("title", "Untitled role"))
        st.caption(f"{row.get('normalized_title', '')} | {row.get('city', '')} | {row.get('work_mode', '')}")

        current_index = next((idx for idx, item in enumerate(filtered_rows) if item.get("job_id") == selected_job_id), 0)
        nav_prev, nav_next = st.columns(2)
        if nav_prev.button("Previous job", use_container_width=True, disabled=current_index <= 0):
            st.session_state["selected_job_id"] = filtered_rows[current_index - 1].get("job_id", selected_job_id)
            st.rerun()
        if nav_next.button("Next job", use_container_width=True, disabled=current_index >= len(filtered_rows) - 1):
            st.session_state["selected_job_id"] = filtered_rows[current_index + 1].get("job_id", selected_job_id)
            st.rerun()

        context = _read_job_context(batch_dir, selected_job_id)
        review_brief = _build_review_brief(row, context)

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Overall", row.get("overall_score", ""))
        s2.metric("Expertise", row.get("expertise_fit", ""))
        s3.metric("Role Fit", row.get("role_fit", ""))
        s4.metric("Tool Fit", row.get("tool_fit", ""))
        s5.metric("Risk", row.get("risk_score", ""))

        st.markdown("**Decision brief**")
        st.write(context.get("summary") or "No summary available.")
        hint = str(review_brief.get("decision_hint") or "")
        if hint:
            st.info(hint)

        meta_bits = []
        assignment = context.get("assignment_period") or {}
        if assignment.get("start") or assignment.get("end"):
            meta_bits.append(f"Assignment: {assignment.get('start') or '?'} to {assignment.get('end') or '?'}")
        if context.get("application_deadline"):
            meta_bits.append(f"Deadline: {context.get('application_deadline')}")
        if context.get("role_goal"):
            meta_bits.append(f"Goal: {context.get('role_goal')}")
        if meta_bits:
            st.caption(" | ".join(meta_bits))

        fit_left, fit_right = st.columns(2)
        with fit_left:
            st.markdown("**Useful signals**")
            signals = review_brief.get("signals", [])
            if signals:
                for signal in signals:
                    st.markdown(f"- {signal}")
            else:
                st.caption("No strong positive signals found in the current machine evidence.")
        with fit_right:
            st.markdown("**Concerns**")
            concerns = review_brief.get("concerns", [])
            if concerns:
                for concern in concerns:
                    st.markdown(f"- {concern}")
            else:
                st.caption("No obvious blockers or major risks found.")

        st.markdown("**Must-have fit**")
        must_have_lines = context.get("must_have", [])
        matched_terms = _split_compact_list(row.get("matched_terms", ""))
        if must_have_lines:
            for line in must_have_lines:
                st.markdown(f"- **{_classify_requirement_fit(line, matched_terms)}:** {line}")
        else:
            st.caption("No must-have requirements found in job_standardized.yaml for this job.")

        st.markdown("**Responsibilities**")
        responsibilities = context.get("responsibilities", [])
        if responsibilities:
            for line in responsibilities:
                st.markdown(f"- {line}")
        else:
            st.caption("No responsibilities found in job_standardized.yaml for this job.")

        with st.expander("Nice-to-have requirements", expanded=False):
            nice_to_have = context.get("nice_to_have", [])
            if nice_to_have:
                for line in nice_to_have:
                    st.markdown(f"- {line}")
            else:
                st.caption("No nice-to-have requirements found.")

        with st.expander("Matcher details", expanded=False):
            st.markdown("**Matched terms**")
            st.write(row.get("matched_terms", "") or "No matched terms.")
            st.markdown("**Suggested evidence groups**")
            st.write(row.get("suggested_role_groups", "") or "No suggested role groups.")
            st.markdown("**Reason**")
            st.write(row.get("match_reason", "") or "No matcher reason available.")

        with st.expander("Full job description", expanded=False):
            job_description = context.get("job_description") or _read_job_description(batch_dir, selected_job_id)
            if job_description:
                st.write(job_description)
            else:
                st.caption("No job description found in job_standardized.yaml for this job.")

        if row.get("source_url"):
            st.link_button("Open Source Job", row["source_url"], use_container_width=False)

        st.markdown("---")
        st.subheader("Decision")
        a1, a2, a3, a4 = st.columns(4)
        if a1.button("Keep", use_container_width=True):
            all_rows = _read_tracker(tracker_path)
            _set_status_in_memory(all_rows, row["job_id"], "keep")
            _write_tracker(tracker_path, all_rows)
            st.rerun()
        if a2.button("Maybe", use_container_width=True):
            all_rows = _read_tracker(tracker_path)
            _set_status_in_memory(all_rows, row["job_id"], "maybe")
            _write_tracker(tracker_path, all_rows)
            st.rerun()
        if a3.button("Reject", use_container_width=True):
            all_rows = _read_tracker(tracker_path)
            _set_status_in_memory(all_rows, row["job_id"], "reject")
            _write_tracker(tracker_path, all_rows)
            st.rerun()
        if a4.button("Prepare CV", use_container_width=True):
            all_rows = _read_tracker(tracker_path)
            _set_status_in_memory(all_rows, row["job_id"], "prepare_cv")
            _write_tracker(tracker_path, all_rows)
            st.rerun()

        status_choice = st.selectbox("Status", application_tracker.VALID_STATUSES, index=application_tracker.VALID_STATUSES.index(application_tracker.normalize_status(row.get("status"))))
        priority = st.selectbox("Priority", ["", "low", "medium", "high"], index=["", "low", "medium", "high"].index(row.get("priority", "") if row.get("priority", "") in {"", "low", "medium", "high"} else ""))
        notes = st.text_area("Notes", value=row.get("user_notes", ""), height=90)
        decision_reason = st.text_area("Decision reason", value=row.get("decision_reason", ""), height=90)

        if st.button("Save Decision", type="primary", use_container_width=True):
            all_rows = _read_tracker(tracker_path)
            ok = _set_status_in_memory(
                all_rows,
                job_id=row["job_id"],
                status=status_choice,
                notes=notes,
                decision_reason=decision_reason,
                priority=priority,
            )
            if not ok:
                st.error(f"Could not find {row['job_id']} in tracker.")
            else:
                _write_tracker(tracker_path, all_rows)
                st.success(f"Updated {row['job_id']} -> {status_choice}")
                st.rerun()

        st.markdown("---")
        st.subheader("CV Pipeline")
        st.caption(f"tracked queue: {tracked_review_queue}")
        st.caption(f"batch: {batch_dir} | data: {data_dir} | out: {selected_out_dir}")
        if st.button("One-Click Generate CV For This Job", type="primary", use_container_width=True):
            ok, message = _run_single_job_cv_pipeline(
                tracker_path=tracker_path,
                tracked_review_queue=tracked_review_queue,
                batch_dir=batch_dir,
                data_dir=data_dir,
                out_dir=selected_out_dir,
                job_id=row["job_id"],
                notes=notes,
                decision_reason=decision_reason,
                priority=priority,
            )
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)
        if st.button("Generate CVs For prepare_cv Jobs", type="primary", use_container_width=True):
            ok, message = _run_selected_cv_pipeline(
                tracker_path=tracker_path,
                tracked_review_queue=tracked_review_queue,
                batch_dir=batch_dir,
                data_dir=data_dir,
                out_dir=selected_out_dir,
            )
            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

        st.markdown("---")
        st.subheader("Artifacts")
        st.write(f"CV Strategy: {row.get('cv_strategy_path', '') or 'not generated'}")
        st.write(f"CV Draft Text: {row.get('cv_draft_txt_path', '') or 'not generated'}")
        st.write(f"MPYA HTML: {row.get('mpya_cv_html_path', '') or 'not generated'}")
        if row.get("mpya_cv_html_path"):
            st.caption("Open the MPYA HTML file directly from your file explorer or browser.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
