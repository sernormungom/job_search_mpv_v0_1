import csv
import uuid
from pathlib import Path
from types import SimpleNamespace

from job_search_mvp import application_tracker, run_job_batch, run_selected_cv_pipeline
from job_search_mvp.paths import DATA_DIR, OUTPUTS_DIR
from job_search_mvp import streamlit_dashboard


def write_csv(path: Path, rows, fieldnames) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_job_file(path: Path, title: str, company: str = "Example AB") -> None:
    path.write_text(
        (
            f"Title: {title}\n"
            f"Company: {company}\n"
            "Location: Gothenburg\n\n"
            "Full job description\n"
            f"{title} role for embedded software and verification work.\n"
            "Required: C++, AUTOSAR, CI/CD, verification and validation, and safety-critical systems experience.\n"
        ),
        encoding="utf-8",
    )


def make_work_dir(name: str) -> Path:
    work_dir = OUTPUTS_DIR / "pytest_work" / name / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def blank_tracker_row(job_id: str, *, status: str = "keep", title: str = "Senior Embedded Software Engineer") -> dict[str, str]:
    row = {field: "" for field in application_tracker.TRACKER_FIELDS}
    row.update(
        {
            "job_id": job_id,
            "status": status,
            "priority": "medium",
            "title": title,
            "normalized_title": "Embedded Software Engineer",
            "company": "Example AB",
            "city": "Gothenburg",
            "work_mode": "hybrid",
            "overall_score": "77",
            "recommended_status": "keep",
            "match_reason": "Initial review fit",
            "user_notes": "Keep this one",
        }
    )
    return row


def test_run_job_batch_processes_single_job_folder(monkeypatch):
    work_dir = make_work_dir("phase4_batch")
    jobs_dir = work_dir / "jobs"
    out_dir = work_dir / "batch"
    jobs_dir.mkdir()
    write_job_file(jobs_dir / "sample_job.txt", "Senior Embedded Software Engineer")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", [
        "run_job_batch.py",
        "--jobs-dir",
        str(jobs_dir),
        "--data-dir",
        str(DATA_DIR),
        "--out-dir",
        str(out_dir),
        "--standardizer",
        "deterministic",
    ])

    assert run_job_batch.main() == 0

    review_queue = out_dir / "review_queue.csv"
    rows = read_csv(review_queue)
    assert len(rows) == 1
    job_id = rows[0]["job_id"]
    assert rows[0]["input_file"] == "sample_job.txt"
    assert (out_dir / f"{job_id}.job_standardized.yaml").exists()
    assert (out_dir / f"{job_id}.match_result.yaml").exists()


def test_tracker_sync_preserves_human_decisions_when_review_queue_refreshes():
    work_dir = make_work_dir("phase4_tracker")
    review_queue = work_dir / "review_queue.csv"
    tracker = work_dir / "application_tracker.csv"
    write_csv(
        review_queue,
        [
            {
                "review_status": "keep",
                "recommended_status": "keep",
                "overall_score": "79",
                "expertise_fit": "98",
                "role_fit": "91",
                "tool_fit": "96",
                "domain_fit": "90",
                "growth_fit": "72",
                "interest_fit": "60",
                "practical_fit": "95",
                "risk_score": "15",
                "job_id": "job_123",
                "input_file": "sample_job.txt",
                "title": "Senior Embedded Software Engineer",
                "normalized_title": "Embedded Software Engineer",
                "company": "Example AB",
                "city": "Gothenburg",
                "work_mode": "hybrid",
                "source_url": "https://example.com/jobs/123",
                "matched_terms": "C++, AUTOSAR",
                "suggested_role_groups": "VOLVO_2024_2026",
                "hard_blockers": "",
                "soft_risks": "Swedish may be preferred",
                "reason": "good fit",
            }
        ],
        [
            "review_status",
            "recommended_status",
            "overall_score",
            "expertise_fit",
            "role_fit",
            "tool_fit",
            "domain_fit",
            "growth_fit",
            "interest_fit",
            "practical_fit",
            "risk_score",
            "job_id",
            "input_file",
            "title",
            "normalized_title",
            "company",
            "city",
            "work_mode",
            "source_url",
            "matched_terms",
            "suggested_role_groups",
            "hard_blockers",
            "soft_risks",
            "reason",
        ],
    )

    rows = application_tracker.sync_tracker(review_queue, tracker)
    assert rows[0]["status"] == "keep"
    application_tracker.set_status(
        tracker,
        "job_123",
        "prepare_cv",
        notes="Strong fit",
        decision_reason="Prepare tailored CV",
        priority="high",
    )
    tracker_rows = application_tracker.read_csv(tracker)
    tracker_rows[0]["status"] = "prepare_cv"
    tracker_rows[0]["overall_score"] = "81"
    tracker_rows[0]["match_reason"] = "updated reason"
    write_csv(tracker, tracker_rows, application_tracker.TRACKER_FIELDS)

    refreshed_review_queue = work_dir / "review_queue_refreshed.csv"
    write_csv(
        refreshed_review_queue,
        [
            {
                "review_status": "maybe",
                "recommended_status": "maybe",
                "overall_score": "60",
                "expertise_fit": "83",
                "role_fit": "75",
                "tool_fit": "70",
                "domain_fit": "68",
                "growth_fit": "55",
                "interest_fit": "50",
                "practical_fit": "88",
                "risk_score": "24",
                "job_id": "job_123",
                "input_file": "sample_job.txt",
                "title": "Senior Embedded Software Engineer",
                "normalized_title": "Embedded Software Engineer",
                "company": "Example AB",
                "city": "Gothenburg",
                "work_mode": "hybrid",
                "source_url": "https://example.com/jobs/123",
                "matched_terms": "C++, AUTOSAR, CI/CD",
                "suggested_role_groups": "VOLVO_2024_2026",
                "hard_blockers": "",
                "soft_risks": "Swedish may be preferred",
                "reason": "refreshed reason",
            }
        ],
        [
            "review_status",
            "recommended_status",
            "overall_score",
            "expertise_fit",
            "role_fit",
            "tool_fit",
            "domain_fit",
            "growth_fit",
            "interest_fit",
            "practical_fit",
            "risk_score",
            "job_id",
            "input_file",
            "title",
            "normalized_title",
            "company",
            "city",
            "work_mode",
            "source_url",
            "matched_terms",
            "suggested_role_groups",
            "hard_blockers",
            "soft_risks",
            "reason",
        ],
    )

    synced = application_tracker.sync_tracker(refreshed_review_queue, tracker)
    updated = synced[0]
    assert updated["status"] == "prepare_cv"
    assert updated["user_notes"] == "Strong fit"
    assert updated["priority"] == "high"
    assert updated["overall_score"] == "60"
    assert updated["match_reason"] == "refreshed reason"


