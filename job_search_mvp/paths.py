"""Shared filesystem locations for the local prototype package."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
ASSETS_DIR = PACKAGE_DIR / "assets"

DATA_FILE_NAMES = {
    "career_preferences.yaml",
    "consultancy_static_profile.yaml",
    "cv_generation_policy.yaml",
    "employee_profile.yaml",
    "experience_database.yaml",
    "job_sources.yaml",
    "tool_aliases.yaml",
}


def resolve_project_root(path: str | Path | None = None) -> Path:
    """Resolve a user-supplied project or data path back to the project root."""
    if path in [None, ""]:
        return PROJECT_ROOT
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if candidate.name == "data" and candidate.is_dir():
        return candidate.parent
    return candidate


def resolve_data_dir(path: str | Path | None = None) -> Path:
    """Accept either the new data directory or the old project-root data-dir."""
    if path in [None, ""]:
        return DATA_DIR
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if _looks_like_data_dir(candidate):
        return candidate
    nested = candidate / "data"
    if _looks_like_data_dir(nested):
        return nested
    return candidate


def resolve_config_path(path: str | Path, package_root: Path | None = None) -> Path:
    """Resolve config files from explicit paths, project root, or data/."""
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw
    root = (package_root or PROJECT_ROOT).resolve()
    root_path = root / raw
    if root_path.exists():
        return root_path
    data_path = root / "data" / raw
    if data_path.exists():
        return data_path
    return root_path


def default_assets_dir() -> Path:
    return ASSETS_DIR


def _looks_like_data_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any((path / name).exists() for name in DATA_FILE_NAMES)
