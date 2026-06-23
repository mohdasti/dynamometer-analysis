"""Shared task inclusion rules for gripforce and behavioral analysis."""

from __future__ import annotations

EXCLUDED_TASKS: frozenset[str] = frozenset({"MVCnPRAC"})
ANALYSIS_TASKS: frozenset[str] = frozenset({"Aoddball", "Voddball"})


def is_analysis_task(task: str) -> bool:
    return task not in EXCLUDED_TASKS


def filter_tasks(
    tasks: frozenset[str] | tuple[str, ...] | None = None,
    *,
    exclude: frozenset[str] | tuple[str, ...] | None = None,
) -> frozenset[str]:
    """Return allowed task names; defaults to ANALYSIS_TASKS (excludes MVCnPRAC)."""
    if tasks is not None:
        allowed = frozenset(tasks)
    else:
        allowed = ANALYSIS_TASKS
    excluded = frozenset(exclude if exclude is not None else EXCLUDED_TASKS)
    return allowed - excluded
