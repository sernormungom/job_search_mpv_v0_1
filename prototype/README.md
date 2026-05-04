# Prototype compatibility wrappers

The implementation now lives in the `job_search_mvp/` package. This folder keeps the original command-line script names as thin wrappers so existing commands such as `python prototype/matcher.py ...` continue to work.

Current layout:

```text
data/                  manually maintained YAML files
outputs/               generated artifacts and tracker files
job_search_mvp/        importable Python package
prototype/examples/    sample copied job ads
prototype/*.py         compatibility wrappers
```

## Main workflows

Single-job match:

```bash
python prototype/matcher.py \
  --job prototype/examples/sample_job_embedded.txt \
  --data-dir data \
  --out-dir outputs/single
```

Batch review queue:

```bash
python prototype/run_job_batch.py \
  --jobs-dir prototype/examples/job_batch \
  --data-dir data \
  --out-dir outputs/batch
```

Source intake to tracked queue:

```bash
python prototype/run_sources_to_review.py \
  --sources job_sources.yaml \
  --data-dir . \
  --sync-tracker
```

Selected CV generation:

```bash
python prototype/run_selected_cv_pipeline.py \
  --review-queue outputs/batch/review_queue.tracked.csv \
  --batch-dir outputs/batch \
  --data-dir data \
  --out-dir outputs/selected
```

Tracker export:

```bash
python prototype/application_tracker.py export-html \
  --tracker outputs/application_tracker.csv \
  --out-html outputs/application_tracker.html
```

Run tests:

```bash
python -m pytest
```

The package also supports module execution, for example `python -m job_search_mvp.matcher ...`.
