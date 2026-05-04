# Job Search Automation MVP v0.1

This is a local deterministic prototype for collecting job ads, matching them against experience data, and generating reviewable CV artifacts.

## Project layout

```text
job_search_mvp/        Python package modules
data/                  Manually maintained YAML data and templates
outputs/               Generated files, review queues, trackers, collected jobs
prototype/             Compatibility command wrappers plus examples
tests/                 Pytest coverage for the core prototype behavior
```

The old `python prototype/<script>.py ...` commands still work. The wrappers delegate to the packaged modules in `job_search_mvp/`.

`--data-dir .` is still accepted for older commands; it resolves to `data/` when the YAML files are not in the project root.

## Main workflows

### 1. Match one copied job

```bash
python prototype/matcher.py \
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
python prototype/strategy_generator.py \
  --job-standardized outputs/single/<job_id>.job_standardized.yaml \
  --match-result outputs/single/<job_id>.match_result.yaml \
  --data-dir data \
  --out-dir outputs/single

python prototype/cv_draft_generator.py \
  --cv-strategy outputs/single/<job_id>.cv_strategy.yaml \
  --job-standardized outputs/single/<job_id>.job_standardized.yaml \
  --data-dir data \
  --out-dir outputs/single

python prototype/mpya_cv_renderer.py \
  --cv-draft outputs/single/<job_id>.cv_draft.yaml \
  --data-dir data \
  --out-dir outputs/single
```

### 3. Batch match copied jobs

```bash
python prototype/run_job_batch.py \
  --jobs-dir prototype/examples/job_batch \
  --data-dir data \
  --out-dir outputs/batch
```

Outputs:

```text
outputs/batch/review_queue.csv
outputs/batch/review_queue.html
outputs/batch/<job_id>.job_standardized.yaml
outputs/batch/<job_id>.match_result.yaml
```

### 4. Collect sources and build a tracked review queue

```bash
python prototype/run_sources_to_review.py \
  --sources job_sources.yaml \
  --data-dir . \
  --sync-tracker
```

`job_sources.yaml` now lives in `data/`; the command resolves it there for compatibility.

Outputs:

```text
outputs/collected_jobs/
outputs/batch/review_queue.csv
outputs/batch/review_queue.tracked.csv
outputs/application_tracker.csv
outputs/application_tracker.html
```

### 5. Prepare CVs only for selected jobs

Mark rows in `outputs/batch/review_queue.tracked.csv` with `review_status = prepare_cv`, then run:

```bash
python prototype/run_selected_cv_pipeline.py \
  --review-queue outputs/batch/review_queue.tracked.csv \
  --batch-dir outputs/batch \
  --data-dir data \
  --out-dir outputs/selected
```

Afterward, attach generated CV paths to the persistent tracker:

```bash
python prototype/application_tracker.py ingest-cv-report \
  --tracker outputs/application_tracker.csv \
  --cv-report outputs/selected/selected_cv_pipeline_report.csv
```

### 6. Run tests

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The tests cover matcher behavior, CV strategy generation, application tracker state transitions, and local source adapter deduplication.

## Design decisions locked in

1. `role_fit_profiles` are optional for MVP.
2. CVs are not generated directly from `match_result.yaml`; `cv_strategy.yaml` is the intermediate approval artifact.
3. Explicit job tools should appear in the CV if the job asks for them and evidence or aliases support them.
4. Professional summaries are generated dynamically from evidence and writing constraints.
5. Older foundational experience can be kept when it supports the target role, but should usually be compressed.

## Important limitation

This remains a local deterministic prototype. It does not use an LLM, publish to a website, or apply for jobs. The optional Playwright adapter is available for browser-assisted collection, but copied job folders remain the most reliable workflow.
