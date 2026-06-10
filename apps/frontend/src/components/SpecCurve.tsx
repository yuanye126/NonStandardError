/**
 * Specification curve: sorted coefficient estimates with CI bands,
 * and a factor grid beneath (each row = one design factor).
 * Pure D3 rendering — no chart library.
 */
import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

interface Point {
  rank: number
  estimate: number
  ci_low: number | null
  ci_high: number | null
  factors: Record<string, string>
}

interface Props {
  data: { coefficient: string; points: Point[] }
}

const MARGIN = { top: 12, right: 16, bottom: 8, left: 52 }
const CURVE_H = 180
const FACTOR_ROW_H = 14
const GAP = 10

export default function SpecCurve({ data }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current || !data?.points?.length) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const points = data.points
    const W = svgRef.current.clientWidth || 720
    const factorKeys = Object.keys(points[0]?.factors ?? {})
    const totalH = MARGIN.top + CURVE_H + GAP + factorKeys.length * FACTOR_ROW_H + MARGIN.bottom

    svg.attr('height', totalH)

    const innerW = W - MARGIN.left - MARGIN.right
    const g = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`)

    const x = d3.scaleLinear().domain([1, points.length]).range([0, innerW])
    const estimates = points.map(p => p.estimate)
    const allCi = [
      ...points.map(p => p.ci_low ?? p.estimate),
      ...points.map(p => p.ci_high ?? p.estimate),
    ]
    const y = d3.scaleLinear()
      .domain([d3.min(allCi)! * 1.05, d3.max(allCi)! * 1.05])
      .nice()
      .range([CURVE_H, 0])

    // Zero line
    g.append('line')
      .attr('x1', 0).attr('x2', innerW)
      .attr('y1', y(0)).attr('y2', y(0))
      .attr('stroke', 'var(--rule)').attr('stroke-dasharray', '3,3').attr('stroke-width', 0.8)

    // CI segments
    const segs = points.filter(p => p.ci_low != null && p.ci_high != null)
    g.selectAll('.ci').data(segs).join('line')
      .attr('class', 'chart-ci')
      .attr('x1', d => x(d.rank)).attr('x2', d => x(d.rank))
      .attr('y1', d => y(d.ci_low!)).attr('y2', d => y(d.ci_high!))

    // Dots
    const isPos = (d: Point) => d.estimate > 0
    const isSig = (d: Point) => {
      if (d.ci_low == null || d.ci_high == null) return false
      return (d.ci_low > 0 && d.ci_high > 0) || (d.ci_low < 0 && d.ci_high < 0)
    }

    g.selectAll('.dot').data(points).join('circle')
      .attr('class', d => `chart-dot${isSig(d) ? ' chart-dot--sig' : (!isPos(d) ? ' chart-dot--neg' : '')}`)
      .attr('cx', d => x(d.rank))
      .attr('cy', d => y(d.estimate))
      .attr('r', points.length > 2000 ? 0.8 : 1.5)

    // Axes
    g.append('g')
      .attr('class', 'chart-axis')
      .call(d3.axisLeft(y).ticks(4).tickSize(-innerW))
      .select('.domain').remove()

    g.selectAll('.chart-axis .tick line').attr('stroke', 'var(--rule-light)').attr('stroke-dasharray', '2,2')

    // Factor grid
    const colorScale = d3.scaleOrdinal<string>().range(['var(--ink)', 'var(--accent)', 'var(--muted)'])

    factorKeys.forEach((fkey, fi) => {
      const yOff = CURVE_H + GAP + fi * FACTOR_ROW_H
      const vals = [...new Set(points.map(p => p.factors[fkey]))]
      const fColor = d3.scaleOrdinal<string>().domain(vals).range(
        ['var(--ink)', 'var(--accent)', 'var(--rule)'].concat(d3.schemeTableau10)
      )

      // Row label
      g.append('text')
        .attr('x', -4).attr('y', yOff + FACTOR_ROW_H / 2 + 3)
        .attr('text-anchor', 'end')
        .attr('font-size', 9)
        .attr('font-family', 'var(--serif)')
        .attr('fill', 'var(--muted)')
        .text(fkey.replace(/_/g, ' ').replace(' str', ''))

      // Tiles
      g.selectAll(`.tile-${fi}`).data(points).join('rect')
        .attr('x', d => x(d.rank) - 0.8)
        .attr('y', yOff)
        .attr('width', Math.max(1, innerW / points.length))
        .attr('height', FACTOR_ROW_H - 2)
        .attr('fill', d => fColor(d.factors[fkey] ?? ''))
        .attr('opacity', 0.7)
    })

    svg.attr('height', MARGIN.top + CURVE_H + GAP + factorKeys.length * FACTOR_ROW_H + MARGIN.bottom)
  }, [data])

  return (
    <figure>
      <svg ref={svgRef} width="100%" style={{ display: 'block' }} />
      <figcaption>
        Figure 1. Specification curve for <em>{data.coefficient}</em>.
        Each point is one specification sorted by effect size.
        {' '}<span style={{ color: 'var(--accent)' }}>Blue dots</span> = statistically significant (95% CI excludes zero).
        Rows below show the factor configuration for each specification.
      </figcaption>
    </figure>
  )
}
