from pathlib import Path
import uuid

from job_search_mvp.paths import OUTPUTS_DIR, resolve_data_dir


def _work_dir() -> Path:
    path = OUTPUTS_DIR / "pytest_work" / "paths" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_resolve_data_dir_prefers_nested_data_when_project_root_has_job_sources_file():
    root = _work_dir()
    (root / "job_sources.yaml").write_text("sources: []\n", encoding="utf-8")
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "career_preferences.yaml").write_text("career_preferences: {}\n", encoding="utf-8")

    assert resolve_data_dir(root) == data.resolve()


def test_resolve_data_dir_accepts_direct_data_folder():
    data = _work_dir() / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "career_preferences.yaml").write_text("career_preferences: {}\n", encoding="utf-8")

    assert resolve_data_dir(data) == data.resolve()
