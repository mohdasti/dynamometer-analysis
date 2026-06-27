# BAP Dynamometer Analysis — Project Context

Handoff document for Cursor agents working on this repo locally on Mohd's MacBook.

## Goal

Build analysis tooling for **BAP in-scanner dynamometer (grip force) data**, starting with understanding and inventorying the raw files, then linking them to existing behavioral outputs, and eventually running more advanced analyses.

**Current phase:** exploratory — get a solid sense of the gripforce files (structure, coverage, force ranges, alignment with behavioral data) before advanced modeling.

## Repository

- **Code:** `/Users/mohdasti/Documents/GitHub/dynamometer-analysis`
- **Remote:** `dynamometer-analysis` on GitHub (analysis code only; raw data stay outside git)

## Data locations (local Mac — not in git)

| Resource | Path |
|----------|------|
| Raw gripforce CSVs | `/Users/mohdasti/Documents/LC-BAP/BAP/BAP data` |
| Behavioral / prior analysis (Nov 2025) | `/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025` |

**Confirmed (Mac):** `BAP data/` holds 85 `sub-BAP###` folders plus `BAP tablet data/`. `Nov2025/` is a flat folder of behavioral CSVs and LC master spreadsheet exports; primary trial-level file is `bap_beh_trialdata_v3.csv`.

## Raw dynamometer data layout

BIDS-like hierarchy:

```
BAP data/
├── sub-BAP001/
│   ├── ses-1/
│   │   └── InsideScanner/
│   │       └── subjectBAP001_{Task}_session1_run{N}_{M}_{D}_{H}_{Min}_gripforce.csv
│   └── ses-2/ ...
├── sub-BAP103/
└── ... (~90 subject folders)
```

- **202** gripforce CSV files total (all under `*InsideScanner*` folders)
- Files match pattern: `*_gripforce.csv`

### Task types (from filenames)

Analysis uses **oddball tasks only**; MVCnPRAC calibration runs are excluded from pipelines (MVC comes from behavioral `mvc` column).

| Task | File count | Status |
|------|----------:|--------|
| Aoddball | 84 | Included |
| Voddball | 72 | Included |
| MVCnPRAC | 46 | Excluded from analysis |

### Filename pattern

```
subject{BAP###}_{TASK}_session{N}_run{R}_{M}_{D}_{H}_{Min}_gripforce.csv
```

Example:

```
subjectBAP103_MVCnPRAC_session3_run1_7_8_12_44_gripforce.csv
```

- `{M}_{D}_{H}_{Min}` ≈ acquisition date/time (e.g. July 8, 12:44)

## Gripforce CSV format

- **No header row**
- **4 comma-separated numeric columns**
- **~100 Hz** sampling (column 2 steps ≈ 0.01 s)

```
col1,  col2,       col3,          col4
257,   0.010000,   15358.043546,  11.000000   ← MVCnPRAC example
0,     0.010030,   11286.366915,  1.000000    ← Voddball example
```

| Col | Likely meaning | Notes |
|-----|----------------|-------|
| 1 | Marker / event / run code | e.g. 257 in MVCnPRAC, 0 in Voddball — **not force** |
| 2 | Elapsed time within run (seconds) | Use for within-run alignment |
| 3 | Absolute timestamp (seconds, large offset) | Use for cross-modal sync (scanner, behavior) |
| 4 | Grip force | Values ~1–13 in samples seen; **units TBD** — check acquisition notes |

## Behavioral data (Nov2025)

Folder: `/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025`

Prior behavioral processing already exists here. The agent should **inventory this folder** and determine how tables map to gripforce files (subject, session, run, task, event timestamps).

Expected linking keys: `sub-BAP###`, session, run, task name (`Aoddball`, `Voddball`, `MVCnPRAC`).

## Suggested next steps for the agent

1. Confirm both data paths exist and list `Nov2025` contents.
2. Run `python scripts/run_inventory.py` to build a **data inventory** (subjects, sessions, tasks, file counts, run durations, peak force per file).
3. Inspect `Nov2025` behavioral outputs and document join keys to gripforce files (see `docs/DATA_LINKAGE.md` and generated `reports/dataset_inventory.md`).
4. Paths are configured in `config/paths.local.yaml` (copy from `config/paths.example.yaml`).
5. Produce a short summary report before any advanced analyses.

## Conventions

- Keep **raw data outside git**; only scripts, config templates, and derived summaries in repo.
- Prefer simple, focused scripts over heavy abstraction at this stage.
- Match existing conventions in `Nov2025` if present before inventing new schemas.

## Useful shell commands (run on Mac)

```bash
export BAP_DATA="/Users/mohdasti/Documents/LC-BAP/BAP/BAP data"
export BAP_BEHAV="/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025"

find "$BAP_DATA" -path "*InsideScanner*" -name "*_gripforce.csv" | wc -l

find "$BAP_DATA" -path "*InsideScanner*" -name "*_gripforce.csv" \
  | sed 's/.*subjectBAP[0-9]*_//; s/_session.*//' | sort | uniq -c

ls -la "$BAP_BEHAV"
find "$BAP_BEHAV" -maxdepth 3 -type f | head -40
```
