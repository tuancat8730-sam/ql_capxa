import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { primaryButton } from '@/features/auth/LoginPage'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'
import { FindingsList } from './FindingsList'
import { PlanImportSheet } from './PlanImportSheet'
import { PlanItems } from './PlanItems'
import { periodText } from './period'
import { PlanSteps } from './PlanSteps'
import type { Plan } from './types'
import { useRole } from '@/features/projects/ProjectContext'

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** Tab "Kế hoạch" of a package: the contractor's delivery plan, tracked step by step. */
export function PlanTab({ packageId }: { packageId: string }) {
  const { t } = useTranslation()
  const role = useRole()
  const queryClient = useQueryClient()
  const canUpload = can(role, 'package', 'W')
  const canTrack = can(role, 'progress', 'W')
  const [importing, setImporting] = useState(false)

  const { data, isPending, isError } = useQuery({
    queryKey: ['plan', packageId],
    queryFn: () => api.get<Plan | null>(`/packages/${packageId}/plan`),
  })
  const remove = useMutation({
    mutationFn: () => api.request<void>('DELETE', `/packages/${packageId}/plan`),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['plan', packageId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      ]),
  })

  if (isPending) return <p role="status">{t('common.loading')}</p>
  if (isError)
    return (
      <p role="alert" className="text-danger">
        {t('common.error')}
      </p>
    )

  const upload = canUpload && (
    <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setImporting(true)}>
      {data ? t('plan.replace') : t('plan.upload')}
    </button>
  )

  if (!data) {
    return (
      <div className="space-y-3">
        <h2 className="text-lg font-semibold">{t('plan.title')}</h2>
        <p className="text-muted-foreground">{t('plan.empty')}</p>
        {canUpload && <p className="text-sm text-muted-foreground">{t('plan.emptyHint')}</p>}
        {upload}
        {importing && <PlanImportSheet packageId={packageId} onClose={() => setImporting(false)} />}
      </div>
    )
  }

  const { progress } = data
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">{t('plan.title')}</h2>
          {canUpload && (
            <div className="flex flex-wrap gap-2">
              {upload}
              <button
                type="button"
                className="min-h-11 rounded-md border border-border px-3"
                onClick={() => window.confirm(t('plan.confirmRemove')) && remove.mutate()}
              >
                {t('plan.remove')}
              </button>
            </div>
          )}
        </div>
        {data.source_file_name && (
          <p className="text-xs text-muted-foreground">
            {t('plan.source', { file: data.source_file_name })}
            {data.imported_at && ` · ${t('plan.importedAt', { date: formatDate(data.imported_at.slice(0, 10)) })}`}
          </p>
        )}
        <p>{t('plan.progress', { done: progress.done, total: progress.total, pct: String(progress.pct).replace('.', ',') })}</p>
        <div
          role="progressbar"
          aria-label={t('plan.title')}
          aria-valuenow={progress.pct}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 w-full overflow-hidden rounded-full bg-muted"
        >
          <div className="h-full bg-success" style={{ width: `${progress.pct}%` }} />
        </div>
      </div>

      <FindingsList findings={data.findings} />

      <section aria-label={t('plan.info')} className="space-y-2 rounded-md border border-border p-3">
        <h3 className="font-semibold">{t('plan.info')}</h3>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          {data.addressee && <Info label={t('plan.addressee')}>{data.addressee}</Info>}
          {(data.contract_start || data.contract_end) && (
            <Info label={t('plan.contractPeriod')}>{periodText(data.contract_start, data.contract_end)}</Info>
          )}
          {(data.implement_start || data.implement_end) && (
            <Info label={t('plan.implementPeriod')}>{periodText(data.implement_start, data.implement_end)}</Info>
          )}
          {data.signer && <Info label={t('plan.signer')}>{data.signer}</Info>}
        </dl>
        {data.locations.length > 0 && (
          <div className="text-sm">
            <p className="text-muted-foreground">{t('plan.locations')}</p>
            <ul className="space-y-1">
              {data.locations.map((l, i) => (
                <li key={i}>
                  {l.label && <span className="font-medium">{l.label}: </span>}
                  {l.text}
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.legal_basis && (
          <details className="text-sm">
            <summary className="min-h-11 cursor-pointer py-2 text-primary">{t('plan.basis')}</summary>
            <p className="text-muted-foreground">{data.legal_basis}</p>
          </details>
        )}
      </section>

      <PlanSteps steps={data.steps} packageId={packageId} canTrack={canTrack} />
      <PlanItems items={data.items} totalQuantity={data.total_quantity} />

      {importing && <PlanImportSheet packageId={packageId} onClose={() => setImporting(false)} />}
    </div>
  )
}
