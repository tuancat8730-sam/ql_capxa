import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { HealthBadge } from '@/components/ui/StatusBadge'
import { formatDate, formatMoney, formatMoneyShort, NO_DATA } from '@/lib/format'
import type { CashflowMonth, DashFinance, DashPackage, DashProject, Milestone } from './types'

const card = 'rounded-md border border-border p-3'

export function ProjectCard({ project }: { project: DashProject }) {
  const { t } = useTranslation()
  const left = project.tvqlda_days_left
  const countdown =
    left == null ? t('dashboard.project.unknown') : left >= 0 ? t('dashboard.project.daysLeft', { n: left }) : t('dashboard.project.overdue', { n: -left })
  const period = project.start_year ? `${project.start_year}–${project.end_year ?? ''}` : NO_DATA
  return (
    <section aria-label={project.name} className={`${card} space-y-2`}>
      <h2 className="text-lg font-semibold">{project.name}</h2>
      <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <Item label={t('dashboard.project.investor')} value={project.investor_name ?? NO_DATA} />
        <Item label={t('dashboard.project.investment')} value={formatMoneyShort(project.total_investment)} />
        <Item label={t('dashboard.project.funding')} value={project.funding_source ?? NO_DATA} />
        <Item label={t('dashboard.project.period')} value={period} />
        <Item label={t('dashboard.project.packages')} value={String(project.package_count)} />
        <Item
          label={`${t('dashboard.project.countdown')}${project.tvqlda_end_date ? ` (${formatDate(project.tvqlda_end_date)})` : ''}`}
          value={countdown}
          strong
        />
      </dl>
    </section>
  )
}

function Item({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={strong ? 'text-base font-semibold' : ''}>{value}</dd>
    </div>
  )
}

export function PackageStrip({ packages }: { packages: DashPackage[] }) {
  const { t } = useTranslation()
  return (
    <section aria-label={t('dashboard.strip.title')} className="space-y-2">
      <h2 className="text-lg font-semibold">{t('dashboard.strip.title')}</h2>
      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {packages.map((p) => (
          <li key={p.id}>
            <Link to={`/packages/${p.id}`} className={`${card} block space-y-1`} title={p.health_reason ?? undefined}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">{t('packages.number', { n: String(p.number).padStart(2, '0') })}</span>
                <HealthBadge health={p.health} />
              </div>
              <p className="line-clamp-2 text-sm">{p.name}</p>
              <p className="text-xs text-muted-foreground">{p.contractor ?? NO_DATA}</p>
              <p className="text-xs">{formatMoneyShort(p.winning_price)}</p>
              <p className="text-xs text-muted-foreground">{t(`packages.stage.${p.current_stage}`)}</p>
              {/* the health reason is also printed: nothing relies on hover (SPEC 15.1) */}
              {p.health_reason && <p className="text-xs text-muted-foreground">{p.health_reason}</p>}
              <div role="progressbar" aria-label={t('dashboard.strip.progress', { pct: p.progress_pct })} aria-valuenow={p.progress_pct} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full bg-primary" style={{ width: `${p.progress_pct}%` }} />
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function FinanceBlock({ finance, months }: { finance: DashFinance; months: CashflowMonth[] }) {
  const { t } = useTranslation()
  const max = Math.max(1, ...months.flatMap((m) => [m.planned, m.actual]))
  const rows: [string, number][] = [
    [t('dashboard.finance.packagePrice'), finance.total_package_price],
    [t('dashboard.finance.winningPrice'), finance.total_winning_price],
    [t('dashboard.finance.contractValue'), finance.total_contract_value],
    [t('dashboard.finance.advance'), finance.total_advance],
    [t('dashboard.finance.paid'), finance.total_paid],
  ]
  return (
    <section aria-label={t('dashboard.finance.title')} className={`${card} space-y-3`}>
      <h2 className="text-lg font-semibold">{t('dashboard.finance.title')}</h2>
      <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {rows.map(([label, value]) => (
          <Item key={label} label={label} value={formatMoney(value)} />
        ))}
        <Item
          label={t('dashboard.finance.rate')}
          value={finance.disbursement_rate_pct == null ? t('dashboard.finance.noPlan') : `${finance.disbursement_rate_pct}%`}
          strong
        />
      </dl>
      {months.length > 0 && (
        <figure className="space-y-1">
          <figcaption className="text-sm text-muted-foreground">{t('dashboard.finance.chart')}</figcaption>
          <div className="flex items-end gap-2 overflow-x-auto pb-1" role="img" aria-label={t('dashboard.finance.chart')}>
            {months.map((m) => (
              <div key={`${m.year}-${m.month}`} className="flex min-w-10 flex-col items-center gap-1 text-xs">
                <div className="flex h-24 items-end gap-0.5">
                  <div className="w-3 bg-info" style={{ height: `${(m.planned / max) * 100}%` }} title={`${t('dashboard.finance.planned')}: ${formatMoney(m.planned)}`} />
                  <div className="w-3 bg-success" style={{ height: `${(m.actual / max) * 100}%` }} title={`${t('dashboard.finance.actual')}: ${formatMoney(m.actual)}`} />
                </div>
                <span>{String(m.month).padStart(2, '0')}/{String(m.year).slice(2)}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            <span className="mr-3">■ {t('dashboard.finance.planned')}</span>
            <span>■ {t('dashboard.finance.actual')}</span>
          </p>
        </figure>
      )}
    </section>
  )
}

export function MilestonesBlock({ items }: { items: Milestone[] }) {
  const { t } = useTranslation()
  return (
    <section aria-label={t('dashboard.milestones.title')} className={`${card} space-y-2`}>
      <h2 className="text-lg font-semibold">{t('dashboard.milestones.title')}</h2>
      {items.length === 0 && <p className="text-muted-foreground">{t('dashboard.milestones.none')}</p>}
      <ul className="space-y-2">
        {items.map((m) => (
          <li key={`${m.kind}-${m.entity_id}-${m.date}`} className="flex items-start justify-between gap-2 text-sm">
            <span>
              <span className="font-medium">{t(`dashboard.milestones.kinds.${m.kind}`)}</span>
              {m.package_number != null && ` · ${t('packages.number', { n: String(m.package_number).padStart(2, '0') })}`}
              <br />
              {m.title}
            </span>
            <span className="shrink-0 text-right">
              {formatDate(m.date)}
              <br />
              <span className="text-xs text-muted-foreground">
                {m.days_left === 0 ? t('dashboard.milestones.today') : t('dashboard.milestones.inDays', { n: m.days_left })}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
