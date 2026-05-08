# Refactor Plan

## Goal

Simplify the project so the source-to-review batch workflow is the clear default path, while preserving the existing working behavior.

The primary cleanup is conceptual and structural: make the project easy for a human or AI agent to understand without reading historical workflows first.

## Refactor principles

1. Preserve working behavior before deleting code.
2. Keep the batch workflow canonical.
3. Treat single-job behavior as batch-of-1 unless proven otherwise.
4. Keep dashboard review as the normal human decision gate.
5. Keep selected CV generation downstream of dashboard/user selection.
6. Prefer small reviewable changes.
7. Update `project_context/` when project direction changes.
8. Keep tests passing.
9. Do not add new features during stabilization unless explicitly requested.

## Phase 1: Baseline and classify

### Tasks

- Run the test suite.
- List all top-level entry points.
- Classify files/modules as:
  - `current`
  - `helper`
  - `legacy`
  - `generated`
  - `persistent_state`
  - `local_state`
  - `unknown`
- Identify imports/references from `prototype/`.
- Identify generated/local-state files that should not be committed long-term.

### Commands

```bash
python -m pytest
find . -maxdepth 3 -type f | sort
grep -R "prototype" .
```

### Output

Create or update a classification table in either this file or a new file:

```text
project_context/file_classification.md
```

Do not delete anything in this phase.

## Phase 2: Define output and workspace lifecycle

### Goal

Reduce confusion around current-cycle outputs, cache files, persistent tracker state, examples, fixtures, and local/session state.

### Tasks

- Document which paths are maintained source/config.
- Document which paths are generated active-cycle artifacts.
- Document which paths are persistent user history.
- Document which paths are local/session state and should not be committed.
- Decide whether existing sample files under `outputs/` or `sources/` should become fixtures/examples or be treated as generated local state.
- Update `.gitignore` recommendations if needed.

### Important constraint

Do not implement an automated cleanup command in this phase. Workspace cleanup is a future feature. The current refactor should only clarify lifecycle and reduce accidental confusion.

### Definition of done

A future maintainer can tell whether a file is source, generated output, persistent history, fixture/example, or local state before moving or deleting it.

## Phase 3: README cleanup

### Goal

Make the README match the current intended workflow.

### Tasks

- Move source collection and batch processing to the top.
- Explain that a single job should be processed as a batch of 1.
- Make dashboard review the visible human decision gate.
- Explain that selected CV generation is downstream of dashboard/user selection.
- Move individual-job commands into a legacy/developer/debug section.
- Show one recommended command style, preferably `python -m jobsearch...` or installed console scripts.
- Keep optional dashboard, Verama, and LLM standardizer sections clearly marked as optional.

### Definition of done

A new user reading the README should understand that the first real workflow is:

```text
collect jobs -> batch process -> dashboard review -> selected CV generation
```

## Phase 4: Add/confirm smoke tests

### Goal

Protect the key behavior before deeper cleanup.

### Tasks

- Confirm there is a test for batch processing multiple jobs.
- Add or confirm a test for batch processing a folder with exactly one job.
- Confirm tracker sync preserves human decisions.
- Confirm selected CV pipeline only processes selected jobs.
- Confirm dashboard-triggered or tracker-status-driven CV generation semantics if testable without launching the UI.

### Suggested fixture structure

```text
tests/fixtures/jobs/batch_one/
tests/fixtures/jobs/batch_many/
```

### Definition of done

The project has a small test that proves the old single-job workflow can be replaced by batch-of-1 behavior.

## Phase 5: Clean generated/local-state files

### Goal

Separate source code, examples, generated output, persistent tracker state, and local state.

### Tasks

- Decide whether committed files under `outputs/` are examples, fixtures, or local generated output.
- Decide whether committed files under `sources/collected_jobs/` and `sources/copied_jobs/` are examples, fixtures, or local input/output.
- Move useful examples to `examples/` or `tests/fixtures/`.
- Update `.gitignore` for generated outputs, browser profiles, `__pycache__`, and local state.
- Be careful with `outputs/application_tracker.csv`; it may represent useful working state for the user, but it should not be confused with source code.

### Definition of done

A new clone should not contain confusing generated state unless it is clearly marked as sample/fixture data.

## Phase 6: Resolve package duplication

### Goal

Clarify the relationship between `job_search_mvp/` and `jobsearch/`.

### Current working assumption

- `job_search_mvp/` is the implementation package.
- `jobsearch/` is the preferred public command/wrapper package.

### Options

#### Option A: Keep wrappers

Keep `job_search_mvp/` as implementation and `jobsearch/` as public wrappers. Document this explicitly.

#### Option B: Migrate implementation

Move implementation into `jobsearch/` and leave compatibility wrappers in `job_search_mvp/` temporarily.

### Recommendation

Do not start with this phase. First clean README, lifecycle docs, and tests. Then choose one option intentionally.

## Phase 7: Archive or remove `prototype/`

### Goal

Remove duplicate historical implementation from the active tree if unused.

### Tasks

- Check references to `prototype/`.
- Compare prototype files with active files if needed.
- If unused, either:
  - delete `prototype/`, or
  - move it to `archive/prototype/`, or
  - keep only `prototype/README.md` explaining that it is historical.

### Definition of done

The active project no longer looks like it has two or three competing implementations.

## Phase 8: Remove/deprecate old single-job docs and commands

### Goal

Make old individual-case usage clearly secondary.

### Tasks

- Identify direct single-job console commands and README examples.
- Decide whether to keep them as developer/debug utilities.
- If kept, document them as lower-level helpers.
- If removed, update tests and wrappers accordingly.

### Definition of done

The project owner and future AI agents understand that single-job behavior is not the primary workflow.

## Future feature: workspace cleanup

A future feature may provide a command or dashboard action to clean the workspace before a new search cycle.

Possible future behavior:

```text
clean generated intake/cache
clean outputs/batch
clean outputs/selected
preserve outputs/application_tracker.csv unless explicitly reset
preserve data/*.yaml
preserve examples and tests/fixtures
```

This is intentionally not part of the current stabilization refactor.

## Suggested execution order

1. Phase 1: Baseline and classify.
2. Phase 2: Define output and workspace lifecycle.
3. Phase 3: README cleanup.
4. Phase 4: Smoke tests.
5. Phase 5: Generated/local-state cleanup.
6. Phase 7: Prototype cleanup.
7. Phase 6/8: Package and command-surface cleanup.

## Safe first AI-agent prompt

```text
Read project_context/ first. Do not modify code yet.

Inspect the repository and classify all major files/modules as current, helper, legacy, generated, persistent_state, local_state, or unknown.
Focus on the canonical workflow: source collection -> batch processing -> dashboard review/tracker -> selected CV generation.
Assume individual-job workflows are legacy unless used by the batch or selected-CV pipeline.
Do not implement workspace cleanup yet; only classify what a future cleanup feature would need to know.
Return a proposed refactor plan, but do not apply changes.
```
