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
# Analysis force trace: oddball col1 (marker); MVCnPRAC col4 (raw_force).
FORCE_COLUMN = "grip_force_au"
ODDBALL_TASKS = frozenset({"AODDBALL", "VODDBALL"})
DEFAULT_EXCLUDE_TASKS = ("MVCnPRAC",)
TASK_MODALITY_MAP = {"Aoddball": "aud", "Voddball": "vis"}
EXPECTED_TRIALS_PER_TASK = 150
EXPECTED_TRIALS_PER_RUN = 30
EXPECTED_RUNS_PER_TASK = 5
EXPECTED_GRIP_PER_LEVEL = 75
# Subject-tasks below this trial count after v3 cleaning are treated as mid-task aborts.
ABORT_TRIAL_THRESHOLD = 100
# Oddball grip files stored under OutsideScanner for these subjects (data relocation).
OUTSIDE_SCANNER_SUBJECTS = frozenset({"BAP166", "BAP171"})


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


def _gripforce_scanner_eligible(path: Path) -> bool:
    """InsideScanner for all subjects; OutsideScanner only for allowlisted subjects."""
    if "InsideScanner" in path.parts:
        return True
    if "OutsideScanner" not in path.parts:
        return False
    try:
        subject_id = parse_gripforce_filename(path)["subject_id"]
    except ValueError:
        return False
    return subject_id in OUTSIDE_SCANNER_SUBJECTS


def find_gripforce_files(
    gripforce_root: str | Path,
    *,
    sessions: tuple[int, ...] | None = (2, 3),
    exclude_tasks: tuple[str, ...] | None = DEFAULT_EXCLUDE_TASKS,
) -> list[Path]:
    """
    Return sorted gripforce CSV paths under InsideScanner folders.

    Also includes OutsideScanner oddball files for subjects in
    ``OUTSIDE_SCANNER_SUBJECTS`` (currently BAP166, BAP171).
    """
    root = Path(gripforce_root)
    if not root.is_dir():
        raise FileNotFoundError(f"gripforce_root not found: {root}")

    files = sorted(
        p for p in root.rglob(GRIPFORCE_GLOB) if _gripforce_scanner_eligible(p)
    )
    if sessions is not None:
        session_tokens = {f"ses-{s}" for s in sessions}
        files = [p for p in files if any(token in p.parts for token in session_tokens)]

    if exclude_tasks:
        excluded = {task.upper() for task in exclude_tasks}
        kept: list[Path] = []
        for path in files:
            try:
                task = parse_gripforce_filename(path)["task"].upper()
            except ValueError:
                warnings.warn(
                    f"Skipping unparseable gripforce filename: {path.name}",
                    stacklevel=2,
                )
                continue
            if task not in excluded:
                kept.append(path)
        files = kept
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


def _attach_force_column(df: pd.DataFrame, *, task: str) -> pd.DataFrame:
    """
    Map the 100 Hz force trace into ``FORCE_COLUMN``.

    Oddball CSVs store continuous force in col1 (``marker``); col4 (``raw_force``)
    is a per-trial block code. MVCnPRAC files use col4 as force.
    """
    out = df.copy()
    if task.upper() in ODDBALL_TASKS:
        out[FORCE_COLUMN] = out["marker"].astype(np.float64)
    else:
        out[FORCE_COLUMN] = out["raw_force"].astype(np.float64)
    return out


def _output_columns() -> tuple[str, ...]:
    return (
        "subject_id",
        "session_num",
        "run_num",
        "task",
        "trial_idx",
        *COLUMN_NAMES,
        FORCE_COLUMN,
        "source_file",
    )


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
    out = out[out["trial_idx"].isin(keep_trials)].copy()
    if out.empty:
        return out.reset_index(drop=True)

    trial_remap = {
        old: new for new, old in enumerate(sorted(keep_trials), start=1)
    }
    out["trial_idx"] = out["trial_idx"].map(trial_remap)
    return out.reset_index(drop=True)


