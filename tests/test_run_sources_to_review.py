from pathlib import Path

from job_search_mvp import run_sources_to_review


def test_main_without_reset_does_not_call_cleanup(monkeypatch):
    cleanup_calls = []
    run_calls = []

    monkeypatch.setattr(
        run_sources_to_review,
        "resolve_project_root",
        lambda data_dir: Path("C:/repo"),
    )
    monkeypatch.setattr(
        run_sources_to_review,
        "reset_search_cycle_artifacts",
        lambda project_root: cleanup_calls.append(project_root) or {"removed": [], "missing": []},
    )
    monkeypatch.setattr(
        run_sources_to_review,
        "run",
        lambda cmd, cwd: run_calls.append((cmd, cwd)),
    )
    monkeypatch.setattr(
        run_sources_to_review.sys,
        "argv",
        [
            "run_sources_to_review.py",
            "--data-dir",
            ".",
        ],
    )

    exit_code = run_sources_to_review.main()

    assert exit_code == 0
    assert cleanup_calls == []
    assert len(run_calls) == 2


def test_main_with_reset_calls_cleanup_before_pipeline(monkeypatch):
    order = []
    run_calls = []

    monkeypatch.setattr(
        run_sources_to_review,
        "resolve_project_root",
        lambda data_dir: Path("C:/repo"),
    )
    monkeypatch.setattr(
        run_sources_to_review,
        "reset_search_cycle_artifacts",
        lambda project_root: order.append(("cleanup", project_root)) or {"removed": [], "missing": []},
    )
    monkeypatch.setattr(
        run_sources_to_review,
        "run",
        lambda cmd, cwd: order.append(("run", cmd)) or run_calls.append((cmd, cwd)),
    )
    monkeypatch.setattr(
        run_sources_to_review.sys,
        "argv",
        [
            "run_sources_to_review.py",
            "--data-dir",
            ".",
            "--reset-cycle-artifacts",
        ],
    )

    exit_code = run_sources_to_review.main()

    assert exit_code == 0
    assert len(run_calls) == 2
    assert order[0] == ("cleanup", Path("C:/repo"))


def test_main_with_reset_and_sync_tracker_runs_tracker_sync(monkeypatch):
    run_calls = []

    monkeypatch.setattr(
        run_sources_to_review,
        "resolve_project_root",
        lambda data_dir: Path("C:/repo"),
    )
    monkeypatch.setattr(
        run_sources_to_review,
        "reset_search_cycle_artifacts",
        lambda project_root: {"removed": [], "missing": []},
    )
    monkeypatch.setattr(
        run_sources_to_review,
        "run",
        lambda cmd, cwd: run_calls.append((cmd, cwd)),
    )
    monkeypatch.setattr(
        run_sources_to_review.sys,
        "argv",
        [
            "run_sources_to_review.py",
            "--data-dir",
            ".",
            "--batch-out",
            "outputs/batch",
            "--tracker",
            "outputs/application_tracker.csv",
            "--sync-tracker",
            "--reset-cycle-artifacts",
        ],
    )

    exit_code = run_sources_to_review.main()

    assert exit_code == 0
    assert len(run_calls) == 3
    assert run_calls[0][1] == Path("C:/repo")
    assert run_calls[1][1] == Path("C:/repo")
    assert run_calls[2][1] == Path("C:/repo")
    assert run_calls[2][0][2:4] == ["jobsearch.tracking.application_tracker", "sync"]
    normalized_cmd = [part.replace("\\", "/") for part in run_calls[2][0]]
    assert "--review-queue" in normalized_cmd
    assert "outputs/batch/review_queue.csv" in normalized_cmd
    assert "--out-review-queue" in normalized_cmd
    assert "outputs/batch/review_queue.tracked.csv" in normalized_cmd
    assert "--tracker" in normalized_cmd
    assert "outputs/application_tracker.csv" in normalized_cmd
