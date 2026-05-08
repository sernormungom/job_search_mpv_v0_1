# Legacy / Deprecation Candidates

Archival note: this file captures historical cleanup candidates and provenance. It is not an active to-do list.

This file lists likely legacy or confusing parts of the project. Do not delete anything solely because it appears here. First verify imports, tests, entry points, and actual usage.

## Guiding rule

The batch workflow is canonical. Anything that exists only to support the old individual-job workflow is a candidate for removal, deprecation, or movement into a developer/debug section.

The dashboard is the normal human decision gate. Selected CV generation is downstream of dashboard/user selection.

## Cleanup policy

Before removing or moving data files, classify them as one of:

```text
source/config
example
fixture
generated active-cycle artifact
persistent tracker state
local/session state
unknown
```

Do not delete `unknown` files. Do not delete `outputs/application_tracker.csv` unless the user explicitly requests a reset.

A future cleanup feature may clear generated workspace/cache artifacts before a new search cycle, but that feature is out of scope for the current refactor.

## Likely obsolete or secondary

### 1. README-first individual-job workflow

The README currently presents individual-job matching/CV flow too prominently. This is likely the biggest human-facing source of confusion.

Recommended action:

- Move single-job commands out of the main quickstart.
- Add a short statement that a single job should be processed as a batch of 1.
- If single-job commands remain useful for debugging, place them under a `Developer/debug commands` or `Legacy commands` section.

### 2. Old single-job primary flow

The old individual-case flow is legacy unless it is required internally by batch processing.

Candidate commands/files to review before changing:

```text
job_search_mvp/matcher.py
job_search_mvp/strategy_generator.py
job_search_mvp/cv_draft_generator.py
job_search_mvp/mpya_cv_renderer.py
```

These modules may still be valid helpers used by batch/selected-CV workflows, so do not delete them blindly. The target is not to remove all single-item functions; the target is to remove the single-item user workflow as the main product path.

### 3. `prototype/` folder

The `prototype/` folder duplicated many implementation files and has now been removed from the active tree:

```text
prototype/application_tracker.py
prototype/cv_draft_generator.py
prototype/cv_renderer.py
prototype/matcher.py
prototype/mpya_cv_renderer.py
prototype/run_job_batch.py
prototype/run_selected_cv_pipeline.py
prototype/run_sources_to_review.py
prototype/source_adapter.py
prototype/strategy_generator.py
prototype/verama_playwright_adapter.py
```

Recommended action:

1. Keep historical references only in archival docs like this one.
2. Treat any remaining mentions as provenance, not active workflow guidance.
3. Use `tests/fixtures/` for sample inputs that need to stay alive.

### 4. Duplicated package surfaces

The repository currently has both:

```text
job_search_mvp/
jobsearch/
```

Current interpretation:

- `job_search_mvp/` contains the tested implementation.
- `jobsearch/` contains the preferred public package/wrapper shape.

This may be acceptable temporarily, but it is confusing.

Recommended action:

- Keep wrappers while stabilizing.
- Later choose whether to migrate implementation into `jobsearch/` or keep `job_search_mvp/` as implementation package.
- Do not maintain two independent implementations of the same logic.

### 5. Generated outputs and local state

The ZIP may contain generated or machine-local data such as:

```text
outputs/application_tracker.csv
outputs/application_tracker.html
outputs/batch/*
outputs/selected/*
sources/collected_jobs/*.txt
sources/copied_jobs/*.txt
browser_profiles/verama/*
__pycache__/
*.egg-info/
```

Recommended action:

- Decide what sample data should remain as fixtures/examples.
- Move fixtures into `tests/fixtures/` or examples into `examples/` if they are needed.
- Ignore/remove machine-generated state from the active source tree where appropriate.
- Preserve `outputs/application_tracker.csv` if it represents real user history.
- Be especially careful with browser profile files because they can contain local session state.

### 6. Legacy CV renderer names

There are multiple CV rendering-related modules:

```text
job_search_mvp/cv_renderer.py
job_search_mvp/mpya_cv_renderer.py
prototype/cv_renderer.py
prototype/mpya_cv_renderer.py
```

Recommended action:

- Identify which renderer is used by the selected-CV pipeline.
- Keep the active renderer.
- Deprecate/remove duplicate or unused renderers.

### 7. Direct `job_search_mvp` command examples in user docs

For user-facing docs, prefer the `jobsearch` command shape or installed console scripts.

Recommended action:

- Keep `job_search_mvp` implementation imports where needed.
- Avoid making users choose between multiple command styles.

## Removal safety checklist

Before deleting, moving, or renaming a file, check:

```bash
grep -R "file_or_symbol_name" .
python -m pytest
```

Also inspect:

```text
pyproject.toml
README.md
tests/
jobsearch/ wrappers
job_search_mvp/ imports
```

## Suggested classifications

Initial best-effort classification:

| Area | Initial classification | Notes |
|---|---|---|
| `job_search_mvp/run_sources_to_review.py` | current | Orchestrates source collection and batch review. |
| `job_search_mvp/run_job_batch.py` | current | Core batch processor. |
| `job_search_mvp/run_selected_cv_pipeline.py` | current | Generates CV outputs only for selected jobs. |
| `job_search_mvp/application_tracker.py` | current | Persistent decision tracker. |
| `job_search_mvp/streamlit_dashboard.py` | current/optional | Dashboard; optional UI. |
| `job_search_mvp/verama_playwright_adapter.py` | optional | Browser source collection. Keep isolated. |
| `jobsearch/` wrappers | helper/current | Preferred command shape, but mostly wrappers. |
| `prototype/` | removed | Historical reference only; no longer present in the active tree. |
| `outputs/batch/` | generated | Active-cycle artifacts, not source truth. |
| `outputs/selected/` | generated | Selected-job artifacts, not source truth. |
| `outputs/application_tracker.csv` | persistent user history | Preserve unless explicitly reset. |
| `sources/collected_jobs/` | generated/cache | Deduplicated intake/cache. |
| `sources/copied_jobs/` | manual input/cache | May contain current or historical job text. |
| `browser_profiles/` | local/session state | Do not commit; may contain session information. |
