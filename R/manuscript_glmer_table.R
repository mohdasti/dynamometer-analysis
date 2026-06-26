# Shared high-grip GLMM fixed-effects table (post-outlier screen).
# Source from manuscript and analysis notebooks for a single source of truth.

suppressPackageStartupMessages({
  library(lme4)
  library(dplyr)
})

is_high_grip <- function(x) tolower(as.character(x)) == "true"
is_correct <- function(x) tolower(as.character(x)) == "true"

prep_glmer_dat <- function(df) {
  df %>%
    filter(!is.na(resp_is_correct), !is.na(pow_05_3hz), !is.na(pow_8_12hz)) %>%
    mutate(
      resp_is_correct  = as.integer(is_correct(resp_is_correct)),
      task_modality    = factor(task_modality, levels = c("aud", "vis")),
      stim_level_index = factor(stim_level_index, ordered = TRUE),
      subject_id       = factor(subject_id),
      pow_05_3hz_z     = as.numeric(scale(pow_05_3hz)),
      pow_8_12hz_z     = as.numeric(scale(pow_8_12hz))
    ) %>%
    filter(abs(pow_8_12hz_z) <= 3.5)
}

label_fixed_terms <- function(term) {
  dplyr::recode(
    term,
    "(Intercept)"           = "Intercept",
    "task_modalityvis"      = "Modality (visual vs. auditory)",
    "stim_level_index.L"    = "Stimulus difficulty (linear)",
    "stim_level_index.Q"    = "Stimulus difficulty (quadratic)",
    "stim_level_index.C"    = "Stimulus difficulty (cubic)",
    "stim_level_index^4"    = "Stimulus difficulty (4th order)",
    "pow_05_3hz_z"          = "Tracking power 0.5–3 Hz (z)",
    "pow_8_12hz_z"          = "Tremor power 8–12 Hz (z)",
    .default = term
  )
}

tidy_or_row <- function(model, label) {
  cf <- summary(model)$coefficients
  rows <- lapply(rownames(cf), function(nm) {
    est <- cf[nm, "Estimate"]
    se  <- cf[nm, "Std. Error"]
    pv  <- cf[nm, "Pr(>|z|)"]
    data.frame(
      Model = label,
      Predictor = label_fixed_terms(nm),
      `OR (95% CI)` = sprintf(
        "%.2f (%.2f, %.2f)",
        exp(est), exp(est - 1.96 * se), exp(est + 1.96 * se)
      ),
      p = if (pv < 0.001) "< .001" else sprintf("%.3f", pv),
      check.names = FALSE
    )
  })
  do.call(rbind, rows)
}

build_high_grip_fx_table <- function(trial_path) {
  raw <- read.csv(trial_path, stringsAsFactors = FALSE)
  high_dat <- raw %>% filter(is_high_grip(is_high_grip)) %>% prep_glmer_dat()
  ctrl <- glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))

  m_base <- glmer(
    resp_is_correct ~ task_modality + stim_level_index + (1 | subject_id),
    data = high_dat, family = binomial(), control = ctrl
  )
  m_dsp <- glmer(
    resp_is_correct ~ task_modality + stim_level_index +
      pow_05_3hz_z + pow_8_12hz_z + (1 | subject_id),
    data = high_dat, family = binomial(), control = ctrl
  )

  bind_rows(
    tidy_or_row(m_base, "Baseline (high grip)"),
    tidy_or_row(m_dsp,  "DSP-augmented (high grip)")
  )
}
