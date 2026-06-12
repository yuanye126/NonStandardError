import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  store, ConfigState, DEFAULT_CONFIG, DEFAULT_DEP_OUTLIER, DEFAULT_FIXED_EFFECTS,
} from '../store'
import { apiFetch } from '../api'

interface ValidateResult {
  valid: boolean
  errors: string[]
  warnings: string[]
  n_specs: number | null
  n_combos: number | null
  est_runtime_s: number | null
  will_sample: boolean | null
  sample_size: number | null
}

function OutlierToggle({
  label,
  active,
  onToggle,
}: {
  label: string
  active: boolean
  onToggle: () => void
}) {
  return (
    <label className="checkbox-row">
      <input type="checkbox" checked={active} onChange={onToggle} />
      {label}
    </label>
  )
}

export default function ConfigurePage() {
  const navigate = useNavigate()
  const upload = store.getUpload()
  const roles = store.getRoles()
  if (!upload || !roles) { navigate('/upload'); return null }

  const saved = store.getConfig() ?? DEFAULT_CONFIG
  const [cfg, setCfg] = useState<ConfigState>(saved)
  const [validation, setValidation] = useState<ValidateResult | null>(null)
  const [validating, setValidating] = useState(false)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const update = (patch: Partial<ConfigState>) => setCfg(prev => ({ ...prev, ...patch }))

  // Live validation on any change
  useEffect(() => {
    const timer = setTimeout(() => validate(), 400)
    return () => clearTimeout(timer)
  }, [cfg])

  const validate = useCallback(async () => {
    setValidating(true)
    try {
      const body = buildRequestBody()
      const res = await apiFetch('/api/configure/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) setValidation(await res.json())
    } catch {
      // ignore transient errors in live validation
    } finally {
      setValidating(false)
    }
  }, [cfg])

  const buildRequestBody = () => ({
    dataset_id: upload.dataset_id,
    config: {
      dataset: { path: '', format: upload.columns ? 'csv' : 'csv' },
      roles: {
        dependent: roles.dependent,
        independent: roles.independent,
        time_var: roles.time_var,
        country_var: roles.country_var,
        instruments: roles.instruments,
      },
      variable_selection: {
        min_variables: cfg.min_variables,
        max_correlation: cfg.max_correlation,
        required_vars: roles.required_vars,
        target_combinations: cfg.target_combinations,
      },
      design_space: {
        dep_na_treatment: cfg.dep_na_treatment,
        dep_outlier: cfg.dep_outlier,
        dep_transform: cfg.dep_transform,
        ind_na_treatment: cfg.ind_na_treatment,
        ind_outlier: cfg.ind_outlier,
        ind_transform: cfg.ind_transform,
        fixed_effects: cfg.fixed_effects,
        models: cfg.models,
      },
      constraints: { min_obs: cfg.min_obs },
      run: {
        mode: (validation?.n_specs ?? Infinity) <= 5000 ? 'full' : 'sample',
        sample_size: 5000,
        seed: cfg.seed,
        max_workers: 1,
      },
      focal_coefficients: roles.required_vars.length ? roles.required_vars : roles.independent.slice(0, 3),
    },
  })

  const startRun = async () => {
    store.setConfig(cfg)
    setRunning(true)
    setRunError(null)
    try {
      const body = buildRequestBody()
      const res = await apiFetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error((await res.json()).detail ?? 'Run failed')
      const { run_id } = await res.json()
      store.setRunId(run_id)
      navigate('/results')
    } catch (e: unknown) {
      setRunError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const toggleModel = (m: string) =>
    update({ models: cfg.models.includes(m) ? cfg.models.filter(x => x !== m) : [...cfg.models, m] })

  const toggleDepNa = (v: string) =>
    update({ dep_na_treatment: cfg.dep_na_treatment.includes(v)
      ? cfg.dep_na_treatment.filter(x => x !== v)
      : [...cfg.dep_na_treatment, v] })

  const toggleIndTransform = (v: string) =>
    update({ ind_transform: cfg.ind_transform.includes(v)
      ? cfg.ind_transform.filter(x => x !== v)
      : [...cfg.ind_transform, v] })

  const n = validation

  return (
    <>
      <h2>Configure design space</h2>
      <p className="small muted">
        Each toggle adds a fork to the specification multiverse. Paper defaults are pre-selected.
      </p>

      {/* Live spec count */}
      <div className="spec-bar mt-2">
        <span className="spec-bar__count">
          {n?.n_specs != null ? n.n_specs.toLocaleString() : '…'}
        </span>
        <span>total specifications</span>
        {n?.n_combos != null && (
          <span className="muted">({n.n_combos.toLocaleString()} variable combos)</span>
        )}
        {n?.est_runtime_s != null && (
          <span className="muted">· est. {n.est_runtime_s.toFixed(0)} s web preview</span>
        )}
        {n?.n_specs != null && n.n_specs > 5000 && (
          <span className="badge badge--info">
            web preview capped at 5,000 of {n.n_specs.toLocaleString()}
          </span>
        )}
        {validating && <span className="muted small">updating…</span>}
      </div>

      {n?.errors && n.errors.length > 0 && (
        <ul className="warn-text mb-1" style={{ paddingLeft: '1.2rem' }}>
          {n.errors.map(e => <li key={e}>{e}</li>)}
        </ul>
      )}
      {n?.warnings && n.warnings.length > 0 && (
        <ul className="small mb-1" style={{ paddingLeft: '1.2rem', color: 'var(--warn)' }}>
          {n.warnings.map(w => <li key={w}>{w}</li>)}
        </ul>
      )}

      <h3>Models</h3>
      <div>
        <OutlierToggle label="OLS" active={cfg.models.includes('OLS')} onToggle={() => toggleModel('OLS')} />
        <OutlierToggle label="RLM (robust)" active={cfg.models.includes('RLM')} onToggle={() => toggleModel('RLM')} />
        <OutlierToggle
          label="2SLS (instrumental variables)"
          active={cfg.models.includes('2SLS')}
          onToggle={() => toggleModel('2SLS')}
        />
        {cfg.models.includes('2SLS') && (
          <p className="small warn-text">
            2SLS multiplies specification count ×3. Recommended for the local export run.
          </p>
        )}
        <OutlierToggle
          label="Hurdle (two-part model for zero-inflated DV)"
          active={cfg.models.includes('Hurdle')}
          onToggle={() => toggleModel('Hurdle')}
        />
        {cfg.models.includes('Hurdle') && (
          <p className="small warn-text">
            Hurdle is slow. Recommended for the local export run.
          </p>
        )}
      </div>

      <h3>Dependent variable</h3>
      <div>
        <p className="small muted">NA treatment</p>
        {['omit', 'zero'].map(v => (
          <OutlierToggle key={v} label={v === 'omit' ? 'Omit missing rows' : 'Replace missing with zero'}
            active={cfg.dep_na_treatment.includes(v)} onToggle={() => toggleDepNa(v)} />
        ))}
      </div>

      <div className="mt-2">
        <p className="small muted">Outlier treatment — all 5 options are on by default (matches paper)</p>
        <OutlierToggle
          label={`All 5 outlier treatments (${DEFAULT_DEP_OUTLIER.length} options)`}
          active={cfg.dep_outlier.length === DEFAULT_DEP_OUTLIER.length}
          onToggle={() => update({ dep_outlier: cfg.dep_outlier.length === DEFAULT_DEP_OUTLIER.length ? [{ apply: false }] : DEFAULT_DEP_OUTLIER })}
        />
      </div>

      <h3>Independent variables</h3>
      <div>
        <p className="small muted">Transform</p>
        {['none', 'zscore', 'mean_center'].map(v => (
          <OutlierToggle key={v} label={v} active={cfg.ind_transform.includes(v)} onToggle={() => toggleIndTransform(v)} />
        ))}
      </div>

      <div className="mt-2">
        <p className="small muted">Outlier treatment</p>
        <OutlierToggle
          label={`All 5 outlier treatments`}
          active={cfg.ind_outlier.length === DEFAULT_DEP_OUTLIER.length}
          onToggle={() => update({ ind_outlier: cfg.ind_outlier.length === DEFAULT_DEP_OUTLIER.length ? [{ apply: false }] : DEFAULT_DEP_OUTLIER })}
        />
      </div>

      <h3>Fixed effects</h3>
      <div>
        <OutlierToggle
          label={`All 8 FE combinations (none / year / quarter / month × with/without country)`}
          active={cfg.fixed_effects.length === DEFAULT_FIXED_EFFECTS.length}
          onToggle={() => update({ fixed_effects: cfg.fixed_effects.length === DEFAULT_FIXED_EFFECTS.length
            ? [{ time: null, country: false, fe_method: 'dummy' }]
            : DEFAULT_FIXED_EFFECTS })}
        />
      </div>

      <h3>Variable selection</h3>
      <div className="role-grid mt-1">
        <div>
          <label>Min variables per spec</label>
          <input type="number" value={cfg.min_variables} min={1} max={20}
            onChange={e => update({ min_variables: Number(e.target.value) })} />
        </div>
        <div>
          <label>Max pairwise correlation (|ρ| &lt;)</label>
          <input type="number" value={cfg.max_correlation} min={0.1} max={0.99} step={0.05}
            onChange={e => update({ max_correlation: Number(e.target.value) })} />
        </div>
        <div>
          <label>Target variable combinations</label>
          <input type="number" value={cfg.target_combinations} min={100} max={50000}
            onChange={e => update({ target_combinations: Number(e.target.value) })} />
        </div>
        <div>
          <label>Min observations per spec</label>
          <input type="number" value={cfg.min_obs} min={10}
            onChange={e => update({ min_obs: Number(e.target.value) })} />
        </div>
      </div>

      <h3>Run settings</h3>
      <div className="role-grid">
        <div>
          <label>Random seed</label>
          <input type="number" value={cfg.seed}
            onChange={e => update({ seed: Number(e.target.value) })} />
        </div>
      </div>

      {runError && <p className="warn-text mt-2">{runError}</p>}

      <div className="row mt-3">
        <button onClick={() => navigate('/roles')}>← Back</button>
        <button
          className="btn-primary"
          onClick={startRun}
          disabled={running || (n !== null && !n.valid)}
        >
          {running ? 'Starting…' : 'Run multiverse →'}
        </button>
      </div>
    </>
  )
}