def load_gripforce_file(
    path: str | Path,
    *,
    min_rows_per_trial: int = 100,
) -> pd.DataFrame:
    """Load one gripforce CSV, segment trials, attach run metadata."""
    csv_path = Path(path)
    meta = parse_gripforce_filename(csv_path)
    raw = _attach_force_column(_load_raw_gripforce_csv(csv_path), task=meta["task"])
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
        Columns: marker, elapsed_time, abs_time, raw_force, grip_force_au,
        trial_idx, subject_id, session_num, run_num, task, source_file.
    """
    files = find_gripforce_files(
        gripforce_root,
        sessions=sessions,
        exclude_tasks=exclude_tasks,
    )
    out_cols = _output_columns()
    if not files:
        return pd.DataFrame(columns=[c for c in out_cols if c != "source_file"])

    frames: list[pd.DataFrame] = []
    for path in files:
        try:
            frames.append(
                load_gripforce_file(path, min_rows_per_trial=min_rows_per_trial)
            )
        except (ValueError, OSError, pd.errors.ParserError) as exc:
            warnings.warn(f"Skipping {path}: {exc}", stacklevel=2)

    if not frames:
        return pd.DataFrame(columns=[c for c in out_cols if c != "source_file"])

    out = pd.concat(frames, ignore_index=True)
    return out[list(out_cols)]


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


def _grip_trial_keys(
    grip: pd.DataFrame,
    *,
    task_map: dict[str, str],
) -> pd.DataFrame:
    """One row per grip trial; fatigue-break runs merged when aggregating."""
    labeled = grip.assign(task_modality=grip["task"].map(task_map))
    trial_keys = ["subject_id", "session_num", "run_num", "trial_idx", "task_modality"]
    return labeled[trial_keys].drop_duplicates()


def _count_grip_trials(
    grip: pd.DataFrame,
    *,
    task_map: dict[str, str] | None = None,
    group_cols: tuple[str, ...] = ("subject_id", "task_modality"),
) -> pd.DataFrame:
    task_map = task_map or TASK_MODALITY_MAP
    if grip.empty:
        return pd.DataFrame(columns=[*group_cols, "grip_trials"])

    trials = _grip_trial_keys(grip, task_map=task_map)
    return (
        trials.groupby(list(group_cols), as_index=False)
        .size()
        .rename(columns={"size": "grip_trials"})
    )


def _count_beh_trials(
    beh: pd.DataFrame,
    *,
    group_cols: tuple[str, ...] = ("subject_id", "task_modality"),
) -> pd.DataFrame:
    if beh.empty:
        return pd.DataFrame(columns=[*group_cols, "beh_trials", "beh_high", "beh_low"])

    return (
        beh.groupby(list(group_cols), as_index=False)
        .agg(
            beh_trials=("trial_num", "count"),
            beh_high=("grip_level", lambda s: int((s == "high").sum())),
            beh_low=("grip_level", lambda s: int((s == "low").sum())),
        )
    )


def summarize_join_trial_counts(
    grip: pd.DataFrame,
    beh: pd.DataFrame,
    merged: pd.DataFrame | None = None,
    *,
    task_map: dict[str, str] | None = None,
) -> dict[str, int]:
    """
    Headline trial counts after merging fatigue-break runs within each session.

    Each row in ``beh`` is one trial. Grip trials are unique
    (subject, session, run, trial_idx) combinations rolled up across runs.
    """
    task_map = task_map or TASK_MODALITY_MAP

    beh_trials = len(beh)
    grip_trials = 0 if grip.empty else len(_grip_trial_keys(grip, task_map=task_map))

    out = {
        "behavioral_trials": beh_trials,
        "grip_trials_on_disk": grip_trials,
        "matched_trials": 0,
        "matched_samples": 0,
        "grip_samples": len(grip),
    }
    if merged is not None and not merged.empty:
        out["matched_samples"] = len(merged)
        out["matched_trials"] = merged.drop_duplicates(
            ["subject_id", "session_num", "run_num", "trial_idx"]
        ).shape[0]
    elif merged is not None:
        out["matched_samples"] = 0
        out["matched_trials"] = 0
    return out


def summarize_trial_coverage(
    grip: pd.DataFrame,
    beh: pd.DataFrame,
    *,
    feat: pd.DataFrame | None = None,
    task_map: dict[str, str] | None = None,
    group_cols: tuple[str, ...] = ("subject_id", "task_modality"),
) -> pd.DataFrame:
    """
    Compare merged trial counts per subject × task against the study design.

    Fatigue-break runs (typically 5 × 30 trials) are **merged** before counting.
    The unit of interest is the **trial**, not the run file.

    Interpretation
    --------------
    * ``beh_complete`` — full design: 150 trials with 75 high / 75 low grip.
    * ``drop_aborted`` — subject-task likely stopped mid-collection (``beh_trials``
      below ``ABORT_TRIAL_THRESHOLD``). Drop at the participant-task level.
    * ``beh_retainable`` — subject-task with enough behavioral data to keep; individual
      missing responses are already handled by v3 trial filters.
    * ``grip_has_files`` / ``grip_trials`` — grip trials on disk (runs merged),
      separate from behavioral quality.
    """
    task_map = task_map or TASK_MODALITY_MAP

    beh_summary = _count_beh_trials(beh, group_cols=group_cols)
    grip_summary = _count_grip_trials(grip, task_map=task_map, group_cols=group_cols)

    out = beh_summary.merge(grip_summary, on=list(group_cols), how="outer")
    out["beh_trials"] = out["beh_trials"].fillna(0).astype(np.int64)
    out["beh_high"] = out["beh_high"].fillna(0).astype(np.int64)
    out["beh_low"] = out["beh_low"].fillna(0).astype(np.int64)
    out["grip_trials"] = out["grip_trials"].fillna(0).astype(np.int64)

    if feat is not None and not feat.empty:
        if "task_modality" not in feat.columns:
            feat_labeled = feat.merge(
                grip.assign(task_modality=grip["task"].map(task_map))[
                    ["subject_id", "session_num", "run_num", "trial_idx", "task_modality"]
                ].drop_duplicates(),
                on=["subject_id", "session_num", "run_num", "trial_idx"],
                how="left",
            )
        else:
            feat_labeled = feat
        feat_trials = (
            feat_labeled.groupby(list(group_cols), as_index=False)
            .size()
            .rename(columns={"size": "feat_trials"})
        )
        out = out.merge(feat_trials, on=list(group_cols), how="left")
        out["feat_trials"] = out["feat_trials"].fillna(0).astype(np.int64)
    else:
        out["feat_trials"] = np.int64(0)

    out["beh_complete"] = (
        (out["beh_trials"] == EXPECTED_TRIALS_PER_TASK)
        & (out["beh_high"] == EXPECTED_GRIP_PER_LEVEL)
        & (out["beh_low"] == EXPECTED_GRIP_PER_LEVEL)
    )
    out["retention_pct"] = 100.0 * out["beh_trials"] / EXPECTED_TRIALS_PER_TASK
    out["drop_aborted"] = out["beh_trials"] < ABORT_TRIAL_THRESHOLD
    out["beh_retainable"] = ~out["drop_aborted"]
    out["grip_has_files"] = out["grip_trials"] > 0
    out["grip_complete"] = out["grip_trials"] == EXPECTED_TRIALS_PER_TASK
    out["feat_complete"] = out["feat_trials"] == EXPECTED_TRIALS_PER_TASK
    out["analysis_ready"] = (
        out["beh_retainable"] & out["grip_has_files"] & (out["feat_trials"] > 0)
    )
    out["beh_minus_grip"] = out["beh_trials"] - out["grip_trials"]
    out["grip_minus_feat"] = out["grip_trials"] - out["feat_trials"]
    out["feat_match_pct"] = np.where(
        out["beh_trials"] > 0,
        100.0 * out["feat_trials"] / out["beh_trials"],
        np.nan,
    )
    return out.sort_values(list(group_cols)).reset_index(drop=True)


def summarize_grip_trial_counts(
    grip: pd.DataFrame,
    *,
    group_cols: tuple[str, ...] = ("subject_id", "session_num", "task_modality"),
    task_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Trial counts from gripforce, merging fatigue-break runs via ``group_cols``."""
    return _count_grip_trials(grip, task_map=task_map, group_cols=group_cols)


