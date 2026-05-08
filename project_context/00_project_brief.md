# Project Brief

## What this project does

This project is a local job-search automation and CV-preparation prototype. It collects job ads from configured/manual sources, deduplicates them into a local intake folder, standardizes and matches them against maintained profile/experience data, produces a review queue, tracks human decisions, and generates tailored CV artifacts only for selected jobs.

The project is intentionally local and human-in-the-loop. It does not apply to jobs automatically, submit forms, or publish generated CVs.

## Current intended behavior

The current intended workflow is batch-based and should be operated as a recurring weekly job-search cycle:

1. Collect or copy the current search cycle's job ads into local source folders.
2. Normalize/deduplicate them into `sources/collected_jobs/`.
3. Run batch matching over a folder of job `.txt` files.
4. Review the generated queue in the dashboard and update statuses.
5. Generate CV strategy/draft/rendered CV artifacts only for jobs explicitly selected for CV preparation.
6. Keep persistent application decisions in `outputs/application_tracker.csv`.

A single job should be processed as a batch of 1. The old individual-job workflow is legacy unless it is needed internally by the batch workflow or by tests.

## Two-stage product boundary

The system has two connected but separate workflows:

```text
Stage 1: Weekly batch job search
Job sources -> position searcher -> raw job store -> standardizer/translator -> structured job data -> matching/ranking -> dashboard review queue

Stage 2: Selected-job CV preparation
Dashboard-selected job -> CV tailoring -> human approval -> CV formatting/publishing artifact -> recruiter/talent-advisor view
```

CV generation is downstream of human review. The dashboard is the normal decision gate between Stage 1 and Stage 2.

## Weekly workspace model

The normal operating model is to work with the positions of the current search cycle. Previous positions may remain on disk as cache/history if the user wants to avoid reprocessing, but they should not be treated as active review work unless explicitly reused.

A future feature may provide a workspace cleanup command that removes or archives previous run artifacts before starting a new search. That feature is out of scope for the current refactor; for now, documentation and code should avoid introducing new cleanup behavior unless explicitly requested.

## Canonical command shape

Prefer the `jobsearch` package command shape:

```bash
python -m jobsearch.pipeline.run_sources_to_review
python -m jobsearch.pipeline.run_job_batch
python -m jobsearch.pipeline.run_selected_cv_pipeline
python -m jobsearch.pipeline.run_dashboard
```

The `job_search_mvp` package currently contains the tested implementation. The `jobsearch` package mostly acts as the preferred public/wrapper layout. Keep this distinction in mind during refactors.

Console scripts in `pyproject.toml`, such as `job-search-batch`, `job-search-sources`, `job-search-selected-cv`, and `job-search-dashboard`, are also valid entry points.

## Current project stage

The project is in refactor/stabilization mode. The priority is to make the canonical workflow clear, isolate or remove legacy paths, reduce output/file chaos, and preserve the batch pipeline.

Do not add new product features during this refactor unless explicitly requested.

## Main source of truth files

- `project_context/00_project_brief.md`: project purpose and current direction.
- `project_context/01_current_workflow.md`: canonical workflow and expected inputs/outputs.
- `project_context/02_features_to_keep.md`: current capabilities that should be preserved.
- `project_context/03_features_to_remove.md`: legacy or suspicious areas to remove/deprecate after investigation.
- `project_context/04_architecture_map.md`: high-level code, command, and data-flow map.
- `project_context/05_refactor_plan.md`: near-term cleanup plan.
- `project_context/06_ai_agent_instructions.md`: instructions for future AI coding agents.
- `project_context/07_decision_log.md`: decisions and rationale.

## Important current directories

- `job_search_mvp/`: tested implementation package.
- `jobsearch/`: planned/preferred public package layout and command wrappers.
- `data/`: manually maintained YAML data, profile, preferences, templates, policies, and source config.
- `sources/copied_jobs/`: manually copied job ads.
- `sources/collected_jobs/`: collected/deduplicated job ads and manifest.
- `outputs/batch/`: batch standardization, matching, and review queue outputs for the active search cycle.
- `outputs/selected/`: selected-job CV pipeline outputs.
- `outputs/application_tracker.csv`: persistent tracker of review/application decisions.
- `tests/`: pytest coverage for core behavior.
- `prototype/`: older compatibility/example area; treat as legacy unless code/tests prove otherwise.

## Data lifecycle categories

During refactor, classify files by lifecycle before moving or deleting them:

| Category | Examples | Refactor treatment |
|---|---|---|
| Maintained source/config | `data/*.yaml`, code, tests, templates | Preserve and test. |
| Active search-cycle artifacts | `sources/collected_jobs/`, `outputs/batch/`, `outputs/selected/` | Generated/cache-like; do not treat as source of truth. |
| Persistent user history | `outputs/application_tracker.csv` | Preserve unless the user explicitly resets it. |
| Examples/fixtures | `examples/`, `tests/fixtures/` | Keep only if clearly labeled. |
| Local/session state | `browser_profiles/`, `__pycache__/`, egg-info | Do not commit; ignore or remove from active tree. |

## Non-goals for the current refactor

- Do not add new features before clarifying the existing workflow.
- Do not implement automated workspace cleanup yet; document it as a future capability only.
- Do not preserve the old individual-case workflow as a primary user path.
- Do not treat README order as authoritative until the README has been refactored.
- Do not make the system apply to jobs automatically.
- Do not store credentials in code or committed files.
- Do not remove compatibility wrappers without first checking tests, entry points, and imports.

## Definition of done for the near-term cleanup

- README presents the source-to-review batch workflow first.
- Batch processing is documented as the canonical path, including batch-of-1 usage.
- Dashboard review is documented as the human decision gate.
- Selected CV generation is documented as downstream of dashboard/user selection.
- Individual-job commands are either removed from primary docs, moved to a legacy section, or explained as developer/debug commands.
- Generated output, persistent tracker state, examples/fixtures, and local session state are clearly distinguished.
- Legacy areas are identified before deletion.
- A future AI agent can understand the intended behavior by reading `project_context/` before modifying code.
