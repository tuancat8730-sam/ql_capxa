import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import { AlertsBlock, MissingDocsBlock, TimelineBlock, TopRisksBlock } from './LowerBlocks'
import { FinanceBlock, MilestonesBlock, PackageStrip, ProjectCard } from './TopBlocks'
import type { CashflowMonth, Summary } from './types'

/** Each block asks for its own endpoint, so a slow or failing one never blanks the page (SPEC 4.2). */
export function DashboardPage() {
  const { t } = useTranslation()
  const summary = useQuery({ queryKey: ['dashboard', 'summary'], queryFn: () => api.get<Summary>('/dashboard/summary') })
  const cash = useQuery({ queryKey: ['dashboard', 'cashflow'], queryFn: () => api.get<{ months: CashflowMonth[] }>('/dashboard/cashflow') })

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold md:text-2xl">{t('dashboard.title')}</h1>
      {summary.isPending && <p role="status">{t('common.loading')}</p>}
      {summary.isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void summary.refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {summary.data && (
        <>
          <ProjectCard project={summary.data.project} />
          <AlertsBlock />
          <PackageStrip packages={summary.data.packages} />
          <div className="grid gap-4 lg:grid-cols-2">
            <FinanceBlock finance={summary.data.finance} months={cash.data?.months ?? []} />
            <MilestonesBlock items={summary.data.milestones} />
            <TopRisksBlock />
            <MissingDocsBlock />
          </div>
          <TimelineBlock />
        </>
      )}
    </section>
  )
}
