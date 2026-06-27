# Dataset Summary

Confirmed local paths (Mac, Jun 2026). Per-file gripforce stats (duration, force min/max) require running `python scripts/run_inventory.py`.

## Data paths — confirmed

| Path | Status | Contents |
|------|--------|----------|
| `/Users/mohdasti/Documents/LC-BAP/BAP/BAP data` | Exists | 85 `sub-BAP###` folders + `BAP tablet data/` |
| `/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025` | Exists | Flat folder; 13 data files (CSVs, reports, master spreadsheet exports) |

## Gripforce data (`BAP data/`)

### Top-level layout

- **85** subject folders matching `sub-BAP###`
- **`BAP tablet data/`** — separate tablet recordings (not in-scanner `InsideScanner` gripforce; treat as distinct modality until inventoried)

### In-scanner gripforce — analysis scope

Oddball tasks only for gripforce analysis (**MVCnPRAC excluded**; MVC values come from behavioral `mvc` column).

| Metric | Value |
|--------|------:|
| Files (`*_gripforce.csv` under `*InsideScanner*`, oddball only) | **156** (84 Aoddball + 72 Voddball) |
| All gripforce files including MVCnPRAC | 202 |
| Task: Aoddball | 84 |
| Task: Voddball | 72 |
| Task: MVCnPRAC | 46 *(excluded from analysis)* |

### File format

- No header; 4 numeric columns at ~100 Hz
- Col 1: marker/code | Col 2: elapsed time (s) | Col 3: absolute timestamp (s) | Col 4: grip force (**units TBD**)

### Keys for linkage

`sub-BAP###/ses-N/InsideScanner/subjectBAP###_{Task}_session{N}_run{R}_..._gripforce.csv`

→ **subject**, **session**, **run**, **task**

## Behavioral data (`Nov2025/`)

Flat folder (no subdirectories). File inventory:

| File | Role |
|------|------|
| `bap_beh_trialdata_v3.csv` | **Primary trial-level table** (8.8 MB; Jan 2026) — main target for gripforce linkage |
| `bap_beh_trialdata_v3_report.txt` | Processing / QA report for v3 |
| `bap_beh_trialdata_v2.csv` | Prior trial-level export (6.3 MB) |
| `bap_beh_trialdata_v2_report.txt` | Processing report for v2 |
| `bap_beh_subjxtaskdata_v2.csv` | Subject × task summary (aggregated, not trial-level) |
| `bap_beh_trialdata_v2_trials_per_subject_per_task.csv` | Trial counts per subject/task (coverage QA) |
| `LC Aging Subject Data master spreadsheet - behavioral data dictionary.csv` | Column definitions |
| `LC Aging Subject Data master spreadsheet - behavioral.csv` | Master behavioral export |
| `LC Aging Subject Data master spreadsheet - demographics.csv` | Demographics |
| `LC Aging Subject Data master spreadsheet - neuropsych.csv` | Neuropsych |
| `LC Aging Subject Data master spreadsheet - LC integrity.csv` | LC integrity |
| `LC_Grant_Updated_LC_values.2026.csv` / `.xlsx` | LC grant values |

## Linkage plan (gripforce ↔ behavior)

1. **File-level join:** Match gripforce filenames to rows in `bap_beh_trialdata_v3.csv` on **subject + session + run + task** (exact column names confirmed when inventory script reads headers).
2. **Coverage QA:** Compare gripforce file counts vs `bap_beh_trialdata_v2_trials_per_subject_per_task.csv` and/or aggregated counts from v3.
3. **Event-level join:** Map behavioral trial onsets onto gripforce **column 2** (elapsed s within run). Use **column 3** if v3 includes absolute timestamps on a shared clock.
4. **Reference:** `LC Aging ... behavioral data dictionary.csv` for behavioral field definitions.

## Next steps

1. Run locally: `python scripts/run_inventory.py` → fills `reports/dataset_inventory.md` with measured durations, force ranges, and v3 column list.
2. Confirm grip force units (acquisition notes / MVC calibration).
3. Spot-check one subject-session-run (e.g. BAP103 ses-3 MVCnPRAC run1) against v3 trials.
4. Decide whether `BAP tablet data/` should be inventoried separately from in-scanner gripforce.
