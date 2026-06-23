"""Smoke tests for inventory script using synthetic fixtures."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_inventory import (  # noqa: E402
    find_gripforce_files,
    load_paths,
    run_inventory,
    summarize_gripforce,
    summarize_gripforce_file,
)
FIXTURE_CONFIG = ROOT / "tests" / "fixtures" / "paths.test.yaml"


def test_load_fixture_paths():
    paths = load_paths(FIXTURE_CONFIG)
    assert "gripforce_root" in paths
    assert "behavioral_root" in paths


def test_find_three_fixture_gripforce_files():
    paths = load_paths(FIXTURE_CONFIG)
    files = find_gripforce_files(ROOT / paths["gripforce_root"])
    assert len(files) == 3


def test_summarize_single_file_sample_rate():
    paths = load_paths(FIXTURE_CONFIG)
    files = find_gripforce_files(ROOT / paths["gripforce_root"])
    stats = summarize_gripforce_file(files[0])
    assert stats.n_rows > 0
    assert stats.sample_rate_hz == 100.0


def test_run_inventory_exit_code(tmp_path):
    assert run_inventory(config_path=FIXTURE_CONFIG, output_dir=tmp_path) == 0
    assert (tmp_path / "dataset_inventory.md").exists()
    assert (tmp_path / "gripforce_file_inventory.csv").exists()


def test_gripforce_summary_task_counts():
    paths = load_paths(FIXTURE_CONFIG)
    files = find_gripforce_files(ROOT / paths["gripforce_root"])
    stats = [summarize_gripforce_file(path) for path in files]
    summary = summarize_gripforce(stats)
    assert summary["tasks"] == {"Aoddball": 1, "MVCnPRAC": 1, "Voddball": 1}
