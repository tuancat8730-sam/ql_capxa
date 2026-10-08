import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useRole } from '@/features/projects/ProjectContext'
import { can } from '@/lib/permissions'
import { dm, StateBadge } from './meta'
import { ProgressChart } from './ProgressChart'
import { useOverview, useTasks } from './queries'
import { TaskSheet } from './TaskSheet'
import type { Attention, Overview } from './types'

const CHIP_CLASS: Record<Attention['chip'], string> = {
  good: 'border-success text-success',
  warn: 'border-warning text-warning',
  bad: 'border-danger text-danger',
  accent: 'border-info text-info',
  stale: 'border-neutral text-neutral',
  muted: 'border-border text-muted-foreground',
}

function Kpi({ label, value, unit, note, tone }: { label: string; value: string; unit?: string; note: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-semibold">
        {value}
        {unit && <small className="ml-1 text-base font-normal text-muted-foreground">{unit}</small>}
      </p>
      <p className={`text-sm ${tone ?? 'text-muted-foreground'}`}>{note}</p>
    </div>
  )
}

function Kpis({ data }: { data: Overview }) {
  const { t } = useTranslation()
  const next = data.next_milestone
  const diffNote =
    data.diff === 0
      ? t('delivery.kpi.onPlan')
      : t(data.diff > 0 ? 'delivery.kpi.ahead' : 'delivery.kpi.behind', { n: Math.abs(data.diff) })
  const diffTone = data.diff >= 0 ? 'text-success' : data.diff <= -10 ? 'text-danger' : 'text-warning'
  const nextNote = next
    ? `${next.days_left < 0 ? t('delivery.kpi.overdueDays', { n: -next.days_left }) : next.days_left === 0 ? t('delivery.kpi.today') : t('delivery.kpi.daysLeft', { n: next.days_left })} · ${next.name}`
    : t('delivery.kpi.allMilestones')
  const missing = data.weeks_ended - data.weeks_received
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Kpi
        label={t('delivery.kpi.actual')}
        value={String(Math.round(data.actual_pct))}
        unit="%"
        note={data.has_progress ? diffNote : `${t('delivery.kpi.noneEntered')} · ${diffNote}`}
        tone={diffTone}
      />
      <Kpi label={t('delivery.kpi.planToday')} value={String(Math.round(data.plan_pct))} unit="%" note={t('delivery.kpi.planNote')} />
      <Kpi
        label={t('delivery.kpi.nextMilestone')}
        value={next ? next.code : '—'}
        unit={next ? dm(next.date) : undefined}
        note={nextNote}
      />
      <Kpi
        label={t('delivery.kpi.attention')}
        value={String(data.late_count + data.stale_count)}
        note={t('delivery.kpi.attentionNote', { late: data.late_count, stale: data.stale_count })}
        tone={data.late_count ? 'text-danger' : undefined}
      />
      <Kpi
        label={t('delivery.kpi.reports')}
        value={String(data.weeks_received)}
        unit={`/${data.weeks_ended} ${t('delivery.kpi.periods')}`}
        note={t('delivery.kpi.reportsNote', { n: missing })}
        tone={missing ? 'text-warning' : undefined}
      />
    </div>
  )
}

