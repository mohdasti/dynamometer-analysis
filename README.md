# dynamometer-analysis

Portfolio-grade analysis of **BAP in-scanner dynamometer (grip force)** data linked to perceptual oddball performance. The pipeline extracts trial-level spectral features from 100 Hz force streams, models cognitive–motor interference under physical load, and validates predictions with out-of-sample ML and LC neuroimaging covariates.

**Primary question:** Does physiological tremor (8–12 Hz) in continuous grip telemetry predict perceptual accuracy beyond nominal task difficulty — and does that relationship flip under high vs. low muscular load?

## Quick start (portfolio output)

After running ingest and generating figures (see below), render the self-contained case study:

```bash
quarto render analysis/portfolio.qmd
cp _site/analysis/portfolio.html portfolio_case_study.html
```

Open `portfolio_case_study.html` at the repo root — all figures are embedded for sharing with reviewers or LLMs.

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

Install [Quarto](https://quarto.org/docs/get-started/) for HTML output. Open the repo folder in Positron (not just a single `.qmd` file).

Raw data stay outside this repo. See [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) for paths, file formats, and design notes.

## Analysis pipeline

Run in order:

| Step | Document | Language | What it does |
|------|----------|----------|--------------|
| 1 | `analysis/01_ingest.qmd` | Python | Load grip CSVs, segment trials, extract DSP features (Welch PSD, band power), join behavioral + LC MRI metrics |
| 2 | `analysis/02_cognitive_motor_model.qmd` | R | Stratified GLMMs (high vs. low grip), LC brain–behavior, GroupKFold ML ROC-AUC |
| 3 | `analysis/03_hero_visuals.qmd` | R | Hero figures (trial anatomy, spectrogram, PSD ribbons, caterpillar, SAT, SHAP, windowed tremor) |
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
| `cognitive_motor_glmer_fixed_effects.csv` | High-grip GLMM fixed effects |
| `ml_auc_summary.csv` | GroupKFold ROC-AUC lift (baseline vs. +DSP) |
| `shap_feature_importance.csv` | SHAP global importance |
| `lc_bootstrap_ci.csv` | Bootstrap 95% CI for LC × tremor correlations |
| `subject_level_summary.csv` | Per-subject load cost, Δ tremor, LC metrics |
| `figures/hero_*.png` | Static hero visualizations |

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

- **13,759 trials**, **65 subjects** with matched grip + behavioral data (~78% of retainable trials)
- **High grip (40% MVC)** is the primary inference arm; low grip (5% MVC) is a comparison arm (precision-noise artifact)
- Tremor–accuracy slope **flips sign** between high and low grip conditions
- **GroupKFold RF:** AUC 0.850 (difficulty only) → 0.855 (+ DSP features)
- **LC fICVF × Δ tremor:** r ≈ −0.19, 95% bootstrap CI crosses zero (trend, n = 55)
- **Window × Difficulty interaction** (visual trials): tremor elevated post-stimulus at max difficulty (p < 0.001)

## Tests

```bash
source .venv/bin/activate
python3 -m pytest tests/
```
