/**
 * NSE / SE / Ratio table — booktabs style.
 */
interface PredRow {
  nse: number
  se: number | null
  ratio: number | null
}

interface CoefRow {
  name: string
  nse: number
  se: number | null
  ratio: number | null
  pct_positive: number
  pct_negative: number
  pct_sig: number | null
}

interface Props {
  predictions: PredRow | null
  coefficients: CoefRow[]
}

function fmt(v: number | null | undefined, decimals = 3): string {
  if (v == null) return '—'
  return v.toFixed(decimals)
}

export default function NseTable({ predictions, coefficients }: Props) {
  return (
    <>
      <table>
        <thead>
          <tr>
            <th>Quantity</th>
            <th className="num">NSE</th>
            <th className="num">SE</th>
            <th className="num">Ratio (NSE/SE)</th>
            <th className="num">% positive</th>
            <th className="num">% sig.</th>
          </tr>
        </thead>
        <tbody>
          {predictions && (
            <tr>
              <td><em>Predicted funding</em></td>
              <td className="num">{fmt(predictions.nse)}</td>
              <td className="num">{fmt(predictions.se)}</td>
              <td className="num"><strong>{fmt(predictions.ratio, 1)}</strong></td>
              <td className="num">—</td>
              <td className="num">—</td>
            </tr>
          )}
          {coefficients.map(c => (
            <tr key={c.name}>
              <td><code>{c.name}</code></td>
              <td className="num">{fmt(c.nse)}</td>
              <td className="num">{fmt(c.se)}</td>
              <td className="num"><strong>{fmt(c.ratio, 2)}</strong></td>
              <td className="num">{c.pct_positive != null ? `${(c.pct_positive * 100).toFixed(0)}%` : '—'}</td>
              <td className="num">{c.pct_sig != null ? `${(c.pct_sig * 100).toFixed(0)}%` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="table-note">
        Note. NSE = interquartile range of estimates across specifications (Q3 − Q1).
        SE = mean of per-specification reported standard errors. Ratio = NSE/SE.
        Sig. = share of specifications with p &lt; 0.05.
      </p>
    </>
  )
}