function AttentionList({ items, onOpen }: { items: Attention[]; onOpen: (a: Attention) => void }) {
  const { t } = useTranslation()
  if (items.length === 0) return <p className="text-sm text-muted-foreground">{t('delivery.attention.none')}</p>
  return (
    <>
      <ul className="space-y-2">
        {items.slice(0, 8).map((a) => (
          <li key={`${a.target}-${a.ref}-${a.rank}`}>
            <button
              type="button"
              onClick={() => onOpen(a)}
              className="flex min-h-11 w-full items-start gap-3 rounded-md border border-border p-2 text-left"
            >
              <span className={`mt-0.5 shrink-0 rounded-full border px-2 text-xs font-medium ${CHIP_CLASS[a.chip]}`}>
                {a.label}
              </span>
              <span className="min-w-0">
                <b className="block truncate font-medium">{a.title}</b>
                <span className="block text-sm text-muted-foreground">{a.sub}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {items.length > 8 && (
        <p className="mt-2 text-sm text-muted-foreground">{t('delivery.attention.more', { n: items.length - 8 })}</p>
      )}
    </>
  )
}

function PhaseTable({ phases }: { phases: Overview['phases'] }) {
  const { t } = useTranslation()
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{t('delivery.phases.title')}</caption>
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th scope="col" className="px-3 py-2 font-medium">{t('delivery.phases.phase')}</th>
            <th scope="col" className="px-3 py-2 font-medium">{t('delivery.phases.time')}</th>
            <th scope="col" className="min-w-40 px-3 py-2 font-medium">{t('delivery.phases.progress')}</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">{t('delivery.phases.actual')}</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">{t('delivery.phases.plan')}</th>
            <th scope="col" className="px-3 py-2 font-medium">{t('delivery.phases.state')}</th>
          </tr>
        </thead>
        <tbody>
          {phases.map((p) => (
            <tr key={p.code} className="border-b border-border">
              <td className="px-3 py-2">
                <span className="mr-2 font-mono text-muted-foreground">{p.code}</span>
                {p.name}
              </td>
              <td className="whitespace-nowrap px-3 py-2 font-mono">
                {dm(p.start)} – {dm(p.end)}
              </td>
              <td className="px-3 py-2">
                <div
                  role="progressbar"
                  aria-valuenow={Math.round(p.actual_pct)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${p.code} ${t('delivery.phases.actual')}`}
                  className="relative h-2.5 overflow-hidden rounded-full bg-muted"
                >
                  <i className="block h-full bg-primary" style={{ width: `${p.actual_pct}%` }} />
                  <b className="absolute inset-y-0 w-0.5 bg-foreground" style={{ left: `calc(${p.plan_pct}% - 1px)` }} />
                </div>
              </td>
              <td className="px-3 py-2 text-right font-mono">{Math.round(p.actual_pct)}%</td>
              <td className="px-3 py-2 text-right font-mono">{Math.round(p.plan_pct)}%</td>
              <td className="px-3 py-2">
                <StateBadge state={p.state} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function DeliveryOverviewPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const role = useRole()
  const overview = useOverview()
  const tasks = useTasks()
  const [openTask, setOpenTask] = useState<string | null>(null)

  const open = (a: Attention) => {
    if (a.target === 'task') setOpenTask(a.ref)
    else if (a.target === 'week') navigate(`/weekly-reports?week=${a.ref}`)
    else navigate(a.ref === 'decisions' ? '/decisions' : '/risks')
  }
  const task = tasks.data?.find((x) => x.id === openTask)
  const data = overview.data

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold md:text-2xl">{t('dashboard.title')}</h1>
      {overview.isPending && <p role="status">{t('common.loading')}</p>}
      {overview.isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void overview.refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {data && (
        <>
          <Kpis data={data} />
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-border p-3">
              <h2 className="text-lg font-semibold">{t('delivery.chart.title')}</h2>
              <p className="mb-2 text-sm text-muted-foreground">{t('delivery.chart.subtitle')}</p>
              <ProgressChart data={data} />
            </div>
            <div className="rounded-lg border border-border p-3">
              <h2 className="text-lg font-semibold">{t('delivery.attention.title')}</h2>
              <p className="mb-2 text-sm text-muted-foreground">{t('delivery.attention.subtitle')}</p>
              <AttentionList items={data.attention} onOpen={open} />
            </div>
          </div>
          <div className="rounded-lg border border-border p-3">
            <h2 className="text-lg font-semibold">{t('delivery.phases.title')}</h2>
            <p className="mb-2 text-sm text-muted-foreground">{t('delivery.phases.subtitle')}</p>
            <PhaseTable phases={data.phases} />
          </div>
        </>
      )}
      {task && <TaskSheet task={task} canWrite={can(role, 'wbs', 'W')} onClose={() => setOpenTask(null)} />}
    </section>
  )
}
