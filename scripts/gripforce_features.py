"""Trial-level grip force normalization and spectral feature extraction."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import signal
from scipy.integrate import trapezoid

from gripforce_io import FORCE_COLUMN

GRIP_SAMPLE_RATE_HZ = 100.0
TRACKING_BAND_HZ = (0.5, 3.0)
TREMOR_BAND_HZ = (8.0, 12.0)
HIGHPASS_CUTOFF_HZ = 0.5
HIGHPASS_FILTER_ORDER = 4

TRIAL_GROUP_COLS = ("subject_id", "session_num", "run_num", "trial_idx")
BEH_JOIN_COLS = ("subject_id", "session_num", "run_num")
BEH_TRIAL_COL = "trial_num"
TARGET_PROP_COL = "grip_targ_prop_mvc"
MVC_COL = "mvc"

SUMMARY_COLS = ("rms_error", "pow_05_3hz", "pow_8_12hz")


def _highpass_sosfiltfilt(
    x: np.ndarray,
    *,
    fs: float,
    cutoff_hz: float = HIGHPASS_CUTOFF_HZ,
    order: int = HIGHPASS_FILTER_ORDER,
) -> np.ndarray:
    """
    Zero-phase high-pass (Butterworth, SOS) to remove residual drift.

    ``sosfiltfilt`` preserves event timing in the 8–12 Hz tremor band relative
    to cognitive probe markers — critical for trial-aligned hero visuals.
    """
    if x.size < order * 3:
        return x
    sos = signal.butter(order, cutoff_hz, btype="highpass", fs=fs, output="sos")
    return signal.sosfiltfilt(sos, x)


def _prepare_spectral_signal(normalized_error: np.ndarray, *, fs: float) -> np.ndarray:
    """Linear detrend, then zero-phase high-pass before Welch PSD."""
    detrended = signal.detrend(normalized_error, type="linear")
    return _highpass_sosfiltfilt(detrended, fs=fs)


def _band_power(
    freqs: np.ndarray,
    psd: np.ndarray,
    band: tuple[float, float],
) -> float:
    """Integrate PSD over a frequency band (absolute power)."""
    fmin, fmax = band
    mask = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(mask):
        return np.nan
    return float(trapezoid(psd[mask], freqs[mask]))


def _summarize_trial_signal(
    normalized_error: np.ndarray,
    *,
    fs: float,
    tracking_band: tuple[float, float],
    tremor_band: tuple[float, float],
    welch_nperseg: int | None,
) -> dict[str, float]:
    """Detrend, high-pass filter, compute Welch PSD, return RMS + band powers."""
    nan_row = {col: np.nan for col in SUMMARY_COLS}
    if normalized_error.size == 0:
        return nan_row

    rms_error = float(np.sqrt(np.mean(normalized_error**2)))

    filtered = _prepare_spectral_signal(normalized_error, fs=fs)
    nperseg = welch_nperseg or min(len(filtered), 256)
    nperseg = min(nperseg, len(filtered))
    if nperseg < 2:
        return {**nan_row, "rms_error": rms_error}

    freqs, psd = signal.welch(
        filtered,
        fs=fs,
        nperseg=nperseg,
        detrend=False,
    )
    return {
        "rms_error": rms_error,
        "pow_05_3hz": _band_power(freqs, psd, tracking_band),
        "pow_8_12hz": _band_power(freqs, psd, tremor_band),
    }


def _attach_trial_targets(
    grip: pd.DataFrame,
    beh: pd.DataFrame,
    *,
    target_prop_col: str = TARGET_PROP_COL,
    mvc_col: str = MVC_COL,
    beh_trial_col: str = BEH_TRIAL_COL,
) -> pd.DataFrame:
    """Join behavioral trial targets onto long-format gripforce rows."""
    required_grip = {FORCE_COLUMN, "trial_idx", *TRIAL_GROUP_COLS}
    missing_grip = required_grip - set(grip.columns)
    if missing_grip:
        raise ValueError(f"grip missing columns: {sorted(missing_grip)}")

    required_beh = {target_prop_col, mvc_col, beh_trial_col, *BEH_JOIN_COLS}
    missing_beh = required_beh - set(beh.columns)
    if missing_beh:
        raise ValueError(f"beh missing columns: {sorted(missing_beh)}")

    trial_targets = beh.loc[:, [*BEH_JOIN_COLS, beh_trial_col, target_prop_col, mvc_col]]
    trial_targets = trial_targets.drop_duplicates(
        subset=[*BEH_JOIN_COLS, beh_trial_col],
        keep="first",
    )
    trial_targets = trial_targets.rename(columns={beh_trial_col: "trial_idx"})
    trial_targets["target_force"] = (
        trial_targets[target_prop_col] * trial_targets[mvc_col]
    )

    return grip.merge(
        trial_targets[[*BEH_JOIN_COLS, "trial_idx", "target_force"]],
        on=[*BEH_JOIN_COLS, "trial_idx"],
        how="inner",
        validate="m:1",
    )


def extract_trial_spectral_features(
    grip: pd.DataFrame,
    beh: pd.DataFrame,
    *,
    fs: float = GRIP_SAMPLE_RATE_HZ,
    tracking_band: tuple[float, float] = TRACKING_BAND_HZ,
    tremor_band: tuple[float, float] = TREMOR_BAND_HZ,
    target_prop_col: str = TARGET_PROP_COL,
    mvc_col: str = MVC_COL,
    beh_trial_col: str = BEH_TRIAL_COL,
    welch_nperseg: int | None = None,
) -> pd.DataFrame:
    """
    Normalize grip force per trial and extract spectral summary features.

    For each trial (grouped by ``subject_id``, ``session_num``, ``run_num``,
    ``trial_idx``):

    1. Join behavioral targets and compute
       ``normalized_error = (grip_force_au - target_force) / target_force`` where
       ``target_force = grip_targ_prop_mvc * mvc`` (same arbitrary units as
       ``grip_force_au`` from col1 on oddball files).
    2. Linearly detrend ``normalized_error`` (``scipy.signal.detrend``).
    3. Apply a zero-phase Butterworth high-pass (``signal.sosfiltfilt`` at
       0.5 Hz) so macro-level drift does not leak into tremor-band power.
    4. Estimate PSD with Welch's method (``scipy.signal.welch``).
    5. Integrate absolute power in the tracking (0.5–3 Hz) and tremor (8–12 Hz)
       bands.

    Parameters
    ----------
    grip:
        Long-format gripforce DataFrame from ``load_gripforce_long``.
    beh:
        Trial-level behavioral table (e.g. ``bap_beh_trialdata_v3.csv``).
    fs:
        Sampling rate in Hz (default 100).
    tracking_band, tremor_band:
        ``(fmin, fmax)`` Hz for band-power integration.
    target_prop_col, mvc_col, beh_trial_col:
        Behavioral columns used to derive per-trial ``target_force``.
    welch_nperseg:
        Segment length passed to ``signal.welch``; default ``min(n, 256)``.

    Returns
    -------
    pd.DataFrame
        One row per trial with ``subject_id``, ``session_num``, ``run_num``,
        ``trial_idx``, ``rms_error``, ``pow_05_3hz``, and ``pow_8_12hz``.
    """
    merged = _attach_trial_targets(
        grip,
        beh,
        target_prop_col=target_prop_col,
        mvc_col=mvc_col,
        beh_trial_col=beh_trial_col,
    )
    if merged.empty:
        return pd.DataFrame(columns=[*TRIAL_GROUP_COLS, *SUMMARY_COLS])

    rows: list[dict[str, float | int | str]] = []
    for keys, trial in merged.groupby(list(TRIAL_GROUP_COLS), sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)

        target_force = float(trial["target_force"].iloc[0])
        if not np.isfinite(target_force) or target_force <= 0:
            summary = {col: np.nan for col in SUMMARY_COLS}
        else:
            force = trial[FORCE_COLUMN].to_numpy(dtype=np.float64)
            normalized_error = (force - target_force) / target_force
            summary = _summarize_trial_signal(
                normalized_error,
                fs=fs,
                tracking_band=tracking_band,
                tremor_band=tremor_band,
                welch_nperseg=welch_nperseg,
            )

        row = dict(zip(TRIAL_GROUP_COLS, keys))
        row.update(summary)
        rows.append(row)

    return pd.DataFrame(rows)[list(TRIAL_GROUP_COLS) + list(SUMMARY_COLS)]
