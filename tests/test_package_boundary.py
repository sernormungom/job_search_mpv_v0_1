from jobsearch.cv import draft_generator
from jobsearch.matching import matcher
from jobsearch.pipeline import run_job_batch, run_selected_cv_pipeline, run_sources_to_review
from jobsearch.sources import source_adapter, verama_playwright
from jobsearch.standardization import llm_standardizer
from jobsearch.tracking import application_tracker


def test_jobsearch_public_package_surfaces_the_canonical_entrypoints():
    assert callable(matcher.main)
    assert callable(draft_generator.main)
    assert callable(source_adapter.main)
    assert callable(verama_playwright.main)
    assert callable(llm_standardizer.main)
    assert callable(application_tracker.main)
    assert callable(run_sources_to_review.main)
    assert callable(run_job_batch.main)
    assert callable(run_selected_cv_pipeline.main)
