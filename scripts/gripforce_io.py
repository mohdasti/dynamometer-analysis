"""Load and segment BAP in-scanner 100 Hz dynamometer gripforce CSVs."""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

GRIPFORCE_GLOB = "*_gripforce.csv"
GRIPFORCE_FILENAME_RE = re.compile(
    r"subject(?P<subject>BAP\d+)_(?P<task>[A-Za-z0-9]+)_session(?P<session>\d+)_"
    r"run(?P<run>\d+)_(?P<month>\d+)_(?P<day>\d+)_(?P<hour>\d+)_(?P<minute>\d+)_gripforce\.csv$",
    re.IGNORECASE,
)

COLUMN_NAMES = ("marker", "elapsed_time", "abs_time", "raw_force")
DEFAULT_EXCLUDE_TASKS = ("MVCnPRAC",)


def parse_gripforce_filename(path: Path) -> dict[str, str | int]:
    """Extract subject_id, session_num, run_num, and task from a gripforce filename."""
    match = GRIPFORCE_FILENAME_RE.search(path.name)
    if not match:
        raise ValueError(f"Filename does not match expected pattern: {path.name}")

    groups = match.groupdict()
    return {
        "subject_id": groups["subject"].upper(),
        "session_num": int(groups["session"]),
        "run_num": int(groups["run"]),
        "task": groups["task"],
    }


def find_gripforce_files(
    gripforce_root: str | Path,
    *,
    sessions: tuple[int, ...] | None = (2, 3),
    exclude_tasks: tuple[str, ...] | None = DEFAULT_EXCLUDE_TASKS,
) -> list[Path]:
    """Return sorted gripforce CSV paths under InsideScanner folders."""
    root = Path(gripforce_root)
    if not root.is_dir():
        raise FileNotFoundError(f"gripforce_root not found: {root}")

    files = sorted(p for p in root.rglob(GRIPFORCE_GLOB) if "InsideScanner" in p.parts)
    if sessions is not None:
        session_tokens = {f"ses-{s}" for s in sessions}
        files = [p for p in files if any(token in p.parts for token in session_tokens)]

    if exclude_tasks:
        excluded = {task.upper() for task in exclude_tasks}
        files = [
            p
            for p in files
            if parse_gripforce_filename(p)["task"].upper() not in excluded
        ]
    return files


def _load_raw_gripforce_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        header=None,
        names=COLUMN_NAMES,
        usecols=range(4),
        dtype={
            "marker": np.int64,
            "elapsed_time": np.float64,
            "abs_time": np.float64,
            "raw_force": np.float64,
        },
    )
    if df.empty:
        return df

    if df["elapsed_time"].isna().any():
        raise ValueError(f"NaN values in elapsed_time: {path}")

    return df


def _assign_trial_idx(elapsed_time: np.ndarray) -> np.ndarray:
    """Label rows with sequential trial_idx; increment when elapsed_time resets."""
    n = len(elapsed_time)
    if n == 0:
        return np.array([], dtype=np.int64)

    trial_idx = np.ones(n, dtype=np.int64)
    if n == 1:
        return trial_idx

    resets = elapsed_time[1:] < elapsed_time[:-1]
    trial_idx[1:] = np.cumsum(resets) + 1
    return trial_idx


def _segment_run(
    df: pd.DataFrame,
    *,
    min_rows_per_trial: int,
) -> pd.DataFrame:
    """Add trial_idx and drop truncated trial epochs."""
    if df.empty:
        df = df.copy()
        df["trial_idx"] = pd.Series(dtype=np.int64)
        return df

    out = df.copy()
    out["trial_idx"] = _assign_trial_idx(out["elapsed_time"].to_numpy())

    trial_counts = out.groupby("trial_idx", sort=True).size()
    keep_trials = trial_counts[trial_counts >= min_rows_per_trial].index
    return out[out["trial_idx"].isin(keep_trials)].reset_index(drop=True)


def load_gripforce_file(
    path: str | Path,
    *,
    min_rows_per_trial: int = 100,
) -> pd.DataFrame:
    """Load one gripforce CSV, segment trials, attach run metadata."""
    csv_path = Path(path)
    meta = parse_gripforce_filename(csv_path)
    raw = _load_raw_gripforce_csv(csv_path)
    segmented = _segment_run(raw, min_rows_per_trial=min_rows_per_trial)

    for key, value in meta.items():
        segmented[key] = value
    segmented["source_file"] = str(csv_path)
    return segmented


def load_gripforce_long(
    gripforce_root: str | Path,
    *,
    min_rows_per_trial: int = 100,
    sessions: tuple[int, ...] | None = (2, 3),
    exclude_tasks: tuple[str, ...] | None = DEFAULT_EXCLUDE_TASKS,
) -> pd.DataFrame:
    """
    Load all in-scanner gripforce CSVs into one long-format DataFrame.

    Parameters
    ----------
    gripforce_root:
        Path to `BAP data/` (contains `sub-BAP###/ses-N/InsideScanner/`).
    min_rows_per_trial:
        Drop trial epochs with fewer rows (default 100 ≈ 1 s at 100 Hz).
    sessions:
        Include only these session folders (default (2, 3)). Pass None for all.
    exclude_tasks:
        Task names to skip (default: MVCnPRAC calibration/practice runs).

    Returns
    -------
    pd.DataFrame
        Columns: marker, elapsed_time, abs_time, raw_force, trial_idx,
        subject_id, session_num, run_num, task, source_file.
    """
    files = find_gripforce_files(
        gripforce_root,
        sessions=sessions,
        exclude_tasks=exclude_tasks,
    )
    if not files:
        return pd.DataFrame(
            columns=[
                *COLUMN_NAMES,
                "trial_idx",
                "subject_id",
                "session_num",
                "run_num",
                "task",
                "source_file",
            ]
        )

    frames: list[pd.DataFrame] = []
    for path in files:
        try:
            frames.append(
                load_gripforce_file(path, min_rows_per_trial=min_rows_per_trial)
            )
        except (ValueError, OSError, pd.errors.ParserError) as exc:
            warnings.warn(f"Skipping {path}: {exc}", stacklevel=2)

    if not frames:
        return pd.DataFrame(
            columns=[
                *COLUMN_NAMES,
                "trial_idx",
                "subject_id",
                "session_num",
                "run_num",
                "task",
                "source_file",
            ]
        )

    out = pd.concat(frames, ignore_index=True)
    col_order = [
        "subject_id",
        "session_num",
        "run_num",
        "task",
        "trial_idx",
        *COLUMN_NAMES,
        "source_file",
    ]
    return out[col_order]


def filter_behavioral_trials(
    beh: pd.DataFrame,
    *,
    task_col: str = "task_modality",
    exclude_tasks: tuple[str, ...] | None = DEFAULT_EXCLUDE_TASKS,
) -> pd.DataFrame:
    """Drop behavioral rows for excluded tasks (default: MVCnPRAC)."""
    if not exclude_tasks:
        return beh
    excluded = set(exclude_tasks)
    return beh.loc[~beh[task_col].isin(excluded)].reset_index(drop=True)
