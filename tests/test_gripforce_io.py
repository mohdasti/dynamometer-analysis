"""Tests for gripforce trial segmentation loader."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gripforce_io import (  # noqa: E402
    _assign_trial_idx,
    EXPECTED_TRIALS_PER_TASK,
    FORCE_COLUMN,
    filter_behavioral_trials,
    find_gripforce_files,
    grip_attrition_funnel,
    load_gripforce_file,
    load_gripforce_long,
    parse_gripforce_filename,
    summarize_join_trial_counts,
    summarize_trial_coverage,
)

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "BAP data"
FIXTURE_FILE = (
    FIXTURE_ROOT
    / "sub-BAP103/ses-3/InsideScanner/subjectBAP103_MVCnPRAC_session3_run1_7_8_12_44_gripforce.csv"
)


def test_parse_gripforce_filename():
    meta = parse_gripforce_filename(FIXTURE_FILE)
    assert meta == {
        "subject_id": "BAP103",
        "session_num": 3,
        "run_num": 1,
        "task": "MVCnPRAC",
    }


def test_assign_trial_idx_detects_resets():
    elapsed = np.array([0.01, 0.02, 0.03, 0.01, 0.02, 0.03, 0.01])
    assert list(_assign_trial_idx(elapsed)) == [1, 1, 1, 2, 2, 2, 3]


def test_load_gripforce_file_drops_short_epochs(tmp_path):
    path = tmp_path / "subjectBAP001_Aoddball_session2_run1_1_1_12_0_gripforce.csv"
    rows = []
    # trial 1: 50 rows (drop)
    rows.extend(f"100.0,{0.01 * i:.6f},{1000 + 0.01 * i:.6f},1" for i in range(1, 51))
    # trial 2: 120 rows (keep)
    rows.extend(f"200.0,{0.01 * i:.6f},{2000 + 0.01 * i:.6f},2" for i in range(1, 121))
    path.write_text("\n".join(rows) + "\n")

    df = load_gripforce_file(path, min_rows_per_trial=100)
    assert set(df["trial_idx"]) == {1}  # trial 1 dropped; kept epoch renumbered to 1
    assert len(df) == 120
    assert (df[FORCE_COLUMN] == 200.0).all()
    assert df["subject_id"].iloc[0] == "BAP001"
    assert df["session_num"].iloc[0] == 2
    assert df["run_num"].iloc[0] == 1
    assert df["task"].iloc[0] == "Aoddball"


def test_load_gripforce_long_excludes_mvcnprac():
    df = load_gripforce_long(FIXTURE_ROOT, min_rows_per_trial=50, sessions=None)
    assert "MVCnPRAC" not in set(df["task"])
    assert set(df["task"]) <= {"Aoddball", "Voddball"}


def test_load_gripforce_long_on_fixtures():
    df = load_gripforce_long(FIXTURE_ROOT, min_rows_per_trial=50, sessions=None)
    assert not df.empty
    assert {"subject_id", "session_num", "run_num", "task", "trial_idx"}.issubset(df.columns)
    assert df["subject_id"].nunique() >= 1
    assert (df["trial_idx"] >= 1).all()


def test_filter_behavioral_trials():
    beh = pd.DataFrame(
        {
            "task_modality": ["Aoddball", "Voddball", "MVCnPRAC"],
            "x": [1, 2, 3],
        }
    )
    out = filter_behavioral_trials(beh)
    assert len(out) == 2
    assert "MVCnPRAC" not in set(out["task_modality"])


def test_find_gripforce_files_session_filter():
    all_files = find_gripforce_files(FIXTURE_ROOT, sessions=None)
    ses3_only = find_gripforce_files(FIXTURE_ROOT, sessions=(3,))
    assert len(all_files) >= len(ses3_only)
    assert all("ses-3" in str(p) for p in ses3_only)


def test_parse_gripforce_filename_invalid():
    with pytest.raises(ValueError, match="does not match"):
        parse_gripforce_filename(Path("bad_filename.csv"))


def test_segment_run_renumbers_kept_trials_sequentially(tmp_path):
    path = tmp_path / "subjectBAP001_Aoddball_session2_run1_1_1_12_0_gripforce.csv"
    rows = []
    rows.extend(f"100.0,{0.01 * i:.6f},{1000 + 0.01 * i:.6f},1" for i in range(1, 51))
    rows.extend(f"200.0,{0.01 * i:.6f},{2000 + 0.01 * i:.6f},2" for i in range(1, 121))
    rows.extend(f"300.0,{0.01 * i:.6f},{3000 + 0.01 * i:.6f},3" for i in range(1, 121))
    path.write_text("\n".join(rows) + "\n")

    df = load_gripforce_file(path, min_rows_per_trial=100)
    assert list(df["trial_idx"].unique()) == [1, 2]
    assert df.groupby("trial_idx")[FORCE_COLUMN].mean().tolist() == [200.0, 300.0]


def test_oddball_grip_force_au_comes_from_marker_not_raw_force(tmp_path):
    path = tmp_path / "subjectBAP001_Voddball_session2_run1_1_1_12_0_gripforce.csv"
    force = 1500.0
    trial_code = 7.0
    rows = [
        f"{force:.1f},{0.01 * i:.6f},{1000 + 0.01 * i:.6f},{trial_code}"
        for i in range(1, 121)
    ]
    path.write_text("\n".join(rows) + "\n")

    df = load_gripforce_file(path, min_rows_per_trial=100)

    assert (df[FORCE_COLUMN] == force).all()
    assert (df["raw_force"] == trial_code).all()
    assert df[FORCE_COLUMN].nunique() > 1 or force != trial_code


def test_summarize_trial_coverage_counts():
    grip = pd.DataFrame(
        {
            "subject_id": ["BAP001", "BAP001", "BAP001"],
            "session_num": [2, 2, 2],
            "run_num": [1, 1, 2],
            "task": ["Aoddball", "Aoddball", "Aoddball"],
            "trial_idx": [1, 2, 1],
            FORCE_COLUMN: [1.0, 2.0, 3.0],
        }
    )
    beh = pd.DataFrame(
        {
            "subject_id": ["BAP001", "BAP001", "BAP001"],
            "task_modality": ["aud", "aud", "aud"],
            "session_num": [2, 2, 2],
            "run_num": [1, 1, 2],
            "trial_num": [1, 2, 1],
            "grip_level": ["high", "high", "low"],
        }
    )
    out = summarize_trial_coverage(grip, beh)
    assert len(out) == 1
    assert out.loc[0, "beh_trials"] == 3
    assert out.loc[0, "grip_trials"] == 3
    assert out.loc[0, "beh_complete"] is np.bool_(False)
    assert out.loc[0, "drop_aborted"] is np.bool_(True)
    assert out.loc[0, "beh_retainable"] is np.bool_(False)
    assert out.loc[0, "grip_has_files"] is np.bool_(True)
    assert EXPECTED_TRIALS_PER_TASK == 150


def test_grip_attrition_funnel_stages():
    coverage = pd.DataFrame(
        {
            "beh_trials": [100, 80, 50, 90],
            "grip_trials": [100, 0, 0, 90],
            "feat_trials": [100, 0, 0, 90],
            "beh_retainable": [True, True, False, True],
            "drop_aborted": [False, False, True, False],
            "grip_has_files": [True, False, False, True],
            "analysis_ready": [True, False, False, True],
        }
    )
    funnel = grip_attrition_funnel(coverage)
    assert list(funnel["stage"]) == [
        "Oddball subject-tasks in behavioral v3",
        "Excluded: aborted mid-task",
        "Retainable subject-tasks",
        "Missing gripforce trials on disk",
        "Gripforce trials on disk",
        "Analysis set (trial features extracted)",
    ]
    assert funnel.loc[
        funnel["stage"] == "Analysis set (trial features extracted)", "n_trials"
    ].iloc[0] == 190


def test_summarize_join_trial_counts_merges_runs():
    grip = pd.DataFrame(
        {
            "subject_id": ["BAP001", "BAP001"],
            "session_num": [2, 2],
            "run_num": [1, 2],
            "task": ["Aoddball", "Aoddball"],
            "trial_idx": [1, 1],
            FORCE_COLUMN: [1.0, 2.0],
        }
    )
    beh = pd.DataFrame(
        {
            "subject_id": ["BAP001", "BAP001"],
            "task_modality": ["aud", "aud"],
            "session_num": [2, 2],
            "run_num": [1, 2],
            "trial_num": [1, 1],
        }
    )
    merged = grip.merge(
        beh,
        left_on=["subject_id", "session_num", "run_num", "trial_idx"],
        right_on=["subject_id", "session_num", "run_num", "trial_num"],
        how="inner",
    )
    counts = summarize_join_trial_counts(grip, beh, merged)
    assert counts["behavioral_trials"] == 2
    assert counts["grip_trials_on_disk"] == 2
    assert counts["matched_trials"] == 2
