# Behavioral ↔ Gripforce Linkage

Confirmed Nov2025 layout: **flat folder** of CSV/report exports. Primary table: **`bap_beh_trialdata_v3.csv`** (trial-level, 202 gripforce runs confirmed in `BAP data/`).

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
| 3 | Absolute timestamp (seconds) — cross-modal sync if shared clock |
| 4 | Grip force (raw; **units TBD** — compare to `grip_force_mean_au` in v3) |

## `bap_beh_trialdata_v3.csv` — confirmed join columns

Header confirmed on Mac (Jan 2026 export):

| v3 column | Maps to gripforce | Notes |
|-----------|-------------------|-------|
| `subject_id` | `BAP###` in filename / BIDS folder | e.g. `BAP103` |
| `session_num` | `sessionN` / `ses-N` | Integer session |
| `run_num` | `runN` in filename | Integer run |
| `task_modality` | Task in filename | See task mapping below — **verify unique values** |
| `run_datetime` | `{M}_{D}_{H}_{Min}` in filename | Cross-check acquisition timestamp |
| `trial_num` | — | Trial index within run |
| `mvc` | MVCnPRAC runs | Subject MVC used for normalization |

### Task name mapping (verify with `cut -d, -f6 ... | sort -u`)

| Gripforce filename task | Expected `task_modality` |
|-------------------------|--------------------------|
| `Aoddball` | Auditory oddball (e.g. `Aud`, `auditory`) |
| `Voddball` | Visual oddball (e.g. `Vis`, `visual`) |
| `MVCnPRAC` | MVC / practice (exact label TBD) |

Run on Mac:

```bash
cut -d, -f6 "/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025/bap_beh_trialdata_v3.csv" | sort -u | head -20
```

### Grip columns already in v3 (prior pipeline)

The behavioral export **already includes trial-level grip summaries** derived from grip samples:

| Column | Likely meaning |
|--------|----------------|
| `grip_targ_prop_mvc` | Target grip as proportion of MVC |
| `grip_level` | Coded grip condition / level |
| `prop_valid_grip_samples` | Fraction of valid grip samples in trial window |
| `grip_force_mean_prop_mvc` | Mean force as proportion of MVC |
| `grip_force_sd_2to3s` | Force variability (2–3 s window) |
| `grip_force_mean_au` | Mean force in arbitrary units |
| `grip_force_sd_runmean` | Variability relative to run mean |
| `grip_valid_lt_*pct` | QA flags for grip adherence thresholds |

**Implication:** Raw `*_gripforce.csv` files are for re-analysis, validation, or finer temporal alignment — not the only source of grip metrics. Compare raw traces to these v3 summaries after joining.

### Behavioral timing columns (event alignment)

| Column | Use |
|--------|-----|
| `stim_offset` | Stimulus timing relative to trial structure |
| `same_diff_resp_secs` | Same/different response time (seconds) |
| `confidence_resp_secs` | Confidence response time (seconds) |

For event-locked raw force, align trial events to gripforce **column 2** (elapsed s within run) using trial structure + these timestamps (exact offset rules in data dictionary / v3 report).

## File-level join (SQL-style)

```
gripforce.subject     = v3.subject_id
gripforce.session     = v3.session_num
gripforce.run         = v3.run_num
gripforce.task        ↔ v3.task_modality   (via mapping table)
```

Optional QA key: `run_datetime` ↔ filename acquisition suffix.

## Nov2025 file roles

| File | Use |
|------|-----|
| `bap_beh_trialdata_v3.csv` | **Primary** trial-level join table |
| `bap_beh_trialdata_v2_trials_per_subject_per_task.csv` | Coverage QA (trial counts) |
| `bap_beh_subjxtaskdata_v2.csv` | Subject × task aggregates |
| `bap_beh_trialdata_v3_report.txt` | Processing / exclusion rules |
| `LC Aging ... behavioral data dictionary.csv` | Field definitions |

## Join workflow

1. Inventory gripforce → `reports/gripforce_file_inventory.csv`
2. Load v3; build task_modality ↔ filename task map
3. Inner join on `subject_id + session_num + run_num + task`; report unmatched runs
4. Spot-check: raw col4 stats vs `grip_force_mean_au` for matched trials
5. Event-level: align `stim_offset` / response times to gripforce col2 for trial windows

## Other v3 columns (not join keys)

QC / exclusion flags (`invalid_*`, `missing_*`, `outlier_*`, `same_diff_dominant_*`, etc.) — use to filter trials/runs before force analysis; see v3 report and data dictionary.

## Gripforce root note

`BAP data/BAP tablet data/` is separate from `sub-BAP###/ses-N/InsideScanner/` in-scanner CSVs.
