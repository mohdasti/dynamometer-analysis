# colors_manuscript.R — single source of truth for all figure colors
# Source at top of every figure script: source(file.path(repo, "R", "colors_manuscript.R"))

cond_colors <- c(
  "Standard/Low"  = "#B8BCC4",
  "Standard/High" = "#6B7280",
  "Easy/Low"      = "#5DADE2",
  "Easy/High"     = "#2E86AB",
  "Hard/Low"      = "#EC70AB",
  "Hard/High"     = "#A23B72"
)
diff_colors <- c("Standard" = "#8B9099", "Easy" = "#2E86AB", "Hard" = "#A23B72")
effort_colors <- c("Low" = "#5DADE2", "High" = "#A23B72")
task_colors   <- c("ADT" = "#1D9E75", "VDT" = "#6B4F8C")
param_colors  <- c("v" = "#1D9E75", "a" = "#6B4F8C", "z" = "#8B6914", "t0" = "#6B7280")
param_labels  <- c("v"="Drift rate (v)", "a"="Boundary separation (a)",
                   "z"="Bias (z)", "t0"="Non-decision time (t\u2080)")
pupil_colors  <- c("baseline" = "#8B9099", "tepr" = "#C4681A", "total_auc" = "#3D6B8C")
stat_colors   <- c("prior"="#B0B8C0", "posterior"="#374151", "empirical"="#1F2937",
                   "predicted"="#A23B72", "zero_line"="#9CA3AF")
model_colors  <- c("history" = "#1D9E75", "wsls" = "#B8860B")

# Derived palettes for common figure mappings
pupil_tertile_colors <- c(
  Low    = unname(effort_colors["Low"]),
  Medium = unname(pupil_colors["baseline"]),
  High   = unname(effort_colors["High"])
)
pupil_state_label_colors <- c(
  "Low Pupil"    = unname(effort_colors["Low"]),
  "Medium Pupil" = unname(pupil_colors["baseline"]),
  "High Pupil"   = unname(effort_colors["High"])
)
missingness_colors <- c(
  Usable  = unname(task_colors["ADT"]),
  Missing = unname(stat_colors["predicted"])
)
coupling_line_color <- unname(stat_colors["predicted"])
reference_line_color <- unname(stat_colors["zero_line"])

#' Shared ggplot2 theme: `theme_minimal()` with all panel grid lines removed.
theme_ch2 <- function(base_size = 11) {
  ggplot2::theme_minimal(base_size = base_size) +
    ggplot2::theme(panel.grid = ggplot2::element_blank())
}

#' Psychometric-function plots: `theme_minimal()` with default light panel grids.
theme_ch2_pf <- function(base_size = 11) {
  ggplot2::theme_minimal(base_size = base_size)
}

# --- Grip-force manuscript derived palettes ---

grip_level_colors <- c(
  "Low grip (5% MVC)"    = unname(effort_colors["Low"]),
  "High grip (40% MVC)"  = unname(effort_colors["High"]),
  "Low (5% MVC)"         = unname(effort_colors["Low"]),
  "High (40% MVC)"       = unname(effort_colors["High"]),
  "Low effort"           = unname(effort_colors["Low"]),
  "High effort"          = unname(effort_colors["High"]),
  "Low grip\n(5% MVC)"   = unname(effort_colors["Low"]),
  "High grip\n(40% MVC)" = unname(effort_colors["High"])
)

outcome_colors <- c(
  Correct   = unname(task_colors["ADT"]),
  Incorrect = unname(effort_colors["High"])
)

load_effect_colors <- c(
  Hindered             = unname(effort_colors["High"]),
  Facilitated          = unname(effort_colors["Low"]),
  "Hindered by load"   = unname(effort_colors["High"]),
  "Facilitated by load"= unname(effort_colors["Low"])
)

band_colors <- c(
  "Tracking\n0.5–3 Hz" = unname(task_colors["ADT"]),
  "Tremor\n8–12 Hz"    = unname(effort_colors["High"])
)

signal_colors <- c(
  force        = unname(effort_colors["Low"]),
  error        = unname(task_colors["ADT"]),
  instability  = unname(effort_colors["High"]),
  psd          = unname(param_colors["a"]),
  probe_marker = unname(pupil_colors["tepr"]),
  reference    = unname(reference_line_color),
  pre_epoch    = unname(stat_colors["empirical"])
)

lc_scatter_colors <- c(
  LC_CNR   = unname(effort_colors["High"]),
  LC_fICVF = unname(effort_colors["Low"]),
  LC_cost  = unname(task_colors["VDT"])
)

roc_feature_colors <- c(
  Baseline = unname(effort_colors["Low"]),
  DSP      = unname(effort_colors["High"]),
  Chance   = unname(reference_line_color)
)
