import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { HealthBadge, StatusBadge } from '@/components/ui/StatusBadge'
import { inputClass } from '@/features/auth/LoginPage'
import { api, type Page } from '@/lib/api'
import { formatDate, formatMoney, NO_DATA } from '@/lib/format'
import type { Health, PackageItem } from './types'

const HEALTH_FILTERS: Health[] = ['green', 'amber', 'red', 'grey']

/** Whole days from today (local) to an ISO date; negative when already past. */
export function daysUntil(iso: string, now = new Date()): number {
  const [y, m, d] = iso.split('-').map(Number)
  const start = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((Date.UTC(y, m - 1, d) - start) / 86_400_000)
}

function DaysLeft({ iso }: { iso: string }) {
  const { t } = useTranslation()
  const n = daysUntil(iso)
  return <span>{n >= 0 ? t('packages.daysLeft', { count: n }) : t('packages.overdue', { count: -n })}</span>
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      className="h-2 w-full overflow-hidden rounded-full bg-muted"
    >
      <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
    </div>
  )
}

function PackageCard({ p }: { p: PackageItem }) {
  const { t } = useTranslation()
  return (
    <Link to={`/packages/${p.id}`} className="block space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm text-muted-foreground">{t('packages.number', { n: String(p.number).padStart(2, '0') })}</p>
          <p className="font-semibold">{p.name}</p>
        </div>
        <HealthBadge health={p.health} />
      </div>
      <p className="text-sm">{p.winning_org_text ?? NO_DATA}</p>
      <p className="text-sm">
        {t('packages.winningPrice')}: <span className="font-medium">{formatMoney(p.winning_price)}</span>
      </p>
      <ProgressBar pct={p.progress_pct} />
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>{t(`packages.status.${p.status}`)}</span>
        {p.contract_end_date && (
          <span>
            · {t('packages.endDate')} {formatDate(p.contract_end_date)} (<DaysLeft iso={p.contract_end_date} />)
          </span>
        )}
        {p.checklist_pct != null && <span>· {t('packages.documentsPct', { pct: String(p.checklist_pct).replace('.', ',') })}</span>}
        {p.needs_review && <StatusBadge tone="warning" icon="⚠">{t('packages.needsReview')}</StatusBadge>}
        {p.is_sensitive && <StatusBadge tone="info" icon="🔒">{t('packages.sensitive')}</StatusBadge>}
      </div>
    </Link>
  )
}

export function PackagesPage() {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [health, setHealth] = useState<Health | ''>('')

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['packages', { q, health }],
    queryFn: () => {
      const p = new URLSearchParams({ page_size: '100' })
      if (q.trim()) p.set('q', q.trim())
      if (health) p.set('health', health)
      return api.get<Page<PackageItem>>(`/packages?${p}`)
    },
  })

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold md:text-2xl">{t('packages.title')}</h1>
      <input
        type="search"
        aria-label={t('packages.search')}
        placeholder={t('packages.search')}
        className={`${inputClass} md:max-w-md`}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label={t('health.green')}>
        {(['', ...HEALTH_FILTERS] as const).map((h) => (
          <button
            key={h || 'all'}
            type="button"
            aria-pressed={health === h}
            onClick={() => setHealth(h)}
            className={`min-h-11 shrink-0 rounded-full border px-4 text-sm ${
              health === h ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
            }`}
          >
            {h ? t(`health.${h}`) : t('packages.allHealth')}
          </button>
        ))}
      </div>

      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('common.empty')}</p>}
      {data && data.items.length > 0 && (
        <ResponsiveList
          caption={t('packages.title')}
          rows={data.items}
          rowKey={(p) => p.id}
          renderCard={(p) => <PackageCard p={p} />}
          columns={[
            {
              key: 'name',
              header: t('packages.title'),
              cell: (p) => (
                <Link to={`/packages/${p.id}`} className="font-medium text-primary">
                  {t('packages.number', { n: String(p.number).padStart(2, '0') })} · {p.name}
                </Link>
              ),
            },
            { key: 'org', header: t('packages.contractor'), cell: (p) => p.winning_org_text ?? NO_DATA },
            { key: 'price', header: t('packages.winningPrice'), cell: (p) => formatMoney(p.winning_price) },
            { key: 'status', header: t('contract.status'), cell: (p) => t(`packages.status.${p.status}`), secondary: true },
            {
              key: 'end',
              header: t('packages.endDate'),
              cell: (p) => (p.contract_end_date ? formatDate(p.contract_end_date) : NO_DATA),
              secondary: true,
            },
            { key: 'health', header: t('packages.healthColumn'), cell: (p) => <HealthBadge health={p.health} /> },
          ]}
        />
      )}
    </section>
  )
}
