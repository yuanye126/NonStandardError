# nse_engine

Standalone Python package that runs the Non-Standard Errors (NSE) multiverse analysis.

## Install

```bash
pip install -e .
# or with all dependencies:
pip install -r requirements.txt && pip install -e .
```

## CLI usage

```bash
python run.py --config config.json --output-dir output/
```

Outputs:
- `output/results.parquet` — per-specification rows (full schema)
- `output/results.json`    — aggregated NSE/SE/ratio statistics
- `output/results.html`    — self-contained HTML report

## Config format

See `nse_engine/config.py` and the top-level `SPEC.md` for the full JSON schema.
The `mode` field controls sampling:

- `"mode": "sample"` — draw `sample_size` specs via Sobol (reproducible by `seed`)
- `"mode": "full"`   — run the complete specification multiverse

## Python API

```python
from nse_engine import Config, run_multiverse, aggregate

config = Config.from_json("config.json")
result = run_multiverse(config, output_path="output/results.parquet")
agg = aggregate(
    parquet_path="output/results.parquet",
    config_dict=config.to_dict(),
    **{k: result[k] for k in ("n_specs_run","n_specs_total","sampled","failure_stats")},
)
```
