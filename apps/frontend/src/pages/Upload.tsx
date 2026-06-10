import { useCallback, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { store, UploadResult, ColumnInfo } from '../store'

const MAX_MB = 20
const MAX_BYTES = MAX_MB * 1024 * 1024

function FlaggedColumns({ cols }: { cols: ColumnInfo[] }) {
  const flagged = cols.filter(c => c.missing_share > 0.1 || c.zero_share > 0.3)
  if (!flagged.length) return null
  return (
    <div className="mt-2">
      <p className="small warn-text">
        <strong>Flagged columns</strong> — high missing or zero share (these are the axes that drive NSE):
      </p>
      <table>
        <thead><tr>
          <th>Column</th><th className="num">Missing %</th><th className="num">Zero %</th>
        </tr></thead>
        <tbody>{flagged.map(c => (
          <tr key={c.name}>
            <td><code>{c.name}</code></td>
            <td className="num">{(c.missing_share * 100).toFixed(1)}%</td>
            <td className="num">{(c.zero_share * 100).toFixed(1)}%</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  )
}

export default function UploadPage() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(() => store.getUpload())

  const processFile = useCallback(async (file: File) => {
    setError(null)
    if (file.size > MAX_BYTES) {
      setError(`File is ${(file.size / 1_048_576).toFixed(1)} MB — maximum is ${MAX_MB} MB.`)
      return
    }
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['csv', 'xlsx', 'xls'].includes(ext ?? '')) {
      setError('Only CSV and XLSX files are supported.')
      return
    }

    setLoading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch('/api/upload', { method: 'POST', body: form })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Upload failed (${res.status})`)
      }
      const data: UploadResult = await res.json()
      store.setUpload(data)
      setResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) processFile(file)
  }, [processFile])

  return (
    <>
      <h2>Upload dataset</h2>
      <p className="small muted">
        Upload a CSV or XLSX file (max {MAX_MB} MB). The file stays on the server for
        the duration of your session.
      </p>

      <div
        className={`dropzone mt-2${dragging ? ' dropzone--active' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <p style={{ fontSize: '1.1rem' }}>Drop file here or click to browse</p>
        <p className="dropzone__label">CSV or XLSX · max {MAX_MB} MB</p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          style={{ display: 'none' }}
          onChange={e => { const f = e.target.files?.[0]; if (f) processFile(f) }}
        />
      </div>

      {loading && <p className="small muted mt-2">Uploading…</p>}
      {error && <p className="warn-text mt-2">{error}</p>}

      {result && (
        <>
          <p className="small mt-2">
            <strong>{result.n_rows.toLocaleString()}</strong> rows ·{' '}
            <strong>{result.columns.length}</strong> columns
          </p>

          <FlaggedColumns cols={result.columns} />

          <h3>Column inventory</h3>
          <table>
            <thead><tr>
              <th>Column</th><th>Type</th>
              <th className="num">Missing</th>
              <th className="num">Zeros</th>
              <th className="num">Unique</th>
            </tr></thead>
            <tbody>{result.columns.map(c => (
              <tr key={c.name}>
                <td><code>{c.name}</code></td>
                <td><code>{c.dtype}</code></td>
                <td className="num">{(c.missing_share * 100).toFixed(1)}%</td>
                <td className="num">{(c.zero_share * 100).toFixed(1)}%</td>
                <td className="num">{c.n_unique.toLocaleString()}</td>
              </tr>
            ))}</tbody>
          </table>
          <p className="table-note">
            Note. Missing = share of null values; Zeros = share of exact zeros (numeric columns only).
          </p>

          <div className="mt-3">
            <button className="btn-primary" onClick={() => navigate('/roles')}>
              Continue to variable roles →
            </button>
          </div>
        </>
      )}
    </>
  )
}
