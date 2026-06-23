# Behavioral ↔ Gripforce Linkage

Confirmed Nov2025 layout: **flat folder** of CSV/report exports (no subdirectories). Run `scripts/run_inventory.py` to read column headers from `bap_beh_trialdata_v3.csv`.

## Gripforce file keys

Parsed from BIDS path and filename:

| Key | Source | Example |
|-----|--------|---------|
| Subject | `sub-BAP###` folder + `subjectBAP###` in filename | `BAP103` |
| Session | `ses-N` folder + `sessionN` in filename | `3` |
| Run | `runN` in filename | `1` |
| Task | token before `_session` in filename | `MVCnPRAC`, `Voddball`, `Aoddball` |
| Acquisition time | `{M}_{D}_{H}_{Min}` suffix in filename | `07-08 12:44` |

Within each gripforce CSV (no header):

| Col | Use for linkage |
|-----|-----------------|
| 2 | Elapsed seconds within run — align to trial onsets relative to run start |
| 3 | Absolute timestamp (seconds) — align across modalities if behavioral logs share clock |
| 4 | Grip force (units TBD) |

## Nov2025 behavioral files (confirmed)

| Priority | File | Use |
|----------|------|-----|
| 1 | `bap_beh_trialdata_v3.csv` | Trial-level behavioral data — **primary join target** |
| 2 | `bap_beh_trialdata_v2_trials_per_subject_per_task.csv` | Expected trial counts per subject/task |
| 3 | `bap_beh_subjxtaskdata_v2.csv` | Subject-task aggregates (summary stats, not event-level) |
| — | `bap_beh_trialdata_v3_report.txt` | Processing log / QA for v3 |
| — | `LC Aging ... behavioral data dictionary.csv` | Field definitions |

LC master spreadsheet exports (demographics, neuropsych, LC integrity) are **subject-level covariates**, not run-level linkage tables.

## Expected join keys in `bap_beh_trialdata_v3.csv`

Based on BAP naming conventions (confirm via inventory script or data dictionary):

- Subject ID containing `BAP###`
- Session / visit number
- Run number (for multi-run tasks)
- Task name (`Aoddball`, `Voddball`, `MVCnPRAC` or abbreviations)
- Trial-level timing: onset, RT, and/or timestamp columns

The inventory script previews headers and flags columns matching: `subject`, `session`, `run`, `task`, `onset`, `time`, `rt`.

## Join workflow

1. **Inventory gripforce** → one row per `*_gripforce.csv` with parsed subject/session/run/task.
2. **Load v3 trials** → filter to in-scanner tasks present in gripforce filenames.
3. **File-level match:** inner join on subject + session + run + task; flag gripforce files with no behavioral rows and vice versa.
4. **Event-level match:** for each matched run, align trial onsets to gripforce column 2; validate on one manual example.
5. **Optional:** attach subject-level covariates from LC master spreadsheets after trial-level join is verified.

## Gripforce root note

`BAP data/` also contains **`BAP tablet data/`** (outside `sub-BAP###/ses-N/InsideScanner/`). That folder is separate from in-scanner dynamometer CSVs and should not be mixed into the InsideScanner inventory without explicit review.

## Artifacts after local run

- `reports/dataset_inventory.md` — full summary including v3 column preview
- `reports/gripforce_file_inventory.csv` — per-file force/duration stats

After running locally, update this doc with the exact v3 column names used for the join.
