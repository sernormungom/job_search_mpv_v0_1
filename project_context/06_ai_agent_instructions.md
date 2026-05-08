# Instructions for AI Coding Agents

## Read these first

Before changing code, read:

1. `project_context/00_project_brief.md`
2. `project_context/01_current_workflow.md`
3. `project_context/02_features_to_keep.md`
4. `project_context/03_features_to_remove.md`
5. `project_context/04_architecture_map.md`
6. `project_context/05_refactor_plan.md`
7. `project_context/06_ai_agent_instructions.md`
8. `project_context/07_decision_log.md`
9. `README.md`
10. `pyproject.toml`
11. Relevant tests under `tests/`

If the README conflicts with `project_context/`, treat `project_context/` as the current source of truth during refactor. The README may still contain older workflow ordering.

## Current priority

Refactor and simplify. Do not add new features unless explicitly requested.

The main product direction is:

```text
source collection -> batch processing -> dashboard review/tracker -> selected CV generation
```

## Main rules

The batch workflow is canonical. A single job should be processed as a batch of 1.

The dashboard is the normal human decision gate. Selected CV generation is downstream of a human decision, normally a job marked `prepare_cv`.

Do not preserve the old individual-case workflow as a primary user path unless the project owner explicitly asks for it.

## Preferred command surface

Prefer the `jobsearch` package command shape for user-facing documentation and examples:

```bash
python -m jobsearch.pipeline.run_sources_to_review
python -m jobsearch.pipeline.run_job_batch
python -m jobsearch.pipeline.run_selected_cv_pipeline
python -m jobsearch.pipeline.run_dashboard
python -m jobsearch.sources.verama_playwright
```

The `job_search_mvp` package currently contains the tested implementation. The `jobsearch` package is mostly wrappers/public layout. Be careful not to break this compatibility layer without updating tests and entry points.

For job standardization changes:

- Keep deterministic multilingual parsing as first-line behavior.
- Treat hybrid LLM standardization as a low-confidence rescue path, not a default always-on path.
- Preserve confidence-gating behavior when modifying `job_search_mvp/standardization/llm_standardizer.py`.

## Before modifying code

First classify affected files as one of:

- `current`: part of the canonical batch/source/review/selected-CV workflow.
- `helper`: used by current workflow but not a direct entry point.
- `legacy`: old prototype or individual-case behavior not needed by the canonical workflow.
- `generated`: generated active-cycle output or cache, not source truth.
- `persistent_state`: user history/state that should be preserved unless explicitly reset.
- `local_state`: browser/session/cache/build state that should not be committed.
- `unknown`: unclear; needs investigation before modification or deletion.

Do not delete files classified as `unknown`.

## Before deleting or moving code

Check all of the following:

```bash
grep -R "module_or_function_name" .
python -m pytest
```

Also inspect:

- `pyproject.toml` console scripts
- `jobsearch/` wrappers
- `tests/`
- README references
- imports from `job_search_mvp/`
- files under `prototype/` that may still be used as examples or fixtures

## Before changing output paths

Do not introduce new output locations without updating:

1. `project_context/01_current_workflow.md`
2. `project_context/04_architecture_map.md`
3. Relevant README sections
4. Tests or fixtures that assert paths

Always identify whether the path stores source/config, generated active-cycle artifacts, persistent tracker state, examples/fixtures, or local/session state.

## Workspace cleanup guidance

A workspace cleanup feature is allowed as a future idea but is out of scope for the current refactor unless the project owner explicitly requests it.

During this refactor:

- Do not add a cleanup command just because outputs are confusing.
- Do document which files a future cleanup command could safely remove.
- Preserve `outputs/application_tracker.csv` unless an explicit reset is requested.
- Treat old collected jobs as cache/history, not necessarily as errors.

## Refactor behavior

Prefer small, reviewable changes.

For every proposed change, explain:

1. What changed.
2. Why it changed.
3. Whether it affects the canonical workflow.
4. Whether it removes, deprecates, or preserves legacy behavior.
5. How to test it.

## Documentation rules

README should become user-facing and current-state focused. It should present the canonical source/batch/dashboard workflow first.

`project_context/` is maintainer-facing and AI-facing. Update it when project direction changes.

Do not let README become the only place where architectural or refactor intent is stored.

## Testing expectations

At minimum, preserve or add smoke coverage for:

- Processing a folder of job `.txt` files with `run_job_batch`.
- Processing a batch containing one job.
- Producing `review_queue.csv` and `review_queue.html`.
- Preserving tracker decisions across sync.
- Generating CV artifacts only for selected jobs.
- Keeping selected CV generation downstream of a review status such as `prepare_cv`.

Before claiming the refactor is safe, run:

```bash
python -m pytest
```

If tests fail, report the failing tests and do not hide the failure.

## Do not

- Do not add new features during cleanup unless explicitly requested.
- Do not implement workspace cleanup during this refactor unless explicitly requested.
- Do not treat old README workflow order as authoritative.
- Do not make single-job processing the primary documented workflow.
- Do not remove wrappers or console scripts without checking callers and tests.
- Do not commit secrets, browser session data, or credentials.
- Do not make the tool apply to jobs automatically.
- Do not convert this into a heavy enterprise requirements system.

## Good first refactor tasks

1. Reorder README so source collection, batch processing, and dashboard review are first.
2. Move individual-job commands into a legacy/developer section.
3. Add a short "batch of 1" example.
4. Add or confirm a smoke test for one-job batch processing.
5. Clarify generated output vs persistent tracker state.
6. Classify `prototype/` and duplicate package areas before deleting anything.
