# Architecture Map

This document maps the intended workflow to commands, modules, inputs, and outputs. It is a refactor aid, not a complete implementation reference.

## Canonical data flow

```text
Configured/manual sources
-> sources/copied_jobs/ or configured source adapters
-> sources/collected_jobs/*.txt
-> outputs/batch/*.job_standardized.yaml
-> outputs/batch/*.match_result.yaml
-> outputs/batch/review_queue.csv/html
-> dashboard / tracker decision gate
-> outputs/selected/*.cv_strategy.yaml
-> outputs/selected/*.cv_draft.yaml/txt
-> outputs/selected/*.mpya_cv.html
-> outputs/application_tracker.csv/html
```

## Workflow-to-code map

| Canonical step | Preferred command | Main implementation | Main inputs | Main outputs | Status |
|---|---|---|---|---|---|
| Source collection to review | `python -m jobsearch.pipeline.run_sources_to_review` | `job_search_mvp/run_sources_to_review.py`, `job_search_mvp/source_adapter.py` | `data/job_sources.yaml`, `sources/copied_jobs/` | `sources/collected_jobs/`, `outputs/batch/review_queue.*`, tracker sync | Current |
| Batch job processing | `python -m jobsearch.pipeline.run_job_batch` | `job_search_mvp/run_job_batch.py` | Folder of `.txt` jobs, `data/*.yaml` | standardized job YAML, match result YAML, review queue | Current |
| Dashboard review | `python -m jobsearch.pipeline.run_dashboard` | `job_search_mvp/streamlit_dashboard.py` | review queue, tracker, batch outputs | updated tracker/statuses, selected CV trigger | Current/optional |
| Selected CV generation | `python -m jobsearch.pipeline.run_selected_cv_pipeline` | `job_search_mvp/run_selected_cv_pipeline.py`, strategy/draft/render modules | tracked review queue, batch outputs, `data/*.yaml` | CV strategy, draft, rendered HTML, selected pipeline report | Current |
| Tracker operations | `python -m jobsearch.tracking.application_tracker ...` | `job_search_mvp/application_tracker.py` | review queue or CV report | `outputs/application_tracker.csv/html` | Current |
| Browser collection | `python -m jobsearch.sources.verama_playwright ...` | `job_search_mvp/verama_playwright_adapter.py` | Verama/Ework page/session | collected job `.txt` files | Optional |
| Single-job commands | varies | matcher/strategy/draft helpers | one job | one-off artifacts | Legacy/developer unless used internally |

Notes for batch standardization path:

- `job_search_mvp/matcher.py` now performs multilingual deterministic section/header normalization (Swedish/English) and language-aware requirement extraction.
- `job_search_mvp/standardization/llm_standardizer.py` now computes deterministic confidence and gates hybrid LLM calls (LLM on low-confidence only; deterministic output retained on high-confidence).

## Package map

### `job_search_mvp/`

This is currently the tested implementation package.

| Module | Role |
|---|---|
| `run_sources_to_review.py` | Orchestrates source collection, batch processing, and optional tracker sync. |
| `source_adapter.py` | Reads configured sources and deduplicates collected jobs. |
| `run_job_batch.py` | Core batch standardization/matching/review queue pipeline. |
| `matcher.py` | Matching logic. |
| `standardization/` | Deterministic/LLM/hybrid standardization logic, including confidence-gated hybrid fallback behavior. |
| `application_tracker.py` | Persistent review/application tracker. |
| `run_selected_cv_pipeline.py` | CV generation for jobs selected by review status. |
| `strategy_generator.py` | Generates CV strategy YAML. |
| `cv_draft_generator.py` | Generates CV draft YAML/text. |
| `mpya_cv_renderer.py` | Renders MPYA-style CV HTML. |
| `streamlit_dashboard.py` | Streamlit review/control dashboard. |
| `run_dashboard.py` | CLI wrapper for launching dashboard. |
| `verama_playwright_adapter.py` | Optional browser-based Verama/Ework collection. |
| `paths.py` | Shared path helpers. |

### `jobsearch/`

This appears to be the intended public package layout. Many files wrap or re-export implementation from `job_search_mvp/`.

| Subpackage | Role |
|---|---|
| `jobsearch/pipeline/` | Preferred `python -m jobsearch.pipeline...` entry points. |
| `jobsearch/sources/` | Source-related public wrappers/helpers. |
| `jobsearch/matching/` | Matching/standardization public wrappers. |
| `jobsearch/cv/` | CV generation public wrappers. |
| `jobsearch/tracking/` | Tracker public wrapper. |
| `jobsearch/standardization/` | LLM standardization wrapper. |

