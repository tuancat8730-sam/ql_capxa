import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { primaryButton } from '@/features/auth/LoginPage'
import { IssueCard } from '@/features/issues/IssuesPage'
import { IssueSheet, NewIssueSheet } from '@/features/issues/IssueSheets'
import type { Issue } from '@/features/issues/types'
import { RiskForm } from '@/features/risks/RiskForm'
import { RiskLevelBadge } from '@/features/risks/RisksPage'
import type { Risk } from '@/features/risks/types'
import { api, type Page } from '@/lib/api'
import { can } from '@/lib/permissions'
import { useRole } from '@/features/projects/ProjectContext'

/** Risks and issues of one package (SPEC 4.3 tab 6), with quick add. */
export function RisksIssuesTab({ packageId }: { packageId: string }) {
  const { t } = useTranslation()
  const role = useRole()
  const canWrite = can(role, 'risk', 'W')
  const canClose = can(role, 'risk', 'A')
  const [addRisk, setAddRisk] = useState(false)
  const [addIssue, setAddIssue] = useState(false)
  const [opened, setOpened] = useState<Issue | null>(null)

  const risks = useQuery({
    queryKey: ['risks', { package: packageId }],
    queryFn: () => api.get<Page<Risk>>(`/risks?package_id=${packageId}&page_size=50`),
  })
  const issues = useQuery({
    queryKey: ['issues', { package: packageId }],
    queryFn: () => api.get<Page<Issue>>(`/issues?package_id=${packageId}&page_size=50`),
  })

  return (
    <div className="space-y-8">
      <section className="space-y-3" aria-label={t('risks.title')}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">{t('risks.title')}</h2>
          {canWrite && (
            <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setAddRisk(true)}>
              {t('risks.add')}
            </button>
          )}
        </div>
        {risks.data?.items.length === 0 && <p className="text-muted-foreground">{t('risks.none')}</p>}
        <ul className="space-y-2">
          {risks.data?.items.map((r) => (
            <li key={r.id} className="flex items-start justify-between gap-2 rounded-md border border-border p-3">
              <div>
                <p className="text-sm text-muted-foreground">{r.code}</p>
                <p className="font-semibold">{r.title}</p>
              </div>
              <RiskLevelBadge risk={r} />
            </li>
          ))}
        </ul>
        <Link to="/risks" className="inline-block min-h-11 py-2 text-primary">
          {t('risks.title')} ›
        </Link>
      </section>

      <section className="space-y-3" aria-label={t('issues.title')}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">{t('issues.title')}</h2>
          {canWrite && (
            <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setAddIssue(true)}>
              {t('issues.add')}
            </button>
          )}
        </div>
        {issues.data?.items.length === 0 && <p className="text-muted-foreground">{t('issues.none')}</p>}
        <ul className="space-y-2">
          {issues.data?.items.map((i) => (
            <li key={i.id} className="rounded-md border border-border p-3">
              <IssueCard i={i} onOpen={() => setOpened(i)} />
            </li>
          ))}
        </ul>
        <Link to="/issues" className="inline-block min-h-11 py-2 text-primary">
          {t('issues.title')} ›
        </Link>
      </section>

      {addRisk && (
        <BottomSheet title={t('risks.add')} onClose={() => setAddRisk(false)}>
          <RiskForm packageId={packageId} canClose={canClose} onDone={() => setAddRisk(false)} />
        </BottomSheet>
      )}
      {addIssue && <NewIssueSheet packageId={packageId} onClose={() => setAddIssue(false)} />}
      {opened && <IssueSheet issue={opened} canWrite={canWrite} canApprove={canClose} onClose={() => setOpened(null)} />}
    </div>
  )
}
