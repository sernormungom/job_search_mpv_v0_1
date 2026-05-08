# File Classification

## Purpose

This document classifies the major files and directories in the repository so future cleanup and refactor work can proceed without confusing source/config, generated output, persistent user state, local session data, and legacy compatibility areas.

This is a planning and safety aid. It does not authorize deletion by itself.

## Classification Labels

| Label | Meaning |
|---|---|
| `current` | Active implementation or maintained source of truth for the canonical workflow. |
| `helper` | Supporting code or metadata that is useful but not the main workflow surface. |
| `legacy` | Historical or compatibility area that should not be treated as the primary workflow. |
| `generated` | Regenerable output or cache produced by commands/tests. |
| `persistent_state` | User-maintained or long-lived state that should be preserved unless explicitly reset. |
| `local_state` | Machine/session-specific local data that should not be treated as source. |
| `unknown` | Needs more verification before cleanup or migration. |

## Top-Level Repository Classification

| Path | Classification | Notes |
|---|---|---|
| `.git/` | `local_state` | VCS internals; never treat as project source. |
| `data/` | `current` | Maintained YAML source/config for matching, profiles, policies, and sources. |
| `docs/` | `helper` | Design/reference docs; useful but not the canonical workflow source of truth. |
| `job_search_mvp/` | `current` | Main implementation package today. |
| `jobsearch/` | `current` | Preferred public package/command surface today; most modules are still wrappers over `job_search_mvp/`. |
| `outputs/` | mixed | Contains both `generated` artifacts and `persistent_state`; see subtable below. |
| `project_context/` | `current` | Maintained project intent, workflow, architecture, and refactor planning docs. |
| `prototype/` | `removed` | Historical wrapper area; deleted from the active tree. |
| `sources/` | mixed | Contains manual input/cache and generated intake/cache; see subtable below. |
| `tests/` | `current` | Active automated verification. |
| `browser_profiles/` | `local_state` | Local browser session state; should not be treated as project data. |
| `secrets/` | `local_state` | Local secret/session holder; should not be committed as meaningful source. |
| `job_search_mvp.egg-info/` | `generated` | Build/install metadata, not source of truth. |
| `README.md` | `current` | User-facing workflow entrypoint. |
| `pyproject.toml` | `current` | Packaging and entrypoint source of truth. |
| `requirements.txt` | `helper` | Dependency convenience file; `pyproject.toml` is the main packaging definition. |
| `.gitignore` | `current` | Repo hygiene and generated/local-state protection. |

## Code and Package Surface

| Path | Classification | Notes |
|---|---|---|
| `job_search_mvp/run_sources_to_review.py` | `current` | Canonical workflow orchestrator for collection -> batch -> optional tracker sync. |
| `job_search_mvp/run_job_batch.py` | `current` | Canonical batch processing entrypoint. |
| `job_search_mvp/run_dashboard.py` | `current` | Canonical dashboard launcher. |
| `job_search_mvp/run_selected_cv_pipeline.py` | `current` | Canonical selected-job CV pipeline. |
| `job_search_mvp/source_adapter.py` | `current` | Current collection/dedup implementation. |
| `job_search_mvp/matcher.py` | `current` | Current standardization/matching core. |
| `job_search_mvp/standardization/` | `current` | Current deterministic/LLM/hybrid standardization logic. |
| `job_search_mvp/application_tracker.py` | `current` | Current tracker implementation. |
| `job_search_mvp/strategy_generator.py` | `current` | Current CV strategy implementation. |
| `job_search_mvp/cv_draft_generator.py` | `current` | Current CV draft generation implementation. |
| `job_search_mvp/cv_llm_routing.py` | `current` | Current CV LLM routing policy layer. |
| `job_search_mvp/cv_llm_orchestrator.py` | `current` | Current CV LLM orchestration layer. |
| `job_search_mvp/mpya_cv_renderer.py` | `current` | Current MPYA-style CV renderer. |
| `job_search_mvp/cv_renderer.py` | `helper` | Alternate/local HTML renderer; useful but secondary to MPYA renderer in the visible workflow. |
| `job_search_mvp/streamlit_dashboard.py` | `current` | Active review UI implementation. |
| `job_search_mvp/verama_playwright_adapter.py` | `helper` | Optional browser collection adapter. |
| `job_search_mvp/assets/` | `current` | Rendering assets used by the active CV pipeline. |
| `jobsearch/pipeline/` | `current` | Preferred public command surface; mostly wrappers today. |
| `jobsearch/tracking/` | `current` | Preferred public tracker surface; mostly wrappers today. |
| `jobsearch/cv/` | `current` | Preferred public CV surface; mostly wrappers today. |
| `jobsearch/matching/` | `current` | Preferred public matching surface; mostly wrappers today. |
| `jobsearch/sources/` | `current` | Preferred public source surface; mostly wrappers/helpers today. |
| `jobsearch/standardization/` | `current` | Preferred public LLM standardization surface; mostly wrappers today. |
| `prototype/*.py` wrappers | `removed` | Historical command names/compatibility wrappers; deleted from the active tree. |
| `prototype/README.md` | `removed` | Historical wrapper documentation; deleted from the active tree. |
| `prototype/examples/` and `prototype/to_delete/` | `removed` | Example/historical data; deleted from the active tree. |

