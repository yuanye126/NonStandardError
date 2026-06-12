import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { store } from '../store'
import { apiFetch, API_BASE } from '../api'
import NseTable from '../components/NseTable'
import SpecCurve from '../components/SpecCurve'
import VarianceDecomp from '../components/VarianceDecomp'
import SignStability from '../components/SignStability'
import HurdlePanel from '../components/HurdlePanel'

interface RunStatus {
  run_id: string
  state: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  n_done: number
  n_total: number
  failure_message: string | null
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Results = any

export default function ResultsPage() {
  const navigate = useNavigate()
  const runId = store.getRunId()
  if (!runId) { navigate('/upload'); return null }

  const [status, setStatus] = useState<RunStatus | null>(null)
  const [results, setResults] = useState<Results | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedCoef, setSelectedCoef] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/run/${runId}/status`)
        if (!res.ok) return
        const s: RunStatus = await res.json()
        setStatus(s)
        if (s.state === 'done') {
          clearInterval(pollRef.current!)
          const rres = await apiFetch(`/api/results/${runId}`)
          if (rres.ok) setResults(await rres.json())
        } else if (s.state === 'failed') {
          clearInterval(pollRef.current!)
          setError(s.failure_message ?? 'Run failed')
        }
      } catch (e) {
        setError(String(e))
        clearInterval(pollRef.current!)
      }
    }, 2000)
    return () => clearInterval(pollRef.current!)
  }, [runId])

  const downloadExport = () => window.open(`${API_BASE}/api/export/${runId}`, '_blank')

  if (error) return (
    <div>
      <h2>Run failed</h2>
      <p className="warn-text">{error}</p>
      <button className="mt-2" onClick={() => navigate('/configure')}>← Back to configure</button>
    </div>
  )

  if (!results) {
    const pct = status ? Math.round((status.progress ?? 0) * 100) : 0
    return (
      <div>
        <h2>Running multiverse…</h2>
        <div className="progress-track mt-2">
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
        <p className="small muted mt-1">
          {status?.state === 'queued' ? 'Queued…' :
            status ? `${status.n_done.toLocaleString()} / ${status.n_total.toLocaleString()} specifications (${pct}%)` :
            'Connecting…'}
        </p>
      </div>
    )
  }

  const meta = results.meta ?? {}
  const coefs = results.coefficients ?? []
  const specCurveData = selectedCoef
    ? { ...results.spec_curve, coefficient: selectedCoef }
    : results.spec_curve

  return (
    <>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '0.5rem' }}>
        <div>
          <h2 style={{ margin: 0 }}>Results</h2>
          {meta.sampled && (
            <p className="small muted">
              Based on <strong>{meta.n_specs_run?.toLocaleString()}</strong> sampled
              specifications of <strong>{meta.n_specs_total?.toLocaleString()}</strong> total
            </p>
          )}
        </div>
        <button onClick={downloadExport} className="btn-primary">
          Download replication package
        </button>
      </div>

      {/* Failure stats disclosure */}
      {meta.failure_stats && Object.keys(meta.failure_stats).length > 0 && (
        <details className="small mt-1" style={{ marginBottom: '1rem' }}>
          <summary className="muted" style={{ cursor: 'pointer' }}>
            Specification failures (
            {Object.values(meta.failure_stats as Record<string, number>).reduce((a, b) => a + b, 0)}
            )
          </summary>
          <table style={{ marginTop: '0.5rem' }}>
            <thead><tr><th>Reason</th><th className="num">Count</th></tr></thead>
            <tbody>
              {Object.entries(meta.failure_stats as Record<string, number>).map(([k, v]) => (
                <tr key={k}><td><code>{k}</code></td><td className="num">{v}</td></tr>
              ))}
            </tbody>
          </table>
        </details>
      )}

      <hr />

      {/* NSE / SE table */}
      <h2>Non-standard errors</h2>
      <NseTable coefficients={coefs} selectedCoef={selectedCoef} />

      <hr />

      {/* Spec curve with coefficient selector */}
      <h2>Specification curve</h2>
      {coefs.length > 1 && (
        <div className="row mt-1 mb-1">
          <label className="small" style={{ margin: 0 }}>Focal coefficient:</label>
          <select
            value={selectedCoef ?? results.spec_curve?.coefficient ?? ''}
            onChange={e => setSelectedCoef(e.target.value)}
            style={{ width: 'auto', fontSize: '0.88rem' }}
          >
            {coefs.map((c: { name: string }) => (
              <option key={c.name} value={c.name}>{c.name}</option>
            ))}
          </select>
        </div>
      )}
      {specCurveData?.points?.length > 0
        ? <SpecCurve data={specCurveData} />
        : <p className="small muted">No spec curve data.</p>
      }

      <hr />

      {/* Variance decomposition */}
      <h2>Variance decomposition</h2>
      <p className="small muted">
        Which design choices drive the spread in estimates? Each bar shows that factor's share
        of explained variance (sequential R², normalized).
      </p>
      <VarianceDecomp coefficients={coefs} />

      <hr />

      {/* Sign stability */}
      <h2>Sign and significance stability</h2>
      <SignStability coefficients={coefs} />
      <p className="table-note" style={{ marginTop: '0.35rem' }}>
        Note. Each row summarizes the sign and significance of the coefficient across all
        specifications in which that variable appears.
      </p>

      <hr />

      {/* Hurdle panel */}
      <HurdlePanel hurdle={results.hurdle ?? { available: false }} />

      {/* Sticky export button */}
      <div className="sticky-export mt-3">
        <button onClick={downloadExport}>
          Download replication package (.zip)
        </button>
      </div>
    </>
  )
}
