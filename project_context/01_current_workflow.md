# Current Workflow

## Canonical workflow summary

The canonical workflow is a recurring batch process:

```text
Configured/manual job sources
-> collected/deduplicated .txt jobs
-> batch standardization and matching
-> review queue + persistent tracker
-> dashboard human review
-> selected-job CV generation
-> human approval/application decision
```

The batch workflow is the official workflow. A single job should be handled as a folder containing one `.txt` file and processed with the batch command.

## Operating model: current search cycle

The normal usage pattern is weekly or periodic:

1. Work with the positions relevant to the current search cycle.
2. Use existing collected/processed positions as cache only if they are intentionally reused.
3. Keep long-lived decisions in `outputs/application_tracker.csv`.
4. Do not mix old positions into the active review queue unless that is intentional.

A future cleanup feature may reset or archive previous cycle artifacts before a new search. That feature is intentionally not part of the current refactor.

## Step 0: Install for development

```bash
python -m pip install -e ".[dev]"
```

Optional extras:

```bash
python -m pip install -e ".[ui]"       # Streamlit dashboard
python -m pip install -e ".[browser]"  # Playwright/Verama collection
python -m playwright install chromium
```

## Step 1: Collect sources and build the review queue

Preferred high-level command:

```bash
python -m jobsearch.pipeline.run_sources_to_review \
  --sources job_sources.yaml \
  --data-dir . \
  --sync-tracker
```

What this orchestrates:

1. `jobsearch.sources.source_adapter` collects jobs from `data/job_sources.yaml`.
2. Jobs are deduplicated and written to `sources/collected_jobs/`.
3. `jobsearch.pipeline.run_job_batch` processes the collected folder.
4. If `--sync-tracker` is set, the review queue is merged into the persistent tracker.

Expected important outputs:

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

If jobs are already available as `.txt` files, run the batch processor directly:

```bash
python -m jobsearch.pipeline.run_job_batch \
  --jobs-dir sources/collected_jobs \
  --data-dir data \
  --out-dir outputs/batch
```

For one job, create a folder with one `.txt` file and use the same command. Do not use the old individual-job workflow as the default path.

Optional LLM/hybrid standardization:

```bash
python -m jobsearch.pipeline.run_job_batch \
  --jobs-dir sources/collected_jobs \
  --data-dir data \
  --out-dir outputs/batch \
  --standardizer hybrid \
  --llm-provider openai \
  --llm-model gpt-3.5-turbo
```

Important constraint: the code currently restricts OpenAI LLM calls to the configured budget model for cost control.

Language and extraction behavior:

- Deterministic standardization now includes multilingual section normalization for Swedish/English job ads.
- Canonical section handling includes mappings such as:
  - `Uppdragsbeskrivning` -> job description context
  - `Krav` -> `must_have`
  - `Meriterande` -> `nice_to_have`
- Requirement extraction uses language-aware marker sets to reduce Swedish/English parsing gaps.

Hybrid-mode behavior:

- `--standardizer hybrid` is confidence-gated.
- If deterministic confidence is high enough, the pipeline skips the LLM call and keeps deterministic output.
- If deterministic confidence is low, the pipeline attempts LLM enrichment and falls back to deterministic output if LLM is unavailable or invalid.

Expected batch outputs:

```text
outputs/batch/review_queue.csv
outputs/batch/review_queue.html
outputs/batch/<job_id>.job_standardized.yaml
outputs/batch/<job_id>.job_standardized.validation.yaml  # when LLM/hybrid mode runs
outputs/batch/<job_id>.job_standardized.llm_raw.yaml     # when LLM runs
outputs/batch/<job_id>.match_result.yaml
```

## Step 3: Review jobs in the dashboard

The dashboard is the normal human review gate. It should be used to inspect matched jobs, update decisions, and decide which jobs should move to CV preparation.

Statuses include values such as:

```text
new
keep
maybe
reject
prepare_cv
cv_ready
applied
archived
```

Only jobs explicitly marked for CV preparation should move into the selected-CV pipeline.

## Step 4: Launch dashboard

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

The dashboard is a control center for reviewing jobs, updating tracker decisions, syncing tracker data, and triggering selected CV generation.

## Step 5: Generate CV artifacts only for selected jobs

CV generation is downstream of the dashboard/human decision. The normal trigger is a job row marked with `review_status = prepare_cv`.

CLI execution:

```bash
python -m jobsearch.pipeline.run_selected_cv_pipeline \
  --review-queue outputs/batch/review_queue.tracked.csv \
  --batch-dir outputs/batch \
  --data-dir data \
  --out-dir outputs/selected
```

Expected selected-CV outputs:

```text
outputs/selected/<job_id>.cv_strategy.yaml
outputs/selected/<job_id>.cv_draft.yaml
outputs/selected/<job_id>.cv_draft.txt
outputs/selected/<job_id>.mpya_cv.html
outputs/selected/selected_cv_pipeline_report.csv
outputs/selected/selected_cv_pipeline_report.html
```

After CV generation, ingest the report into the tracker if not done by the dashboard:

```bash
python -m jobsearch.tracking.application_tracker ingest-cv-report \
  --tracker outputs/application_tracker.csv \
  --cv-report outputs/selected/selected_cv_pipeline_report.csv
```

## Step 6: Optional Verama/Ework browser collection

Use this only when browser collection is needed:

```bash
python -m jobsearch.sources.verama_playwright \
  --url "https://app.verama.com/app/job-requests" \
  --out-dir sources/collected_jobs \
  --headed \
  --login-if-needed
```

The adapter uses `browser_profiles/verama/` for local browser session state. It should not store credentials in code and should not click apply/submit controls.

## Step 7: Run tests

```bash
python -m pytest
```

The current tests cover matcher behavior, source adapter deduplication, the compatibility package, CV draft/strategy behavior, tracker transitions, and LLM model budget enforcement.

## Output lifecycle

| Path | Lifecycle | Notes |
|---|---|---|
| `data/*.yaml` | Maintained source/config | Source of truth for profile, preferences, templates, and source config. |
| `sources/copied_jobs/` | Manual input/cache | Jobs manually copied for a search cycle. |
| `sources/collected_jobs/` | Generated intake/cache | Deduplicated job text and manifest. May be cleaned in a future feature. |
| `outputs/batch/` | Generated active-cycle output | Standardized jobs, match results, and review queues. |
| `outputs/selected/` | Generated selected-job output | CV strategy, draft, and rendered HTML for selected jobs. |
| `outputs/application_tracker.csv` | Persistent user history | Preserve across cycles unless explicitly reset. |
| `browser_profiles/` | Local session state | Do not commit or treat as project data. |

## Legacy or secondary workflows

The README may still include individual-job matching and CV generation commands. Treat those as legacy, debugging, or lower-level developer commands unless they are required by the batch pipeline.

The current refactor goal is to make the batch workflow clear enough that a new user or AI agent does not perceive the project as having two or three competing workflows.
