# LLM Standardizer / Translator Design

## MVP Goal

Add an optional LLM-powered standardization step that converts cleaned raw job text into a comparable, English, structured job record.

This should improve demo quality without changing the whole architecture. The first implementation should stay local and file-based:

```text
sources/collected_jobs/*.txt
  -> deterministic metadata + explicit term extraction
  -> LLM standardizer/translator
  -> outputs/<batch>/<job_id>.job_standardized.yaml
  -> matcher/scoring/review queue
```

The deterministic matcher remains the fallback and safety layer.

## What Problem This Solves

Current deterministic standardization is good at preserving explicit tools, but weak at:

- Removing leftover source formatting from summaries
- Translating Swedish labels and mixed-language job ads
- Extracting company/client, deadline, role, seniority, work mode, contract type
- Separating responsibilities from must-have and nice-to-have requirements
- Identifying language requirements and risk flags
- Normalizing role categories beyond simple keyword heuristics

The LLM standardizer should make the review queue feel more intelligent before we add a database, embeddings, or a full agent system.

## Non-Goals For MVP

- No automatic applications
- No database required
- No vector search required
- No autonomous browsing decisions
- No CV generation directly from raw LLM output
- No invention of requirements, company names, deadlines, or tools

## Recommended Module Shape

Create a new package area:

```text
job_search_mvp/
  standardization/
    __init__.py
    schema.py
    llm_standardizer.py
    prompts.py
    validation.py
```

Compatibility wrapper:

```text
jobsearch/standardization/
  __init__.py
  llm_standardizer.py
```

Suggested command:

```powershell
python -m jobsearch.standardization.llm_standardizer `
  --job sources/collected_jobs/job_30065ec2e7.txt `
  --out-dir outputs/standardized `
  --provider openai `
  --model gpt-3.5-turbo
```

Batch integration should be added as a flag later:

```powershell
python -m jobsearch.pipeline.run_job_batch `
  --jobs-dir sources/collected_jobs `
  --data-dir data `
  --out-dir outputs/batch `
  --standardizer llm
```

## Output Contract

The LLM should return one strict JSON object. The implementation can save it as YAML using the existing `write_yaml` style.

```json
{
  "schema_version": "job_standardized_llm_v1",
  "job_id": "job_30065ec2e7",
  "source": {
    "site": "verama",
    "url": "https://app.verama.com/app/job-requests/79391",
    "scraped_at": "2026-05-05T08:32:25+00:00"
  },
  "language": {
    "original": "mixed Swedish/English",
    "standardized_output": "English",
    "translation_notes": ["Swedish portal labels translated; English assignment text preserved."]
  },
  "identity": {
    "original_title": "Diagnostic SW Product Owner - Inverters",
    "normalized_title": "Diagnostic Software Product Owner",
    "company": "InfiMotion Technology Europe AB",
    "client_or_broker": "client",
    "location": {
      "city": "Gothenburg",
      "country": "Sweden",
      "work_mode": "onsite",
      "remote_percentage": 0
    },
    "employment_type": "consultant_assignment",
    "assignment_period": {
      "start": "2026-05-18",
      "end": "2026-11-01"
    },
    "application_deadline": "2026-05-15T23:59:00"
  },
  "summary": {
    "short_summary": "The client is looking for a senior diagnostic software product owner for inverter software development, covering diagnostic requirements, architecture, OBD certification documents, and validation support.",
    "role_goal": "Own and coordinate diagnostics work for inverter software development.",
    "business_context": "Electric drive units and hybrid/electric vehicle technology."
  },
  "job_analysis": {
    "role_archetype": "Systems Engineer",
    "seniority": "senior",
    "primary_technical_focus": ["diagnostics", "inverter software", "automotive embedded systems"],
    "secondary_technical_focus": ["OBD legislation", "AUTOSAR", "FMEA/FTA", "validation"],
    "leadership_expectations": ["technical ownership", "cross-functional coordination"],
    "consultant_fit_notes": ["Consultant assignment handled through Ework."]
  },
  "explicit_terms": {
    "languages": [],
    "tools": ["AUTOSAR"],
    "platforms": [],
    "methods": ["requirements analysis", "diagnostic analysis"],
    "standards": ["ISO 14229", "OBDII", "EOBD", "J1979", "J2012"],
    "verification": ["validation", "test plan", "test cases"],
    "domains": ["automotive", "electric drive units", "diagnostics"],
    "soft_skills": ["knowledge transfer", "presentations"]
  },
  "normalized_requirements": {
    "responsibilities": [
      "Own diagnostic work in inverter software development.",
      "Analyze requirements based on OBD legislation, ISO standards, OEM requirements, and FMEA.",
      "Design diagnostic monitoring strategy and diagnostic architecture.",
      "Support diagnostic test planning, test cases, issue analysis, and FuSa interaction."
    ],
    "must_have": [
      "Good knowledge of OBDII, EOBD, J1979, J2012, and ISO 14229.",
      "Good understanding of FMEA/FTA and diagnostic analysis.",
      "Experience with diagnostic monitor design for hybrid transmission.",
      "Familiarity with AUTOSAR, especially DEM and FIM."
    ],
    "nice_to_have": []
  },
  "tags": {
    "skills": ["AUTOSAR", "diagnostics", "requirements analysis", "validation"],
    "domain": ["automotive", "inverters", "electric drive units"],
    "work_mode": ["onsite Gothenburg"],
    "language_requirement": ["English unspecified", "Swedish not explicit"],
    "risk_flags": [],
    "opportunity_flags": ["automotive embedded fit", "senior technical ownership"]
  },
  "blockers": {
    "hard": [],
    "soft": ["Onsite work appears to be required."]
  },
  "llm_audit": {
    "confidence": 0.82,
    "unsupported_or_ambiguous_fields": ["Exact language requirement not stated."],
    "source_quote_refs": [
      "Lead / Own Diagnostic field in inverter SW development",
      "Good knowledge of OBDII, EOBD, J1979, J2012, ISO14229",
      "Distansarbete 0%"
    ]
  }
}
```

