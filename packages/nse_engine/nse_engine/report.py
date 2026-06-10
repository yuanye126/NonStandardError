"""
Generate a self-contained static HTML results report from the aggregated results JSON.
Used by the local export run and by the web export builder.
"""
from __future__ import annotations

import json
from pathlib import Path


_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --serif: 'EB Garamond', Georgia, 'Times New Roman', serif;
  --mono: 'Source Code Pro', 'Courier New', monospace;
  --ink: #111; --paper: #faf9f6; --rule: #999; --rule-light: #ccc;
  --accent: #2c3e7a; --muted: #555;
  font-size: 16px; line-height: 1.6;
}
body { font-family: var(--serif); background: var(--paper); color: var(--ink);
  max-width: 760px; margin: 0 auto; padding: 2.5rem 2rem 5rem; }
h1 { font-size: 1.5rem; font-weight: 500; margin-bottom: 0.4rem; }
h2 { font-size: 1.15rem; font-weight: 500; margin: 2.5rem 0 0.6rem; }
h3 { font-size: 1rem; font-weight: 600; margin: 1.5rem 0 0.4rem; }
p { margin-bottom: 0.6rem; }
small, .small { font-size: 0.82rem; color: var(--muted); }
code { font-family: var(--mono); font-size: 0.84em; }
hr { border: none; border-top: 1px solid var(--rule-light); margin: 2rem 0; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0 0.2rem; font-size: 0.88rem; }
thead tr th { font-weight: 600; padding: 0.3rem 0.55rem;
  border-top: 1.5px solid var(--ink); border-bottom: 1px solid var(--ink); text-align: left; }
thead tr th.num { text-align: right; }
tbody tr td { padding: 0.25rem 0.55rem; }
tbody tr td.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr:last-child td { border-bottom: 1.5px solid var(--ink); }
.note { font-size: 0.76rem; color: var(--muted); font-style: italic; margin-top: 0.3rem; }
.badge { display: inline-block; font-size: 0.72rem; font-family: var(--mono);
  border: 1px solid var(--accent); color: var(--accent); padding: 0 0.35rem; }
"""


def _fmt(v, decimals=3):
    if v is None:
        return "—"
    try:
        return f"{float(v):.{decimals}f}"
    except Exception:
        return str(v)


def _pct(v):
    if v is None:
        return "—"
    return f"{float(v)*100:.0f}%"


def generate_html_report(results: dict) -> str:
    meta = results.get("meta", {})
    coefs = results.get("coefficients", [])
    pred = results.get("predictions")
    hurdle = results.get("hurdle", {})

    sampled_note = ""
    if meta.get("sampled"):
        sampled_note = (
            f'<p class="small">Based on <strong>{meta["n_specs_run"]:,}</strong> sampled '
            f'specifications of <strong>{meta["n_specs_total"]:,}</strong> total. '
            f'Models: {", ".join(meta.get("models", []))}.</p>'
        )

    # --- NSE table ---
    rows_html = ""
    if pred:
        rows_html += f"""<tr>
          <td><em>Predicted values</em></td>
          <td class="num">{_fmt(pred.get('nse'))}</td>
          <td class="num">{_fmt(pred.get('se'))}</td>
          <td class="num"><strong>{_fmt(pred.get('ratio'), 1)}</strong></td>
          <td class="num">—</td><td class="num">—</td></tr>"""
    for c in coefs:
        rows_html += f"""<tr>
          <td><code>{c['name']}</code></td>
          <td class="num">{_fmt(c.get('nse'))}</td>
          <td class="num">{_fmt(c.get('se'))}</td>
          <td class="num"><strong>{_fmt(c.get('ratio'), 2)}</strong></td>
          <td class="num">{_pct(c.get('pct_positive'))}</td>
          <td class="num">{_pct(c.get('pct_sig'))}</td></tr>"""

    nse_table = f"""
    <table>
      <thead><tr>
        <th>Quantity</th><th class="num">NSE</th><th class="num">SE</th>
        <th class="num">Ratio</th><th class="num">% positive</th><th class="num">% sig.</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p class="note">NSE = IQR of estimates across specifications. SE = mean per-spec standard error.
    Sig. = share with p&lt;0.05.</p>
    """

    # --- Variance decomp ---
    vd_html = ""
    for c in coefs:
        shares = c.get("variance_share", {})
        if not shares:
            continue
        sorted_s = sorted(shares.items(), key=lambda x: -x[1])
        dominant = sorted_s[0] if sorted_s else None
        rows = "".join(
            f'<tr><td>{k.replace("_str","").replace("_"," ")}</td>'
            f'<td class="num">{_pct(v)}</td></tr>'
            for k, v in sorted_s
        )
        dom_badge = (
            f' <span class="badge">{dominant[0].replace("_str","").replace("_"," ")}'
            f' {_pct(dominant[1])}</span>'
            if dominant else ""
        )
        vd_html += f"""
        <h3><code>{c['name']}</code>{dom_badge}</h3>
        <table><thead><tr><th>Factor</th><th class="num">Variance share</th></tr></thead>
        <tbody>{rows}</tbody></table>"""

    # --- Hurdle ---
    hurdle_html = ""
    if hurdle.get("available"):
        h_rows = "".join(
            f'<tr><td><code>{r["name"]}</code></td><td>{r["model"]}</td>'
            f'<td class="num">{_fmt(r.get("iqr_med"))}</td>'
            f'<td class="num">{_fmt(r.get("iqr_med_hurdle"))}</td>'
            f'<td class="num">{_fmt(r.get("delta"),4) if r.get("delta") is not None else "—"}</td></tr>'
            for r in hurdle.get("rows", [])
        )
        hurdle_html = f"""
        <hr>
        <h2>Hurdle model comparison</h2>
        <table><thead><tr>
          <th>Coefficient</th><th>Model</th>
          <th class="num">IQR/|med|</th><th class="num">IQR/|med| (hurdle)</th><th class="num">Δ</th>
        </tr></thead><tbody>{h_rows}</tbody></table>"""

    # --- Failure stats ---
    failure_html = ""
    fs = meta.get("failure_stats", {})
    if fs:
        f_rows = "".join(
            f'<tr><td><code>{k}</code></td><td class="num">{v}</td></tr>'
            for k, v in fs.items()
        )
        failure_html = f"""
        <details class="small"><summary>Specification failures</summary>
        <table><thead><tr><th>Reason</th><th class="num">Count</th></tr></thead>
        <tbody>{f_rows}</tbody></table></details>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>NSE Results</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=Source+Code+Pro:wght@400&display=swap" rel="stylesheet">
  <style>{_CSS}</style>
</head>
<body>
  <h1>Non-Standard Errors — Results</h1>
  {sampled_note}
  {failure_html}
  <hr>
  <h2>Non-standard errors</h2>
  {nse_table}
  <hr>
  <h2>Variance decomposition</h2>
  <p class="small">Share of variance in each focal coefficient explained by each design factor
  (sequential R², normalized to sum to 1).</p>
  {vd_html}
  {hurdle_html}
</body>
</html>
"""


def write_html_report(results: dict, output_path: str) -> None:
    html = generate_html_report(results)
    Path(output_path).write_text(html, encoding="utf-8")
