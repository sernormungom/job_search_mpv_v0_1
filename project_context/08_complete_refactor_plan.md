# Complete Refactor Plan

## Purpose

This plan turns the current working MVP into a clearer, leaner, easier-to-run project without changing the core workflow.

The refactor should preserve the canonical path:

```text
collect jobs -> batch process -> dashboard review/tracker -> selected CV generation -> rendered CV artifacts
```

The goal is not to rewrite the project. The goal is to make the current system feel like one coherent product instead of a set of useful scripts that grew organically.

## Current Diagnosis

The project already has the right major pieces:

- source collection and deduplication
- batch standardization and matching
- review queue and persistent tracker
- dashboard as human decision gate
- selected-job CV strategy, draft, LLM text orchestration, and rendering
- optional browser collection
- optional LLM-assisted standardization and CV text generation

The main friction is structural:

- `job_search_mvp/` is the implementation package, while `jobsearch/` is the preferred public wrapper package.
- Some command modules still contain orchestration, business logic, IO, and report writing together.
- Generated outputs, examples, persistent state, and source/config files are easy to confuse.
- Historical/legacy paths such as `prototype/` make the active workflow look less obvious.
- LLM code now exists in multiple parts of the workflow and should be gathered behind a single service boundary.

## Target Architecture

The preferred long-term shape is to make `jobsearch/` the canonical public package and organize implementation around workflow, service, IO, rendering, and LLM boundaries.

```text
jobsearch/
  workflows/
    sources_to_review.py
    batch_review.py
    selected_cv.py
    tracker_sync.py
  services/
    source_collection.py
    standardization.py
    matching.py
    tracking.py
    cv_strategy.py
    cv_text.py
    cv_validation.py
  llm/
    client.py
    routing.py
    standardization_steps.py
    cv_steps.py
    validation.py
  io/
    yaml_io.py
    csv_io.py
    artifact_paths.py
    reports.py
  renderers/
    mpya_html.py
    local_html.py
  models/
    standardized_job.py
    match_result.py
    review_queue.py
    tracker.py
    cv_strategy.py
    cv_draft.py
```

During migration, `job_search_mvp/` should remain as a compatibility layer or temporary implementation home. Do not move everything at once.

## Design Rules

1. Keep the batch workflow canonical.
2. Treat a single job as a batch of one.
3. Keep dashboard/tracker decisions as the human approval gate.
4. Keep generated output inspectable as local files.
5. Keep deterministic fallback for every LLM-assisted step.
6. Keep LLM routing and budget policy centralized.
7. Move behavior only when tests protect the current behavior.
8. Avoid introducing a database until the file workflow becomes a real bottleneck.
9. Preserve `outputs/application_tracker.csv` unless the user explicitly resets it.

## Phase 0: Planning Baseline

Goal: create the shared map before moving code.

Tasks:

- Keep this plan as the refactor source of truth.
- Keep `04_architecture_map.md` as the current-state reference.
- Keep `05_refactor_plan.md` as the stabilization checklist.
- Create `file_classification.md` before cleanup or deletion.

Done means:

- A future agent can understand current state, target state, and safe first steps without reading the whole repository.

Recommended GPT/thinking power:

- `gpt-5.5`, reasoning `high` for architecture planning.
- `gpt-5.4`, reasoning `medium` for turning the plan into issue/checklist text.

## Phase 1: Behavior Freeze and Smoke Tests

Goal: protect the canonical workflow before structural edits.

Tasks:

- Add or confirm smoke tests for batch-of-one.
- Add or confirm smoke tests for batch-many.
- Add or confirm selected CV generation only processes `prepare_cv` rows.
- Add or confirm tracker sync preserves human decisions.
- Add or confirm LLM routing falls back deterministically when API/network is unavailable.

Suggested fixtures:

```text
tests/fixtures/jobs/batch_one/
tests/fixtures/jobs/batch_many/
tests/fixtures/review_queues/
tests/fixtures/cv/
```

Done means:

- Refactors can be checked with a small test suite that proves the main workflow still works.

Recommended GPT/thinking power:

- `gpt-5.4-mini`, reasoning `medium` for test scaffolding.
- `gpt-5.4`, reasoning `medium` if tests expose subtle behavior differences.

## Phase 2: File Lifecycle and Repository Hygiene

