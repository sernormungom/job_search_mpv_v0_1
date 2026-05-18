"""Safe cleanup helpers for resetting generated search-cycle artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, List, Sequence

from .paths import resolve_project_root

DEFAULT_CYCLE_RESET_TARGETS: Sequence[str] = (
    "sources/collected_jobs",
    "outputs/batch",
    "outputs/selected",
)


class CleanupSafetyError(RuntimeError):
    """Raised when requested cleanup targets are outside the allowed safe scope."""


def reset_search_cycle_artifacts(
    project_root: str | Path | None = None,
    targets: Iterable[str | Path] | None = None,
    dry_run: bool = False,
) -> dict[str, List[str]]:
    """Delete generated cycle artifact folders under project root.

    By default this removes only:
    - sources/collected_jobs
    - outputs/batch
    - outputs/selected

    The tracker and maintained data files are intentionally out of scope.
    """
    root = resolve_project_root(project_root).resolve()
    validated_targets = validate_cycle_reset_targets(root, targets)
    removed: List[str] = []
    missing: List[str] = []

    for path in validated_targets:
        rel = path.relative_to(root).as_posix()
        if not path.exists():
            missing.append(rel)
            continue
        if dry_run:
            removed.append(rel)
            continue
        shutil.rmtree(path)
        removed.append(rel)

    return {"removed": removed, "missing": missing}


def validate_cycle_reset_targets(
    project_root: str | Path | None = None,
    targets: Iterable[str | Path] | None = None,
) -> List[Path]:
    """Resolve and validate cleanup targets against the default allowlist."""
    root = resolve_project_root(project_root).resolve()
    raw_targets = list(targets) if targets is not None else list(DEFAULT_CYCLE_RESET_TARGETS)
    allowed = {_normalize_relative(t) for t in DEFAULT_CYCLE_RESET_TARGETS}
    seen: set[str] = set()
    validated: List[Path] = []

    for raw in raw_targets:
        rel = _normalize_relative(raw)
        if rel not in allowed:
            raise CleanupSafetyError(
                f"Refusing cleanup target '{rel}'. Allowed targets: {sorted(allowed)}"
            )
        if rel in seen:
            continue
        target = (root / rel).resolve()
        _assert_within_root(root, target)
        validated.append(target)
        seen.add(rel)

    return validated


def _normalize_relative(path: str | Path) -> str:
    p = Path(path).expanduser()
    if p.is_absolute():
        raise CleanupSafetyError(f"Cleanup target must be relative to project root, got absolute path: {p}")
    if ".." in p.parts:
        raise CleanupSafetyError(f"Invalid cleanup target path: {path}")
    parts = [part for part in p.parts if part not in ("", ".")]
    rel = Path(*parts).as_posix()
    if not rel:
        raise CleanupSafetyError(f"Invalid cleanup target path: {path}")
    return rel


def _assert_within_root(root: Path, candidate: Path) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CleanupSafetyError(f"Cleanup target escapes project root: {candidate}") from exc
