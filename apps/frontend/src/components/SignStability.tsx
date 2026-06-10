/**
 * Sign / significance stability bars.
 */
interface CoefData {
  name: string
  pct_positive: number
  pct_negative: number
  pct_sig: number | null
}

interface Props { coefficients: CoefData[] }

function StackedBar({ pos, neg, sig }: { pos: number; neg: number; sig: number | null }) {
  return (
    <div style={{ display: 'flex', height: '14px', width: '100%', gap: '1px' }}>
      <div title={`${(pos * 100).toFixed(1)}% positive`}
        style={{ width: `${pos * 100}%`, background: 'var(--accent)', opacity: 0.8 }} />
      <div title={`${(neg * 100).toFixed(1)}% negative`}
        style={{ width: `${neg * 100}%`, background: 'var(--muted)', opacity: 0.6 }} />
    </div>
  )
}

export default function SignStability({ coefficients }: Props) {
  return (
    <table>
      <thead>
        <tr>
          <th>Coefficient</th>
          <th className="num">% positive</th>
          <th className="num">% negative</th>
          <th className="num">% significant (p &lt; .05)</th>
          <th>Direction</th>
        </tr>
      </thead>
      <tbody>
        {coefficients.map(c => (
          <tr key={c.name}>
            <td><code>{c.name}</code></td>
            <td className="num">{(c.pct_positive * 100).toFixed(0)}%</td>
            <td className="num">{(c.pct_negative * 100).toFixed(0)}%</td>
            <td className="num">{c.pct_sig != null ? `${(c.pct_sig * 100).toFixed(0)}%` : '—'}</td>
            <td style={{ width: '200px' }}>
              <StackedBar pos={c.pct_positive} neg={c.pct_negative} sig={c.pct_sig} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
