interface BreakdownLevel {
  value: string
  label: string
  nse: number
  se: number | null
  ratio: number | null
  n: number
}

interface BreakdownGroup {
  factor: string
  label: string
  levels: BreakdownLevel[]
}

interface CoefRow {
  name: string
  nse: number
  se: number | null
  ratio: number | null
  pct_positive: number
  pct_negative: number
  pct_sig: number | null
  breakdown?: BreakdownGroup[]
}

interface Props {
  coefficients: CoefRow[]
  selectedCoef?: string | null
}

function fmt2(v: number | null | undefined): string {
  if (v == null) return '—'
  return v.toFixed(2)
}

function fmt4(v: number | null | undefined): string {
  if (v == null) return '—'
  return v.toFixed(4)
}

export default function NseTable({ coefficients, selectedCoef }: Props) {
  const coef = (selectedCoef ? coefficients.find(c => c.name === selectedCoef) : null)
    ?? coefficients[0]

  if (!coef) return <p className="small muted">No coefficient data.</p>

  const breakdown = coef.breakdown ?? []

  return (
    <>
      <table>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', width: '55%' }}>Research-design choice</th>
            <th className="num">Non-standard errors</th>
            <th className="num">Standard errors</th>
            <th className="num">
              NSE / SE
            </th>
          </tr>
        </thead>
        <tbody>
          {/* Overall row */}
          <tr style={{ borderBottom: '1px solid var(--rule)' }}>
            <td>
              <em>Overall</em>
              <span className="small muted" style={{ marginLeft: '0.4rem' }}>
                ({coef.name})
              </span>
            </td>
            <td className="num"><strong>{fmt2(coef.nse)}</strong></td>
            <td className="num"><strong>{fmt4(coef.se)}</strong></td>
            <td className="num"><strong>{fmt2(coef.ratio)}</strong></td>
          </tr>

          {/* Per-factor breakdown */}
          {breakdown.map(group => (
            <>
              <tr key={group.factor}>
                <td
                  colSpan={4}
                  style={{ paddingTop: '0.9rem', paddingBottom: '0.1rem', fontStyle: 'italic' }}
                >
                  {group.label}
                </td>
              </tr>
              {group.levels.map(level => (
                <tr key={`${group.factor}-${level.value}`}>
                  <td style={{ paddingLeft: '2.2rem' }}>{level.label}</td>
                  <td className="num">{fmt2(level.nse)}</td>
                  <td className="num">{fmt4(level.se)}</td>
                  <td className="num">{fmt2(level.ratio)}</td>
                </tr>
              ))}
            </>
          ))}
        </tbody>
      </table>

      <p className="table-note" style={{ marginTop: '0.5rem' }}>
        Note. NSE = interquartile range (IQR) of estimates across all specifications
        that share that design choice. SE = mean per-specification standard error.
        Ratio = NSE / SE. Overall NSE/SE is computed across all specifications.
      </p>
    </>
  )
}
