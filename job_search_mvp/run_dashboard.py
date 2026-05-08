#!/usr/bin/env python3
"""Launch the Streamlit dashboard with project defaults."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .paths import PROJECT_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Job Search MVP Streamlit dashboard")
    parser.add_argument("--review-queue", default="", help="Path to review_queue.csv")
    parser.add_argument("--tracker", default="outputs/application_tracker.csv", help="Path to tracker CSV")
    parser.add_argument("--outputs-dir", default="outputs", help="Outputs dir used for auto-discovery")
    parser.add_argument("--batch-dir", default="outputs/batch", help="Batch directory containing matcher YAML outputs")
    parser.add_argument("--data-dir", default="data", help="Data directory used by CV pipeline")
    parser.add_argument("--selected-out-dir", default="outputs/selected", help="Output directory for generated CV artifacts")
    parser.add_argument("--tracked-review-queue", default="outputs/batch/review_queue.tracked.csv", help="Tracked review queue path generated from tracker")
    parser.add_argument("--port", default="8501", help="Streamlit port")
    args = parser.parse_args()

    dashboard = PROJECT_ROOT / "job_search_mvp" / "streamlit_dashboard.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard),
        "--server.port",
        str(args.port),
        "--",
        "--tracker",
        args.tracker,
        "--outputs-dir",
        args.outputs_dir,
        "--batch-dir",
        args.batch_dir,
        "--data-dir",
        args.data_dir,
        "--selected-out-dir",
        args.selected_out_dir,
        "--tracked-review-queue",
        args.tracked_review_queue,
    ]
    if args.review_queue:
        cmd.extend(["--review-queue", args.review_queue])
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
