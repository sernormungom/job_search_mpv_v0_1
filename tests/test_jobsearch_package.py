from jobsearch.cv import draft_generator
from jobsearch.matching import matcher
from jobsearch.pipeline import run_sources_to_review
from jobsearch.sources import verama_playwright
from jobsearch.tracking import application_tracker


def test_jobsearch_compatibility_package_exposes_planned_modules():
    assert callable(matcher.standardize_job)
    assert callable(draft_generator.generate_draft)
    assert callable(verama_playwright.collect_verama_jobs)
    assert callable(application_tracker.sync_tracker)
    assert callable(run_sources_to_review.main)
