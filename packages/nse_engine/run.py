#!/usr/bin/env python3
"""CLI entry point: python run.py --config config.json"""
import argparse
import json
import sys
from pathlib import Path

from nse_engine import Config, run_multiverse, aggregate
from nse_engine.report import write_html_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NSE multiverse analysis")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = Config.from_json(str(config_path))

    # Validate (without column checks — the engine will catch missing columns)
    config.validate()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = str(output_dir / "results.parquet")

    def progress(done: int, total: int) -> None:
        pct = 100 * done // total
        print(f"\r  {done}/{total} specs ({pct}%)  ", end="", flush=True)

    print(f"Running multiverse (mode={config.run.mode}) ...")
    result = run_multiverse(config, progress_callback=progress, output_path=parquet_path)
    print()
    print(f"Done in {result['elapsed_s']:.1f}s  |  "
          f"{result['n_specs_run']} specs run "
          f"({'sampled' if result['sampled'] else 'full'} of {result['n_specs_total']})")
    if result["failure_stats"]:
        print(f"Failures: {result['failure_stats']}")

    print("Computing aggregates ...")
    config_dict = config.to_dict()
    agg = aggregate(
        parquet_path=parquet_path,
        config_dict=config_dict,
        n_specs_run=result["n_specs_run"],
        n_specs_total=result["n_specs_total"],
        sampled=result["sampled"],
        failure_stats=result["failure_stats"],
    )

    results_path = output_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(agg, f, indent=2, default=str)
    print(f"Results written to {results_path}")

    html_path = output_dir / "results.html"
    write_html_report(agg, str(html_path))
    print(f"HTML report written to {html_path}")

    # Print summary
    if agg["predictions"]:
        p = agg["predictions"]
        print(f"\nPredictions: NSE={p['nse']:.2f}  SE={p['se']:.4f}  Ratio={p.get('ratio', '?'):.1f}")
    for coef in agg["coefficients"]:
        print(f"  {coef['name']}: NSE={coef['nse']:.4f}  SE={coef['se']:.4f}  "
              f"Ratio={coef.get('ratio', '?'):.2f}  "
              f"+{coef['pct_positive']:.0%} -{coef['pct_negative']:.0%} "
              f"sig{coef.get('pct_sig', 0):.0%}")


if __name__ == "__main__":
    main()
