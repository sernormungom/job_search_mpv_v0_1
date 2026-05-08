# Job Search Automation MVP v0.1

This is a local deterministic prototype for collecting job ads, matching them against experience data, and generating reviewable CV artifacts.

## Project layout

```text
job_search_mvp/        Tested implementation package
jobsearch/             Planned public package layout and command wrappers
data/                  Manually maintained YAML data and templates
outputs/               Generated files, review queues, trackers, collected jobs
sources/               Local copied/manual/collected job text folders
browser_profiles/      Local Playwright browser profiles, ignored by git
secrets/               Local secrets/session files, ignored by git
prototype/             Compatibility command wrappers plus examples
tests/                 Pytest coverage for the core prototype behavior
```

The preferred command shape is now `python -m jobsearch...`, matching the project plan. The old `python prototype/<script>.py ...` commands still work and delegate to the tested implementation in `job_search_mvp/`.

`--data-dir .` is still accepted for older commands; it resolves to `data/` when the YAML files are not in the project root.

## Main workflows

### 1. Match one copied job

```bash
python -m jobsearch.matching.matcher \
  --job prototype/examples/sample_job_embedded.txt \
  --data-dir data \
  --out-dir outputs/single
```

Outputs:

```text
outputs/single/<job_id>.job_standardized.yaml
outputs/single/<job_id>.match_result.yaml
```

### 2. Generate CV strategy, draft, and HTML

```bash
python -m jobsearch.cv.strategy_generator \
  --job-standardized outputs/single/<job_id>.job_standardized.yaml \
  --match-result outputs/single/<job_id>.match_result.yaml \
  --data-dir data \
  --out-dir outputs/single

python -m jobsearch.cv.draft_generator \
  --cv-strategy outputs/single/<job_id>.cv_strategy.yaml \
  --job-standardized outputs/single/<job_id>.job_standardized.yaml \
  --data-dir data \
  --out-dir outputs/single

python -m jobsearch.cv.renderers.mpya_html \
  --cv-draft outputs/single/<job_id>.cv_draft.yaml \
  --data-dir data \
  --out-dir outputs/single
```

### 3. Batch match copied jobs

```bash
python -m jobsearch.pipeline.run_job_batch \
  --jobs-dir prototype/examples/job_batch \
  --data-dir data \
  --out-dir outputs/batch
```

Optional LLM standardization in the same batch command:

```bash
python -m jobsearch.pipeline.run_job_batch \
  --jobs-dir sources/collected_jobs \
  --data-dir data \
  --out-dir outputs/batch \
  --standardizer hybrid \
  --llm-provider openai \
  --llm-model gpt-3.5-turbo
```

Environment for LLM mode:

```bash
set OPENAI_API_KEY=...
set JOBSEARCH_LLM_PROVIDER=openai
set JOBSEARCH_LLM_MODEL=gpt-3.5-turbo
```

For cost control, OpenAI LLM calls are pinned to `gpt-3.5-turbo`; other model names are rejected before any API request is sent.

Outputs:

```text
outputs/batch/review_queue.csv
outputs/batch/review_queue.html
outputs/batch/<job_id>.job_standardized.yaml
outputs/batch/<job_id>.job_standardized.validation.yaml
outputs/batch/<job_id>.job_standardized.llm_raw.yaml (only when LLM runs)
outputs/batch/<job_id>.match_result.yaml
```

### 3b. Standardize one job with LLM

```bash
python -m jobsearch.standardization.llm_standardizer \
  --job sources/collected_jobs/job_30065ec2e7.txt \
  --out-dir outputs/standardized \
  --mode hybrid \
  --provider openai \
  --model gpt-3.5-turbo
```

### 4. Collect sources and build a tracked review queue

```bash
python -m jobsearch.pipeline.run_sources_to_review \
  --sources job_sources.yaml \
  --data-dir . \
  --sync-tracker
```

`job_sources.yaml` now lives in `data/`; the command resolves it there for compatibility. Put manually copied job ads in `sources/copied_jobs/`. The collected, deduplicated intake folder is `sources/collected_jobs/`.

Outputs:

```text
sources/collected_jobs/
outputs/batch/review_queue.csv
outputs/batch/review_queue.tracked.csv
outputs/application_tracker.csv
outputs/application_tracker.html
```

### 4b. Streamlit review dashboard (Step 1 MVP control center)

Install UI support once:

```powershell
python -m pip install -e ".[ui]"
```

Launch the dashboard:

```powershell
python -m job_search_mvp.run_dashboard `
  --review-queue outputs/demo_verama_batch/review_queue.csv `
  --tracker outputs/application_tracker.csv `
  --batch-dir outputs/batch `
  --data-dir data `
  --selected-out-dir outputs/selected `
  --tracked-review-queue outputs/batch/review_queue.tracked.csv `
  --port 8501
```

The dashboard lets you:
- Sync tracker from review queue
- Filter and inspect jobs
- Set status (`keep`, `maybe`, `reject`, `prepare_cv`, etc.) with one-click action buttons
- Store notes and decision reason
- One-click generate CV for the currently selected job (status update + generation + tracker artifact ingest)
- Run selected CV generation for all tracker rows marked `prepare_cv`
- Auto-ingest `selected_cv_pipeline_report.csv` back into tracker after generation
- View CV artifact paths once generated

### Optional Verama/Ework browser collection

Install browser support once:

```powershell
python -m pip install -e ".[browser]"
python -m playwright install chromium
```

Then collect with a visible browser. Log in manually if needed, confirm the Gothenburg filter, and press Enter in the terminal:

```powershell
python -m jobsearch.sources.verama_playwright `
  --url "https://app.verama.com/app/job-requests" `
  --out-dir sources/collected_jobs `
  --headed `
  --login-if-needed
```

The adapter uses `browser_profiles/verama/` for local session state. It never stores credentials in code and does not click apply or submit controls.

### 5. Prepare CVs only for selected jobs

Mark rows in `outputs/batch/review_queue.tracked.csv` with `review_status = prepare_cv`, then run:

```bash
python -m jobsearch.pipeline.run_selected_cv_pipeline \
  --review-queue outputs/batch/review_queue.tracked.csv \
  --batch-dir outputs/batch \
  --data-dir data \
  --out-dir outputs/selected
```

Afterward, attach generated CV paths to the persistent tracker:

```bash
python -m jobsearch.tracking.application_tracker ingest-cv-report \
  --tracker outputs/application_tracker.csv \
  --cv-report outputs/selected/selected_cv_pipeline_report.csv
```

### 6. Run tests

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The tests cover matcher behavior, alias matching, CV strategy generation, unsupported-tool filtering in CV drafts, application tracker state transitions, source adapter deduplication, and the `jobsearch` compatibility package.

## Design decisions locked in

1. `role_fit_profiles` are optional for MVP.
2. CVs are not generated directly from `match_result.yaml`; `cv_strategy.yaml` is the intermediate approval artifact.
3. Explicit job tools should appear in the CV if the job asks for them and evidence or aliases support them.
4. Professional summaries are generated dynamically from evidence and writing constraints.
5. Older foundational experience can be kept when it supports the target role, but should usually be compressed.

## Important limitation

This remains a local prototype with human approval gates. It supports deterministic standardization and optional LLM-assisted standardization with deterministic fallback. It does not publish to a website or apply for jobs automatically.
