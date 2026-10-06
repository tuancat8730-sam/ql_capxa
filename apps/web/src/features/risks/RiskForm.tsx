import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError, type Page } from '@/lib/api'
import { levelOf, RISK_CATEGORIES, RISK_STATUSES, type Risk, type RiskCategory, type RiskStatus } from './types'

interface RiskFormProps {
  risk?: Risk
  packageId?: string
  /** Only the director may set or leave `closed` (SPEC 4.8). */
  canClose: boolean
  onDone: () => void
}

export function RiskForm({ risk, packageId, canClose, onDone }: RiskFormProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [v, setV] = useState({
    title: risk?.title ?? '',
    description: risk?.description ?? '',
    category: (risk?.category ?? 'schedule') as RiskCategory,
    probability: risk?.probability ?? 3,
    impact: risk?.impact ?? 3,
    package_id: risk?.package_id ?? packageId ?? '',
    mitigation: risk?.mitigation ?? '',
    contingency: risk?.contingency ?? '',
    status: (risk?.status ?? 'open') as RiskStatus,
    due_date: risk?.due_date ?? '',
  })
  const [error, setError] = useState<string | null>(null)
  const packages = useQuery({
    queryKey: ['packages', 'options'],
    queryFn: () => api.get<Page<{ id: string; number: number }>>('/packages?page_size=100'),
  })

  const score = v.probability * v.impact
  const save = useMutation({
    mutationFn: () => {
      const payload = {
        ...v,
        package_id: v.package_id || null,
        description: v.description || null,
        mitigation: v.mitigation || null,
        contingency: v.contingency || null,
        due_date: v.due_date || null,
      }
      return risk ? api.patch(`/risks/${risk.id}`, payload) : api.post('/risks', payload)
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['risks'] }),
        queryClient.invalidateQueries({ queryKey: ['risk-matrix'] }),
      ])
      onDone()
    },
    onError: (e) => setError(e instanceof ApiError && e.status === 403 ? t('risks.onlyDirector') : t('common.error')),
  })

  const label = (id: string, text: string) => (
    <label htmlFor={id} className="mb-1 block text-sm font-medium">
      {text}
    </label>
  )
  const scale = (id: string, key: 'probability' | 'impact', text: string) => (
    <div>
      {label(id, text)}
      <select id={id} className={inputClass} value={v[key]} onChange={(e) => setV({ ...v, [key]: Number(e.target.value) })}>
        {[1, 2, 3, 4, 5].map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
    </div>
  )

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (v.title.trim()) save.mutate()
      }}
    >
      <div>
        {label('rk-title', t('issues.titleField'))}
        <input id="rk-title" className={inputClass} value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} required />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          {label('rk-category', t('risks.category'))}
          <select id="rk-category" className={inputClass} value={v.category} onChange={(e) => setV({ ...v, category: e.target.value as RiskCategory })}>
            {RISK_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`risks.categories.${c}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          {label('rk-package', t('documents.package'))}
          <select id="rk-package" className={inputClass} value={v.package_id} onChange={(e) => setV({ ...v, package_id: e.target.value })}>
            <option value="">{t('issues.noPackage')}</option>
            {packages.data?.items.map((p) => (
              <option key={p.id} value={p.id}>
                {t('packages.number', { n: String(p.number).padStart(2, '0') })}
              </option>
            ))}
          </select>
        </div>
        {scale('rk-prob', 'probability', t('risks.probability'))}
        {scale('rk-impact', 'impact', t('risks.impact'))}
      </div>
      <p role="status" className="rounded-md bg-muted p-2 font-medium">
        {t('risks.live', { score, level: t(`risks.level.${levelOf(score)}`) })}
      </p>
      <div>
        {label('rk-desc', t('issues.description'))}
        <textarea id="rk-desc" rows={2} className={`${inputClass} py-2`} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />
      </div>
      <div>
        {label('rk-mit', t('risks.mitigation'))}
        <textarea id="rk-mit" rows={2} className={`${inputClass} py-2`} value={v.mitigation} onChange={(e) => setV({ ...v, mitigation: e.target.value })} />
      </div>
      <div>
        {label('rk-cont', t('risks.contingency'))}
        <textarea id="rk-cont" rows={2} className={`${inputClass} py-2`} value={v.contingency} onChange={(e) => setV({ ...v, contingency: e.target.value })} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          {label('rk-status', t('contract.status'))}
          <select id="rk-status" className={inputClass} value={v.status} onChange={(e) => setV({ ...v, status: e.target.value as RiskStatus })}>
            {RISK_STATUSES.filter((s) => s !== 'closed' || canClose || v.status === 'closed').map((s) => (
              <option key={s} value={s} disabled={s === 'closed' && !canClose}>
                {t(`risks.status.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          {label('rk-due', t('risks.dueDate'))}
          <input id="rk-due" type="date" className={inputClass} value={v.due_date} onChange={(e) => setV({ ...v, due_date: e.target.value })} />
        </div>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" className={primaryButton} disabled={save.isPending || !v.title.trim()}>
        {t('common.save')}
      </button>
    </form>
  )
}
