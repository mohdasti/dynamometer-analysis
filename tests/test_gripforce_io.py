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
    find_gripforce_files,
    load_gripforce_file,
    load_gripforce_long,
    parse_gripforce_filename,
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
    rows.extend(f"0,{0.01 * i:.6f},{1000 + 0.01 * i:.6f},2.0" for i in range(1, 51))
    # trial 2: 120 rows (keep)
    rows.extend(f"0,{0.01 * i:.6f},{2000 + 0.01 * i:.6f},3.0" for i in range(1, 121))
    path.write_text("\n".join(rows) + "\n")

    df = load_gripforce_file(path, min_rows_per_trial=100)
    assert set(df["trial_idx"]) == {2}  # trial 1 dropped; kept epoch keeps original index
    assert len(df) == 120
    assert df["subject_id"].iloc[0] == "BAP001"
    assert df["session_num"].iloc[0] == 2
    assert df["run_num"].iloc[0] == 1
    assert df["task"].iloc[0] == "Aoddball"


def test_load_gripforce_long_on_fixtures():
    df = load_gripforce_long(FIXTURE_ROOT, min_rows_per_trial=50, sessions=None)
    assert not df.empty
    assert {"subject_id", "session_num", "run_num", "task", "trial_idx"}.issubset(df.columns)
    assert df["subject_id"].nunique() >= 2
    assert (df["trial_idx"] >= 1).all()


def test_find_gripforce_files_session_filter():
    all_files = find_gripforce_files(FIXTURE_ROOT, sessions=None)
    ses3_only = find_gripforce_files(FIXTURE_ROOT, sessions=(3,))
    assert len(all_files) >= len(ses3_only)
    assert all("ses-3" in str(p) for p in ses3_only)


def test_parse_gripforce_filename_invalid():
    with pytest.raises(ValueError, match="does not match"):
        parse_gripforce_filename(Path("bad_filename.csv"))
