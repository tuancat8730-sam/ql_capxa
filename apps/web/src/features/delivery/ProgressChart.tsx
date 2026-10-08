import { useTranslation } from 'react-i18next'
import { toDay } from '@/lib/gantt'
import { dm } from './meta'
import type { Overview } from './types'

const W = 640
const H = 270
const M = { l: 40, r: 16, t: 22, b: 30 }
const GRID = [0, 25, 50, 75, 100]

/** The plan as a dashed line, the reported figures as dots, today's computed figure as a ring. */
export function ProgressChart({ data }: { data: Overview }) {
  const { t } = useTranslation()
  if (!data.project_start || !data.project_end || data.plan_curve.length === 0) return null

  const x0 = toDay(data.project_start)
  const x1 = toDay(data.project_end)
  const span = Math.max(1, x1 - x0)
  const X = (iso: string) => M.l + ((toDay(iso) - x0) / span) * (W - M.l - M.r)
  const Y = (pct: number) => H - M.b - (pct / 100) * (H - M.t - M.b)

  const plan = data.plan_curve.map((p) => `${X(p.date).toFixed(1)},${Y(p.pct).toFixed(1)}`).join(' ')
  const reported = data.report_points.map((p) => `${X(p.date).toFixed(1)},${Y(p.pct).toFixed(1)}`).join(' ')
  const todayInside = toDay(data.today) >= x0 && toDay(data.today) <= x1

  // a label every seven days from the start of the project
  const ticks: string[] = []
  for (let d = 0; d <= span; d += 7) ticks.push(new Date((x0 + d) * 86_400_000).toISOString().slice(0, 10))

  const caption =
    `${t('delivery.chart.planToday', { pct: Math.round(data.plan_pct) })}, ` +
    (data.has_progress
      ? t('delivery.chart.actualFromTasks', { pct: Math.round(data.actual_pct) })
      : t('delivery.chart.noProgress'))

  return (
    <figure>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={t('delivery.chart.aria')}
      >
        {GRID.map((v) => (
          <g key={v}>
            <line x1={M.l} x2={W - M.r} y1={Y(v)} y2={Y(v)} stroke="var(--border)" />
            <text x={M.l - 7} y={Y(v) + 4} textAnchor="end" fontSize="11" fill="var(--muted-foreground)">
              {v}%
            </text>
          </g>
        ))}
        {ticks.map((iso, i) => (
          <text
            key={iso}
            x={X(iso)}
            y={H - 10}
            textAnchor="middle"
            fontSize="11"
            fill="var(--muted-foreground)"
            className={i % 2 ? 'hidden sm:block' : undefined}
          >
            {dm(iso)}
          </text>
        ))}
        <polyline points={plan} fill="none" stroke="var(--neutral)" strokeWidth="2" strokeDasharray="5 4" />
        {todayInside && (
          <g>
            <line x1={X(data.today)} x2={X(data.today)} y1={M.t} y2={H - M.b} stroke="var(--danger)" strokeWidth="1.5" />
            <text x={X(data.today)} y={12} textAnchor="middle" fontSize="11" fill="var(--danger)">
              {t('delivery.chart.today')}
            </text>
          </g>
        )}
        {data.report_points.length > 1 && (
          <polyline points={reported} fill="none" stroke="var(--primary)" strokeWidth="3" />
        )}
        {data.report_points.map((p) => (
          <circle key={p.date} cx={X(p.date)} cy={Y(p.pct)} r="5" fill="var(--primary)" />
        ))}
        {data.has_progress && todayInside && (
          <circle cx={X(data.today)} cy={Y(data.actual_pct)} r="6" fill="var(--background)" stroke="var(--primary)" strokeWidth="2.5">
            <title>{t('delivery.chart.actualFromTasks', { pct: Math.round(data.actual_pct) })}</title>
          </circle>
        )}
      </svg>
      <figcaption className="mt-2 text-sm text-muted-foreground">
        {caption}.{' '}
        {data.report_points.length > 0 ? t('delivery.chart.dotsNote') : t('delivery.chart.noDotsNote')}
      </figcaption>
      <p className="mt-1 flex flex-wrap gap-4 text-xs text-muted-foreground" aria-hidden>
        <span>┄ {t('delivery.chart.legendPlan')}</span>
        <span>● {t('delivery.chart.legendReports')}</span>
        <span>◯ {t('delivery.chart.legendNow')}</span>
      </p>
    </figure>
  )
}
