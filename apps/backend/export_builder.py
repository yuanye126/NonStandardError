"""
Build the replication zip package for download.

nse_replication/
  nse_engine/         (copied engine source)
  config.json         (mode forced to "full")
  data.csv
  combos.csv          (precomputed combos)
  run.py
  requirements.txt
  Dockerfile
  README.md
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "nse_engine"))

from nse_engine.config import Config

_ENGINE_DIR = Path(__file__).resolve().parents[2] / "packages" / "nse_engine"


def build_export_zip(
    config_dict: dict,
    data_path: str,
    parquet_path: str,
    combos_csv_path: str | None = None,
) -> bytes:
    """Return the zip file bytes ready for streaming."""
    buf = io.BytesIO()

    # Force mode to "full" in the exported config
    export_config = json.loads(json.dumps(config_dict))
    export_config.setdefault("run", {})["mode"] = "full"
    export_config.setdefault("run", {}).pop("sample_size", None)
    export_config["dataset"] = {"path": "data.csv", "format": "csv"}
    if combos_csv_path:
        export_config.setdefault("variable_selection", {})["precomputed_combos_path"] = "combos.csv"

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Engine package
        engine_pkg = _ENGINE_DIR / "nse_engine"
        for py_file in engine_pkg.rglob("*.py"):
            arcname = "nse_replication/nse_engine/" + py_file.relative_to(engine_pkg).as_posix()
            zf.write(py_file, arcname)

        # config.json
        zf.writestr("nse_replication/config.json", json.dumps(export_config, indent=2))

        # data.csv
        zf.write(data_path, "nse_replication/data.csv")

        # combos.csv (optional)
        if combos_csv_path and Path(combos_csv_path).exists():
            zf.write(combos_csv_path, "nse_replication/combos.csv")

        # run.py
        run_py = _ENGINE_DIR / "run.py"
        zf.write(run_py, "nse_replication/run.py")

        # requirements.txt
        zf.writestr(
            "nse_replication/requirements.txt",
            (
                "pandas>=2.0\n"
                "numpy>=1.24\n"
                "statsmodels>=0.14\n"
                "linearmodels>=5.3\n"
                "scipy>=1.10\n"
                "pyarrow>=12.0\n"
                "openpyxl>=3.1\n"
            ),
        )

        # Dockerfile
        zf.writestr(
            "nse_replication/Dockerfile",
            _DOCKERFILE,
        )

        # Static HTML results (if parquet exists, generate now)
        try:
            if Path(parquet_path).exists():
                import json as _json
                from nse_engine.aggregate import aggregate as _agg
                from nse_engine.report import generate_html_report as _html
                agg = _agg(
                    parquet_path=parquet_path,
                    config_dict=export_config,
                    n_specs_run=0, n_specs_total=0,
                    sampled=False, failure_stats={},
                )
                zf.writestr("nse_replication/results_preview.html", _html(agg))
        except Exception:
            pass

        # README.md
        n_specs = export_config.get("run", {}).get("sample_size", "full")
        readme = _README.format(
            focal=", ".join(export_config.get("focal_coefficients", ["<coefficient>"])),
        )
        zf.writestr("nse_replication/README.md", readme)

    buf.seek(0)
    return buf.read()


_DOCKERFILE = """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "run.py", "--config", "config.json", "--output-dir", "output"]
"""

_README = """\
# NSE Replication Package

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python run.py --config config.json --output-dir output
```

This runs the **full** (uncapped) multiverse on your local machine using all available CPU cores.
Results are written to `output/results.json` (aggregated statistics) and `output/results.parquet`
(per-specification rows for custom analysis).

## Focal coefficients

{focal}

## Reproducing the web preview

The web preview used `mode: sample`. To reproduce it exactly, change `run.mode` to `"sample"` in
`config.json` and set `run.sample_size` to the value shown on the results page.

## Docker (optional)

```bash
docker build -t nse-replication .
docker run -v $(pwd)/output:/app/output nse-replication
```
"""
