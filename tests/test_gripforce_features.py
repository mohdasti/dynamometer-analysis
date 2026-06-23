"""Tests for trial-level grip force spectral features."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gripforce_features import (  # noqa: E402
    GRIP_SAMPLE_RATE_HZ,
    extract_trial_spectral_features,
)


def _make_beh(
    *,
    subject_id: str = "BAP001",
    session_num: int = 2,
    run_num: int = 1,
    trial_num: int = 1,
    grip_targ_prop_mvc: float = 0.5,
    mvc: float = 10.0,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "subject_id": [subject_id],
            "session_num": [session_num],
            "run_num": [run_num],
            "trial_num": [trial_num],
            "grip_targ_prop_mvc": [grip_targ_prop_mvc],
            "mvc": [mvc],
        }
    )


def _make_grip_from_force(
    force: np.ndarray,
    *,
    subject_id: str = "BAP001",
    session_num: int = 2,
    run_num: int = 1,
    trial_idx: int = 1,
) -> pd.DataFrame:
    n = len(force)
    return pd.DataFrame(
        {
            "subject_id": subject_id,
            "session_num": session_num,
            "run_num": run_num,
            "trial_idx": trial_idx,
            "elapsed_time": np.arange(1, n + 1) * 0.01,
            "grip_force_au": force,
        }
    )


def test_constant_force_yields_zero_rms_and_low_band_power():
    target_force = 5.0
    n = 512
    grip = _make_grip_from_force(np.full(n, target_force))
    beh = _make_beh(grip_targ_prop_mvc=0.5, mvc=10.0)

    out = extract_trial_spectral_features(grip, beh)

    assert len(out) == 1
    assert out["rms_error"].iloc[0] == pytest.approx(0.0, abs=1e-12)
    assert out["pow_05_3hz"].iloc[0] == pytest.approx(0.0, abs=1e-10)
    assert out["pow_8_12hz"].iloc[0] == pytest.approx(0.0, abs=1e-10)


def test_tracking_band_picks_up_slow_oscillation():
    fs = GRIP_SAMPLE_RATE_HZ
    duration_s = 10.0
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    target_force = 8.0
    amplitude = 0.2
    freq_hz = 1.0
    raw_force = target_force * (1.0 + amplitude * np.sin(2 * np.pi * freq_hz * t))
    grip = _make_grip_from_force(raw_force)
    beh = _make_beh(grip_targ_prop_mvc=0.4, mvc=20.0)

    out = extract_trial_spectral_features(grip, beh)
    row = out.iloc[0]

    assert row["rms_error"] > 0.1
    assert row["pow_05_3hz"] > row["pow_8_12hz"]


def test_tremor_band_picks_up_fast_oscillation():
    fs = GRIP_SAMPLE_RATE_HZ
    duration_s = 10.0
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    target_force = 8.0
    amplitude = 0.1
    freq_hz = 10.0
    raw_force = target_force * (1.0 + amplitude * np.sin(2 * np.pi * freq_hz * t))
    grip = _make_grip_from_force(raw_force)
    beh = _make_beh(grip_targ_prop_mvc=0.4, mvc=20.0)

    out = extract_trial_spectral_features(grip, beh)
    row = out.iloc[0]

    assert row["pow_8_12hz"] > row["pow_05_3hz"]


def test_multiple_trials_return_one_row_each():
    fs = GRIP_SAMPLE_RATE_HZ
    n = int(fs * 5)
    t = np.arange(n) / fs
    target = 6.0

    trial1 = _make_grip_from_force(
        target * (1 + 0.15 * np.sin(2 * np.pi * 1.0 * t)),
        trial_idx=1,
    )
    trial2 = _make_grip_from_force(
        target * (1 + 0.15 * np.sin(2 * np.pi * 10.0 * t)),
        trial_idx=2,
    )
    grip = pd.concat([trial1, trial2], ignore_index=True)
    beh = pd.DataFrame(
        {
            "subject_id": ["BAP001", "BAP001"],
            "session_num": [2, 2],
            "run_num": [1, 1],
            "trial_num": [1, 2],
            "grip_targ_prop_mvc": [0.6, 0.6],
            "mvc": [10.0, 10.0],
        }
    )

    out = extract_trial_spectral_features(grip, beh)

    assert len(out) == 2
    assert set(out["trial_idx"]) == {1, 2}
    t1 = out.loc[out["trial_idx"] == 1].iloc[0]
    t2 = out.loc[out["trial_idx"] == 2].iloc[0]
    assert t1["pow_05_3hz"] > t1["pow_8_12hz"]
    assert t2["pow_8_12hz"] > t2["pow_05_3hz"]


def test_highpass_removes_slow_drift_before_tremor_extraction():
    fs = GRIP_SAMPLE_RATE_HZ
    duration_s = 10.0
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    target_force = 8.0
    slow_drift = 0.3 * t / duration_s
    tremor = 0.08 * np.sin(2 * np.pi * 10.0 * t)
    raw_force = target_force * (1.0 + slow_drift + tremor)
    grip = _make_grip_from_force(raw_force)
    beh = _make_beh(grip_targ_prop_mvc=0.4, mvc=20.0)

    out = extract_trial_spectral_features(grip, beh)
    row = out.iloc[0]

    assert row["pow_8_12hz"] > row["pow_05_3hz"]


def test_missing_behavioral_columns_raises():
    grip = _make_grip_from_force(np.ones(200))
    beh = pd.DataFrame({"subject_id": ["BAP001"], "session_num": [2], "run_num": [1]})
    with pytest.raises(ValueError, match="beh missing columns"):
        extract_trial_spectral_features(grip, beh)
