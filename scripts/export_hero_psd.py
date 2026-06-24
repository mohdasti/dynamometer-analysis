"""Export hero-trial Welch PSD for R visualization (matches gripforce_features pipeline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gripforce_features import (  # noqa: E402
    GRIP_SAMPLE_RATE_HZ,
    TRACKING_BAND_HZ,
    TREMOR_BAND_HZ,
    _band_power,
    _prepare_spectral_signal,
    compute_trial_welch_psd,
)
from gripforce_io import FORCE_COLUMN, load_gripforce_file  # noqa: E402


def load_trial_force(
    *,
    subject_id: str,
    session_num: int,
    run_num: int,
    trial_idx: int,
    task: str,
    grip_root: Path,
    min_rows_per_trial: int = 100,
) -> np.ndarray:
    """Load one trial's force trace using the same segmentation as the R loader."""
    pattern = f"subject{subject_id}_{task}_session{session_num}_run{run_num}_*_gripforce.csv"
    hits = list(grip_root.glob(f"**/{pattern}"))
    if not hits:
        raise FileNotFoundError(f"No grip file for {subject_id} {task} session {session_num} run {run_num}")

    raw = load_gripforce_file(hits[0], min_rows_per_trial=min_rows_per_trial)
    trial = raw.loc[raw["trial_idx"] == trial_idx, FORCE_COLUMN].to_numpy(dtype=np.float64)
    if trial.size == 0:
        raise ValueError(f"Trial {trial_idx} not found in {hits[0].name}")
    return trial


def probe_onset_seconds(meta: pd.Series) -> float:
    """Seconds into trial when the oddball probe appears."""
    if "probe_onset_s" in meta.index and pd.notna(meta["probe_onset_s"]):
        return float(meta["probe_onset_s"])
    if meta.get("task_modality") == "vis":
        return float(meta["stim_offset"])
    return 0.0


def compute_probe_locked_spectrogram(
    force: np.ndarray,
    target_force: float,
    probe_onset_s: float,
    *,
    fs: float = GRIP_SAMPLE_RATE_HZ,
    nperseg: int = 64,
    noverlap: int = 48,
) -> pd.DataFrame:
    """
    Short-time Fourier spectrogram aligned to probe onset (t = 0 at probe).

    Uses the same filtered signal as the Welch feature pipeline.
    """
    if not np.isfinite(target_force) or target_force <= 0 or force.size == 0:
        return pd.DataFrame(columns=["time_from_probe_s", "freq_hz", "power"])

    from scipy import signal

    normalized = (force - target_force) / target_force
    filtered = _prepare_spectral_signal(normalized, fs=fs)

    seg = min(nperseg, len(filtered))
    if seg < 16:
        return pd.DataFrame(columns=["time_from_probe_s", "freq_hz", "power"])

    overlap = min(noverlap, seg - 1)
    freqs, times, sxx = signal.spectrogram(
        filtered,
        fs=fs,
        nperseg=seg,
        noverlap=overlap,
        detrend=False,
    )
    times_probe = times - probe_onset_s

    freq_grid, time_grid = np.meshgrid(freqs, times_probe, indexing="ij")
    return pd.DataFrame(
        {
            "time_from_probe_s": time_grid.ravel(),
            "freq_hz": freq_grid.ravel(),
            "power": sxx.ravel(),
        }
    )


def main(meta_path: Path, out_path: Path, specgram_path: Path | None = None) -> None:
    meta = pd.read_csv(meta_path).iloc[0]
    config_path = ROOT / "config" / "paths.local.yaml"
    if not config_path.exists():
        config_path = ROOT / "config" / "paths.example.yaml"
    with config_path.open() as f:
        paths = yaml.safe_load(f)

    grip_root = Path(paths["gripforce_root"])
    force = load_trial_force(
        subject_id=str(meta["subject_id"]),
        session_num=int(meta["session_num"]),
        run_num=int(meta["run_num"]),
        trial_idx=int(meta["trial_idx"]),
        task=str(meta["task"]),
        grip_root=grip_root,
    )
    target_force = float(meta["grip_targ_prop_mvc"]) * float(meta["mvc"])
    probe_onset = probe_onset_seconds(meta)
    freqs, psd = compute_trial_welch_psd(force, target_force, fs=GRIP_SAMPLE_RATE_HZ)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame({"freq_hz": freqs, "psd": psd})
    out.to_csv(out_path, index=False)

    specgram_path = specgram_path or out_path.with_name("_hero_spectrogram.csv")
    specgram = compute_probe_locked_spectrogram(force, target_force, probe_onset)
    specgram.to_csv(specgram_path, index=False)

    summary = {
        "pow_05_3hz": _band_power(freqs, psd, TRACKING_BAND_HZ),
        "pow_8_12hz": _band_power(freqs, psd, TREMOR_BAND_HZ),
        "n_samples": int(force.size),
        "probe_onset_s": probe_onset,
    }
    summary_path = out_path.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {out_path} ({len(out)} frequency bins)")
    print(f"Wrote {specgram_path} ({len(specgram):,} time–frequency cells)")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    meta = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/figures/_hero_meta.csv"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "reports/figures/_hero_psd.csv"
    main(meta, out)
