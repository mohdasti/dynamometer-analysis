# Behavioral ↔ Gripforce Linkage

This document describes how Nov2025 behavioral outputs are expected to link to in-scanner gripforce files. Run `scripts/run_inventory.py` on your Mac to refresh findings from the actual `Nov2025` folder.

## Gripforce file keys

Parsed from BIDS path and filename:

| Key | Source | Example |
|-----|--------|---------|
| Subject | `sub-BAP###` folder + `subjectBAP###` in filename | `BAP103` |
| Session | `ses-N` folder + `sessionN` in filename | `3` |
| Run | `runN` in filename | `1` |
| Task | token before `_session` in filename | `MVCnPRAC`, `Voddball`, `Aoddball` |
| Acquisition time | `{M}_{D}_{H}_{Min}` suffix in filename | `07-08 12:44` |

Within each CSV (no header):

| Col | Use for linkage |
|-----|-----------------|
| 2 | Elapsed seconds within run — align to trial onsets relative to run start |
| 3 | Absolute timestamp (seconds) — align across modalities if behavioral logs share clock |
| 4 | Grip force (units TBD) |

## Expected behavioral join keys

Prior BAP behavioral processing typically organizes trial-level tables with some combination of:

- `subject` / `subject_id` / `participant` containing `BAP###`
- `session` / `ses`
- `run`
- `task` / `condition` (`Aoddball`, `Voddball`, `MVCnPRAC`)
- `trial_onset`, `onset`, `timestamp`, or `time` for event alignment

The inventory script scans tabular files under `behavioral_root` and flags columns matching these patterns.

## Join workflow (recommended)

1. **File-level join:** `subject + session + run + task` between behavioral summary tables and gripforce filenames.
2. **Event-level join:** For each matched run, map behavioral trial onsets onto gripforce column 2 (elapsed time). Validate on one known run manually.
3. **Cross-modal timestamp check:** If behavioral exports include absolute timestamps, compare ranges to gripforce column 3 min/max per file.

## After local inventory run

Check generated artifacts:

- `reports/dataset_inventory.md` — human-readable summary
- `reports/gripforce_file_inventory.csv` — one row per gripforce file

Update this document with concrete Nov2025 file names and column mappings once the script has been run against `/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025`.
