import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { ExportButton } from '@/components/ui/ExportButton'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'
import { IssueSheet, NewIssueSheet } from './IssueSheets'
import { BOARD_STATUSES, daysUntilDue, FINISHED, type Issue, ISSUE_TYPES } from './types'

/** Deadline in words and colour-independent: "còn 2 ngày", "hết hạn hôm nay", "quá hạn 1 ngày". */
export function DueLabel({ issue }: { issue: Pick<Issue, 'due_at' | 'status' | 'overdue' | 'overdue_days'> }) {
  const { t } = useTranslation()
  if (FINISHED.includes(issue.status)) return null
  if (!issue.due_at) return <span className="text-muted-foreground">{t('issues.noDue')}</span>
  if (issue.overdue) {
    return (
      <StatusBadge tone="danger" icon="!">
        {t('issues.overdueBy', { count: Math.max(1, issue.overdue_days) })}
      </StatusBadge>
    )
  }
  const n = daysUntilDue(issue.due_at)
  return <span>{n <= 0 ? t('issues.dueToday') : t('issues.dueIn', { count: n })}</span>
}

export function IssueCard({ i, onOpen, packageLabel }: { i: Issue; onOpen: () => void; packageLabel?: string }) {
  const { t } = useTranslation()
  return (
    <button type="button" onClick={onOpen} className="block w-full space-y-1 text-left">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm text-muted-foreground">
            {i.code} · {t('issues.level', { n: i.level })}
            {packageLabel && ` · ${packageLabel}`}
          </p>
          <p className="font-semibold">{i.title}</p>
        </div>
        <StatusBadge tone={i.level === 3 ? 'danger' : i.level === 2 ? 'warning' : 'neutral'} icon={String(i.level)}>
          {t(`issues.status.${i.status}`)}
        </StatusBadge>
      </div>
      <p className="text-sm">
        {t(`issues.types.${i.issue_type}`)} · <DueLabel issue={i} />
      </p>
    </button>
  )
}

export function IssuesPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const canWrite = can(user?.role, 'risk', 'W')
  const canApprove = can(user?.role, 'risk', 'A')
  const [status, setStatus] = useState('')
  const [level, setLevel] = useState('')
  const [type, setType] = useState('')
  const [overdueOnly, setOverdueOnly] = useState(false)
  const [view, setView] = useState<'list' | 'board'>('list')
  const [opened, setOpened] = useState<Issue | null>(null)
  const [adding, setAdding] = useState(false)

  const packages = useQuery({
    queryKey: ['packages', 'options'],
    queryFn: () => api.get<Page<{ id: string; number: number }>>('/packages?page_size=100'),
  })
  const pkgLabel = (id: string | null) => {
    const p = packages.data?.items.find((x) => x.id === id)
    return p ? t('packages.number', { n: String(p.number).padStart(2, '0') }) : undefined
  }

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['issues', { status, level, type, overdueOnly }],
    queryFn: () => {
      const p = new URLSearchParams({ page_size: '100' })
      if (status) p.set('status', status)
      if (level) p.set('level', level)
      if (type) p.set('issue_type', type)
      if (overdueOnly) p.set('overdue', 'true')
      return api.get<Page<Issue>>(`/issues?${p}`)
    },
  })

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('issues.title')}</h1>
        <ExportButton path="/export/issues.xlsx" />
        {canWrite && (
          <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setAdding(true)}>
            {t('issues.add')}
          </button>
        )}
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label={t('issues.level', { n: '' })}>
        {(['', '1', '2', '3'] as const).map((l) => (
          <button
            key={l || 'all'}
            type="button"
            aria-pressed={level === l}
            onClick={() => setLevel(l)}
            className={`min-h-11 shrink-0 rounded-full border px-4 text-sm ${level === l ? 'border-primary bg-primary text-primary-foreground' : 'border-border'}`}
          >
            {l ? t('issues.level', { n: l }) : t('issues.allLevels')}
          </button>
        ))}
        <button
          type="button"
          aria-pressed={overdueOnly}
          onClick={() => setOverdueOnly((o) => !o)}
          className={`min-h-11 shrink-0 rounded-full border px-4 text-sm ${overdueOnly ? 'border-danger bg-danger text-primary-foreground' : 'border-border'}`}
        >
          {t('issues.onlyOverdue')}
        </button>
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        <select aria-label={t('contract.status')} className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t('risks.allStatus')}</option>
          {(['open', 'in_progress', 'escalated', 'resolved', 'closed'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`issues.status.${s}`)}
            </option>
          ))}
        </select>
        <select aria-label={t('issues.type')} className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">{t('issues.type')}</option>
          {ISSUE_TYPES.map((x) => (
            <option key={x} value={x}>
              {t(`issues.types.${x}`)}
            </option>
          ))}
        </select>
        <div role="group" aria-label={t('issues.list')} className="hidden gap-1 lg:flex">
          {(['list', 'board'] as const).map((v) => (
            <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)} className={`min-h-11 flex-1 rounded-md border px-3 text-sm ${view === v ? 'border-primary bg-primary text-primary-foreground' : 'border-border'}`}>
              {t(`issues.${v}`)}
            </button>
          ))}
        </div>
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
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('issues.none')}</p>}
      {data && data.items.length > 0 && (
        <>
          <div className={view === 'board' ? 'lg:hidden' : ''}>
            <ResponsiveList
              caption={t('issues.title')}
              rows={data.items}
              rowKey={(i) => i.id}
              renderCard={(i) => <IssueCard i={i} packageLabel={pkgLabel(i.package_id)} onOpen={() => setOpened(i)} />}
              columns={[
                { key: 'code', header: t('risks.code'), cell: (i) => i.code },
                { key: 'title', header: t('issues.titleField'), cell: (i) => <button type="button" className="text-left font-medium text-primary" onClick={() => setOpened(i)}>{i.title}</button> },
                { key: 'level', header: t('issues.level', { n: '' }), cell: (i) => i.level },
                { key: 'type', header: t('issues.type'), cell: (i) => t(`issues.types.${i.issue_type}`), secondary: true },
                { key: 'status', header: t('contract.status'), cell: (i) => t(`issues.status.${i.status}`) },
                { key: 'due', header: t('issues.due'), cell: (i) => (i.due_at ? <span>{formatDate(i.due_at.slice(0, 10))} · <DueLabel issue={i} /></span> : <DueLabel issue={i} />) },
              ]}
            />
          </div>
          {view === 'board' && (
            <div className="hidden gap-3 lg:grid lg:grid-cols-4">
              {BOARD_STATUSES.map((s) => (
                <div key={s} role="group" aria-label={t(`issues.status.${s}`)} className="space-y-2 rounded-md bg-muted p-2">
                  <h2 className="px-1 text-sm font-semibold">
                    {t(`issues.status.${s}`)} ({data.items.filter((i) => i.status === s).length})
                  </h2>
                  {data.items
                    .filter((i) => i.status === s)
                    .map((i) => (
                      <div key={i.id} className="rounded-md border border-border bg-background p-2">
                        <IssueCard i={i} packageLabel={pkgLabel(i.package_id)} onOpen={() => setOpened(i)} />
                      </div>
                    ))}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {adding && <NewIssueSheet onClose={() => setAdding(false)} />}
      {opened && <IssueSheet issue={opened} canWrite={canWrite} canApprove={canApprove} onClose={() => setOpened(null)} />}
    </section>
  )
}