## Data and Configuration Surface

| Path | Classification | Notes |
|---|---|---|
| `data/employee_profile.yaml` | `current` | Maintained employee source/profile data. |
| `data/experience_database.yaml` | `current` | Maintained experience evidence database. |
| `data/career_preferences.yaml` | `current` | Maintained role preference source. |
| `data/consultancy_static_profile.yaml` | `current` | Maintained consultancy/rendering profile data. |
| `data/cv_generation_policy.yaml` | `current` | Maintained policy for CV generation and LLM routing/budgets. |
| `data/job_sources.yaml` | `current` | Maintained collection/source configuration. |
| `data/tool_aliases.yaml` | `current` | Maintained matching alias source. |
| `data/optional_role_fit_profiles.yaml` | `helper` | Optional tuning/support data. |
| `data/*.template.yaml` | `helper` | Output shape references and artifact templates. |

## Output and Workspace Lifecycle

| Path | Classification | Notes |
|---|---|---|
| `outputs/application_tracker.csv` | `persistent_state` | Long-lived user decision history; preserve unless explicitly reset. |
| `outputs/application_tracker.html` | `generated` | Regenerable presentation of tracker state. |
| `outputs/batch/` | `generated` | Active-cycle batch outputs; standardized jobs, match results, review queues. |
| `outputs/selected/` | `generated` | Selected-job CV outputs and reports. |
| `outputs/pytest_work/` | `generated` | Test-created working output; should not be treated as source. |
| `outputs/batch/*.job_standardized.yaml` | `generated` | Regenerable from collected jobs and data config. |
| `outputs/batch/*.match_result.yaml` | `generated` | Regenerable matching outputs. |
| `outputs/batch/*.llm_raw.yaml` | `generated` | LLM intermediate artifacts; useful for debugging but not source of truth. |
| `outputs/batch/review_queue*.csv/html` | `generated` | Regenerable review artifacts. |
| `outputs/selected/*.cv_strategy.yaml` | `generated` | Regenerable selected-job planning outputs. |
| `outputs/selected/*.cv_llm_steps.yaml` | `generated` | Regenerable LLM step artifacts. |
| `outputs/selected/*.cv_draft.yaml/txt` | `generated` | Regenerable CV draft outputs. |
| `outputs/selected/*.mpya_cv.html` | `generated` | Regenerable rendered CV outputs. |
| `outputs/selected/llm_routing.plan.yaml` | `generated` | Regenerable routing artifact. |

## Sources and Intake Lifecycle

| Path | Classification | Notes |
|---|---|---|
| `sources/copied_jobs/` | `helper` | Manual input/cache area; may contain user-curated current-cycle input. |
| `sources/collected_jobs/` | `generated` | Canonical deduplicated intake/cache from collection workflow. |
| `sources/collected_jobs/job_manifest.csv` | `generated` | Regenerable collection manifest. |
| `sources/collected_jobs/*.txt` | `generated` | Regenerable collected job text artifacts unless explicitly curated by the user for reuse. |
| `.gitkeep` files under `sources/` | `helper` | Directory placeholders only. |

## Local and Machine-Specific State

| Path | Classification | Notes |
|---|---|---|
| `browser_profiles/verama/` | `local_state` | Real browser profile/session/cache state; not source code. |
| `browser_profiles/.gitkeep` | `helper` | Placeholder only. |
| `secrets/.gitkeep` | `helper` | Placeholder only; actual secrets should remain local state. |
| `job_search_mvp.egg-info/` | `generated` | Packaging metadata generated by install/build. |

## Tests, Examples, and Docs

| Path | Classification | Notes |
|---|---|---|
| `tests/` | `current` | Active automated verification for the implementation and wrapper surface. |
| `tests/test_matcher.py` | `current` | Depends on `tests/fixtures/jobs/sample_job_embedded.txt`. |
| `tests/test_strategy_generator.py` | `current` | Depends on `tests/fixtures/jobs/sample_job_embedded.txt`. |
| `tests/fixtures/jobs/sample_job_embedded.txt` | `current` | Canonical sample job fixture for matcher/strategy stability tests. |
| `docs/llm_standardizer_design.md` | `helper` | Design document; not the canonical operational workflow. |
| `project_context/` docs | `current` | Maintained project reference and planning materials. |

## Legacy References That Still Matter

These should be treated carefully during cleanup because they are still referenced:

1. `tests/fixtures/jobs/sample_job_embedded.txt`
   Used by:
   - `tests/test_matcher.py`
   - `tests/test_strategy_generator.py`

2. Some module docstrings and help text still say "prototype".
   This is not harmful by itself, but it blurs the active implementation story and should be cleaned during later documentation/code-surface refactor phases.

## Suggested Near-Term Cleanup Boundaries

Safe to treat as non-source during future cleanup planning:

- `outputs/batch/`
- `outputs/selected/`
- `outputs/pytest_work/`
- `sources/collected_jobs/`
- `browser_profiles/verama/`
- `job_search_mvp.egg-info/`

Preserve by default:

- `data/*.yaml`
- `project_context/*.md`
- `tests/`
- `README.md`
- `pyproject.toml`
- `outputs/application_tracker.csv`

Needs verification before deletion or migration:

- `sources/copied_jobs/`
- any example files that may still be referenced by historical docs or tests
