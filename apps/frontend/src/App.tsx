import { Routes, Route, Navigate } from 'react-router-dom'
import UploadPage from './pages/Upload'
import RolesPage from './pages/Roles'
import ConfigurePage from './pages/Configure'
import ResultsPage from './pages/Results'
import StepBar from './components/StepBar'

export default function App() {
  return (
    <div className="page">
      <header style={{ marginBottom: '0.25rem' }}>
        <h1>Non-Standard Errors — Multiverse Tool</h1>
        <p className="small muted">
          Measure specification-driven variation in regression estimates
        </p>
        <p className="small muted" style={{ marginTop: '0.15rem', fontStyle: 'italic' }}>
          For entrepreneurial finance researchers
        </p>
      </header>
      <hr />
      <StepBar />
      <Routes>
        <Route path="/" element={<Navigate to="/upload" replace />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/roles" element={<RolesPage />} />
        <Route path="/configure" element={<ConfigurePage />} />
        <Route path="/results" element={<ResultsPage />} />
      </Routes>
    </div>
  )
}
