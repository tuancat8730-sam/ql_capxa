import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRole } from '@/features/projects/ProjectContext'
import { addDays, daysBetween, makeScale, toDay } from '@/lib/gantt'
import { can } from '@/lib/permissions'
import { dm, STATE_COLOR } from './meta'
import { useOverview, useTasks } from './queries'
import { TaskSheet } from './TaskSheet'
import type { PhaseSummary, Task } from './types'

const DW = 14 // pixels per calendar day
const ROW = 34
const LABEL_W = 'min(340px, 58vw)'

interface Group {
  code: string
  name: string
  tasks: Task[]
  summary: PhaseSummary | undefined
}

function groupByPhase(tasks: Task[], phases: PhaseSummary[]): Group[] {
  const out: Group[] = []
  for (const t of tasks) {
    let g = out.find((x) => x.code === t.phase_code)
    if (!g) {
      g = { code: t.phase_code, name: t.phase_name, tasks: [], summary: phases.find((p) => p.code === t.phase_code) }
      out.push(g)
    }
    g.tasks.push(t)
  }
  return out
}

function percentOf(t: Task): number {
  if (t.is_milestone) return t.status === 'done' && t.tracked ? 100 : 0
  return t.tracked ? t.pct : 0
}

export function SchedulePage() {
  const { t } = useTranslation()
  const role = useRole()
  const tasks = useTasks()
  const overview = useOverview()
  const scroller = useRef<HTMLDivElement>(null)
  const [hideDone, setHideDone] = useState(false)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [openTask, setOpenTask] = useState<string | null>(null)

  const data = tasks.data
  const groups = useMemo(() => groupByPhase(data ?? [], overview.data?.phases ?? []), [data, overview.data])

  const span = useMemo(() => {
    if (!data || data.length === 0) return null
    const start = data.reduce((m, x) => (x.plan_start < m ? x.plan_start : m), data[0].plan_start)
    const end = data.reduce((m, x) => (x.plan_end > m ? x.plan_end : m), data[0].plan_end)
    return makeScale(start, end, DW, 3)
  }, [data])

  const today = overview.data?.today
  const todayX = span && today && today >= span.start && today <= span.end ? span.x(today) + DW / 2 : null

  const scrollToToday = () => {
    if (scroller.current && todayX != null) scroller.current.scrollLeft = Math.max(0, todayX - 160)
  }
  // open on today once the chart is there
  useEffect(() => {
    if (scroller.current && todayX != null) scroller.current.scrollLeft = Math.max(0, todayX - 160)
  }, [todayX])

  if (tasks.isPending) return <p role="status">{t('common.loading')}</p>
  if (tasks.isError || !data || !span) {
    return (
      <div role="alert" className="space-y-2">
        <p className="text-danger">{t('common.error')}</p>
        <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void tasks.refetch()}>
          {t('common.retry')}
        </button>
      </div>
    )
  }

  const days = daysBetween(span.start, span.end) + 1
  const weeks = Array.from({ length: Math.ceil(days / 7) }, (_, i) => addDays(span.start, i * 7))
  const months = monthsOf(span.start, days)
  const toggle = (code: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (!next.delete(code)) next.add(code)
      return next
    })
  const task = data.find((x) => x.id === openTask)

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold md:text-2xl">{t('delivery.gantt.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('delivery.gantt.subtitle')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="flex min-h-11 items-center gap-2">
            <input type="checkbox" checked={hideDone} onChange={(e) => setHideDone(e.target.checked)} />
            {t('delivery.gantt.hideDone')}
          </label>
          <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setCollapsed(new Set(groups.map((g) => g.code)))}>
            {t('delivery.gantt.collapseAll')}
          </button>
          <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setCollapsed(new Set())}>
            {t('delivery.gantt.expandAll')}
          </button>
          <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={scrollToToday}>
            {t('delivery.gantt.toToday')}
          </button>
        </div>
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-hidden>
        <li>▮ {t('delivery.gantt.legendFill')}</li>
        <li>▬ {t('delivery.gantt.legendActual')}</li>
        <li>◆ {t('delivery.gantt.legendMilestone')}</li>
        <li className="text-danger">│ {t('delivery.gantt.legendToday')}</li>
      </ul>

      <div ref={scroller} className="overflow-auto rounded-lg border border-border" style={{ maxHeight: '70vh' }}>
        <div style={{ width: `calc(${LABEL_W} + ${days * DW}px)` }}>
          <div className="sticky top-0 z-20 border-b border-border bg-background">
            <div className="flex">
              <div className="sticky left-0 z-10 shrink-0 bg-background" style={{ width: LABEL_W, height: 26 }} />
              <div className="relative" style={{ width: days * DW, height: 26 }}>
                {months.map((m) => (
                  <div
                    key={m.key}
                    className="absolute top-0 border-l border-border px-1 text-xs font-medium"
                    style={{ left: m.from * DW, width: m.days * DW }}
                  >
                    {t('delivery.gantt.month', { m: m.month, y: m.year })}
                  </div>
                ))}
              </div>
            </div>
            <div className="flex">
              <div
                className="sticky left-0 z-10 shrink-0 bg-background px-2 text-xs text-muted-foreground"
                style={{ width: LABEL_W, height: 26, lineHeight: '26px' }}
              >
                {t('delivery.gantt.labelHeader')}
              </div>
              <div className="relative" style={{ width: days * DW, height: 26 }}>
                {weeks.map((w, i) => (
                  <div
                    key={w}
                    className="absolute top-0 border-l border-border px-1 text-xs text-muted-foreground"
                    style={{ left: i * 7 * DW, width: 7 * DW }}
                  >
                    {dm(w)}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="relative">
            {todayX != null && (
              <>
                <div
                  className="pointer-events-none absolute inset-y-0 z-10 w-0.5 bg-danger"
                  style={{ left: `calc(${LABEL_W} + ${todayX - 1}px)` }}
                />
                <div
                  className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-b bg-danger px-1 text-[10px] font-semibold text-white"
                  style={{ left: `calc(${LABEL_W} + ${todayX}px)` }}
                >
                  {t('delivery.gantt.todayTag')}
                </div>
              </>
            )}
            {groups.map((g) => {
              const isCollapsed = collapsed.has(g.code)
              const start = g.tasks.reduce((m, x) => (x.plan_start < m ? x.plan_start : m), g.tasks[0].plan_start)
              const end = g.tasks.reduce((m, x) => (x.plan_end > m ? x.plan_end : m), g.tasks[0].plan_end)
              const actual = g.summary?.actual_pct ?? 0
              const state = g.summary?.state ?? 'todo'
              return (
                <div key={g.code}>
                  <div className="flex border-b border-border bg-muted/50" style={{ height: ROW }}>
                    <div className="sticky left-0 z-10 flex shrink-0 items-center gap-2 bg-muted px-2" style={{ width: LABEL_W }}>
                      <button
                        type="button"
                        aria-expanded={!isCollapsed}
                        aria-label={`${isCollapsed ? t('delivery.gantt.expand') : t('delivery.gantt.collapse')} ${g.code}`}
                        className="min-h-6 min-w-6"
                        onClick={() => toggle(g.code)}
                      >
                        {isCollapsed ? '▸' : '▾'}
                      </button>
                      <span className="font-mono text-xs text-muted-foreground">{g.code}</span>
                      <span className="min-w-0 flex-1 truncate text-sm font-semibold" title={g.name}>
                        {g.name}
                      </span>
                      <span className="font-mono text-xs">{Math.round(actual)}%</span>
                    </div>
                    <div className="relative" style={{ width: days * DW }}>
                      <div
                        className="absolute top-2.5 h-3.5 overflow-hidden rounded-sm opacity-90"
                        style={{
                          left: span.x(start),
                          width: (daysBetween(start, end) + 1) * DW,
                          background: 'var(--border)',
                        }}
                      >
                        <i className="block h-full" style={{ width: `${actual}%`, background: STATE_COLOR[state] }} />
                      </div>
                    </div>
                  </div>
                  {!isCollapsed &&
                    g.tasks.map((x) => {
                      if (hideDone && x.state === 'done') return null
                      const pct = percentOf(x)
                      const left = span.x(x.plan_start)
                      const width = (daysBetween(x.plan_start, x.plan_end) + 1) * DW
                      const color = STATE_COLOR[x.state]
                      return (
                        <div
                          key={x.id}
                          role="button"
                          tabIndex={0}
                          aria-label={`${x.code} ${x.name}, ${t(`delivery.state.${x.state}`)}`}
                          className="flex cursor-pointer border-b border-border hover:bg-muted/40 focus-visible:outline-2"
                          style={{ height: ROW }}
                          onClick={() => setOpenTask(x.id)}
                          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setOpenTask(x.id)}
                        >
                          <div className="sticky left-0 z-10 flex shrink-0 items-center gap-2 bg-background px-2 pl-6" style={{ width: LABEL_W }}>
                            <span className="size-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden />
                            <span className="font-mono text-xs text-muted-foreground">{x.code}</span>
                            <span className="min-w-0 flex-1 truncate text-sm" title={x.name}>
                              {x.name}
                            </span>
                            <span className="font-mono text-xs">{x.is_milestone ? (pct ? '✓' : '—') : `${pct}%`}</span>
                          </div>
                          <div className="relative" style={{ width: days * DW }}>
                            {x.is_milestone ? (
                              <>
                                <div
                                  className="absolute top-3 size-3.5 rotate-45"
                                  style={{ left: left + DW / 2 - 7, background: color }}
                                  title={`${x.code} · ${dm(x.plan_start)} · ${t(`delivery.state.${x.state}`)}`}
                                />
                                <span className="absolute top-2 text-xs text-muted-foreground" style={{ left: left + DW / 2 + 12 }}>
                                  {dm(x.plan_start)}
                                </span>
                              </>
                            ) : (
                              <>
                                <div
                                  className="absolute top-2 h-4 overflow-hidden rounded-sm"
                                  style={{ left, width, background: 'var(--border)' }}
                                  title={`${x.code} · ${dm(x.plan_start)} – ${dm(x.plan_end)} · ${pct}%`}
                                >
                                  <i className="block h-full" style={{ width: `${pct}%`, background: color }} />
                                </div>
                                {x.actual_start && (
                                  <div
                                    className="absolute top-6.5 h-1 rounded-sm bg-foreground/70"
                                    style={{
                                      left: span.x(x.actual_start),
                                      width: (daysBetween(x.actual_start, x.actual_end ?? maxIso(today ?? x.actual_start, x.actual_start)) + 1) * DW,
                                    }}
                                  />
                                )}
                                <span className="absolute top-2 font-mono text-xs" style={{ left: left + width + 6 }}>
                                  {pct}%
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      )
                    })}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {task && (
        <TaskSheet task={task} canWrite={can(role, 'wbs', 'W')} onClose={() => setOpenTask(null)} />
      )}
    </section>
  )
}

function maxIso(a: string, b: string): string {
  return a > b ? a : b
}

interface MonthSpan {
  key: string
  month: number
  year: number
  from: number
  days: number
}

/** Calendar months over the chart, with the day each one starts at and how many days it spans. */
function monthsOf(start: string, total: number): MonthSpan[] {
  const out: MonthSpan[] = []
  for (let i = 0; i < total; i++) {
    const d = new Date((toDay(start) + i) * 86_400_000)
    const key = `${d.getUTCFullYear()}-${d.getUTCMonth()}`
    const last = out[out.length - 1]
    if (last && last.key === key) last.days += 1
    else out.push({ key, month: d.getUTCMonth() + 1, year: d.getUTCFullYear(), from: i, days: 1 })
  }
  return out
}
