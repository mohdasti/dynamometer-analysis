# Dataset Summary (pre-inventory baseline)

This summary combines documented expectations from project handoff notes with what the inventory script will quantify when run on your Mac. **Run `python scripts/run_inventory.py` locally to replace estimates with measured values.**

## Environment note

Raw data live on the local Mac at paths configured in `config/paths.local.yaml`. Cloud agents cannot access those folders; inventory numbers below marked *(expected)* come from prior manual counts unless you have run the script locally.

## Data paths

| Path | Purpose | Status on Mac |
|------|---------|---------------|
| `/Users/mohdasti/Documents/LC-BAP/BAP/BAP data` | Raw gripforce CSVs | Expected — confirm locally |
| `/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025` | Behavioral / prior analysis | Expected — confirm locally |

## Gripforce files *(expected)*

| Metric | Value |
|--------|------:|
| Total files (`*_gripforce.csv` under `*InsideScanner*`) | 202 |
| Subjects (approx.) | ~90 `sub-BAP###` folders |
| Task: Aoddball | 84 files |
| Task: Voddball | 72 files |
| Task: MVCnPRAC | 46 files |

### File format

- No header; 4 numeric columns at ~100 Hz
- Col 1: marker/code (task-dependent, not force)
- Col 2: elapsed time within run (seconds)
- Col 3: absolute timestamp (seconds)
- Col 4: grip force (**units TBD**; sample values ~1–13)

### Filename / BIDS keys

```
sub-BAP###/ses-N/InsideScanner/subjectBAP###_{Task}_session{N}_run{R}_{M}_{D}_{H}_{Min}_gripforce.csv
```

Join keys: **subject (`BAP###`)**, **session**, **run**, **task**.

## Behavioral data (Nov2025)

Structure must be confirmed by running the inventory script locally. The script will:

- Catalog file types (CSV, R, RData, etc.)
- Preview tabular column names
- Flag candidate join columns (subject, session, run, task, timestamps)
- Identify the best candidate trial-level linkage table

See [DATA_LINKAGE.md](DATA_LINKAGE.md) for the join strategy.

## Linkage plan (gripforce ↔ behavior)

1. **File-level:** Match `BAP### + session + run + task` between gripforce filenames and behavioral tables.
2. **Event-level:** Align behavioral trial onsets to gripforce column 2 (elapsed s within run).
3. **Clock check:** Compare behavioral absolute times (if present) to gripforce column 3 range per file.

## Immediate next steps

1. Run `python scripts/run_inventory.py` on the Mac and commit `reports/dataset_inventory.md` if desired.
2. Confirm force units from acquisition / calibration documentation.
3. Manually validate one subject-session-run dyad (behavioral events vs gripforce trace).
4. Plan task-specific summaries (peak force, mean, variability, event-locked windows) after QA.
