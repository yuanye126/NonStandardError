/**
 * Minimal session store — persisted in sessionStorage so navigating back works.
 * No external state library; just typed helpers around sessionStorage.
 */

export interface ColumnInfo {
  name: string
  dtype: string
  n_missing: number
  n_zero: number
  n_unique: number
  zero_share: number
  missing_share: number
}

export interface UploadResult {
  dataset_id: string
  columns: ColumnInfo[]
  n_rows: number
}

export interface RolesState {
  dependent: string
  independent: string[]
  time_var: string | null
  country_var: string | null
  instruments: string[]
  required_vars: string[]
}

export interface ConfigState {
  dep_na_treatment: string[]
  dep_outlier: object[]
  dep_transform: string[]
  ind_na_treatment: object[]
  ind_outlier: object[]
  ind_transform: string[]
  fixed_effects: object[]
  models: string[]
  min_variables: number
  max_correlation: number
  target_combinations: number
  min_obs: number
  sample_size: number
  seed: number
}

function get<T>(key: string): T | null {
  const v = sessionStorage.getItem(key)
  if (!v) return null
  try { return JSON.parse(v) as T } catch { return null }
}

function set<T>(key: string, val: T): void {
  sessionStorage.setItem(key, JSON.stringify(val))
}

export const store = {
  getUpload: () => get<UploadResult>('upload'),
  setUpload: (v: UploadResult) => set('upload', v),

  getRoles: () => get<RolesState>('roles'),
  setRoles: (v: RolesState) => set('roles', v),

  getConfig: () => get<ConfigState>('config'),
  setConfig: (v: ConfigState) => set('config', v),

  getRunId: () => sessionStorage.getItem('run_id'),
  setRunId: (v: string) => sessionStorage.setItem('run_id', v),
}

// Default design-space config (paper defaults)
export const DEFAULT_DEP_OUTLIER = [
  { apply: false },
  { apply: true, method: 'winsorize', threshold: 0.01, symmetric: 'both' },
  { apply: true, method: 'truncate',  threshold: 0.01, symmetric: 'both' },
  { apply: true, method: 'winsorize', threshold: 0.05, symmetric: 'both' },
  { apply: true, method: 'truncate',  threshold: 0.05, symmetric: 'both' },
]

export const DEFAULT_FIXED_EFFECTS = [
  { time: null,      country: false, fe_method: 'dummy' },
  { time: null,      country: true,  fe_method: 'dummy' },
  { time: 'year',    country: true,  fe_method: 'dummy' },
  { time: 'year',    country: false, fe_method: 'dummy' },
  { time: 'quarter', country: false, fe_method: 'dummy' },
  { time: 'quarter', country: true,  fe_method: 'dummy' },
  { time: 'month',   country: false, fe_method: 'dummy' },
  { time: 'month',   country: true,  fe_method: 'dummy' },
]

export const DEFAULT_CONFIG: ConfigState = {
  dep_na_treatment: ['omit', 'zero'],
  dep_outlier: DEFAULT_DEP_OUTLIER,
  dep_transform: ['none'],
  ind_na_treatment: [{ method: 'omit' }],
  ind_outlier: DEFAULT_DEP_OUTLIER,
  ind_transform: ['none', 'zscore', 'mean_center'],
  fixed_effects: DEFAULT_FIXED_EFFECTS,
  models: ['OLS', 'RLM'],
  min_variables: 8,
  max_correlation: 0.7,
  target_combinations: 3000,
  min_obs: 100,
  sample_size: 20000,
  seed: 42,
}