def test_selected_cv_pipeline_processes_only_prepare_cv_rows(monkeypatch):
    work_dir = make_work_dir("phase4_selected")
    jobs_dir = work_dir / "jobs"
    batch_dir = work_dir / "batch"
    out_dir = work_dir / "selected"
    jobs_dir.mkdir()
    batch_dir.mkdir()
    write_job_file(jobs_dir / "prepare.txt", "Senior Embedded Software Engineer")
    write_job_file(jobs_dir / "skip.txt", "Software Verification Engineer")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", [
        "run_job_batch.py",
        "--jobs-dir",
        str(jobs_dir),
        "--data-dir",
        str(DATA_DIR),
        "--out-dir",
        str(batch_dir),
        "--standardizer",
        "deterministic",
    ])
    assert run_job_batch.main() == 0

    review_queue = read_csv(batch_dir / "review_queue.csv")
    assert len(review_queue) == 2
    review_queue[0]["review_status"] = "prepare_cv"
    review_queue[1]["review_status"] = "new"
    write_csv(batch_dir / "review_queue.csv", review_queue, list(review_queue[0].keys()))

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", [
        "run_selected_cv_pipeline.py",
        "--review-queue",
        str(batch_dir / "review_queue.csv"),
        "--batch-dir",
        str(batch_dir),
        "--data-dir",
        str(DATA_DIR),
        "--out-dir",
        str(out_dir),
    ])
    assert run_selected_cv_pipeline.main() == 0

    report_rows = read_csv(out_dir / "selected_cv_pipeline_report.csv")
    assert len(report_rows) == 1
    selected_job_id = report_rows[0]["job_id"]
    assert report_rows[0]["review_status"] == "prepare_cv"
    assert (out_dir / f"{selected_job_id}.cv_strategy.yaml").exists()
    assert (out_dir / f"{selected_job_id}.cv_draft.yaml").exists()
    assert (out_dir / f"{selected_job_id}.cv_draft.txt").exists()
    assert (out_dir / f"{selected_job_id}.mpya_cv.html").exists()
    assert not (out_dir / f"{review_queue[1]['job_id']}.cv_strategy.yaml").exists()


