import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ExportButton } from '@/components/ui/ExportButton'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { ApiError, api, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'
import { alertLink } from './alertLink'
import { SnoozeSheet } from './SnoozeSheet'
import { SwipeRow } from './SwipeRow'
import { type Alert, type AlertSeverity, SEVERITIES } from './types'
import { useRole } from '@/features/projects/ProjectContext'

const SEVERITY_TONE: Record<AlertSeverity, { tone: Tone; icon: string }> = {
  critical: { tone: 'danger', icon: '✕' },
  warning: { tone: 'warning', icon: '!' },
  info: { tone: 'info', icon: 'i' },
}

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const { t } = useTranslation()
  const m = SEVERITY_TONE[severity]
  return (
    <StatusBadge tone={m.tone} icon={m.icon}>
      {t(`alerts.severity.${severity}`)}
    </StatusBadge>
  )
}

export function AlertsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const role = useRole()
  const queryClient = useQueryClient()
  const canAct = can(role, 'risk', 'W')
  const canRefresh = role === 'admin' || role === 'director'
  const [severity, setSeverity] = useState<AlertSeverity | ''>('')
  const [history, setHistory] = useState(false)
  const [snoozing, setSnoozing] = useState<Alert | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['alerts', { severity, history }],
    queryFn: () => {
      const p = new URLSearchParams({ page_size: '100', status: history ? 'all' : 'active' })
      if (severity) p.set('severity', severity)
      return api.get<Page<Alert>>(`/alerts?${p}`)
    },
  })

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['alerts'] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
    ])
  const fail = (e: unknown) => {
    const code = e instanceof ApiError ? e.code : ''
    const known = ['critical_not_snoozable', 'alert_resolved'].includes(code)
    setError(known ? t(`alerts.errors.${code}`) : e instanceof Error ? e.message : t('common.error'))
  }

  const ack = useMutation({
    mutationFn: (a: Alert) => api.post(`/alerts/${a.id}/ack`),
    onSuccess: () => {
      setError(null)
      return refresh()
    },
    onError: fail,
  })
  const snooze = useMutation({
    mutationFn: ({ a, days, reason }: { a: Alert; days: number; reason: string }) =>
      api.post(`/alerts/${a.id}/snooze`, { days, reason }),
    onSuccess: () => {
      setSnoozing(null)
      setError(null)
      return refresh()
    },
    onError: fail,
  })
  const assign = useMutation({
    mutationFn: ({ a, to }: { a: Alert; to: string | null }) => api.patch(`/alerts/${a.id}`, { assigned_to: to }),
    onSuccess: refresh,
    onError: fail,
  })
  const run = useMutation({
    mutationFn: () => api.post<{ created: number; resolved: number }>('/alerts/refresh'),
    onSuccess: (r) => {
      setNotice(t('alerts.refreshed', { created: r.created, resolved: r.resolved }))
      return refresh()
    },
    onError: fail,
  })

  const items = data?.items ?? []
  const actionable = (a: Alert) => canAct && a.status !== 'resolved'
  const trySnooze = (a: Alert) => {
    if (!actionable(a)) return
    if (!a.can_snooze) setError(t('alerts.criticalNoSnooze'))
    else setSnoozing(a)
  }

  const chip = (active: boolean) =>
    `min-h-11 rounded-full border px-3 text-sm ${active ? 'border-primary bg-primary text-primary-foreground' : 'border-border'}`

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('alerts.title')}</h1>
        <div className="flex flex-wrap gap-2">
          <ExportButton path="/export/alerts.xlsx" />
          {canRefresh && (
            <button type="button" className="min-h-11 rounded-md border border-border px-3" disabled={run.isPending} onClick={() => run.mutate()}>
              {t('alerts.refresh')}
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label={t('alerts.title')}>
        <button type="button" aria-pressed={severity === ''} className={chip(severity === '')} onClick={() => setSeverity('')}>
          {t('alerts.filterAll')}
        </button>
        {SEVERITIES.map((s) => (
          <button key={s} type="button" aria-pressed={severity === s} className={chip(severity === s)} onClick={() => setSeverity(s)}>
            {t(`alerts.severity.${s}`)}
          </button>
        ))}
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" checked={history} onChange={(e) => setHistory(e.target.checked)} />
          {t('alerts.showHistory')}
        </label>
      </div>

      {canAct && <p className="text-xs text-muted-foreground md:hidden">{t('alerts.swipeHint')}</p>}
      {notice && <p role="status" className="text-sm text-success">{notice}</p>}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {data && items.length === 0 && <p className="text-muted-foreground">{t('alerts.none')}</p>}

      <ul className="space-y-3">
        {items.map((a) => (
          <li key={a.id}>
            <SwipeRow onSwipeLeft={() => actionable(a) && ack.mutate(a)} onSwipeRight={() => trySnooze(a)}>
              <article className="space-y-2 rounded-md border border-border bg-background p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={a.severity} />
                  <StatusBadge tone="neutral" icon="•">
                    {t(`alerts.status.${a.status}`)}
                  </StatusBadge>
                  {a.assigned_to === user?.id && <span className="text-xs text-muted-foreground">{t('alerts.assigned')}</span>}
                </div>
                <h2 className="font-semibold">{a.title}</h2>
                <p className="text-sm">{a.message}</p>
                <p className="text-xs text-muted-foreground">
                  {a.due_date && `${t('alerts.due', { date: formatDate(a.due_date) })} · `}
                  {t('alerts.since', { date: formatDate(a.first_seen_at) })}
                  {a.snoozed_until && ` · ${t('alerts.snoozeUntil', { date: formatDate(a.snoozed_until) })}`}
                  {a.snooze_reason && ` (${a.snooze_reason})`}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Link to={alertLink(a)} className="inline-flex min-h-11 items-center rounded-md border border-border px-3">
                    {t('alerts.open')}
                  </Link>
                  {actionable(a) && (
                    <>
                      {a.status !== 'acknowledged' && (
                        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => ack.mutate(a)}>
                          {t('alerts.ack')}
                        </button>
                      )}
                      {a.can_snooze && (
                        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => trySnooze(a)}>
                          {t('alerts.snooze')}
                        </button>
                      )}
                      <button
                        type="button"
                        className="min-h-11 rounded-md border border-border px-3"
                        onClick={() => assign.mutate({ a, to: a.assigned_to === user?.id ? null : (user?.id ?? null) })}
                      >
                        {a.assigned_to === user?.id ? t('alerts.unassign') : t('alerts.assign')}
                      </button>
                    </>
                  )}
                </div>
              </article>
            </SwipeRow>
          </li>
        ))}
      </ul>

      {snoozing && (
        <SnoozeSheet
          alert={snoozing}
          busy={snooze.isPending}
          error={error}
          onClose={() => setSnoozing(null)}
          onSubmit={(days, reason) => snooze.mutate({ a: snoozing, days, reason })}
        />
      )}
    </section>
  )
}
