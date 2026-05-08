# Features to Keep

This file lists the current capabilities that should be preserved during refactor unless the project owner explicitly decides otherwise.

## Must keep: Intake and batch processing

### 1. Batch-first job processing

The batch job workflow is the core feature.

Keep the ability to:

- Process a folder of job `.txt` files.
- Process a batch containing only one job.
- Produce per-job standardized YAML files.
- Produce per-job match result YAML files.
- Produce a consolidated review queue.

Primary entry points:

```bash
python -m jobsearch.pipeline.run_job_batch
job-search-batch
```

Implementation currently lives mainly in:

```text
job_search_mvp/run_job_batch.py
job_search_mvp/matcher.py
job_search_mvp/standardization/
jobsearch/pipeline/run_job_batch.py
```

### 2. Source collection into a deduplicated intake folder

Keep the ability to collect configured/manual sources into `sources/collected_jobs/` with a manifest.

Primary entry points:

```bash
python -m jobsearch.pipeline.run_sources_to_review
job-search-sources
```

Implementation currently lives mainly in:

```text
job_search_mvp/run_sources_to_review.py
job_search_mvp/source_adapter.py
jobsearch/pipeline/run_sources_to_review.py
jobsearch/sources/
```

Important outputs:

```text
sources/collected_jobs/*.txt
sources/collected_jobs/job_manifest.csv
```

## Must keep: Review, tracker, and dashboard

### 3. Review queue generation

Keep generation of human-readable and machine-readable review queues.

Important outputs:

```text
outputs/batch/review_queue.csv
outputs/batch/review_queue.html
outputs/batch/review_queue.tracked.csv
```

The review queue is the human decision gate between matching and CV generation.

### 4. Persistent application tracker

Keep the tracker as the persistent source for user decisions/statuses.

Primary artifact:

```text
outputs/application_tracker.csv
```

Keep behavior that preserves existing human decisions when the review queue is regenerated.

Implementation currently lives mainly in:

```text
job_search_mvp/application_tracker.py
jobsearch/tracking/application_tracker.py
```

### 5. Human-in-the-loop dashboard

Keep the Streamlit dashboard if the optional UI dependency is installed.

Primary entry points:

```bash
python -m jobsearch.pipeline.run_dashboard
job-search-dashboard
```

The dashboard should remain the control center for review/tracker decisions and selected CV generation.

## Must keep: Selected-job CV generation

### 6. Selected-job CV pipeline

Keep CV generation only for selected jobs, especially rows marked with `prepare_cv`.

Primary entry points:

```bash
python -m jobsearch.pipeline.run_selected_cv_pipeline
job-search-selected-cv
```

Important outputs:

```text
outputs/selected/<job_id>.cv_strategy.yaml
outputs/selected/<job_id>.cv_draft.yaml
outputs/selected/<job_id>.cv_draft.txt
outputs/selected/<job_id>.mpya_cv.html
outputs/selected/selected_cv_pipeline_report.csv
outputs/selected/selected_cv_pipeline_report.html
```

Implementation currently lives mainly in:

```text
job_search_mvp/run_selected_cv_pipeline.py
job_search_mvp/strategy_generator.py
job_search_mvp/cv_draft_generator.py
job_search_mvp/mpya_cv_renderer.py
jobsearch/cv/
```

## Must keep: Data model and safety posture

### 7. Local YAML data model

Keep local YAML configuration/profile/template files as the main project data source.

Important files:

```text
data/employee_profile.yaml
data/experience_database.yaml
data/career_preferences.yaml
data/consultancy_static_profile.yaml
data/cv_generation_policy.yaml
data/job_sources.yaml
data/*.template.yaml
```

### 8. Deterministic/default behavior

Keep the project usable without paid LLM calls. LLM/hybrid standardization may remain optional, but deterministic processing should remain the safe default.

Keep multilingual deterministic parsing behavior:

- Swedish/English section-header normalization for job text parsing.
- Language-aware requirement extraction for `must_have` and `nice_to_have`.
- Swedish-friendly aliases in `data/tool_aliases.yaml` for matching robustness.

### 9. LLM cost-control constraint

Keep the current budget-model guardrail for OpenAI standardization unless intentionally redesigned.

The tests indicate this is important behavior.

Also keep hybrid confidence-gating behavior:

- In `hybrid` mode, skip LLM when deterministic confidence is high.
- Attempt LLM enrichment only when deterministic confidence is low.
- Preserve deterministic fallback when LLM cannot be used.

### 10. Local/human-in-the-loop safety posture

Keep the system as a local decision-support and CV-preparation tool. It should not automatically submit job applications, click apply buttons, or publish CVs without human approval.

## Must keep: Test suite

Keep and grow tests around the current workflow.

Important current tests:

```text
tests/test_jobsearch_package.py
tests/test_source_adapter.py
tests/test_application_tracker.py
tests/test_matcher.py
tests/test_strategy_generator.py
tests/test_cv_draft_generator.py
tests/test_llm_model_budget.py
```

## Nice to keep

- HTML review outputs for quick human inspection.
- Resume/retry-friendly local files.
- CLI wrappers from `pyproject.toml`.
- Browser collection for Verama/Ework, if kept isolated and optional.
- Compatibility wrappers in `jobsearch/` while the package structure is stabilizing.
- A future workspace cleanup command, if explicitly requested later, to clear generated intake/batch/selected artifacts before a new search cycle.

## Must not break

- Batch processing of a folder of job files.
- Batch processing of a single job as a batch of 1.
- Review queue fields used by the tracker and selected CV pipeline.
- Dashboard-based human review and selected CV trigger behavior.
- Existing tracker decisions during regeneration/sync.
- Ability to run tests with `python -m pytest`.
- Local-only/human-in-the-loop safety posture.
