/**
 * Variance decomposition panel — horizontal bar chart showing each design factor's
 * share of explained variance in the coefficient, plus sign/significance stability.
 */
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

interface CoefData {
  name: string
  variance_share: Record<string, number>
  by_factor: Record<string, number>
  pct_positive: number
  pct_negative: number
  pct_sig: number | null
}

interface Props {
  coefficients: CoefData[]
}

const LABEL_MAP: Record<string, string> = {
  dep_na_treatment: 'DV missing-data coding',
  dep_transform: 'DV transformation',
  dep_outlier_str: 'DV outlier treatment',
  dep_outlier: 'DV outlier treatment',
  ind_transform: 'IV transformation',
  ind_outlier_str: 'IV outlier treatment',
  ind_outlier: 'IV outlier treatment',
  ind_na_treatment_str: 'IV missing-data coding',
  ind_na_treatment: 'IV missing-data coding',
  model_type: 'Model type',
  fixed_effects_str: 'Fixed effects',
  fixed_effects: 'Fixed effects',
}

function VarBarChart({ shares }: { shares: Record<string, number> }) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current) return
    const entries = Object.entries(shares).sort((a, b) => b[1] - a[1])
    if (!entries.length) return

    const W = svgRef.current.clientWidth || 500
    const rowH = 20
    const lw = 220
    const bw = W - lw - 60
    const H = entries.length * rowH + 4

    const svg = d3.select(svgRef.current).attr('height', H)
    svg.selectAll('*').remove()

    const x = d3.scaleLinear().domain([0, 1]).range([0, bw])

    entries.forEach(([key, val], i) => {
      const y = i * rowH + 2
      const label = LABEL_MAP[key] ?? key
      const g = svg.append('g').attr('transform', `translate(0,${y})`)

      g.append('text')
        .attr('x', lw - 8).attr('y', 13)
        .attr('text-anchor', 'end')
        .attr('font-size', 11).attr('font-family', 'var(--serif)')
        .attr('fill', 'var(--ink)')
        .text(label)

      g.append('rect')
        .attr('x', lw).attr('y', 3)
        .attr('width', x(Math.min(val, 1))).attr('height', 13)
        .attr('fill', key.startsWith('dep_na') ? 'var(--accent)' : 'var(--ink)')
        .attr('opacity', 0.75)

      g.append('text')
        .attr('x', lw + x(Math.min(val, 1)) + 5).attr('y', 13)
        .attr('font-size', 10).attr('font-family', 'var(--mono)')
        .attr('fill', 'var(--muted)')
        .text(`${(val * 100).toFixed(1)}%`)
    })
  }, [shares])

  return <svg ref={svgRef} width="100%" style={{ display: 'block' }} />
}

export default function VarianceDecomp({ coefficients }: Props) {
  return (
    <>
      {coefficients.map(c => {
        const shares = c.variance_share ?? {}
        const dominant = Object.entries(shares).sort((a, b) => b[1] - a[1])[0]
        return (
          <div key={c.name} className="mt-2">
            <h3>
              <code>{c.name}</code>
              {dominant && (
                <span className="badge badge--info" style={{ marginLeft: '0.5rem' }}>
                  dominant: {LABEL_MAP[dominant[0]] ?? dominant[0]} ({(dominant[1] * 100).toFixed(0)}%)
                </span>
              )}
            </h3>
            <figure>
              <VarBarChart shares={shares} />
              <figcaption>
                Figure 2. Share of variance in <em>{c.name}</em> explained by each design factor
                (sequential R², normalized to sum to 1).
              </figcaption>
            </figure>
          </div>
        )
      })}
    </>
  )
}
