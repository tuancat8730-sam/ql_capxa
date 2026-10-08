import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, type Page } from '@/lib/api'
import { formatDate, NO_DATA } from '@/lib/format'
import { can } from '@/lib/permissions'
import { ExportButton } from '@/components/ui/ExportButton'
import { RiskForm } from './RiskForm'
import { RiskMatrix } from './RiskMatrix'
import { RISK_CATEGORIES, RISK_STATUSES, type Matrix, type Risk, type RiskLevel } from './types'
import { useRole } from '@/features/projects/ProjectContext'

const LEVEL_TONE: Record<RiskLevel, { tone: Tone; icon: string }> = {
  low: { tone: 'neutral', icon: '○' },
  medium: { tone: 'warning', icon: '!' },
  high: { tone: 'danger', icon: '✕' },
}

export function RiskLevelBadge({ risk }: { risk: Pick<Risk, 'level' | 'score'> }) {
  const { t } = useTranslation()
  const m = LEVEL_TONE[risk.level]
  return (
    <StatusBadge tone={m.tone} icon={m.icon}>
      {t(`risks.level.${risk.level}`)} · {risk.score}
    </StatusBadge>
  )
}

export function RisksPage() {
  const { t } = useTranslation()
  const role = useRole()
  const queryClient = useQueryClient()
  const canWrite = can(role, 'risk', 'W')
  const canClose = can(role, 'risk', 'A')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [cell, setCell] = useState<{ probability: number; impact: number } | null>(null)
  const [editing, setEditing] = useState<Risk | 'new' | null>(null)

  const matrix = useQuery({ queryKey: ['risk-matrix'], queryFn: () => api.get<Matrix>('/risks/matrix') })
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['risks', { q, status, category, cell }],
    queryFn: () => {
      const p = new URLSearchParams({ page_size: '100' })
      if (q.trim()) p.set('q', q.trim())
      if (status) p.set('status', status)
      if (category) p.set('category', category)
      if (cell) {
        p.set('probability', String(cell.probability))
        p.set('impact', String(cell.impact))
      }
      return api.get<Page<Risk>>(`/risks?${p}`)
    },
  })

  const refresh = () =>
    Promise.all([queryClient.invalidateQueries({ queryKey: ['risks'] }), queryClient.invalidateQueries({ queryKey: ['risk-matrix'] })])
  const review = useMutation({ mutationFn: (r: Risk) => api.post(`/risks/${r.id}/review`), onSuccess: refresh })
  const setClosed = useMutation({
    mutationFn: ({ r, closed }: { r: Risk; closed: boolean }) => api.patch(`/risks/${r.id}`, { status: closed ? 'closed' : 'open' }),
    onSuccess: refresh,
  })

  const actions = (r: Risk) => (
    <div className="flex flex-wrap gap-2">
      {canWrite && (
        <>
          <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setEditing(r)}>
            {t('risks.edit')}
          </button>
          {r.status !== 'closed' && (
            <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => review.mutate(r)}>
              {t('risks.review')}
            </button>
          )}
        </>
      )}
      {canClose && (
        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setClosed.mutate({ r: r, closed: r.status !== 'closed' })}>
          {r.status === 'closed' ? t('risks.reopen') : t('risks.close')}
        </button>
      )}
    </div>
  )

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('risks.title')}</h1>
        <div className="flex flex-wrap gap-2">
          <ExportButton path="/export/risks.xlsx" />
          {canWrite && (
            <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setEditing('new')}>
              {t('risks.add')}
            </button>
          )}
        </div>
      </div>

      {matrix.data && <RiskMatrix matrix={matrix.data} selected={cell} onSelect={setCell} />}

      <div className="grid gap-2 md:grid-cols-3">
        <input type="search" aria-label={t('risks.search')} placeholder={t('risks.search')} className={inputClass} value={q} onChange={(e) => setQ(e.target.value)} />
        <select aria-label={t('contract.status')} className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t('risks.allStatus')}</option>
          {RISK_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`risks.status.${s}`)}
            </option>
          ))}
        </select>
        <select aria-label={t('risks.category')} className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">{t('risks.allCategories')}</option>
          {RISK_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`risks.categories.${c}`)}
            </option>
          ))}
        </select>
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
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('risks.none')}</p>}
      {data && data.items.length > 0 && (
        <ResponsiveList
          caption={t('risks.title')}
          rows={data.items}
          rowKey={(r) => r.id}
          renderCard={(r) => (
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm text-muted-foreground">{r.code}</p>
                  <p className="font-semibold">{r.title}</p>
                </div>
                <RiskLevelBadge risk={r} />
              </div>
              <p className="text-sm text-muted-foreground">
                {t(`risks.categories.${r.category}`)} · {t(`risks.status.${r.status}`)}
                {r.due_date && ` · ${t('risks.dueDate')} ${formatDate(r.due_date)}`}
              </p>
              {r.needs_review && <StatusBadge tone="warning" icon="!">{t('risks.needsReview')}</StatusBadge>}
              {actions(r)}
            </div>
          )}
          columns={[
            { key: 'code', header: t('risks.code'), cell: (r) => r.code },
            { key: 'title', header: t('issues.titleField'), cell: (r) => <span className="font-medium">{r.title}</span> },
            { key: 'score', header: t('risks.score'), cell: (r) => <RiskLevelBadge risk={r} /> },
            { key: 'cat', header: t('risks.category'), cell: (r) => t(`risks.categories.${r.category}`), secondary: true },
            { key: 'status', header: t('contract.status'), cell: (r) => t(`risks.status.${r.status}`) },
            { key: 'due', header: t('risks.dueDate'), cell: (r) => (r.due_date ? formatDate(r.due_date) : NO_DATA), secondary: true },
            { key: 'actions', header: t('users.more'), cell: actions },
          ]}
        />
      )}

      {editing && (
        <BottomSheet title={editing === 'new' ? t('risks.add') : t('risks.edit')} onClose={() => setEditing(null)}>
          <RiskForm risk={editing === 'new' ? undefined : editing} canClose={canClose} onDone={() => setEditing(null)} />
        </BottomSheet>
      )}
    </section>
  )
}