## Important Design Choice

Use a hybrid approach:

1. Deterministic preprocessing extracts source URL, header metadata, job ID, and explicit term catalog matches.
2. LLM extracts semantic structure and translation.
3. Post-validation merges deterministic explicit terms back into the LLM output.

The LLM may add extra explicit terms from the text, but it must not remove deterministic terms.

This protects one of the core project constraints: explicit job tools must survive standardization.

## Prompt Design

System instruction:

```text
You standardize job postings for a local job-search assistant.
Return only valid JSON matching the requested schema.
Translate Swedish or mixed-language content into English.
Do not invent facts. If a field is not stated, use null, an empty list, or "unspecified".
Preserve explicit technologies, standards, tools, methods, and requirements exactly when they appear in the job text.
Separate responsibilities, must-have requirements, nice-to-have requirements, blockers, and risk flags.
Do not decide whether the candidate should apply.
```

User message shape:

```text
Standardize this job posting.

Known metadata:
<metadata JSON>

Deterministic explicit terms:
<explicit term JSON>

Raw job text:
<cleaned job text>
```

## Validation Rules

Implementation should validate after the LLM call:

- JSON parses successfully.
- Required top-level keys exist.
- `job_id` equals deterministic job ID.
- `source.url` equals source URL from the text header.
- Deterministic explicit terms are included in output.
- `identity.company` may be empty only if not present in text/header.
- `blockers.hard` only includes hard blockers explicitly stated in the posting.
- `llm_audit.unsupported_or_ambiguous_fields` is present when fields are inferred weakly.

If validation fails, save an error artifact and fall back to deterministic `matcher.standardize_job`.

## File Outputs

For each job:

```text
outputs/batch/<job_id>.job_standardized.yaml
outputs/batch/<job_id>.job_standardized.llm_raw.json
outputs/batch/<job_id>.job_standardized.validation.json
```

The canonical `job_standardized.yaml` should keep the existing structure expected by the matcher. Extra LLM fields can live under:

```yaml
job_standardized:
  llm_enrichment:
    tags: ...
    llm_audit: ...
    assignment_period: ...
    application_deadline: ...
```

This avoids breaking downstream strategy and CV generation.

## Batch Behavior

Add `--standardizer` to batch runner:

```text
--standardizer deterministic   default, current behavior
--standardizer llm             LLM only, fallback to deterministic on failure
--standardizer hybrid          deterministic + LLM enrichment, recommended default after MVP validation
```

For MVP implementation, `hybrid` is the best target.

## Provider Boundary

Keep provider code small and swappable:

```python
class LLMClient:
    def standardize_job(self, prompt: str, schema: dict) -> dict:
        ...
```

Use environment variables for credentials:

```text
OPENAI_API_KEY
JOBSEARCH_LLM_PROVIDER=openai
JOBSEARCH_LLM_MODEL=gpt-3.5-turbo
```

For API cost control, the implementation allows only `gpt-3.5-turbo` for OpenAI calls.

Do not store API keys in repo files.

## Demo Success Criteria

A good Step 3 demo should show:

- Swedish/mixed Verama job becomes clean English structured data.
- Company/client, deadline, location, work mode, and seniority are visible.
- Requirements are separated into responsibilities, must-have, and nice-to-have.
- Explicit tools/standards are preserved.
- Review queue titles and summaries look human-readable.
- Matching can still run if the LLM fails.

## Implementation Order

1. Add schema and prompt files.
2. Add provider-agnostic `llm_standardizer.py`.
3. Add one-job CLI command.
4. Add validation and deterministic fallback.
5. Integrate `--standardizer hybrid` into `run_job_batch.py`.
6. Run on 3 Verama examples and compare deterministic vs LLM standardized YAML.

Recommended sample jobs:

- `job_30065ec2e7`: diagnostic / AUTOSAR / inverter software
- `job_1224248010`: ML/AI / Databricks / Python
- `job_57ff49c12e`: fullstack / JavaScript / Python / CI/CD / cloud
