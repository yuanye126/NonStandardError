import { useLocation, Link } from 'react-router-dom'

const STEPS = [
  { path: '/upload',    label: '1. Upload' },
  { path: '/roles',     label: '2. Roles' },
  { path: '/configure', label: '3. Configure' },
  { path: '/results',   label: '4. Results' },
]

export default function StepBar() {
  const { pathname } = useLocation()
  const currentIdx = STEPS.findIndex(s => pathname.startsWith(s.path))

  return (
    <nav className="step-bar" aria-label="Steps">
      {STEPS.map((step, i) => {
        let cls = 'step-bar__item'
        if (i === currentIdx) cls += ' step-bar__item--active'
        else if (i < currentIdx) cls += ' step-bar__item--done'
        return (
          <span key={step.path} className={cls}>
            {i < currentIdx
              ? <Link to={step.path}>{step.label}</Link>
              : step.label}
          </span>
        )
      })}
    </nav>
  )
}
