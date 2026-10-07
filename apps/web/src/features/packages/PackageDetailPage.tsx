import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { HealthBadge, StatusBadge } from '@/components/ui/StatusBadge'
import { api, ApiError } from '@/lib/api'
import { formatDate, formatMoney, NO_DATA } from '@/lib/format'
import { useAuth } from '@/features/auth/AuthContext'
import { can } from '@/lib/permissions'
import { StagesTab } from '@/features/progress/StagesTab'
import { AccessSection } from './AccessSection'
import { RisksIssuesTab } from './RisksIssuesTab'
import { ChecklistTab } from './ChecklistTab'
import { ContractGuarantees, ContractPayments } from './ContractFinance'
import { ImportItems } from './ImportItems'
import { PlanTab } from '@/features/plan/PlanTab'
import type { ContractDetail, Issue, PackageItem, PackageOverview } from './types'

const TABS = ['overview', 'contracts', 'progress', 'plan', 'documents', 'risks', 'payments', 'log'] as const
type Tab = (typeof TABS)[number]
const IMPLEMENTED: Tab[] = ['overview', 'contracts', 'payments', 'documents', 'progress', 'plan', 'risks']

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="break-words font-medium">{children ?? NO_DATA}</dd>
    </div>
  )
}

function Section({ title, defaultOpen = false, children }: { title: string; defaultOpen?: boolean; children: ReactNode }) {
  return (
    <details open={defaultOpen} className="rounded-md border border-border p-3">
      <summary className="min-h-11 cursor-pointer py-2 font-semibold">{title}</summary>
      <div className="pt-2">{children}</div>
    </details>
  )
}

function money(value: number | null): string {
  return value === null ? NO_DATA : formatMoney(value)
}

function pctAmount(pct: number | null, amount: number | null): string {
  if (amount === null) return NO_DATA
  return pct === null ? formatMoney(amount) : `${formatMoney(amount)} (${pct}%)`
}

