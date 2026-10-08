import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { useRole } from '@/features/projects/ProjectContext'
import { api, ApiError } from '@/lib/api'
import { can } from '@/lib/permissions'
import { dm, dmy, WeekBadge } from './meta'
import { useDeliveryRisks, useRefreshDelivery, useWeeks } from './queries'
import type { ReportInput, Week } from './types'

const blank = (v: string) => (v.trim() ? v.trim() : null)
const pctOrNull = (v: string) => (v === '' ? null : Math.max(0, Math.min(100, Math.round(Number(v)))))

function ReportSheet({ week, canWrite, onClose }: { week: Week; canWrite: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const refresh = useRefreshDelivery()
  const risks = useDeliveryRisks()
  const r = week.report
  const [no, setNo] = useState(r?.report_no ?? '')
  const [status, setStatus] = useState<ReportInput['status']>(r?.status ?? 'received')
  const [submitted, setSubmitted] = useState(r?.submitted_on ?? (r ? '' : new Date().toISOString().slice(0, 10)))
  const [link, setLink] = useState(r?.link ?? '')
  const [planned, setPlanned] = useState(String(r?.planned_pct ?? week.suggested_planned_pct))
  const [actual, setActual] = useState(r?.actual_pct == null ? '' : String(r.actual_pct))
  const [done, setDone] = useState(r?.done ?? '')
  const [issues, setIssues] = useState(r?.issues ?? '')
  const [recs, setRecs] = useState(r?.recommendations ?? '')
  const [next, setNext] = useState(r?.next_plan ?? '')
  const [riskIds, setRiskIds] = useState<string[]>(r?.risk_ids ?? [])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (call: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await call()
      await refresh()
      onClose()
    } catch (err) {
      setError(err instanceof ApiError && err.status === 422 ? t('delivery.report.invalid') : t('common.error'))
      setBusy(false)
    }
  }

  const save = () => {
    const body: ReportInput = {
      report_no: blank(no),
      status,
      submitted_on: submitted || null,
      link: blank(link),
      planned_pct: pctOrNull(planned),
      actual_pct: pctOrNull(actual),
      done: blank(done),
      issues: blank(issues),
      recommendations: blank(recs),
      next_plan: blank(next),
      risk_ids: riskIds,
    }
    return run(() => api.put(`/delivery/reports/${week.start}`, body))
  }

  const toggleRisk = (id: string) =>
    setRiskIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  const area = (id: string, label: string, value: string, set: (v: string) => void) => (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      <textarea id={id} rows={3} className={inputClass} value={value} onChange={(e) => set(e.target.value)} />
    </div>
  )

  return (
    <BottomSheet
      title={t('delivery.report.title', { no: week.no })}
      onClose={onClose}
    >
      <p className="mb-3 text-sm text-muted-foreground">
        {t('delivery.report.period', { from: dmy(week.start), to: dmy(week.end) })}
      </p>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (canWrite) void save()
        }}
      >
        <fieldset disabled={!canWrite || busy} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="r-no" className="mb-1 block text-sm font-medium">{t('delivery.report.no')}</label>
              <input id="r-no" className={inputClass} placeholder="BC-01" value={no} onChange={(e) => setNo(e.target.value)} />
            </div>
            <div>
              <label htmlFor="r-status" className="mb-1 block text-sm font-medium">{t('delivery.report.status')}</label>
              <select id="r-status" className={inputClass} value={status} onChange={(e) => setStatus(e.target.value as ReportInput['status'])}>
                <option value="received">{t('delivery.week.received')}</option>
                <option value="needs_more">{t('delivery.week.needs_more')}</option>
              </select>
            </div>
            <div>
              <label htmlFor="r-date" className="mb-1 block text-sm font-medium">{t('delivery.report.submittedOn')}</label>
              <input id="r-date" type="date" className={inputClass} value={submitted} onChange={(e) => setSubmitted(e.target.value)} />
            </div>
            <div>
              <label htmlFor="r-link" className="mb-1 block text-sm font-medium">{t('delivery.report.link')}</label>
              <input id="r-link" type="url" className={inputClass} placeholder="https://" value={link} onChange={(e) => setLink(e.target.value)} />
            </div>
            <div>
              <label htmlFor="r-plan" className="mb-1 block text-sm font-medium">{t('delivery.report.planned')}</label>
              <input id="r-plan" type="number" min={0} max={100} inputMode="numeric" className={inputClass} value={planned} onChange={(e) => setPlanned(e.target.value)} />
              <p className="mt-1 text-xs text-muted-foreground">{t('delivery.report.plannedHint')}</p>
            </div>
            <div>
              <label htmlFor="r-act" className="mb-1 block text-sm font-medium">{t('delivery.report.actual')}</label>
              <input id="r-act" type="number" min={0} max={100} inputMode="numeric" className={inputClass} value={actual} onChange={(e) => setActual(e.target.value)} />
              <button
                type="button"
                className="mt-2 min-h-11 rounded-md border border-border px-3 text-sm"
                onClick={() => setActual(String(week.suggested_actual_pct))}
              >
                {t('delivery.report.fromTasks', { pct: week.suggested_actual_pct })}
              </button>
            </div>
          </div>
          {area('r-done', t('delivery.report.done'), done, setDone)}
          {area('r-issues', t('delivery.report.issues'), issues, setIssues)}
          {area('r-recs', t('delivery.report.recommendations'), recs, setRecs)}
          {area('r-next', t('delivery.report.next'), next, setNext)}
          <fieldset>
            <legend className="mb-1 text-sm font-medium">{t('delivery.report.risks')}</legend>
            {(risks.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">{t('delivery.report.noRisks')}</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {risks.data?.map((k) => (
                  <label key={k.id} className="flex min-h-11 items-center gap-2 rounded-md border border-border px-2 text-sm">
                    <input type="checkbox" checked={riskIds.includes(k.id)} onChange={() => toggleRisk(k.id)} />
                    <span className="font-mono">{k.code}</span>
                  </label>
                ))}
              </div>
            )}
          </fieldset>
        </fieldset>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        {canWrite && (
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="submit" disabled={busy} className={primaryButton}>
              {t('common.save')}
            </button>
            {r && (
              <button
                type="button"
                disabled={busy}
                className="min-h-11 rounded-md border border-border px-4"
                onClick={() =>
                  window.confirm(t('delivery.report.confirmDelete')) &&
                  void run(() => api.delete(`/delivery/reports/${week.start}`))
                }
              >
                {t('delivery.report.delete')}
              </button>
            )}
          </div>
        )}
      </form>
    </BottomSheet>
  )
}

