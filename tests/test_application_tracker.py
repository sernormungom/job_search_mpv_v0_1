import csv
import uuid

from job_search_mvp import application_tracker
from job_search_mvp.paths import OUTPUTS_DIR


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_tracker_sync_preserves_decisions_and_ingests_cv_report():
    work_dir = OUTPUTS_DIR / "pytest_work" / "application_tracker" / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)
    review_queue = work_dir / "review_queue.csv"
    tracker = work_dir / "application_tracker.csv"
    cv_report = work_dir / "selected_cv_pipeline_report.csv"

    write_csv(
        review_queue,
        [
            {
                "review_status": "keep",
                "recommended_status": "keep",
                "overall_score": "79",
                "expertise_fit": "98",
                "tool_fit": "96",
                "domain_fit": "100",
                "growth_fit": "72",
                "interest_fit": "60",
                "practical_fit": "95",
                "risk_score": "15",
                "job_id": "job_b089d2425f",
                "input_file": "sample_job_embedded.txt",
                "title": "Senior Embedded Software Engineer",
                "normalized_title": "Embedded Software Engineer",
                "company": "",
                "city": "Gothenburg",
                "work_mode": "hybrid",
                "source_url": "",
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
    assert rows[0]["overall_score"] == "79"

    application_tracker.set_status(
        tracker,
        "job_b089d2425f",
        "prepare_cv",
        notes="Strong fit",
        decision_reason="Prepare tailored CV",
        priority="high",
    )
    updated = application_tracker.read_csv(tracker)[0]
    assert updated["status"] == "prepare_cv"
    assert updated["user_notes"] == "Strong fit"
    assert updated["priority"] == "high"

    rows = application_tracker.sync_tracker(review_queue, tracker)
    assert rows[0]["status"] == "prepare_cv"
    assert rows[0]["user_notes"] == "Strong fit"

    write_csv(
        cv_report,
        [
            {
                "job_id": "job_b089d2425f",
                "cv_strategy": "outputs/selected/job_b089d2425f.cv_strategy.yaml",
                "cv_draft_yaml": "outputs/selected/job_b089d2425f.cv_draft.yaml",
                "cv_draft_txt": "outputs/selected/job_b089d2425f.cv_draft.txt",
                "mpya_cv_html": "outputs/selected/job_b089d2425f.mpya_cv.html",
            }
        ],
        ["job_id", "cv_strategy", "cv_draft_yaml", "cv_draft_txt", "mpya_cv_html"],
    )
    application_tracker.ingest_cv_report(tracker, cv_report)
    ingested = application_tracker.read_csv(tracker)[0]
    assert ingested["status"] == "cv_ready"
    assert ingested["mpya_cv_html_path"].endswith("job_b089d2425f.mpya_cv.html")
