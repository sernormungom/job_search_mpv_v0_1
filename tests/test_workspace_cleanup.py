from pathlib import Path
import uuid

import pytest

from job_search_mvp.paths import OUTPUTS_DIR
from job_search_mvp.workspace_cleanup import (
    CleanupSafetyError,
    reset_search_cycle_artifacts,
    validate_cycle_reset_targets,
)


def _mkdir(root: Path, rel: str) -> Path:
    path = root / rel
    path.mkdir(parents=True, exist_ok=True)
    return path


def _work_dir() -> Path:
    path = OUTPUTS_DIR / "pytest_work" / "workspace_cleanup" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_validate_cycle_reset_targets_returns_only_allowlisted_paths():
    work_dir = _work_dir()
    targets = validate_cycle_reset_targets(work_dir)
    rels = [path.relative_to(work_dir).as_posix() for path in targets]

    assert rels == ["sources/collected_jobs", "outputs/batch", "outputs/selected"]


def test_reset_search_cycle_artifacts_dry_run_reports_without_deleting():
    work_dir = _work_dir()
    _mkdir(work_dir, "sources/collected_jobs")
    _mkdir(work_dir, "outputs/batch")
    _mkdir(work_dir, "outputs/selected")

    result = reset_search_cycle_artifacts(project_root=work_dir, dry_run=True)

    assert result["removed"] == ["sources/collected_jobs", "outputs/batch", "outputs/selected"]
    assert result["missing"] == []
    assert (work_dir / "sources/collected_jobs").exists()
    assert (work_dir / "outputs/batch").exists()
    assert (work_dir / "outputs/selected").exists()


def test_reset_search_cycle_artifacts_deletes_targets_and_preserves_tracker():
    work_dir = _work_dir()
    _mkdir(work_dir, "sources/collected_jobs")
    _mkdir(work_dir, "outputs/batch")
    _mkdir(work_dir, "outputs/selected")
    tracker = work_dir / "outputs" / "application_tracker.csv"
    tracker.parent.mkdir(parents=True, exist_ok=True)
    tracker.write_text("job_id,status\nx,new\n", encoding="utf-8")

    result = reset_search_cycle_artifacts(project_root=work_dir)

    assert result["removed"] == ["sources/collected_jobs", "outputs/batch", "outputs/selected"]
    assert result["missing"] == []
    assert not (work_dir / "sources/collected_jobs").exists()
    assert not (work_dir / "outputs/batch").exists()
    assert not (work_dir / "outputs/selected").exists()
    assert tracker.exists()


def test_validate_cycle_reset_targets_rejects_non_allowlisted_target():
    work_dir = _work_dir()
    with pytest.raises(CleanupSafetyError):
        validate_cycle_reset_targets(work_dir, targets=["outputs/application_tracker.csv"])


def test_validate_cycle_reset_targets_rejects_parent_escape():
    work_dir = _work_dir()
    with pytest.raises(CleanupSafetyError):
        validate_cycle_reset_targets(work_dir, targets=["../outside"])


def test_reset_search_cycle_artifacts_reports_missing_targets():
    work_dir = _work_dir()

    result = reset_search_cycle_artifacts(project_root=work_dir)

    assert result["removed"] == []
    assert result["missing"] == ["sources/collected_jobs", "outputs/batch", "outputs/selected"]


def test_validate_cycle_reset_targets_rejects_absolute_target_path():
    work_dir = _work_dir()
    with pytest.raises(CleanupSafetyError):
        validate_cycle_reset_targets(work_dir, targets=["C:/tmp/outputs/batch"])