def grip_attrition_funnel(coverage: pd.DataFrame) -> pd.DataFrame:
    """
    Stage counts for a CONSORT-style grip force analysis flow diagram.

    Reports both subject-task rows and **merged trial totals** at each stage.

    Notes
    -----
    * **No grip files** — entire subject×task blocks with zero grip CSVs on disk
      (sums behavioral trials, not per-trial join failures).
    * **Partial grip** — subject×task has some grip files but fewer grip trials
      than behavioral trials (typically 1 run ≈ 30 trials vs ~150 behavioral).
    """
    retainable = coverage.loc[coverage["beh_retainable"]]
    retainable_beh = int(retainable["beh_trials"].sum())

    no_grip = retainable.loc[~retainable["grip_has_files"]]
    partial_grip = retainable.loc[
        retainable["grip_has_files"] & (retainable["beh_minus_grip"] > 0)
    ]
    with_grip = retainable.loc[retainable["grip_has_files"]]
    analysis = coverage.loc[coverage["analysis_ready"]]

    no_grip_beh = int(no_grip["beh_trials"].sum())
    partial_beh = int(partial_grip["beh_minus_grip"].sum())
    grip_on_disk = int(with_grip["grip_trials"].sum())
    feat_loss = int(with_grip["grip_minus_feat"].sum())
    analysis_trials = int(analysis["feat_trials"].sum())

    def pct(n: int) -> float | None:
        if retainable_beh == 0:
            return None
        return round(100.0 * n / retainable_beh, 1)

    rows = [
        {
            "stage": "Oddball subject-tasks in behavioral v3",
            "n_subject_tasks": len(coverage),
            "n_trials": int(coverage["beh_trials"].sum()),
            "pct_of_retainable_beh": None,
            "note": "aud + vis; runs merged into trial counts",
        },
        {
            "stage": "Excluded: aborted mid-task",
            "n_subject_tasks": int(coverage["drop_aborted"].sum()),
            "n_trials": int(
                coverage.loc[coverage["drop_aborted"], "beh_trials"].sum()
            ),
            "pct_of_retainable_beh": None,
            "note": f"beh_trials < {ABORT_TRIAL_THRESHOLD}",
        },
        {
            "stage": "Retainable subject-tasks",
            "n_subject_tasks": len(retainable),
            "n_trials": retainable_beh,
            "pct_of_retainable_beh": 100.0,
            "note": "individual missed trials already removed in v3",
        },
        {
            "stage": "No grip files (entire subject×task)",
            "n_subject_tasks": len(no_grip),
            "n_trials": no_grip_beh,
            "pct_of_retainable_beh": pct(no_grip_beh),
            "note": "zero grip CSVs found; all behavioral trials in block excluded",
        },
        {
            "stage": "Partial grip (behavioral > on-disk grip)",
            "n_subject_tasks": len(partial_grip),
            "n_trials": partial_beh,
            "pct_of_retainable_beh": pct(partial_beh),
            "note": "some grip files exist but fewer trials than behavioral (often 1 run ≈ 30 trials)",
        },
        {
            "stage": "Grip trials on disk",
            "n_subject_tasks": len(with_grip),
            "n_trials": grip_on_disk,
            "pct_of_retainable_beh": pct(grip_on_disk),
            "note": "fatigue-break runs merged per session; retainable subject-tasks only",
        },
        {
            "stage": "Feature extraction loss",
            "n_subject_tasks": int(
                (with_grip["grip_minus_feat"] > 0).sum()
            ),
            "n_trials": feat_loss,
            "pct_of_retainable_beh": pct(feat_loss),
            "note": "grip trials present but spectral features not extracted (short epochs, etc.)",
        },
        {
            "stage": "Analysis set (trial features extracted)",
            "n_subject_tasks": len(analysis),
            "n_trials": analysis_trials,
            "pct_of_retainable_beh": pct(analysis_trials),
            "note": "primary grip force modeling cohort",
        },
    ]
    return pd.DataFrame(rows)