Goal: make it obvious which files are source, generated output, persistent state, examples, fixtures, or local state.

Tasks:

- Create `project_context/file_classification.md`.
- Classify top-level folders and important generated files.
- Decide which committed `outputs/` files are working state versus examples.
- Move stable samples into `examples/` or `tests/fixtures/`.
- Update `.gitignore` recommendations for generated outputs, browser profiles, caches, and local secrets.

Done means:

- New clones do not look like active local state is source code.
- The user can still preserve personal tracker history deliberately.

Recommended GPT/thinking power:

- `gpt-5.4`, reasoning `medium` for classification.
- `gpt-5.4-mini`, reasoning `low` for mechanical documentation updates.

## Phase 3: Command Surface Cleanup

Goal: make one command path feel official.

Preferred public shape:

```text
python -m jobsearch.pipeline.run_sources_to_review
python -m jobsearch.pipeline.run_job_batch
python -m jobsearch.pipeline.run_dashboard
python -m jobsearch.pipeline.run_selected_cv_pipeline
python -m jobsearch.tracking.application_tracker
```

Tasks:

- Keep `python -m jobsearch...` as the documented command style.
- Mark individual matcher/strategy/draft commands as developer/debug utilities.
- Make README and `01_current_workflow.md` match the same command story.
- Ensure console scripts in `pyproject.toml` still point to maintained entrypoints.

Done means:

- A user sees one recommended workflow and does not need to choose between competing command families.

Recommended GPT/thinking power:

- `gpt-5.4-mini`, reasoning `medium` for docs.
- `gpt-5.4`, reasoning `medium` for command wiring changes.

## Phase 4: Extract Shared Infrastructure

Goal: remove repeated IO/report/path code from workflow modules.

Candidate modules:

```text
jobsearch/io/yaml_io.py
jobsearch/io/csv_io.py
jobsearch/io/artifact_paths.py
jobsearch/io/reports.py
```

Tasks:

- Centralize YAML read/write.
- Centralize CSV read/write with UTF-8 BOM handling where needed.
- Centralize artifact path construction for batch and selected outputs.
- Centralize report CSV/HTML writing where practical.

Done means:

- Workflow modules are shorter and less repetitive.
- File encoding/path behavior is consistent.

Recommended GPT/thinking power:

- `gpt-5.4`, reasoning `medium` for implementation.
- `gpt-5.4-mini`, reasoning `medium` for narrow helper tests.

## Phase 5: Service Layer Extraction

Goal: move business logic out of CLI modules.

Target services:

- source collection service
- standardization service
- matching service
- tracker service
- CV strategy service
- CV text generation service
- CV render service

Tasks:

- Keep CLI modules thin: parse args, call service, print outcome.
- Keep services callable from tests and dashboard.
- Avoid changing artifact formats during this phase.

Done means:

- The dashboard, CLI, and tests can use the same service functions without subprocess workarounds.

Recommended GPT/thinking power:

- `gpt-5.4`, reasoning `medium` for most service extraction.
- `gpt-5.5`, reasoning `high` for cross-workflow extraction decisions.

## Phase 6: LLM Boundary Refactor

Goal: all model calls, routing, retries, fallback, and budget policy live behind one boundary.

Target modules:

```text
jobsearch/llm/client.py
jobsearch/llm/routing.py
jobsearch/llm/standardization_steps.py
jobsearch/llm/cv_steps.py
jobsearch/llm/validation.py
```

Tasks:

- Move OpenAI HTTP calling into one client module.
- Keep model routing policy in `cv_generation_policy.yaml` or a dedicated LLM policy file.
- Keep step artifacts inspectable.
- Enforce maximum calls per job.
- Enforce compact retry behavior.
- Preserve deterministic fallback for no API key, network failure, invalid output, or budget exhaustion.

Done means:

- No workflow module needs to know OpenAI request details.
- Cost controls are visible and testable.

Recommended GPT/thinking power:

- `gpt-5.5`, reasoning `high` for design/review.
- `gpt-5.4`, reasoning `medium` for implementation once the interface is settled.

## Phase 7: CV Pipeline Refactor

Goal: make selected CV generation a clear staged pipeline.

Target stages:

```text
strategy -> LLM/persona/text plan -> validation -> draft -> render -> report -> tracker ingest
```

