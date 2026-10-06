import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { SeverityBadge } from '@/features/alerts/AlertsPage'
import { alertLink } from '@/features/alerts/alertLink'
import { useDashAlerts } from '@/features/alerts/useAlertCount'
import type { Timeline } from '@/features/progress/types'
import { RiskLevelBadge } from '@/features/risks/RisksPage'
import { RiskMatrix } from '@/features/risks/RiskMatrix'
import type { Matrix, Risk } from '@/features/risks/types'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/format'
import type { MissingDocs } from './types'

const card = 'rounded-md border border-border p-3'

function Loading() {
  const { t } = useTranslation()
  return <p role="status">{t('common.loading')}</p>
}

export function AlertsBlock() {
  const { t } = useTranslation()
  const { data } = useDashAlerts()
  return (
    <section aria-label={t('dashboard.alerts.title')} className={`${card} space-y-2`}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('dashboard.alerts.title')}</h2>
        <Link to="/alerts" className="text-sm text-primary">
          {t('dashboard.alerts.all')}
        </Link>
      </div>
      {!data && <Loading />}
      {data && (
        <>
          <p className="flex flex-wrap gap-3 text-sm">
            {(['critical', 'warning', 'info'] as const).map((s) => (
              <span key={s}>
                {t(`alerts.severity.${s}`)}: <strong>{data.counts[s]}</strong>
              </span>
            ))}
          </p>
          {data.items.length === 0 && <p className="text-muted-foreground">{t('dashboard.alerts.none')}</p>}
          <ul className="space-y-2">
            {data.items.map((a) => (
              <li key={a.id}>
                <Link to={alertLink(a)} className="block space-y-1 rounded-md bg-muted p-2 text-sm">
                  <SeverityBadge severity={a.severity} />
                  <p className="font-medium">{a.title}</p>
                  <p className="text-muted-foreground">{a.message}</p>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

export function TopRisksBlock() {
  const { t } = useTranslation()
  const { data } = useQuery({ queryKey: ['dashboard', 'top-risks'], queryFn: () => api.get<{ items: Risk[]; matrix: Matrix }>('/dashboard/top-risks') })
  return (
    <section aria-label={t('dashboard.risks.title')} className={`${card} space-y-2`}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('dashboard.risks.title')}</h2>
        <Link to="/risks" className="text-sm text-primary">
          {t('dashboard.risks.all')}
        </Link>
      </div>
      {!data && <Loading />}
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('dashboard.risks.none')}</p>}
      {data && (
        <>
          <ul className="space-y-2">
            {data.items.map((r) => (
              <li key={r.id} className="flex items-start justify-between gap-2 text-sm">
                <span>
                  <span className="font-medium">{r.code}</span> {r.title}
                </span>
                <RiskLevelBadge risk={r} />
              </li>
            ))}
          </ul>
          <RiskMatrix matrix={data.matrix} selected={null} onSelect={() => undefined} />
        </>
      )}
    </section>
  )
}

export function MissingDocsBlock() {
  const { t } = useTranslation()
  const { data } = useQuery({ queryKey: ['dashboard', 'documents'], queryFn: () => api.get<MissingDocs>('/dashboard/documents') })
  return (
    <section aria-label={t('dashboard.documents.title')} className={`${card} space-y-2`}>
      <h2 className="text-lg font-semibold">{t('dashboard.documents.title')}</h2>
      {!data && <Loading />}
      {data && data.total_missing === 0 && <p className="text-muted-foreground">{t('dashboard.documents.none')}</p>}
      {data && data.total_missing > 0 && <p className="text-sm">{t('dashboard.documents.total', { n: data.total_missing })}</p>}
      <ul className="space-y-1">
        {data?.packages
          .filter((p) => p.missing > 0)
          .map((p) => (
            <li key={p.package_id}>
              <Link to={`/packages/${p.package_id}?tab=documents`} className="flex items-center justify-between gap-2 rounded-md bg-muted p-2 text-sm">
                <span>{t('packages.number', { n: String(p.number).padStart(2, '0') })}</span>
                <span>{t('dashboard.documents.missing', { missing: p.missing, required: p.required })}</span>
              </Link>
            </li>
          ))}
      </ul>
    </section>
  )
}

const DAY = 86_400_000

/** Contracts of every package on one axis with today's marker (SPEC 4.2 #8); full Gantt is /progress. */
export function TimelineBlock() {
  const { t } = useTranslation()
  const { data } = useQuery({ queryKey: ['timeline'], queryFn: () => api.get<Timeline>('/dashboard/timeline') })
  const bars = (data?.packages ?? []).filter((p) => p.contract?.start && p.contract.end)
  const times = bars.flatMap((p) => [Date.parse(p.contract?.start ?? ''), Date.parse(p.contract?.end ?? '')])
  const today = data ? Date.parse(data.today) : 0
  const min = Math.min(today, ...times)
  const max = Math.max(today, ...times)
  const span = Math.max(DAY, max - min)
  const pct = (ms: number) => ((ms - min) / span) * 100
  return (
    <section aria-label={t('dashboard.timeline.title')} className={`${card} space-y-2`}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('dashboard.timeline.title')}</h2>
        <Link to="/progress" className="text-sm text-primary">
          {t('dashboard.timeline.open')}
        </Link>
      </div>
      {!data && <Loading />}
      {data && (
        <div className="relative space-y-2" role="list">
          <div
            className="absolute inset-y-0 w-px bg-danger"
            style={{ left: `${pct(today)}%` }}
            aria-label={`${t('dashboard.timeline.today')} ${formatDate(data.today)}`}
          />
          {bars.map((p) => {
            const s = Date.parse(p.contract?.start ?? '')
            const e = Date.parse(p.contract?.end ?? '')
            return (
              <div key={p.id} role="listitem" className="space-y-0.5 text-xs">
                <span>
                  {t('packages.number', { n: String(p.number).padStart(2, '0') })} · {formatDate(p.contract?.start)} → {formatDate(p.contract?.end)}
                </span>
                <div className="relative h-3 rounded bg-muted">
                  <div className="absolute h-3 rounded bg-primary" style={{ left: `${pct(s)}%`, width: `${Math.max(1, pct(e) - pct(s))}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
