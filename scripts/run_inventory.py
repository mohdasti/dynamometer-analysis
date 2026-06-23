#!/usr/bin/env python3
"""Inventory BAP in-scanner gripforce data and Nov2025 behavioral outputs."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


GRIPFORCE_GLOB = "*_gripforce.csv"
GRIPFORCE_FILENAME_RE = re.compile(
    r"subject(?P<subject>BAP\d+)_(?P<task>[A-Za-z0-9]+)_session(?P<session>\d+)_"
    r"run(?P<run>\d+)_(?P<month>\d+)_(?P<day>\d+)_(?P<hour>\d+)_(?P<minute>\d+)_gripforce\.csv$"
)
BIDS_SUBJECT_RE = re.compile(r"sub-(BAP\d+)", re.IGNORECASE)
BIDS_SESSION_RE = re.compile(r"ses-(\d+)", re.IGNORECASE)
SUBJECT_TOKEN_RE = re.compile(r"BAP\d+", re.IGNORECASE)

TABULAR_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".parquet"}
CODE_SUFFIXES = {".R", ".r", ".py", ".m", ".ipynb"}
DATA_SUFFIXES = {".RData", ".rds", ".mat", ".sav", ".feather"}

JOIN_KEY_HINTS = (
    "subject",
    "sub",
    "participant",
    "session",
    "ses",
    "run",
    "task",
    "modality",
    "condition",
    "trial",
    "block",
    "time",
    "datetime",
    "timestamp",
    "onset",
    "offset",
    "rt",
    "resp",
    "grip",
    "mvc",
)


@dataclass
class GripforceFileStats:
    filepath: str
    subject: str
    session: str
    task: str
    run: str
    acquisition_datetime: str
    bids_subject: str
    bids_session: str
    n_rows: int
    duration_s: float  # col2 max-min; per-trial epoch span when col2 resets each trial
    col3_span_s: float  # col3 max-min; approximate full run clock span
    col2_max_s: float  # max(col2); longest single-trial elapsed window in file
    col2_resets: int  # times col2 decreases (trial/block boundary marker)
    estimated_epochs: int  # col2_resets + 1
    sample_rate_hz: float
    force_min: float
    force_max: float
    force_mean: float
    abs_time_min: float
    abs_time_max: float
    marker_unique: str
    parse_warning: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_paths(config_path: Path | None = None) -> dict[str, str]:
    root = repo_root()
    candidates = [
        config_path,
        root / "config" / "paths.local.yaml",
        root / "config" / "paths.example.yaml",
    ]
    for candidate in candidates:
        if candidate is None or not candidate.exists():
            continue
        if yaml is None:
            raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
        with candidate.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid config format in {candidate}")
        return {str(k): str(v) for k, v in data.items()}
    raise FileNotFoundError("No paths config found. Copy config/paths.example.yaml to config/paths.local.yaml")


def parse_gripforce_filename(path: Path) -> dict[str, str]:
    match = GRIPFORCE_FILENAME_RE.search(path.name)
    if not match:
        return {
            "subject": "",
            "session": "",
            "task": "",
            "run": "",
            "acquisition_datetime": "",
            "parse_warning": "filename_pattern_mismatch",
        }

    groups = match.groupdict()
    month = int(groups["month"])
    day = int(groups["day"])
    hour = int(groups["hour"])
    minute = int(groups["minute"])
    acq_dt = f"{month:02d}-{day:02d} {hour:02d}:{minute:02d}"
    return {
        "subject": groups["subject"].upper(),
        "session": groups["session"],
        "task": groups["task"],
        "run": groups["run"],
        "acquisition_datetime": acq_dt,
        "parse_warning": "",
    }


def parse_bids_from_path(path: Path) -> tuple[str, str]:
    subject = ""
    session = ""
    for part in path.parts:
        sub_match = BIDS_SUBJECT_RE.search(part)
        if sub_match:
            subject = sub_match.group(1).upper()
        ses_match = BIDS_SESSION_RE.search(part)
        if ses_match:
            session = ses_match.group(1)
    return subject, session


def compute_timing_metrics(elapsed: list[float], abs_times: list[float]) -> dict[str, float | int]:
    col2_span = max(elapsed) - min(elapsed)
    col3_span = max(abs_times) - min(abs_times)
    col2_max = max(elapsed)
    resets = sum(1 for i in range(1, len(elapsed)) if elapsed[i] < elapsed[i - 1])
    positive_diffs = [
        elapsed[i] - elapsed[i - 1]
        for i in range(1, len(elapsed))
        if elapsed[i] >= elapsed[i - 1] and elapsed[i] - elapsed[i - 1] > 0
    ]
    if positive_diffs:
        positive_diffs.sort()
        median_dt = positive_diffs[len(positive_diffs) // 2]
        sample_rate = 1.0 / median_dt
    else:
        sample_rate = 0.0
    return {
        "col2_span": col2_span,
        "col3_span": col3_span,
        "col2_max": col2_max,
        "col2_resets": resets,
        "estimated_epochs": resets + 1,
        "sample_rate_hz": sample_rate,
    }


def summarize_gripforce_file(path: Path) -> GripforceFileStats:
    meta = parse_gripforce_filename(path)
    bids_subject, bids_session = parse_bids_from_path(path)

    elapsed: list[float] = []
    abs_times: list[float] = []
    forces: list[float] = []
    markers: set[str] = set()
    warnings: list[str] = []
    if meta["parse_warning"]:
        warnings.append(meta["parse_warning"])
    if bids_subject and meta["subject"] and bids_subject != meta["subject"]:
        warnings.append("bids_subject_mismatch")
    if bids_session and meta["session"] and bids_session != meta["session"]:
        warnings.append("bids_session_mismatch")

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        for row_idx, row in enumerate(reader, start=1):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) < 4:
                warnings.append(f"short_row_{row_idx}")
                continue
            try:
                marker = row[0].strip()
                elapsed.append(float(row[1]))
                abs_times.append(float(row[2]))
                forces.append(float(row[3]))
                markers.add(marker)
            except ValueError:
                warnings.append(f"non_numeric_row_{row_idx}")

    if not forces:
        return GripforceFileStats(
            filepath=str(path),
            subject=meta["subject"],
            session=meta["session"],
            task=meta["task"],
            run=meta["run"],
            acquisition_datetime=meta["acquisition_datetime"],
            bids_subject=bids_subject,
            bids_session=bids_session,
            n_rows=0,
            duration_s=0.0,
            col3_span_s=0.0,
            col2_max_s=0.0,
            col2_resets=0,
            estimated_epochs=0,
            sample_rate_hz=0.0,
            force_min=float("nan"),
            force_max=float("nan"),
            force_mean=float("nan"),
            abs_time_min=float("nan"),
            abs_time_max=float("nan"),
            marker_unique="",
            parse_warning=";".join(sorted(set(warnings)) or ["empty_file"]),
        )

    timing = compute_timing_metrics(elapsed, abs_times)

    return GripforceFileStats(
        filepath=str(path),
        subject=meta["subject"],
        session=meta["session"],
        task=meta["task"],
        run=meta["run"],
        acquisition_datetime=meta["acquisition_datetime"],
        bids_subject=bids_subject,
        bids_session=bids_session,
        n_rows=len(forces),
        duration_s=round(float(timing["col2_span"]), 3),
        col3_span_s=round(float(timing["col3_span"]), 3),
        col2_max_s=round(float(timing["col2_max"]), 3),
        col2_resets=int(timing["col2_resets"]),
        estimated_epochs=int(timing["estimated_epochs"]),
        sample_rate_hz=round(float(timing["sample_rate_hz"]), 2),
        force_min=round(min(forces), 4),
        force_max=round(max(forces), 4),
        force_mean=round(sum(forces) / len(forces), 4),
        abs_time_min=round(min(abs_times), 6),
        abs_time_max=round(max(abs_times), 6),
        marker_unique=",".join(sorted(markers)[:20]),
        parse_warning=";".join(sorted(set(warnings))),
    )


def find_gripforce_files(root: Path) -> list[Path]:
    files = sorted(root.rglob(GRIPFORCE_GLOB))
    return [path for path in files if "InsideScanner" in path.parts]


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _timing_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "median": None, "max": None}
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": ordered[len(ordered) // 2],
        "max": ordered[-1],
    }


def summarize_gripforce(stats: list[GripforceFileStats]) -> dict[str, Any]:
    by_task = Counter(item.task for item in stats if item.task)
    by_subject = Counter(item.subject for item in stats if item.subject)
    by_session = Counter(item.session for item in stats if item.session)
    run_counts = Counter(
        (item.subject, item.session, item.task) for item in stats if item.subject and item.task
    )

    valid = [item for item in stats if item.n_rows > 0]
    durations = [item.duration_s for item in valid]
    col3_spans = [item.col3_span_s for item in valid]
    col2_maxes = [item.col2_max_s for item in valid]
    n_rows_list = [item.n_rows for item in valid]
    forces_min = [item.force_min for item in valid]
    forces_max = [item.force_max for item in valid]

    timing_by_task: dict[str, dict[str, dict[str, float | None] | float | None]] = {}
    for task in sorted(by_task):
        task_items = [item for item in valid if item.task == task]
        timing_by_task[task] = {
            "n_files": len(task_items),
            "col2_span_s": _timing_stats([item.duration_s for item in task_items]),
            "col3_span_s": _timing_stats([item.col3_span_s for item in task_items]),
            "col2_max_s": _timing_stats([item.col2_max_s for item in task_items]),
            "n_rows": _timing_stats([float(item.n_rows) for item in task_items]),
            "estimated_epochs": _timing_stats([float(item.estimated_epochs) for item in task_items]),
        }

    return {
        "n_files": len(stats),
        "n_subjects": len(by_subject),
        "n_sessions": len(by_session),
        "tasks": dict(by_task.most_common()),
        "subjects": dict(by_subject.most_common()),
        "sessions": dict(by_session.most_common()),
        "run_counts_by_subject_session_task": {
            f"{sub}|ses-{ses}|{task}": count for (sub, ses, task), count in sorted(run_counts.items())
        },
        "duration_s": _timing_stats(durations),
        "col3_span_s": _timing_stats(col3_spans),
        "col2_max_s": _timing_stats(col2_maxes),
        "n_rows": _timing_stats([float(n) for n in n_rows_list]),
        "timing_by_task": timing_by_task,
        "force": {
            "global_min": min(forces_min) if forces_min else None,
            "global_max": max(forces_max) if forces_max else None,
        },
        "parse_warnings": Counter(item.parse_warning for item in stats if item.parse_warning),
    }


def summarize_gripforce_root(root: Path) -> dict[str, Any]:
    if not root.exists():
        return {"exists": False, "path": str(root)}

    sub_folders = sorted(
        p.name for p in root.iterdir() if p.is_dir() and p.name.lower().startswith("sub-bap")
    )
    other_folders = sorted(
        p.name for p in root.iterdir() if p.is_dir() and not p.name.lower().startswith("sub-bap")
    )
    return {
        "exists": True,
        "path": str(root),
        "n_sub_folders": len(sub_folders),
        "sub_folders_sample": sub_folders[:5],
        "other_folders": other_folders,
    }


KNOWN_BEHAVIORAL_FILES = {
    "bap_beh_trialdata_v3.csv": "Primary trial-level behavioral table (latest; use for gripforce linkage)",
    "bap_beh_trialdata_v2.csv": "Prior trial-level behavioral table (superseded by v3)",
    "bap_beh_subjxtaskdata_v2.csv": "Subject-by-task summary (not trial-level)",
    "bap_beh_trialdata_v2_trials_per_subject_per_task.csv": "Trial counts per subject/task (coverage QA)",
    "bap_beh_trialdata_v3_report.txt": "Processing report for trialdata v3",
    "bap_beh_trialdata_v2_report.txt": "Processing report for trialdata v2",
    "LC Aging Subject Data master spreadsheet - behavioral data dictionary.csv": "Column definitions for behavioral fields",
    "LC Aging Subject Data master spreadsheet - behavioral.csv": "Master behavioral spreadsheet export",
}


def classify_behavioral_file(name: str) -> str:
    lower = name.lower()
    if name in KNOWN_BEHAVIORAL_FILES:
        return "bap_behavioral"
    if lower.startswith("lc aging") or lower.startswith("lc_grant"):
        return "lc_master_spreadsheet"
    if lower.endswith("_report.txt"):
        return "processing_report"
    return "other"


def inventory_behavioral_root(root: Path, max_preview_rows: int = 3) -> dict[str, Any]:
    if not root.exists():
        return {"exists": False, "path": str(root)}

    suffix_counts: Counter[str] = Counter()
    top_level: list[dict[str, Any]] = []
    tabular_files: list[dict[str, Any]] = []
    code_files: list[str] = []
    data_files: list[str] = []
    known_files: list[dict[str, str]] = []
    report_files: list[str] = []

    for path in sorted(root.iterdir() if root.is_dir() else []):
        if path.is_dir():
            top_level.append({"name": path.name, "type": "dir"})
        elif path.is_file():
            top_level.append({"name": path.name, "type": "file", "size_bytes": path.stat().st_size})
            role = classify_behavioral_file(path.name)
            if path.name in KNOWN_BEHAVIORAL_FILES:
                known_files.append({"name": path.name, "role": KNOWN_BEHAVIORAL_FILES[path.name]})
            if role == "processing_report":
                report_files.append(path.name)

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        suffix_counts[path.suffix or "(no suffix)"] += 1
        rel = str(path.relative_to(root))

        lower_suffix = path.suffix
        if suffix in {s.lower() for s in TABULAR_SUFFIXES} and not path.name.endswith("_report.txt"):
            tabular_files.append(inspect_tabular_file(path, root, max_preview_rows))
        elif lower_suffix in CODE_SUFFIXES:
            code_files.append(rel)
        elif lower_suffix in DATA_SUFFIXES:
            data_files.append(rel)

    linkage_notes = infer_linkage_notes(tabular_files)
    if any(item["name"] == "bap_beh_trialdata_v3.csv" for item in known_files):
        linkage_notes.insert(
            0,
            "Primary linkage table: `bap_beh_trialdata_v3.csv` (trial-level; pair with gripforce via subject/session/run/task).",
        )

    return {
        "exists": True,
        "path": str(root),
        "layout": "flat",
        "n_files": sum(suffix_counts.values()),
        "suffix_counts": dict(suffix_counts.most_common()),
        "top_level": top_level,
        "known_files": known_files,
        "report_files": sorted(report_files),
        "tabular_files": tabular_files,
        "code_files": sorted(code_files),
        "serialized_data_files": sorted(data_files),
        "linkage_notes": linkage_notes,
    }


def inspect_tabular_file(path: Path, root: Path, max_preview_rows: int) -> dict[str, Any]:
    rel = str(path.relative_to(root))
    info: dict[str, Any] = {
        "path": rel,
        "suffix": path.suffix,
        "columns": [],
        "join_key_columns": [],
        "sample_subjects": [],
        "n_rows_estimate": None,
        "preview": [],
        "read_error": "",
    }

    if path.suffix.lower() not in {".csv", ".tsv", ".txt"}:
        info["read_error"] = "preview_not_supported_for_suffix"
        return info

    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            rows = []
            for idx, row in enumerate(reader):
                if idx == 0:
                    info["columns"] = [cell.strip() for cell in row]
                    info["join_key_columns"] = [
                        col
                        for col in info["columns"]
                        if any(hint in col.lower() for hint in JOIN_KEY_HINTS)
                    ]
                elif idx <= max_preview_rows:
                    rows.append(row)
                elif idx == max_preview_rows + 1:
                    break
            info["preview"] = rows
            info["n_rows_estimate"] = count_data_rows(path, delimiter)
            info["sample_subjects"] = extract_subject_tokens(info["columns"], rows)
    except OSError as exc:
        info["read_error"] = str(exc)

    return info


def count_data_rows(path: Path, delimiter: str) -> int:
    count = 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        next(reader, None)
        for _ in reader:
            count += 1
    return count


def extract_subject_tokens(columns: list[str], rows: list[list[str]]) -> list[str]:
    subjects: set[str] = set()
    subject_cols = [
        idx
        for idx, col in enumerate(columns)
        if any(token in col.lower() for token in ("subject", "sub", "participant", "bap"))
    ]
    for row in rows:
        for idx in subject_cols:
            if idx < len(row):
                for match in SUBJECT_TOKEN_RE.findall(row[idx]):
                    subjects.add(match.upper())
        for cell in row:
            for match in SUBJECT_TOKEN_RE.findall(cell):
                subjects.add(match.upper())
    return sorted(subjects)


def infer_linkage_notes(tabular_files: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    has_subject = any(
        any("subject" in col.lower() or "sub" in col.lower() or "bap" in col.lower() for col in item["columns"])
        for item in tabular_files
        if item["columns"]
    )
    has_session = any(
        any("session" in col.lower() or col.lower() in {"ses", "ses_id"} for col in item["columns"])
        for item in tabular_files
        if item["columns"]
    )
    has_run = any(
        any("run" in col.lower() for col in item["columns"]) for item in tabular_files if item["columns"]
    )
    has_task = any(
        any("task" in col.lower() or "condition" in col.lower() for col in item["columns"])
        for item in tabular_files
        if item["columns"]
    )
    has_time = any(
        any(any(h in col.lower() for h in ("time", "onset", "timestamp")) for col in item["columns"])
        for item in tabular_files
        if item["columns"]
    )

    if has_subject:
        notes.append("Behavioral tables include subject-like columns; join to gripforce via BAP### IDs.")
    if has_session:
        notes.append("Session columns detected; align with gripforce sessionN / ses-N.")
    if has_run:
        notes.append("Run columns detected; align with gripforce runN in filenames.")
    if has_task:
        notes.append("Task/condition columns detected; map to Aoddball, Voddball, MVCnPRAC.")
    if has_time:
        notes.append("Timestamp/onset columns detected; use absolute timestamp (col3) or elapsed time (col2) for alignment.")
    if not notes:
        notes.append("No obvious join-key columns found in previewed tabular files; inspect serialized/code artifacts manually.")

    preferred = [
        item
        for item in tabular_files
        if item["join_key_columns"] and not item["read_error"]
    ]
    if preferred:
        best = sorted(preferred, key=lambda item: len(item["join_key_columns"]), reverse=True)[0]
        notes.append(
            f"Best candidate linkage table so far: {best['path']} "
            f"(columns: {', '.join(best['join_key_columns'])})"
        )
    return notes


def render_markdown_report(
    gripforce_summary: dict[str, Any],
    gripforce_stats: list[GripforceFileStats],
    gripforce_root_summary: dict[str, Any],
    behavioral: dict[str, Any],
    paths: dict[str, str],
    generated_at: str,
) -> str:
    lines = [
        "# BAP Dynamometer Dataset Inventory",
        "",
        f"Generated: {generated_at}",
        "",
        "## Data paths",
        "",
        f"- Gripforce root: `{paths.get('gripforce_root', '')}`",
        f"- Behavioral root: `{paths.get('behavioral_root', '')}`",
        f"- Exists (gripforce): `{Path(paths.get('gripforce_root', '')).exists()}`",
        f"- Exists (behavioral): `{behavioral.get('exists', False)}`",
        "",
    ]

    if gripforce_root_summary.get("exists"):
        lines.extend(
            [
                "### Gripforce root layout",
                "",
                f"- `sub-BAP###` folders: **{gripforce_root_summary['n_sub_folders']}**",
            ]
        )
        if gripforce_root_summary.get("other_folders"):
            lines.append(
                f"- Other folders: {', '.join(f'`{name}`' for name in gripforce_root_summary['other_folders'])}"
            )
        lines.append("")

    lines.extend(
        [
            "## Gripforce summary",
            "",
            f"- Files inventoried: **{gripforce_summary['n_files']}**",
            f"- Subjects: **{gripforce_summary['n_subjects']}**",
            f"- Sessions (unique session labels in filenames): **{gripforce_summary['n_sessions']}**",
            "",
            "### Tasks (file counts)",
            "",
        ]
    )

    for task, count in sorted(gripforce_summary["tasks"].items()):
        lines.append(f"- {task}: {count}")

    lines.extend(
        [
            "",
            "### Timing interpretation",
            "",
            "- **`col2_span_s` (reported as Duration below):** `max(col2) − min(col2)`. When col2 resets each trial, this reflects the **longest single-trial grip window** in the file, not total run length.",
            "- **`col3_span_s`:** `max(col3) − min(col3)`. Approximate **full run clock span** across all trials in the file.",
            "- **`col2_resets` / `estimated_epochs`:** Number of trial/block boundaries (col2 decreases) + 1.",
            "- Expected oddball grip window per trial ≈ **4.7 s** (through response). Compare `col2_max_s` to this.",
            "",
            "### col2 span per file (trial epoch proxy; seconds)",
            "",
            f"- Min: {gripforce_summary['duration_s']['min']}",
            f"- Median: {gripforce_summary['duration_s']['median']}",
            f"- Max: {gripforce_summary['duration_s']['max']}",
            "",
            "### col3 span per file (full run clock; seconds)",
            "",
            f"- Min: {gripforce_summary['col3_span_s']['min']}",
            f"- Median: {gripforce_summary['col3_span_s']['median']}",
            f"- Max: {gripforce_summary['col3_span_s']['max']}",
            "",
            "### Rows per file (samples at ~100 Hz)",
            "",
            f"- Min: {gripforce_summary['n_rows']['min']}",
            f"- Median: {gripforce_summary['n_rows']['median']}",
            f"- Max: {gripforce_summary['n_rows']['max']}",
            "",
            "### Timing by task",
            "",
        ]
    )

    for task, task_timing in sorted(gripforce_summary.get("timing_by_task", {}).items()):
        lines.append(f"**{task}** ({int(task_timing['n_files'])} files):")
        c2 = task_timing["col2_span_s"]
        c3 = task_timing["col3_span_s"]
        nr = task_timing["n_rows"]
        ep = task_timing["estimated_epochs"]
        lines.append(
            f"- col2 span: {c2['min']}–{c2['max']} s (median {c2['median']}); "
            f"col3 span median {c3['median']} s; rows median {nr['median']}; epochs median {ep['median']}"
        )

    lines.extend(
        [
            "",
            "### Force (col4, units TBD)",
            "",
            f"- Global min: {gripforce_summary['force']['global_min']}",
            f"- Global max: {gripforce_summary['force']['global_max']}",
            "",
            "### Run counts by subject / session / task",
            "",
        ]
    )

    for key, count in sorted(gripforce_summary["run_counts_by_subject_session_task"].items()):
        sub, ses_task = key.split("|", 1)
        lines.append(f"- {sub} {ses_task}: {count} run(s)")

    if gripforce_summary["parse_warnings"]:
        lines.extend(["", "### Parse warnings", ""])
        for warning, count in gripforce_summary["parse_warnings"].most_common():
            lines.append(f"- {warning or '(none)'}: {count}")

    lines.extend(["", "## Behavioral folder (Nov2025)", ""])
    if not behavioral.get("exists"):
        lines.append(f"Path not found: `{behavioral.get('path', '')}`")
    else:
        lines.append(f"- Layout: **{behavioral.get('layout', 'unknown')}** (no subfolders)")
        lines.append(f"- Total files: **{behavioral['n_files']}**")
        if behavioral.get("known_files"):
            lines.extend(["", "### Key behavioral files", ""])
            for item in behavioral["known_files"]:
                lines.append(f"- `{item['name']}` — {item['role']}")
        if behavioral.get("report_files"):
            lines.extend(["", "### Processing reports", ""])
            for name in behavioral["report_files"]:
                lines.append(f"- `{name}`")
        lines.append("")
        lines.append("### File types")
        lines.append("")
        for suffix, count in behavioral["suffix_counts"].items():
            lines.append(f"- `{suffix}`: {count}")

        if behavioral["code_files"]:
            lines.extend(["", "### Code artifacts", ""])
            for rel in behavioral["code_files"][:30]:
                lines.append(f"- `{rel}`")
            if len(behavioral["code_files"]) > 30:
                lines.append(f"- ... and {len(behavioral['code_files']) - 30} more")

        if behavioral["serialized_data_files"]:
            lines.extend(["", "### Serialized data artifacts", ""])
            for rel in behavioral["serialized_data_files"][:30]:
                lines.append(f"- `{rel}`")

        lines.extend(["", "### Linkage notes", ""])
        for note in behavioral["linkage_notes"]:
            lines.append(f"- {note}")

        preview_tables = [item for item in behavioral["tabular_files"] if item["columns"]]
        if preview_tables:
            lines.extend(["", "### Tabular file previews", ""])
            for item in preview_tables[:15]:
                lines.append(f"#### `{item['path']}`")
                lines.append(f"- Columns: {', '.join(item['columns'])}")
                if item["join_key_columns"]:
                    lines.append(f"- Join-key columns: {', '.join(item['join_key_columns'])}")
                if item["sample_subjects"]:
                    lines.append(f"- Sample subjects: {', '.join(item['sample_subjects'])}")
                if item["n_rows_estimate"] is not None:
                    lines.append(f"- Rows (excluding header): {item['n_rows_estimate']}")
                lines.append("")

    lines.extend(
        [
            "## Recommended join strategy (initial)",
            "",
            "1. Parse gripforce filenames for `BAP###`, `sessionN`, `runN`, and task (`Aoddball`, `Voddball`, `MVCnPRAC`).",
            "2. Cross-check BIDS folders `sub-BAP###/ses-N/InsideScanner/`.",
            "3. Join behavioral tables on subject + session + run + task where available.",
            "4. For event-level alignment, map behavioral event onsets to gripforce column 2 (elapsed s) or column 3 (absolute timestamp s).",
            "",
            "## Next steps",
            "",
            "- Confirm force units with acquisition notes / calibration files.",
            "- Validate a single subject-session-run manually against behavioral event logs.",
            "- Define task-specific force summaries (peak, mean, AUC) after linkage QA.",
            "",
        ]
    )

    return "\n".join(lines)


def run_inventory(config_path: Path | None = None, output_dir: Path | None = None) -> int:
    paths = load_paths(config_path)
    gripforce_root = Path(paths["gripforce_root"])
    behavioral_root = Path(paths["behavioral_root"])
    out_dir = output_dir or Path(paths.get("output_dir", repo_root() / "reports"))

    if not gripforce_root.exists():
        print(f"ERROR: gripforce_root does not exist: {gripforce_root}", file=sys.stderr)
        return 1

    gripforce_files = find_gripforce_files(gripforce_root)
    stats = [summarize_gripforce_file(path) for path in gripforce_files]
    summary = summarize_gripforce(stats)
    gripforce_root_summary = summarize_gripforce_root(gripforce_root)
    behavioral = inventory_behavioral_root(behavioral_root)

    generated_at = datetime.now().isoformat(timespec="seconds")
    out_dir.mkdir(parents=True, exist_ok=True)

    file_inventory_csv = out_dir / "gripforce_file_inventory.csv"
    write_csv(
        file_inventory_csv,
        (asdict(item) for item in stats),
        fieldnames=list(asdict(stats[0]).keys()) if stats else list(asdict(GripforceFileStats(
            "", "", "", "", "", "", "", "", 0, 0.0, 0.0, 0.0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "", ""
        )).keys()),
    )

    report_md = out_dir / "dataset_inventory.md"
    report_md.write_text(
        render_markdown_report(summary, stats, gripforce_root_summary, behavioral, paths, generated_at),
        encoding="utf-8",
    )

    print(f"Wrote {file_inventory_csv}")
    print(f"Wrote {report_md}")
    print(f"Gripforce files: {summary['n_files']} | Subjects: {summary['n_subjects']} | Tasks: {summary['tasks']}")
    if not behavioral.get("exists"):
        print(f"WARNING: behavioral_root not found: {behavioral_root}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to paths YAML (default: config/paths.local.yaml or paths.example.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for CSV/Markdown reports (default: reports/ or output_dir in config)",
    )
    args = parser.parse_args()
    return run_inventory(config_path=args.config, output_dir=args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
