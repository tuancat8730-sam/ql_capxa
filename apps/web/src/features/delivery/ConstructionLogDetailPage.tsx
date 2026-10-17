import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { primaryButton } from '@/features/auth/LoginPage'
import { useRole } from '@/features/projects/ProjectContext'
import { can } from '@/lib/permissions'
import { ConstructionLogForm } from './ConstructionLogForm'
import { useLog, useLogWeeks } from './logQueries'
import type { ConstructionLog, LogHeader } from './logTypes'
import { DelayBadge, EntryStateBadge, shownCode, weekDays, weekdayOf } from './logMeta'
import { dm, dmy } from './meta'
import { useTasks } from './queries'

function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="whitespace-pre-line break-words">{children}</dd>
    </div>
  )
}

const GENERAL: (keyof LogHeader)[] = ['recipients', 'reporter_org', 'contract_ref', 'coordinator', 'environment_note']
const SUMMARY: (keyof LogHeader)[] = ['overall_status', 'key_results', 'issues', 'coordination_requests', 'related_report']

/** One week's construction log, read-only, with a button that opens the editor. */
function LogView({ log, phaseName }: { log: ConstructionLog; phaseName: (code: string) => string }) {
  const { t } = useTranslation()
  const byDay = new Map<string, ConstructionLog['entries']>()
  for (const e of log.entries) byDay.set(e.entry_date, [...(byDay.get(e.entry_date) ?? []), e])

  return (
    <div className="space-y-6">
      <dl className="space-y-3 rounded-md border border-border p-3">
        {log.report_date && <Line label={t('delivery.log.header.report_date')}>{dmy(log.report_date)}</Line>}
        {GENERAL.map((f) => (log[f] ? <Line key={f} label={t(`delivery.log.header.${f}`)}>{log[f]}</Line> : null))}
      </dl>

      <section aria-label={t('delivery.log.sectionDays')} className="space-y-3">
        <h2 className="text-lg font-semibold">{t('delivery.log.sectionDays')}</h2>
        {weekDays(log.week_start).map((day) => {
          const rows = byDay.get(day) ?? []
          return (
            <div key={day} className="space-y-2">
              <h3 className="font-medium">
                {t(`delivery.log.weekday.${weekdayOf(day)}`)} {dm(day)}
              </h3>
              {rows.length === 0 && <p className="text-sm text-muted-foreground">{t('delivery.log.noActivity')}</p>}
              {rows.map((e) => (
                <article key={e.id} className="space-y-2 rounded-md border border-border p-3">
                  <p className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-medium">{e.phase_code}</span>
                    <span className="text-muted-foreground">{phaseName(e.phase_code)}</span>
                    {e.task_code && <span className="rounded-full border border-border px-2 font-mono">{shownCode(e.task_code)}</span>}
                    {e.state && <EntryStateBadge state={e.state} />}
                    {e.delay_days != null && e.delay_days > 0 && <DelayBadge days={e.delay_days} />}
                  </p>
                  <p className="whitespace-pre-line break-words">{e.content}</p>
                  {e.personnel.length > 0 && (
                    <p className="text-sm text-muted-foreground">
                      {t('delivery.log.form.personnel')}: {e.personnel.join(', ')}
                    </p>
                  )}
                  {e.note && <p className="whitespace-pre-line break-words text-sm text-warning">{e.note}</p>}
                </article>
              ))}
            </div>
          )
        })}
      </section>

      <section aria-label={t('delivery.log.sectionSummary')} className="space-y-3">
        <h2 className="text-lg font-semibold">{t('delivery.log.sectionSummary')}</h2>
        <dl className="space-y-3 rounded-md border border-border p-3">
          {SUMMARY.map((f) => (log[f] ? <Line key={f} label={t(`delivery.log.header.${f}`)}>{log[f]}</Line> : null))}
        </dl>
        {log.carryovers.length > 0 && (
          <>
            <h3 className="font-medium">{t('delivery.log.sectionCarry')}</h3>
            <ul className="space-y-2">
              {log.carryovers.map((c) => (
                <li key={c.id} className="space-y-1 rounded-md border border-border p-3">
                  <p className="font-medium">
                    {c.task_code && <span className="mr-2 font-mono">{shownCode(c.task_code)}</span>}
                    {c.title}
                  </p>
                  <dl className="space-y-1 text-sm">
                    {c.result_to_date && <Line label={t('delivery.log.form.carryResult')}>{c.result_to_date}</Line>}
                    {c.next_week && <Line label={t('delivery.log.form.carryNext')}>{c.next_week}</Line>}
                    {c.note && <Line label={t('delivery.log.form.note')}>{c.note}</Line>}
                  </dl>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {log.member_work.length > 0 && (
        <section aria-label={t('delivery.log.sectionMember')} className="space-y-3">
          <h2 className="text-lg font-semibold">{t('delivery.log.sectionMember')}</h2>
          {log.member_work.map((m) => (
            <article key={m.id} className="space-y-2 rounded-md border border-border p-3">
              <p className="font-medium">
                {m.member_name} · {m.item}
              </p>
              <dl className="space-y-2 text-sm">
                {m.plan_ref && <Line label={t('delivery.log.form.memberPlan')}>{m.plan_ref}</Line>}
                {m.personnel.length > 0 && <Line label={t('delivery.log.form.personnel')}>{m.personnel.join('\n')}</Line>}
                {m.result && <Line label={t('delivery.log.form.memberResult')}>{m.result}</Line>}
                {m.next_plan && <Line label={t('delivery.log.form.memberNext')}>{m.next_plan}</Line>}
                {m.issues_actions && <Line label={t('delivery.log.form.memberIssues')}>{m.issues_actions}</Line>}
              </dl>
            </article>
          ))}
        </section>
      )}
    </div>
  )
}

/** `/construction-log/:week`, where `week` is the day the reporting week starts. */
export function ConstructionLogDetailPage() {
  const { t } = useTranslation()
  const role = useRole()
  const { week = '' } = useParams()
  const weeks = useLogWeeks()
  const log = useLog(week)
  const tasks = useTasks()
  const [editing, setEditing] = useState(false)

  if (weeks.isPending || log.isPending || tasks.isPending) return <p role="status">{t('common.loading')}</p>
  if (weeks.isError || log.isError || tasks.isError || !weeks.data || !tasks.data) {
    return (
      <div role="alert" className="space-y-2">
        <p className="text-danger">{t('common.error')}</p>
        <button
          type="button"
          className="min-h-11 rounded-md border border-border px-4"
          onClick={() => {
            void weeks.refetch()
            void log.refetch()
            void tasks.refetch()
          }}
        >
          {t('common.retry')}
        </button>
      </div>
    )
  }

  const period = weeks.data.find((w) => w.week_start === week)
  const back = (
    <Link to="/construction-log" className="inline-flex min-h-11 items-center text-sm text-primary">
      ← {t('delivery.log.back')}
    </Link>
  )
  if (!period) {
    return (
      <section className="space-y-3">
        {back}
        <p role="alert">{t('delivery.log.notAWeek')}</p>
      </section>
    )
  }

  const canWrite = can(role, 'construction_log', 'W')
  const phaseName = (code: string) => tasks.data.find((x) => x.phase_code === code)?.phase_name ?? ''
  const current = log.data ?? null

  return (
    <section className="space-y-4">
      {back}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold md:text-2xl">
            {t('delivery.log.weekTitle', { no: period.no })}
          </h1>
          <p className="text-sm text-muted-foreground">
            {dmy(period.week_start)} – {dmy(period.week_end)}
          </p>
        </div>
        {canWrite && !editing && (
          <button type="button" className={primaryButton} onClick={() => setEditing(true)}>
            {current ? t('delivery.log.edit') : t('delivery.log.create')}
          </button>
        )}
      </div>

      {editing ? (
        <ConstructionLogForm
          weekStart={period.week_start}
          weekEnd={period.week_end}
          log={current}
          tasks={tasks.data}
          onCancel={() => setEditing(false)}
          onSaved={() => setEditing(false)}
          onReload={() => {
            void log.refetch().then(() => setEditing(false))
          }}
        />
      ) : current ? (
        <LogView log={current} phaseName={phaseName} />
      ) : (
        <p className="text-muted-foreground">{t('delivery.log.noLogYet')}</p>
      )}
    </section>
  )
}
