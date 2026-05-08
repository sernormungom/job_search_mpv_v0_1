# Job Search Automation MVP v0.1

Local, human-in-the-loop job-search and CV-preparation prototype.

This project helps you collect job ads, batch-process and match them against your maintained profile/experience data, review decisions in a dashboard, and generate tailored CV artifacts only for jobs you explicitly select.

It does **not** auto-apply to jobs, submit forms, or publish CVs automatically.

## Canonical workflow (recommended)

```text
collect sources -> batch process jobs -> dashboard review/tracker decisions -> selected-job CV generation
```

Treat one job as a **batch of 1** (a folder containing one `.txt` file).

## Project layout

```text
job_search_mvp/        Tested implementation package
jobsearch/             Preferred public command/wrapper package
data/                  Maintained YAML source/config data
sources/copied_jobs/   Manual copied job ads (input/cache)
sources/collected_jobs/ Collected/deduplicated intake jobs + manifest
outputs/batch/         Generated batch outputs (standardized/match/review queue)
outputs/selected/      Generated selected-job CV artifacts
outputs/application_tracker.csv  Persistent review/application history
tests/                 Pytest coverage
browser_profiles/      Local browser session state (do not commit)
secrets/               Local secret/session files (do not commit)
```

## Install

Base/dev install:

```bash
python -m pip install -e ".[dev]"
```

Optional extras:

```bash
python -m pip install -e ".[ui]"       # Dashboard
python -m pip install -e ".[browser]"  # Playwright/Verama collection
python -m playwright install chromium
```

## Step 1: Collect sources and build review queue

Preferred orchestrator:

```bash
python -m jobsearch.pipeline.run_sources_to_review \
  --sources job_sources.yaml \
  --data-dir . \
  --sync-tracker
```

What it does:

1. Collects jobs from configured/manual sources.
2. Deduplicates into `sources/collected_jobs/`.
3. Runs batch matching.
4. Optionally syncs queue rows into persistent tracker (`--sync-tracker`).

Key outputs:

```text
sources/collected_jobs/*.txt
sources/collected_jobs/job_manifest.csv
outputs/batch/review_queue.csv
outputs/batch/review_queue.html
outputs/batch/review_queue.tracked.csv
outputs/application_tracker.csv
outputs/application_tracker.html
```

## Step 2: Batch process jobs directly

If your `.txt` jobs are already prepared:

```bash
python -m jobsearch.pipeline.run_job_batch \
  --jobs-dir sources/collected_jobs \
  --data-dir data \
  --out-dir outputs/batch
```

Batch-of-1 example: put one job text file in a folder and run the same command.

Optional hybrid/LLM standardization:

```bash
python -m jobsearch.pipeline.run_job_batch \
  --jobs-dir sources/collected_jobs \
  --data-dir data \
  --out-dir outputs/batch \
  --standardizer hybrid \
  --llm-provider openai \
  --llm-model gpt-3.5-turbo
```

LLM environment:

```bash
set OPENAI_API_KEY=...
set JOBSEARCH_LLM_PROVIDER=openai
set JOBSEARCH_LLM_MODEL=gpt-3.5-turbo
```

Current guardrail: OpenAI calls are budget-constrained to the configured model in code.

Batch outputs:

```text
outputs/batch/review_queue.csv
outputs/batch/review_queue.html
outputs/batch/<job_id>.job_standardized.yaml
outputs/batch/<job_id>.job_standardized.validation.yaml  (LLM/hybrid mode)
outputs/batch/<job_id>.job_standardized.llm_raw.yaml     (LLM mode)
outputs/batch/<job_id>.match_result.yaml
```

## Step 3: Review in dashboard (human decision gate)

Launch:

```bash
python -m jobsearch.pipeline.run_dashboard \
  --review-queue outputs/batch/review_queue.csv \
  --tracker outputs/application_tracker.csv \
  --batch-dir outputs/batch \
  --data-dir data \
  --selected-out-dir outputs/selected \
  --tracked-review-queue outputs/batch/review_queue.tracked.csv \
  --port 8501
```

The dashboard is the normal gate between matching and CV generation. Typical statuses include `new`, `keep`, `maybe`, `reject`, `prepare_cv`, `cv_ready`, `applied`, `archived`.

## Step 4: Generate CV artifacts for selected jobs only

Only jobs explicitly marked for CV prep (for example `review_status = prepare_cv`) should move downstream.

```bash
python -m jobsearch.pipeline.run_selected_cv_pipeline \
  --review-queue outputs/batch/review_queue.tracked.csv \
  --batch-dir outputs/batch \
  --data-dir data \
  --out-dir outputs/selected
```

Outputs:

```text
outputs/selected/<job_id>.cv_strategy.yaml
outputs/selected/<job_id>.cv_draft.yaml
outputs/selected/<job_id>.cv_draft.txt
outputs/selected/<job_id>.mpya_cv.html
outputs/selected/selected_cv_pipeline_report.csv
outputs/selected/selected_cv_pipeline_report.html
```

If needed, ingest generated CV report back into the persistent tracker:

```bash
python -m jobsearch.tracking.application_tracker ingest-cv-report \
  --tracker outputs/application_tracker.csv \
  --cv-report outputs/selected/selected_cv_pipeline_report.csv
```

## Optional: Verama/Ework browser collection

```bash
python -m jobsearch.sources.verama_playwright \
  --url "https://app.verama.com/app/job-requests" \
  --out-dir sources/collected_jobs \
  --headed \
  --login-if-needed
```

Uses `browser_profiles/verama/` for local session state. Keep credentials out of code and committed files.

## Tests

```bash
python -m pytest
```

## Data lifecycle

| Path | Lifecycle | Notes |
|---|---|---|
| `data/*.yaml` | Maintained source/config | Source of truth for profile/preferences/templates/sources. |
| `sources/copied_jobs/` | Manual input/cache | Current-cycle or reused manually. |
| `sources/collected_jobs/` | Generated intake/cache | Deduplicated jobs + manifest. |
| `outputs/batch/` | Generated active-cycle output | Regenerable batch artifacts. |
| `outputs/selected/` | Generated selected-job output | Regenerable CV artifacts. |
| `outputs/application_tracker.csv` | Persistent user history | Preserve across cycles unless explicitly reset. |
| `browser_profiles/` | Local session state | Do not treat as project source data. |

## Command surface

Preferred command shape is `python -m jobsearch...`.

Console scripts from `pyproject.toml` are also available:

```text
job-search-batch
job-search-sources
job-search-tracker
job-search-selected-cv
job-search-verama
job-search-dashboard
```

## Legacy/developer commands (secondary)

The implementation package `job_search_mvp/` still contains lower-level modules and compatibility wrappers. They are useful for debugging and tests, but they are not the primary user workflow.

Prefer the batch pipeline even for one job. If you do need a lower-level module for debugging, keep it as a local developer-only choice rather than the documented default.

Typical debug-only examples:

```bash
job-search-match --job path/to/job.txt --data-dir data --out-dir outputs/debug
job-search-standardizer --help
```

## Important limitations

1. Local prototype with explicit human approval gates.
2. No automatic job application submission.
3. No credential storage in code/repo.