export function WeeklyReportsPage() {
  const { t } = useTranslation()
  const role = useRole()
  const weeks = useWeeks()
  const [params, setParams] = useSearchParams()
  const [open, setOpen] = useState<string | null>(params.get('week'))

  if (weeks.isPending) return <p role="status">{t('common.loading')}</p>
  if (weeks.isError || !weeks.data) {
    return (
      <div role="alert" className="space-y-2">
        <p className="text-danger">{t('common.error')}</p>
        <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void weeks.refetch()}>
          {t('common.retry')}
        </button>
      </div>
    )
  }

  const ended = weeks.data.filter((w) => w.state !== 'current' && w.state !== 'future' && (w.report || w.state === 'missing'))
  const got = ended.filter((w) => w.report).length
  const missing = ended.length - got
  const current = weeks.data.find((w) => w.start === open) ?? null
  const close = () => {
    setOpen(null)
    if (params.has('week')) setParams({}, { replace: true })
  }
  const openWeek = (w: Week) => setOpen(w.start)

  const action = (w: Week) => (
    <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => openWeek(w)}>
      {w.report ? t('delivery.report.edit') : t('delivery.report.record')}
    </button>
  )

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold md:text-2xl">{t('delivery.reports.title')}</h1>
        <p className="text-sm text-muted-foreground">{t('delivery.reports.subtitle')}</p>
      </div>
      <p className="flex flex-wrap gap-2 text-sm">
        <span className="rounded-full border border-success px-2 text-success">
          {t('delivery.reports.received', { got, total: ended.length })}
        </span>
        {missing > 0 && (
          <span className="rounded-full border border-warning px-2 text-warning">
            {t('delivery.reports.missing', { n: missing })}
          </span>
        )}
      </p>
      <ResponsiveList
        rows={weeks.data}
        rowKey={(w) => w.start}
        caption={t('delivery.reports.title')}
        columns={[
          { key: 'no', header: t('delivery.reports.period'), cell: (w) => `${w.no} · ${dm(w.start)} – ${dm(w.end)}` },
          { key: 'state', header: t('delivery.reports.state'), cell: (w) => <WeekBadge state={w.state} /> },
          { key: 'ref', header: t('delivery.report.no'), cell: (w) => w.report?.report_no ?? '—', secondary: true },
          { key: 'on', header: t('delivery.report.submittedOn'), cell: (w) => dmy(w.report?.submitted_on), secondary: true },
          {
            key: 'pct',
            header: t('delivery.reports.progress'),
            cell: (w) => (w.report?.actual_pct == null ? '—' : `${w.report.actual_pct}% / ${w.report.planned_pct ?? '—'}%`),
          },
          { key: 'act', header: '', cell: (w) => (can(role, 'weekly_report', 'W') || w.report ? action(w) : null) },
        ]}
        renderCard={(w) => (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <p className="font-medium">
                {t('delivery.report.title', { no: w.no })} · {dm(w.start)} – {dm(w.end)}
              </p>
              <WeekBadge state={w.state} />
            </div>
            {w.report && (
              <p className="text-sm text-muted-foreground">
                {w.report.report_no ?? '—'} · {t('delivery.reports.progress')}:{' '}
                {w.report.actual_pct == null ? '—' : `${w.report.actual_pct}%`}
              </p>
            )}
            {(can(role, 'weekly_report', 'W') || w.report) && action(w)}
          </div>
        )}
      />
      {current && <ReportSheet week={current} canWrite={can(role, 'weekly_report', 'W')} onClose={close} />}
    </section>
  )
}
