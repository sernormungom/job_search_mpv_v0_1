#!/usr/bin/env python3
"""
End-to-end source intake -> review queue runner.

This orchestrates:
  1) source_adapter.py: collect/deduplicate jobs from job_sources.yaml
  2) run_job_batch.py: standardize and match collected jobs
  3) application_tracker.py sync: merge review queue with persistent decisions

It keeps source collection separate from matching, so adapters can evolve without
changing the core matcher.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

from .paths import resolve_project_root
from .workspace_cleanup import reset_search_cycle_artifacts


def run(cmd: List[str], cwd: Path) -> None:
    print("\n$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect sources and build a tracked review queue")
    parser.add_argument("--sources", default="job_sources.yaml", help="Path to job_sources.yaml")
    parser.add_argument("--data-dir", default=".", help="Project root or data directory")
    parser.add_argument("--collected-dir", default="sources/collected_jobs", help="Collected deduped .txt jobs")
    parser.add_argument("--manifest", default="sources/collected_jobs/job_manifest.csv", help="Collection manifest CSV")
    parser.add_argument("--batch-out", default="outputs/batch", help="Batch matcher output folder")
    parser.add_argument("--tracker", default="outputs/application_tracker.csv", help="Persistent tracker CSV")
    parser.add_argument("--sync-tracker", action="store_true", help="Also sync the review queue into the tracker")
    parser.add_argument(
        "--reset-cycle-artifacts",
        action="store_true",
        help="Delete previous generated cycle artifacts (sources/collected_jobs, outputs/batch, outputs/selected) before running",
    )
    args = parser.parse_args()

    project_root = resolve_project_root(args.data_dir)
    if args.reset_cycle_artifacts:
        summary = reset_search_cycle_artifacts(project_root=project_root)
        print("\nReset previous cycle artifacts")
        print(f"Removed: {', '.join(summary['removed']) if summary['removed'] else '(none)'}")
        print(f"Missing: {', '.join(summary['missing']) if summary['missing'] else '(none)'}")

    run([
        sys.executable, "-m", "jobsearch.sources.source_adapter",
        "--sources", args.sources,
        "--package-root", str(project_root),
        "--out-dir", args.collected_dir,
        "--manifest", args.manifest,
    ], cwd=project_root)

    run([
        sys.executable, "-m", "jobsearch.pipeline.run_job_batch",
        "--jobs-dir", args.collected_dir,
        "--data-dir", str(project_root),
        "--out-dir", args.batch_out,
    ], cwd=project_root)

    review_queue = Path(args.batch_out) / "review_queue.csv"
    if args.sync_tracker:
        tracked_queue = Path(args.batch_out) / "review_queue.tracked.csv"
        tracker_html = Path(args.tracker).with_suffix(".html")
        run([
            sys.executable, "-m", "jobsearch.tracking.application_tracker", "sync",
            "--review-queue", str(review_queue),
            "--tracker", args.tracker,
            "--out-review-queue", str(tracked_queue),
            "--out-html", str(tracker_html),
        ], cwd=project_root)
        print(f"\nTracked review queue: {tracked_queue}")
        print(f"Tracker HTML: {tracker_html}")
    else:
        print(f"\nReview queue: {review_queue}")

    print("\nNext: mark a job as prepare_cv in the tracker or tracked review queue, then run run_selected_cv_pipeline.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
