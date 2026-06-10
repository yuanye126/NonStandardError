import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { store, RolesState, ColumnInfo } from '../store'

function MultiSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: string[]
  value: string[]
  onChange: (v: string[]) => void
}) {
  const toggle = (col: string) =>
    onChange(value.includes(col) ? value.filter(v => v !== col) : [...value, col])

  return (
    <div>
      <label><strong>{label}</strong></label>
      <div style={{ maxHeight: '10rem', overflowY: 'auto', border: '1px solid var(--rule)', padding: '0.5rem' }}>
        {options.map(col => (
          <label key={col} className="checkbox-row">
            <input type="checkbox" checked={value.includes(col)} onChange={() => toggle(col)} />
            <code>{col}</code>
          </label>
        ))}
      </div>
    </div>
  )
}

export default function RolesPage() {
  const navigate = useNavigate()
  const upload = store.getUpload()
  if (!upload) { navigate('/upload'); return null }

  const cols = upload.columns
  const colNames = cols.map(c => c.name)
  const colMap = Object.fromEntries(cols.map(c => [c.name, c]))

  const saved = store.getRoles()
  const [dep, setDep] = useState<string>(saved?.dependent ?? '')
  const [ind, setInd] = useState<string[]>(saved?.independent ?? [])
  const [timeVar, setTimeVar] = useState<string>(saved?.time_var ?? '')
  const [countryVar, setCountryVar] = useState<string>(saved?.country_var ?? '')
  const [instruments, setInstruments] = useState<string[]>(saved?.instruments ?? [])
  const [required, setRequired] = useState<string[]>(saved?.required_vars ?? [])

  const errors: string[] = []
  if (!dep) errors.push('Select a dependent variable.')
  if (ind.length < 2) errors.push('Select at least 2 independent variables.')

  const depInfo = dep ? colMap[dep] : null

  const save = () => {
    const roles: RolesState = {
      dependent: dep,
      independent: ind,
      time_var: timeVar || null,
      country_var: countryVar || null,
      instruments,
      required_vars: required,
    }
    store.setRoles(roles)
    navigate('/configure')
  }

  return (
    <>
      <h2>Assign variable roles</h2>
      <p className="small muted">
        Assign each column a role. The dependent variable (DV) and independent variables (IVs)
        are required. Time and country variables enable fixed effects.
      </p>

      <div className="role-grid mt-2">
        <div>
          <label><strong>Dependent variable</strong></label>
          <select value={dep} onChange={e => setDep(e.target.value)}>
            <option value="">— select —</option>
            {colNames.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {depInfo && (
            <p className="small mt-1">
              {(depInfo.missing_share * 100).toFixed(1)}% missing ·{' '}
              {(depInfo.zero_share * 100).toFixed(1)}% zero
              {depInfo.zero_share > 0.1 && (
                <span className="badge badge--warn" style={{ marginLeft: '0.4rem' }}>
                  high zero-mass → Hurdle model available
                </span>
              )}
            </p>
          )}
        </div>

        <div>
          <label><strong>Time variable</strong> <span className="muted small">(optional)</span></label>
          <select value={timeVar} onChange={e => setTimeVar(e.target.value)}>
            <option value="">— none —</option>
            {colNames.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label><strong>Country variable</strong> <span className="muted small">(optional)</span></label>
          <select value={countryVar} onChange={e => setCountryVar(e.target.value)}>
            <option value="">— none —</option>
            {colNames.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="mt-2">
        <MultiSelect
          label="Independent variables"
          options={colNames.filter(c => c !== dep && c !== timeVar && c !== countryVar)}
          value={ind}
          onChange={setInd}
        />
        <p className="small muted mt-1">{ind.length} selected</p>
      </div>

      {ind.length > 0 && (
        <div className="mt-2">
          <label><strong>Pin required variables</strong> <span className="muted small">(always included in each specification)</span></label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.35rem' }}>
            {ind.map(v => (
              <label key={v} className="checkbox-row" style={{ margin: 0 }}>
                <input
                  type="checkbox"
                  checked={required.includes(v)}
                  onChange={() => setRequired(required.includes(v)
                    ? required.filter(r => r !== v)
                    : [...required, v]
                  )}
                />
                <code>{v}</code>
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="mt-2">
        <MultiSelect
          label="Instruments (for 2SLS)"
          options={colNames.filter(c => !ind.includes(c) && c !== dep && c !== timeVar && c !== countryVar)}
          value={instruments}
          onChange={setInstruments}
        />
        <p className="small muted mt-1">Leave empty if not using 2SLS.</p>
      </div>

      {errors.length > 0 && (
        <ul className="warn-text mt-2" style={{ paddingLeft: '1.2rem' }}>
          {errors.map(e => <li key={e}>{e}</li>)}
        </ul>
      )}

      <div className="row mt-3">
        <button onClick={() => navigate('/upload')}>← Back</button>
        <button className="btn-primary" onClick={save} disabled={errors.length > 0}>
          Continue to configuration →
        </button>
      </div>
    </>
  )
}
