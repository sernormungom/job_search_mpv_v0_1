# Historical Decision Log

Archival note: this file records past decisions for provenance. It is not the place to look for current workflow instructions.

This file records project direction decisions so future maintainers and AI agents do not have to infer intent from historical code order.

## 2026-05-08: Batch workflow is canonical

### Decision

The batch workflow is the official project workflow.

A single job should be processed as a batch of 1 rather than through a separate user-facing individual-job workflow.

### Rationale

The project originally started with individual-job processing, but the workflow has evolved into source collection and batch processing. Keeping the old individual workflow as the first documented path makes the project harder for humans and AI agents to understand.

### Consequences

- README should present source collection and batch processing first.
- Individual-job commands should be treated as legacy, debugging, or lower-level helper commands unless explicitly needed.
- Refactors should preserve batch-of-1 behavior.
- Tests should protect batch-of-1 behavior so the old individual workflow can be safely deprecated.

## 2026-05-08: Dashboard is the human decision gate for CV generation

### Decision

The dashboard is the normal human decision gate between job matching and selected-job CV generation.

CV generation is downstream of dashboard/user selection and should normally process only jobs explicitly marked for CV preparation, such as `prepare_cv`.

### Rationale

The system is intended to support weekly job review and decision-making, not to automatically generate or submit CVs for every matched position. Human selection keeps the workflow credible and controllable.

### Consequences

- Documentation should present dashboard review before selected CV generation.
- Selected CV pipeline behavior should remain status/selection-driven.
- Tests should protect that CV artifacts are generated only for selected jobs.
- Future UI work should reinforce, not bypass, the human decision gate.

## 2026-05-08: Current search-cycle artifacts are different from persistent history

### Decision

Generated intake/batch/selected artifacts should be treated as current search-cycle output or cache, while `outputs/application_tracker.csv` should be treated as persistent user history.

### Rationale

The project is intended to be used regularly, often weekly. Old job positions may remain as cache/history, but they should not be confused with active review work or maintained source data. At the same time, application decisions should persist across searches.

### Consequences

- Documentation should distinguish generated output, cache, persistent tracker state, examples/fixtures, and local/session state.
- Refactors should avoid treating generated output as source truth.
- Cleanup behavior may be useful later, but it should preserve persistent tracker state unless the user explicitly resets it.

## 2026-05-08: Workspace cleanup is a future feature, not part of the current refactor

### Decision

A future feature may clean generated workspace/cache artifacts before a new search cycle, but the current refactor should not implement that feature unless explicitly requested.

### Rationale

The current priority is stabilization and documentation clarity. Adding cleanup behavior now could create new risk and distract from the main goal.

### Consequences

- Project context may document what a cleanup command should eventually consider.
- AI agents should not add cleanup commands during stabilization without explicit instruction.
- The refactor should still classify files so future cleanup is safer.

## 2026-05-18: Search-cycle reset should delete only generated position artifacts by default

### Decision

The requested search-cycle reset feature should remove only generated current-cycle position artifacts by default:

- `sources/collected_jobs/`
- `outputs/batch/`
- `outputs/selected/`

It should preserve persistent history and maintained source/config files by default, especially:

- `outputs/application_tracker.csv`
- `outputs/application_tracker.html`
- `data/*.yaml`
- manually maintained source folders such as `sources/copied_jobs/`

The feature should be explicit and opt-in, not automatic on normal pipeline runs.

### Rationale

The user wants a clean starting point for a new workflow run without carrying previous positions into the active queue. At the same time, the project already distinguishes generated cycle artifacts from persistent decision history. Preserving the tracker by default avoids accidental loss of application history while still solving the "start fresh" problem.

### Consequences

- Cleanup behavior should be introduced behind an explicit CLI flag or dedicated command.
- Implementation should use a strict allowlist of removable paths rather than broad pattern deletion.
- Cleanup should validate that every target resolves inside the project root before deleting.
- Documentation should describe the reset as "clear previous generated positions/artifacts" rather than "wipe workspace."
- A separate explicit reset path would be required if the user ever wants to delete tracker history too.

## 2026-05-08: `project_context/` is the source of truth for maintainers and AI agents

### Decision

Create and maintain a `project_context/` folder as the lightweight source of truth for the project.

### Rationale

Formal requirements are too heavy for this personal/mid-complexity project. A small set of Markdown files is enough to communicate project intent to humans and AI agents.

### Consequences

- Future AI agents should read `project_context/` before modifying code.
- README remains user-facing, while `project_context/` remains maintainer/AI-facing.
- When project direction changes, update `project_context/` close to the code change.

## 2026-05-08: Prefer current behavior over historical README order

### Decision

During refactor, treat the current intended behavior described in `project_context/` as more authoritative than the current README order.

### Rationale

The README still reflects the project's evolution and may present older workflows before the current first step.

### Consequences

- README refactor is an early priority.
- AI agents should not assume the first README workflow is the best workflow.
- The new README should guide users from source collection to batch processing to dashboard review to selected CV generation.

## 2026-05-08: Preserve human-in-the-loop behavior

### Decision

The system should remain human-in-the-loop.

It may collect jobs, score/match them, generate review queues, track decisions, and generate CV artifacts for selected jobs. It should not automatically submit applications.

### Rationale

The current project is a local decision-support and CV-preparation tool, not a fully autonomous job-application bot.

### Consequences

- Keep review queue and tracker as explicit decision gates.
- Keep selected CV generation dependent on human status/selection.
- Do not add automatic apply/submit behavior during refactors.

## 2026-05-08: Keep implementation/package duplication until it is intentionally resolved

### Decision

Do not immediately delete either `job_search_mvp/` or `jobsearch/`.

### Rationale

The repository currently appears to use `job_search_mvp/` as the tested implementation and `jobsearch/` as a preferred public/wrapper package. Removing either without a deliberate migration could break entry points or tests.

### Consequences

- Document the distinction for now.
- Refactor README and tests before deeper package migration.
- Later choose whether to keep wrappers or migrate implementation into `jobsearch/`.

## 2026-05-08: Treat `prototype/` as likely legacy pending verification

### Decision

Treat the `prototype/` folder as likely legacy, but do not delete it until imports/tests/references are checked.

### Rationale

The folder duplicates many files from the active implementation and may confuse future maintainers or AI agents.

### Consequences

- Classify `prototype/` during the first refactor phase.
- If unused, archive or remove it.
- If examples are useful, keep only clearly labeled examples/fixtures.

## 2026-05-08: Improve Swedish/English job standardization before forcing LLM usage

### Decision

Improve deterministic job standardization for multilingual (especially Swedish) postings, and use hybrid LLM enrichment only when deterministic confidence is low.

### Rationale

Some source pages and copied job ads are in Swedish. Deterministic extraction previously missed or mixed requirement sections such as `Krav` and `Meriterande`, and hybrid mode could trigger unnecessary LLM calls even when deterministic output was already strong.

### Consequences

- Deterministic standardization should normalize Swedish/English section headers and extract canonical requirement fields (`must_have`, `nice_to_have`) more reliably.
- `data/tool_aliases.yaml` should include Swedish-supporting terms where useful.
- Hybrid mode should be confidence-gated: skip LLM for high-confidence deterministic output, attempt LLM only for low-confidence cases, and retain deterministic fallback behavior when LLM is unavailable or invalid.

## Future decision template

Use this format for future decisions:

```markdown
## YYYY-MM-DD: Decision title

### Decision

What was decided?

### Rationale

Why was this decided?

### Consequences

What should future humans or AI agents do differently because of this?
```
