# dynamometer-analysis

Analysis code for BAP in-scanner dynamometer (grip force) data.

## Local setup (Mac)

```bash
git clone https://github.com/mohdasti/dynamometer-analysis.git
cd dynamometer-analysis
cp config/paths.example.yaml config/paths.local.yaml
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Raw data stay outside this repo. See [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) for paths, file formats, and current goals.

## Data inventory

Run the inventory script against local paths in `config/paths.local.yaml`:

```bash
python scripts/run_inventory.py
```

This writes `reports/dataset_inventory.md` and `reports/gripforce_file_inventory.csv`. See [docs/DATA_LINKAGE.md](docs/DATA_LINKAGE.md) for how behavioral tables are expected to join gripforce files.

## Data (not in git)

| Resource | Default path |
|----------|--------------|
| Gripforce CSVs | `/Users/mohdasti/Documents/LC-BAP/BAP/BAP data` |
| Behavioral (Nov 2025) | `/Users/mohdasti/Documents/LC-BAP/BAP/Nov2025` |