Refactor caution: do not let `jobsearch/` and `job_search_mvp/` become two diverging implementations. Decide later whether `jobsearch/` remains wrappers or becomes the main implementation package.

## Data/configuration layer

The project is largely configured through local YAML files in `data/`.

| File | Purpose |
|---|---|
| `employee_profile.yaml` | Maintained user profile data. |
| `experience_database.yaml` | Experience/projects/skills database used for matching and CV generation. |
| `career_preferences.yaml` | Target role preferences. |
| `consultancy_static_profile.yaml` | Consultancy/company profile data. |
| `cv_generation_policy.yaml` | Rules for CV generation. |
| `job_sources.yaml` | Source collection configuration. |
| `*.template.yaml` | Output/template structure for standardized jobs, match results, CV strategy, and CV draft. |
| `tool_aliases.yaml` | Alias mapping for tools/skills. |

`tool_aliases.yaml` now includes Swedish-supporting terms to improve matching and requirement interpretation for Swedish job postings.

## Source/job intake layer

Important folders:

```text
sources/copied_jobs/
sources/collected_jobs/
```

Interpretation:

- `copied_jobs/` is manual/local source input or cache.
- `collected_jobs/` is the canonical intake folder for batch processing.
- `job_manifest.csv` records collected/deduplicated jobs.

## Output layer

Important folders/files:

```text
outputs/batch/
outputs/selected/
outputs/application_tracker.csv
outputs/application_tracker.html
```

Interpretation:

- `outputs/batch/` contains standardization/matching/review artifacts for the active search cycle.
- `outputs/selected/` contains CV artifacts generated after human selection.
- `outputs/application_tracker.csv` is persistent state and should be preserved across runs.

## Output lifecycle map

| Path | Type | Safe to regenerate? | Notes |
|---|---|---:|---|
| `data/*.yaml` | Maintained config/source truth | No | Edit deliberately. |
| `sources/copied_jobs/` | Manual input/cache | Maybe | Depends whether files are current input or historical examples. |
| `sources/collected_jobs/` | Generated intake/cache | Yes, with user awareness | May be cleared by a future cleanup feature. |
| `outputs/batch/` | Generated active-cycle output | Yes | Can be regenerated from collected jobs and data. |
| `outputs/selected/` | Generated selected-job output | Yes, with user awareness | May contain reviewed CV artifacts; avoid deleting without intent. |
| `outputs/application_tracker.csv` | Persistent user history | No | Preserve unless explicitly reset. |
| `browser_profiles/` | Local session state | No/ignore | Do not commit; may contain session data. |
| `tests/fixtures/` | Test fixtures | No | Should be small and stable. |
| `examples/` | Example data | No | Should be clearly labeled and non-sensitive. |

## Optional browser layer

Optional browser collection uses:

```text
job_search_mvp/verama_playwright_adapter.py
jobsearch/sources/verama_playwright.py
browser_profiles/verama/
```

Caution:

- Keep browser state out of normal source control if possible.
- Do not store credentials in code.
- Do not make browser collection submit applications automatically.

## Test layer

Tests currently live in `tests/`.

| Test file | Area covered |
|---|---|
| `test_jobsearch_package.py` | Public wrapper/package behavior. |
| `test_source_adapter.py` | Source collection/dedup behavior. |
| `test_application_tracker.py` | Tracker/status behavior. |
| `test_matcher.py` | Matching behavior. |
| `test_strategy_generator.py` | CV strategy generation. |
| `test_cv_draft_generator.py` | CV draft generation. |
| `test_llm_model_budget.py` | LLM budget-model guardrail. |

## Console scripts

Defined in `pyproject.toml`:

```text
job-search-match
job-search-batch
job-search-sources
job-search-tracker
job-search-selected-cv
job-search-verama
job-search-dashboard
job-search-standardizer
```

Refactor caution: update docs and tests if entry points change.

## Current architecture tension

The biggest architecture issue is not algorithmic complexity. It is duplicated/historical structure and unclear file lifecycle:

1. User-facing docs still emphasize older individual-job flows.
2. `job_search_mvp/` and `jobsearch/` coexist.
3. `prototype/` duplicates much of the active implementation.
4. Generated outputs, source-cache files, persistent history, and local state can appear together in the repository snapshot.
5. Weekly usage is not yet reflected strongly enough in folder/output conventions.

The near-term architecture goal is to clarify the active path and data lifecycle before moving/deleting large amounts of code.