Tasks:

- Keep `cv_strategy.yaml` as the selection and evidence contract.
- Keep `cv_llm_steps.yaml` as the LLM reasoning/text artifact.
- Keep `cv_draft.yaml` as the final structured text artifact.
- Add title/headline adaptation as an explicit stage.
- Add stronger size validation tied to MPYA template constraints.
- Add one compact revision pass only when size validation fails.

Done means:

- CV generation is understandable from artifacts alone.
- LLM improves text but cannot silently invent unsupported claims.

Recommended GPT/thinking power:

- `gpt-5.5`, reasoning `high` for CV stage design and validation rules.
- `gpt-5.4`, reasoning `medium` for implementation.
- `gpt-5.4-mini`, reasoning `low` for compact retry text generation.

## Phase 8: Package Consolidation

Goal: resolve the `job_search_mvp/` versus `jobsearch/` split.

Options:

- Option A: keep `job_search_mvp/` as implementation and `jobsearch/` as public wrappers.
- Option B: migrate implementation into `jobsearch/` and leave compatibility wrappers in `job_search_mvp/`.

Recommendation:

- Choose Option B only after Phases 1-7 are stable.
- If Option B is chosen, move one subsystem at a time.

Done means:

- There is one clear implementation home and one documented compatibility story.

Recommended GPT/thinking power:

- `gpt-5.5`, reasoning `high` for migration strategy.
- `gpt-5.4`, reasoning `medium` for mechanical moves.
- `gpt-5.5`, reasoning `high` for final review.

## Phase 9: Prototype and Legacy Cleanup

Goal: remove historical distractions from the active workflow.

Tasks:

- Check all references to `prototype/`.
- Move useful examples to `examples/` or `tests/fixtures/`.
- Archive or delete unused historical implementation.
- Update docs to explain any remaining legacy helpers.

Done means:

- The project no longer appears to contain multiple active implementations.

Recommended GPT/thinking power:

- `gpt-5.4`, reasoning `medium` for reference analysis.
- `gpt-5.4-mini`, reasoning `low` for docs and mechanical cleanup.

## Phase 10: Final Review and Release Notes

Goal: check behavior, docs, and user workflow end to end.

Tasks:

- Run the smoke suite and relevant unit tests.
- Run a small manual workflow:
  - collect or use fixture jobs
  - batch process
  - mark one job for CV
  - selected CV generation
  - inspect report
- Review README and project context together.
- Add release notes or a decision log entry summarizing the refactor.

Done means:

- The project is easier to run than before, not merely rearranged.

Recommended GPT/thinking power:

- `gpt-5.5`, reasoning `high` for final code review.
- `gpt-5.4-mini`, reasoning `medium` for release notes.

## Risk Register

| Risk | Mitigation |
|---|---|
| Moving code breaks wrapper imports | Keep compatibility wrappers and test public `python -m jobsearch...` commands. |
| Generated outputs accidentally treated as source | Classify files before cleanup and update `.gitignore` deliberately. |
| Tracker history is overwritten | Preserve `outputs/application_tracker.csv`; add tests around tracker merge behavior. |
| LLM calls become expensive | Keep max calls per job, per-step routing, compact retries, and deterministic fallback. |
| CV text invents unsupported claims | Keep evidence-linked strategy and post-generation validation. |
| Refactor becomes too large | Ship one phase at a time, with tests and docs updated per phase. |

## Suggested Work Slices

Each slice should be small enough to review:

1. Add smoke fixtures and tests.
2. Add file classification doc.
3. Extract IO helpers.
4. Extract selected CV workflow service.
5. Extract LLM client/router boundary.
6. Add CV title/headline adaptation stage.
7. Extract batch processing service.
8. Clean command docs and README.
9. Decide package consolidation path.
10. Archive legacy prototype material.

## Agent Prompt Template

Use this prompt for future refactor work:

```text
Read project_context/04_architecture_map.md and project_context/08_complete_refactor_plan.md first.

Work on only the requested phase. Preserve the canonical workflow:
collect -> batch process -> dashboard/tracker review -> selected CV generation.

Do not delete generated/local files unless explicitly requested.
Keep deterministic fallback for LLM-assisted behavior.
Update tests and project_context when behavior or workflow meaning changes.
Return a concise summary with files changed and verification run.
```

