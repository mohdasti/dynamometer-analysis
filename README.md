# dynamometer-analysis

Trial-level spectral analysis of **BAP in-scanner dynamometer (grip force)** data linked to perceptual oddball performance. The pipeline extracts event-locked band power from 100 Hz force streams, tests whether tremor and tracking features predict perceptual accuracy under physical load, and validates predictions with out-of-sample ML and exploratory LC neuroimaging covariates.

**Manuscript:** *Can Grip-Force Dynamics Track Perceptual Strain? A Trial-Level Spectral Analysis in Older Adults*

**Primary question:** Do sub-second grip-force spectral dynamics (visuomotor tracking 0.5–3 Hz; physiological tremor 8–12 Hz) carry incremental information about trial-level perceptual accuracy beyond nominal task difficulty — especially under high (40% MVC) physical load?

## Quick start

### Full analysis pipeline

Run from the repository root (requires local data paths in `config/paths.local.yaml`):

```bash
quarto render analysis/01_ingest.qmd
quarto render analysis/02_cognitive_motor_model.qmd
quarto render analysis/03_hero_visuals.qmd
```

Figures land in `reports/figures/`; copy to the manuscript with:

```bash
cp reports/figures/hero_*.png manuscript/figures/
```

### Manuscript (HTML + PDF)

```bash
cd manuscript
quarto render manuscript.qmd              # HTML + LaTeX PDF
quarto render manuscript.qmd --to pdf
quarto render manuscript-biorxiv.qmd    # HTML + bioRxiv Typst PDF
quarto render manuscript-biorxiv.qmd --to biorxiv-typst
quarto render supplementary.qmd         # HTML + PDF
quarto render supplementary.qmd --to pdf
```

Shared prose lives in `manuscript/_manuscript-content.qmd` (included by both main and bioRxiv builds).

### Portfolio case study

Self-contained HTML for reviewers or LLMs:

```bash
quarto render analysis/portfolio.qmd
cp _site/analysis/portfolio.html portfolio_case_study.html
```

Or render the full Quarto website:

```bash
quarto render
```

## Local setup (Mac)

macOS often provides `python3` but not `python` or `pip`. Use:

```bash
git clone https://github.com/mohdasti/dynamometer-analysis.git
cd dynamometer-analysis
cp config/paths.example.yaml config/paths.local.yaml
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -r requirements.txt
pip install scikit-learn shap   # optional: ML ROC-AUC + SHAP analyses
```

**R packages** (for modeling and figures): `lme4`, `broom.mixed`, `ggplot2`, `patchwork`, `ggtext`, `gt`, `dplyr`, `tidyr`, `scales`, `yaml`, `boot`, `plotly`, `htmlwidgets`.

