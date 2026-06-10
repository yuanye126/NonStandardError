/**
 * Hurdle model comparison panel (Table-11 style).
 * Only rendered when hurdle.available = true.
 */
interface HurdleRow {
  name: string
  model: string
  iqr_med: number | null
  iqr_med_hurdle: number | null
  delta: number | null
}

interface MPE {
  unconditional: Record<string, number>
  conditional: Record<string, number>
}

interface Props {
  hurdle: {
    available: boolean
    rows?: HurdleRow[]
    mpe?: MPE
  }
}

function fmt(v: number | null, decimals = 3): string {
  if (v == null) return '—'
  return v.toFixed(decimals)
}

export default function HurdlePanel({ hurdle }: Props) {
  if (!hurdle.available) return null

  return (
    <>
      <h2>Hurdle model comparison</h2>
      <p className="small muted">
        Compares NSE/|median| across traditional models and the two-part hurdle model.
        A smaller ratio indicates a more stable effect when the zero mass is modelled explicitly.
      </p>
      <table>
        <thead>
          <tr>
            <th>Coefficient</th>
            <th>Model</th>
            <th className="num">IQR/|med| (model)</th>
            <th className="num">IQR/|med| (hurdle)</th>
            <th className="num">Δ (%)</th>
          </tr>
        </thead>
        <tbody>
          {(hurdle.rows ?? []).map((row, i) => (
            <tr key={i}>
              <td><code>{row.name}</code></td>
              <td>{row.model}</td>
              <td className="num">{fmt(row.iqr_med)}</td>
              <td className="num">{fmt(row.iqr_med_hurdle)}</td>
              <td className="num">
                {row.delta != null
                  ? <span style={{ color: row.delta < 0 ? 'var(--accent)' : 'var(--warn)' }}>
                      {row.delta > 0 ? '+' : ''}{(row.delta * 100).toFixed(1)}%
                    </span>
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="table-note">
        Note. IQR/|med| = interquartile range of coefficient estimates divided by the absolute
        median. Δ = relative change from traditional to hurdle model.
      </p>

      {hurdle.mpe && (
        <div className="mt-2">
          <h3>Marginal partial effects (MPE)</h3>
          <table>
            <thead><tr>
              <th>Estimand</th>
              <th>Model</th>
              <th className="num">Median fitted</th>
            </tr></thead>
            <tbody>
              {Object.entries(hurdle.mpe.unconditional ?? {}).map(([m, v]) => (
                <tr key={`unc-${m}`}>
                  <td>Unconditional</td>
                  <td>{m.toUpperCase()}</td>
                  <td className="num">{fmt(v)}</td>
                </tr>
              ))}
              {Object.entries(hurdle.mpe.conditional ?? {}).map(([m, v]) => (
                <tr key={`cond-${m}`}>
                  <td>Conditional (y &gt; 0)</td>
                  <td>{m.toUpperCase()}</td>
                  <td className="num">{fmt(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
