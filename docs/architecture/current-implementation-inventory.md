# Current Implementation Inventory

## System name

Job Search Automation MVP

## Current architecture type

Local, human-in-the-loop job-search and CV-preparation prototype.

## Current canonical workflow

collect sources -> batch process jobs -> dashboard review/tracker decisions -> selected-job CV generation

## Implemented capabilities

### Source collection

The system can collect jobs from configured or manual sources and write deduplicated job files into `sources/collected_jobs/`.

### Batch processing

The system can process a folder of `.txt` job ads, including a batch-of-1 case. It produces standardized job data, match results, and review queue outputs.

### Hybrid / LLM standardization

The system supports optional hybrid/LLM standardization. LLM use is especially relevant when parsing is difficult or when the core job description content is Swedish.

### Dashboard review

The dashboard is the normal human decision gate between matching and CV generation. Users can review positions and update statuses.

### Persistent tracking

The system maintains persistent decision/application history in `outputs/application_tracker.csv`.

### Selected-job CV generation

Only jobs explicitly selected for CV preparation move downstream. The selected CV pipeline produces CV strategy, CV draft, rendered HTML CV, and reports.

### Browser-based source collection

The system includes optional Verama/Ework browser collection using Playwright and local browser session state.

## Current primary actor

The current primary actor is an individual consultant/job seeker.

## Current secondary actor

A future or implicit Talent Advisor role can be inferred from the tracking, review, and source-curation workflow, but it is not yet clearly modeled as a separate role in the current implementation.

## Current external systems

- Job boards / manual job sources
- Verama/Ework
- OpenAI or compatible LLM provider
- Local browser session
- Local filesystem

## Current containers

- Source-to-review orchestrator
- Batch processing pipeline
- Dashboard review UI
- Selected CV pipeline
- Application tracker
- Maintained YAML data
- Local source folders
- Local output folders

## Current data stores

- `data/*.yaml`
- `sources/copied_jobs/`
- `sources/collected_jobs/`
- `outputs/batch/`
- `outputs/selected/`
- `outputs/application_tracker.csv`
- `browser_profiles/`
- `secrets/`

## Current architectural constraints

- Local-first
- Human-in-the-loop
- No automatic job application submission
- No automatic CV publishing
- No credentials in code or repository
- Generated artifacts are regenerable except persistent tracker history
- Batch pipeline is the canonical workflow