Install [Quarto](https://quarto.org/docs/get-started/) for HTML/PDF output. Open the repo folder in Positron (not just a single `.qmd` file).

Raw data stay outside this repo. See [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) for paths, file formats, and design notes.

## Repository layout

| Path | Purpose |
|------|---------|
| `analysis/` | Quarto notebooks (ingest → models → figures → portfolio) |
| `scripts/` | Python DSP and I/O modules |
| `R/colors_manuscript.R` | Shared figure color palette (sourced by all R figure notebooks) |
| `manuscript/` | Main paper, bioRxiv build, supplementary materials, `references.bib` |
| `reports/` | Generated CSVs, model tables, and `figures/hero_*.png` |
| `config/` | Local path configuration (`paths.local.yaml`, gitignored) |
| `docs/` | Data linkage and project context for agents |

## Analysis pipeline

Run in order:

| Step | Document | Language | What it does |
|------|----------|----------|--------------|
| 1 | `analysis/01_ingest.qmd` | Python | Load grip CSVs, segment trials, extract DSP features (Welch PSD, band power), join behavioral + LC MRI metrics |
| 2 | `analysis/02_cognitive_motor_model.qmd` | R | Stratified GLMMs (high vs. low grip), LC brain–behavior, GroupKFold ML ROC-AUC |
| 3 | `analysis/03_hero_visuals.qmd` | R | Hero figures (trial anatomy, spectrogram, psychometric, PSD ribbons, direction-flip, caterpillar, SAT, SHAP) |
| 4 | `analysis/portfolio.qmd` | R | Single-file portfolio case study (all figures + narrative) |

Core Python modules in `scripts/`:

- `gripforce_io.py` — file discovery, loading, trial segmentation, attrition funnel
- `gripforce_features.py` — target-normalized error, zero-phase high-pass, Welch PSD, pre/post-probe windows
- `export_hero_psd.py` — consistent PSD export for R hero plots
- `run_inventory.py` — dataset inventory against local paths

## Key outputs (`reports/`)

| File | Description |
|------|-------------|
| `analysis_trial_table.csv` | Trial-level merged table (behavior + DSP + LC metrics) |
| `grip_attrition_funnel.csv` | Granular attrition stages (no grip → partial → feature loss) |
| `cognitive_motor_glmer_fixed_effects.csv` | High-grip GLMM fixed effects (baseline + DSP-augmented) |
| `sensitivity_outlier_screen.csv` | Tremor OR / LRT under alternative spectral outlier rules |
| `ml_auc_summary.csv` | GroupKFold ROC-AUC lift (baseline vs. +DSP) |
| `shap_feature_importance.csv` | SHAP global importance |
| `lc_bootstrap_ci.csv` | Bootstrap 95% CI for LC × tremor correlations |
| `subject_level_summary.csv` | Per-subject load cost, Δ tremor, LC metrics |
| `figures/hero_*.png` | Static hero visualizations (synced to `manuscript/figures/`) |

## Data inventory

```bash
source .venv/bin/activate
python3 scripts/run_inventory.py
```

Writes `reports/dataset_inventory.md` and `reports/gripforce_file_inventory.csv`. See [docs/DATA_LINKAGE.md](docs/DATA_LINKAGE.md) for behavioral ↔ gripforce join keys.

## Data (not in git)

| Resource | Default path |
|----------|--------------|
| Gripforce CSVs | `/Users/mohdasti/Documents/LC-BAP/BAP/BAP data` |
| Behavioral + LC MRI (Nov 2025) | `/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025` |

Configure paths in `config/paths.local.yaml`.

## Headline findings (current cohort)

Analysis-ready sample after behavioral cleaning and spectral QC: **~64 subjects**, **13,545 trials** (6,888 high-grip + 6,657 low-grip). High grip (40% MVC) is the primary inference arm; low grip (5% MVC) serves as a specificity comparison.

**Spectral quality control:** 37 trials with implausible tremor-band power (|z| > 3.5 within grip arm; max z ≈ 48.5) were excluded as recording artifacts before inferential models. Accuracy labels were not used in this screen. See `reports/sensitivity_outlier_screen.csv` and Supplementary Materials for threshold sensitivity.

**Primary high-grip GLMM (post-QC):**

- Adding tracking + tremor features improves fit vs. baseline psychometric model: LRT χ²(2) = 7.34, *p* = .025
- Tremor-band power → lower accuracy: OR = 0.64, 95% CI [0.46, 0.89], *p* = .008
- Tracking-band power: OR = 1.03, *p* = .452 (null)
- Tremor × difficulty interaction: *p* = .005 (stronger association at harder trials)
- Tremor × grip interaction: *p* = .244 (not grip-specific; both strata show negative slopes)

**Other:**

- Physical load compresses the psychometric function; ~57% of subjects show lower accuracy under high grip
- **GroupKFold RF:** AUC 0.850 (difficulty only) → 0.855 (+ DSP); interpret with trial-count caveat
- **LC fICVF × Δ tremor:** r ≈ −0.19, 95% bootstrap CI crosses zero (exploratory, *n* ≈ 55)

## Tests

```bash
source .venv/bin/activate
python3 -m pytest tests/
```