function IssueList({ issues }: { issues: Issue[] }) {
  const { t } = useTranslation()
  if (issues.length === 0) return <p className="text-success">✓ {t('packages.noIssues')}</p>
  return (
    <ul className="space-y-2">
      {issues.map((i) => (
        <li key={i.code} className="rounded-md border border-border p-2">
          <StatusBadge tone={i.severity === 'warning' ? 'warning' : 'info'} icon={i.severity === 'warning' ? '⚠' : 'ℹ'}>
            {i.severity === 'warning' ? t('packages.needsReview') : t('common.info')}
          </StatusBadge>
          <p className="mt-1">{i.message}</p>
          {(i.expected || i.actual) && (
            <p className="text-sm text-muted-foreground">
              {t('packages.expected')}: {i.expected ?? NO_DATA} · {t('packages.actual')}: {i.actual ?? NO_DATA}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

function ContractView({ c }: { c: ContractDetail }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const end = c.extended_end_date ?? c.planned_end_date
  return (
    <div className="space-y-4">
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label={t('contract.no')}>{c.contract_no}</Field>
        <Field label={t('contract.status')}>{t(`contract.statuses.${c.status}`)}</Field>
        <Field label={t('contract.value')}>{money(c.value)}</Field>
        <Field label={t('contract.signed')}>{c.signed_date ? formatDate(c.signed_date) : NO_DATA}</Field>
        <Field label={t('contract.duration')}>
          {c.duration_days === null ? NO_DATA : t('contract.days', { count: c.duration_days })}
        </Field>
        <Field label={t('contract.plannedEnd')}>{end ? formatDate(end) : NO_DATA}</Field>
        <Field label={t('contract.type')}>
          {c.contract_type ? t(`contract.types.${c.contract_type}`) : NO_DATA}
        </Field>
        <Field label={t('contract.priceAdjustment')}>
          {c.price_adjustment ? t('common.yes') : t('common.no')}
        </Field>
        <Field label={t('contract.advance')}>{pctAmount(c.advance_pct, c.advance_amount)}</Field>
        <Field label={t('contract.performanceBond')}>
          {pctAmount(c.performance_bond_pct, c.performance_bond_amount)}
        </Field>
        <Field label={t('contract.warrantyBond')}>
          {pctAmount(c.warranty_bond_pct, c.warranty_bond_amount)}
        </Field>
        <Field label={t('contract.penalty')}>
          {c.penalty_rate_pct === null || c.penalty_unit === null
            ? NO_DATA
            : t('contract.penaltyText', {
                rate: c.penalty_rate_pct,
                unit: t(`contract.unit.${c.penalty_unit}`),
                cap: c.penalty_cap_pct ?? '–',
              })}
        </Field>
        <Field label={t('contract.investorAccount')}>{c.investor_account ?? NO_DATA}</Field>
      </dl>
      {c.parties.length > 0 && (
        <div>
          <h3 className="mb-2 font-semibold">{t('contract.parties')}</h3>
          <ul className="space-y-2">
            {c.parties.map((p) => (
              <li key={p.id} className="rounded-md border border-border p-2 text-sm">
                <span className="font-medium">{p.organization_name ?? NO_DATA}</span> ·{' '}
                {t(`contract.roles.${p.role}`)}
                {p.share_amount !== null && (
                  <>
                    {' '}
                    · {t('contract.share')}: {pctAmount(p.share_pct, p.share_amount)}
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {c.data_quality_note && (
        <p className="rounded-md bg-muted p-2 text-sm">
          <span className="font-medium">{t('contract.note')}:</span> {c.data_quality_note}
        </p>
      )}
      <div>
        <h3 className="mb-2 font-semibold">{t('packages.sections.checks')}</h3>
        <IssueList issues={c.consistency} />
      </div>
      {can(user?.role, 'contract', 'W') && <ImportItems contractId={c.id} />}
    </div>
  )
}

function OverviewTab({ pkg, contracts }: { pkg: PackageItem; contracts: ContractDetail[] }) {
  const { t } = useTranslation()
  const issues = contracts.flatMap((c) => c.consistency)
  return (
    <div className="space-y-3">
      <Section title={t('packages.sections.general')} defaultOpen>
        <dl className="grid gap-3 sm:grid-cols-2">
          <Field label={t('packages.price')}>{money(pkg.package_price)}</Field>
          <Field label={t('packages.winningPrice')}>{money(pkg.winning_price)}</Field>
          <Field label={t('packages.contractor')}>{pkg.winning_org_text}</Field>
          <Field label="E-TBMT">{pkg.etbmt_no}</Field>
          <Field label={t('contract.type')}>{t(`packages.type.${pkg.package_type}`)}</Field>
          <Field label={t('contract.status')}>{t(`packages.status.${pkg.status}`)}</Field>
          <Field label={t('packages.tabs.progress')}>{t(`packages.stage.${pkg.current_stage}`)}</Field>
        </dl>
        {pkg.notes && <p className="mt-3 text-sm text-muted-foreground">{pkg.notes}</p>}
      </Section>
      <Section title={t('packages.sections.contract')}>
        {contracts.length === 0 ? (
          <p className="text-muted-foreground">{t('packages.noContract')}</p>
        ) : (
          <ul className="space-y-1">
            {contracts.map((c) => (
              <li key={c.id}>
                {t('contract.no')} {c.contract_no} · {money(c.value)}
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t('packages.sections.checks')} defaultOpen={issues.length > 0}>
        <IssueList issues={issues} />
      </Section>
    </div>
  )
}

export function PackageDetailPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab') as Tab | null
  const tab: Tab = requested && TABS.includes(requested) ? requested : 'overview'

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ['package-overview', id],
    queryFn: () => api.get<PackageOverview>(`/packages/${id}/overview`),
    enabled: !!id,
  })

  if (isPending) return <p role="status">{t('common.loading')}</p>
  if (error) {
    const notFound = error instanceof ApiError && (error.status === 404 || error.status === 422)
    return (
      <div role="alert" className="space-y-3">
        <p className="text-danger">{notFound ? t('packages.notFound') : t('common.error')}</p>
        {!notFound && (
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        )}
        <Link to="/packages" className="block text-primary">
          {t('packages.back')}
        </Link>
      </div>
    )
  }

  const { package: pkg, contracts } = data
  return (
    <section className="space-y-4">
      <div className="sticky top-0 z-10 -mx-4 space-y-2 border-b border-border bg-background px-4 py-3 md:static md:mx-0 md:border-0 md:px-0">
        <Link to="/packages" className="text-sm text-primary">
          ‹ {t('packages.title')}
        </Link>
        <div className="flex items-start justify-between gap-2">
          <h1 className="text-xl font-semibold md:text-2xl">
            {t('packages.number', { n: String(pkg.number).padStart(2, '0') })} · {pkg.name}
          </h1>
          <HealthBadge health={pkg.health} />
        </div>
        {pkg.health_reason && (
          <p className="text-sm text-muted-foreground">
            {t('packages.healthReason')}: {pkg.health_reason}
          </p>
        )}
        <div
          role="progressbar"
          aria-label={t('packages.progress')}
          aria-valuenow={pkg.progress_pct}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 w-full overflow-hidden rounded-full bg-muted"
        >
          <div className="h-full bg-primary" style={{ width: `${pkg.progress_pct}%` }} />
        </div>
      </div>

      <div role="tablist" aria-label={t('packages.title')} className="flex gap-2 overflow-x-auto pb-1">
        {TABS.map((name) => (
          <button
            key={name}
            role="tab"
            type="button"
            aria-selected={tab === name}
            onClick={() => setParams({ tab: name }, { replace: true })}
            className={`min-h-11 shrink-0 rounded-full border px-4 text-sm ${
              tab === name ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
            }`}
          >
            {t(`packages.tabs.${name}`)}
            {name === 'contracts' && data.needs_review && <span aria-hidden> ⚠</span>}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {tab === 'overview' && <OverviewTab pkg={pkg} contracts={contracts} />}
        {tab === 'contracts' &&
          (contracts.length === 0 ? (
            <p className="text-muted-foreground">{t('packages.noContract')}</p>
          ) : (
            <div className="space-y-4">
              {contracts.map((c) => (
                <div key={c.id} className="space-y-6">
                  <ContractView c={c} />
                  <ContractGuarantees contractId={c.id} />
                </div>
              ))}
            </div>
          ))}
        {tab === 'payments' &&
          (contracts.length === 0 ? (
            <p className="text-muted-foreground">{t('packages.noContract')}</p>
          ) : (
            contracts.map((c) => <ContractPayments key={c.id} contractId={c.id} />)
          ))}
        {tab === 'progress' && <StagesTab packageId={pkg.id} />}
        {tab === 'plan' && <PlanTab packageId={pkg.id} />}
        {tab === 'risks' && <RisksIssuesTab packageId={pkg.id} />}
        {tab === 'documents' && (
          <div className="space-y-6">
            <ChecklistTab packageId={pkg.id} />
            {pkg.is_sensitive && user?.role === 'admin' && <AccessSection packageId={pkg.id} />}
          </div>
        )}
        {!IMPLEMENTED.includes(tab) && <p className="text-muted-foreground">{t('packages.laterMilestone')}</p>}
      </div>
    </section>
  )
}