def test_dashboard_single_job_cv_helper_updates_tracker_status(monkeypatch):
    work_dir = make_work_dir("phase4_dashboard")
    tracker = work_dir / "application_tracker.csv"
    tracked_review_queue = work_dir / "review_queue.tracked.csv"
    batch_dir = work_dir / "batch"
    out_dir = work_dir / "selected"
    batch_dir.mkdir()
    out_dir.mkdir()
    write_csv(
        tracker,
        [
            blank_tracker_row("job_dash_1", status="keep"),
            blank_tracker_row("job_dash_2", status="maybe", title="Software Verification Engineer"),
        ],
        application_tracker.TRACKER_FIELDS,
    )

    captured = {}

    def fake_run(cmd, check, capture_output, text):
        captured["cmd"] = cmd
        report = out_dir / "selected_cv_pipeline_report.csv"
        write_csv(
            report,
            [
                {
                    "job_id": "job_dash_1",
                    "cv_strategy": str(out_dir / "job_dash_1.cv_strategy.yaml"),
                    "cv_draft_yaml": str(out_dir / "job_dash_1.cv_draft.yaml"),
                    "cv_draft_txt": str(out_dir / "job_dash_1.cv_draft.txt"),
                    "mpya_cv_html": str(out_dir / "job_dash_1.mpya_cv.html"),
                }
            ],
            ["job_id", "cv_strategy", "cv_draft_yaml", "cv_draft_txt", "mpya_cv_html"],
        )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(streamlit_dashboard.subprocess, "run", fake_run)
    ok, message = streamlit_dashboard._run_single_job_cv_pipeline(
        tracker_path=tracker,
        tracked_review_queue=tracked_review_queue,
        batch_dir=batch_dir,
        data_dir=DATA_DIR,
        out_dir=out_dir,
        job_id="job_dash_1",
        notes="Use tailored summary",
        decision_reason="Dashboard trigger",
        priority="high",
    )

    assert ok is True
    assert "CV ready for job_dash_1" in message
    assert captured["cmd"][2] == "jobsearch.pipeline.run_selected_cv_pipeline"
    assert tracked_review_queue.with_name(f"{tracked_review_queue.stem}.job_dash_1.single.csv").exists()

    updated_tracker = application_tracker.read_csv(tracker)
    row = next(r for r in updated_tracker if r["job_id"] == "job_dash_1")
    assert row["status"] == "cv_ready"
    assert row["priority"] == "high"
    assert row["user_notes"] == "Use tailored summary"
    assert row["decision_reason"] == "Dashboard trigger"
    assert row["cv_strategy_path"].endswith("job_dash_1.cv_strategy.yaml")
    assert row["mpya_cv_html_path"].endswith("job_dash_1.mpya_cv.html")


def test_dashboard_job_context_replaces_raw_scrape_summary_with_review_summary():
    work_dir = make_work_dir("phase4_dashboard_context")
    batch_dir = work_dir / "batch"
    batch_dir.mkdir()
    job_id = "job_context_1"
    run_job_batch.matcher.write_yaml(
        batch_dir / f"{job_id}.job_standardized.yaml",
        {
            "job_standardized": {
                "job_id": job_id,
                "language": {"original": "Swedish", "standardized_output": "English"},
                "identity": {
                    "original_title": "Systemintegrator IBM ACE",
                    "normalized_title": "System Integration Consultant",
                    "company": "Polismyndigheten",
                    "location": {"city": "Gothenburg", "work_mode": "on-site"},
                },
                "summary": {
                    "short_summary": "Source URL: https://example.test\nCollected From: verama\nSystemintegrator IBM ACE",
                },
                "job_description": "Develop integrations on IBM ACE for a public-sector integration platform.",
                "job_analysis": {
                    "primary_technical_focus": ["IBM ACE"],
                    "secondary_technical_focus": ["public-sector integrations"],
                },
                "normalized_requirements": {
                    "responsibilities": ["Develop complex integrations on IBM ACE."],
                    "must_have": ["Minimum 1 year of experience in integration development with IBM ACE"],
                    "nice_to_have": ["Experience in the public sector"],
                },
                "blockers": {"hard": [], "soft": ["Swedish may be preferred"]},
                "llm_enrichment": {
                    "identity_extra": {
                        "assignment_period": {"start": "2026-08-01", "end": "2027-06-01"},
                        "application_deadline": "2026-05-28",
                        "remote_percentage": 0,
                    },
                    "tags": {"language_requirement": ["Swedish"]},
                },
            }
        },
    )

    context = streamlit_dashboard._read_job_context(batch_dir, job_id)

    assert "Source URL" not in context["summary"]
    assert "System Integration Consultant role for Polismyndigheten" in context["summary"]
    assert context["responsibilities"] == ["Develop complex integrations on IBM ACE."]
    assert context["assignment_period"]["start"] == "2026-08-01"
    assert context["application_deadline"] == "2026-05-28"


def test_dashboard_review_brief_is_conservative_for_specific_tool_requirements():
    row = {
        "recommended_status": "reject",
        "overall_score": "50",
        "expertise_fit": "30",
        "role_fit": "66",
        "tool_fit": "23",
        "growth_fit": "72",
        "practical_fit": "40",
        "risk_score": "15",
        "matched_terms": "integration",
        "hard_blockers": "",
        "soft_risks": "Swedish may be preferred",
    }
    context = {
        "must_have": ["Minimum 1 year of experience in integration development with IBM ACE"],
        "hard_blockers": [],
        "soft_blockers": [],
        "identity": {"location": {"work_mode": "on-site"}},
        "remote_percentage": 0,
        "language": {"original": "Swedish", "standardized_output": "English"},
        "llm_enrichment": {"tags": {"language_requirement": ["Swedish"]}},
    }

    assert streamlit_dashboard._classify_requirement_fit(
        "Minimum 1 year of experience in integration development with IBM ACE",
        ["integration"],
    ) == "no direct evidence"

    brief = streamlit_dashboard._build_review_brief(row, context)

    assert brief["decision_hint"].startswith("Likely reject")
    assert any("Weak direct tool fit" in concern for concern in brief["concerns"])
    assert any("IBM ACE" in concern for concern in brief["concerns"])
