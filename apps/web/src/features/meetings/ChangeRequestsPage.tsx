import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'
import { useRole } from '@/features/projects/ProjectContext'

const TYPES = ['model', 'origin', 'allocation', 'schedule', 'other'] as const
type Status = 'proposed' | 'reviewing' | 'approved' | 'rejected' | 'appendix_signed'

interface Change {
  id: string
  code: string
  package_id: string
  change_type: (typeof TYPES)[number]
  description: string
  supervisor_opinion: string | null
  tvqlda_opinion: string | null
  status: Status
  decided_at: string | null
  decision_note: string | null
}

const TONE: Record<Status, { tone: Tone; icon: string }> = {
  proposed: { tone: 'neutral', icon: '○' },
  reviewing: { tone: 'info', icon: '→' },
  approved: { tone: 'success', icon: '✓' },
  rejected: { tone: 'danger', icon: '✕' },
  appendix_signed: { tone: 'success', icon: '✓✓' },
}

const label = (id: string, text: string) => (
  <label htmlFor={id} className="mb-1 block text-sm font-medium">
    {text}
  </label>
)

function NewChange({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [v, setV] = useState({ package_id: '', change_type: 'model', description: '' })
  const packages = useQuery({
    queryKey: ['packages', 'options'],
    queryFn: () => api.get<Page<{ id: string; number: number }>>('/packages?page_size=100'),
  })
  const create = useMutation({
    mutationFn: () => api.post('/change-requests', v),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['change-requests'] })
      onDone()
    },
  })
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (v.package_id && v.description.trim()) create.mutate()
      }}
    >
      <div>
        {label('cr-pkg', t('documents.package'))}
        <select id="cr-pkg" className={inputClass} value={v.package_id} onChange={(e) => setV({ ...v, package_id: e.target.value })} required>
          <option value="" />
          {packages.data?.items.map((p) => (
            <option key={p.id} value={p.id}>
              {t('packages.number', { n: String(p.number).padStart(2, '0') })}
            </option>
          ))}
        </select>
      </div>
      <div>
        {label('cr-type', t('changes.type'))}
        <select id="cr-type" className={inputClass} value={v.change_type} onChange={(e) => setV({ ...v, change_type: e.target.value })}>
          {TYPES.map((x) => (
            <option key={x} value={x}>
              {t(`changes.types.${x}`)}
            </option>
          ))}
        </select>
      </div>
      <div>
        {label('cr-desc', t('changes.description'))}
        <textarea id="cr-desc" rows={4} className={`${inputClass} py-2`} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} required />
      </div>
      <button type="submit" className={primaryButton} disabled={create.isPending || !v.package_id || !v.description.trim()}>
        {t('common.save')}
      </button>
    </form>
  )
}

export function ChangeRequestsPage() {
  const { t } = useTranslation()
  const role = useRole()
  const qc = useQueryClient()
  const canWrite = can(role, 'meeting', 'W')
  const canDecide = can(role, 'meeting', 'A')
  const [adding, setAdding] = useState(false)
  const [deciding, setDeciding] = useState<{ change: Change; decision: 'approved' | 'rejected' } | null>(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data, isPending, isError } = useQuery({
    queryKey: ['change-requests'],
    queryFn: () => api.get<Page<Change>>('/change-requests?page_size=100'),
  })
  const packages = useQuery({
    queryKey: ['packages', 'options'],
    queryFn: () => api.get<Page<{ id: string; number: number }>>('/packages?page_size=100'),
  })
  const pkg = (id: string) => {
    const p = packages.data?.items.find((x) => x.id === id)
    return p ? t('packages.number', { n: String(p.number).padStart(2, '0') }) : ''
  }

  const refresh = () => qc.invalidateQueries({ queryKey: ['change-requests'] })
  const move = useMutation({
    mutationFn: ({ c, status }: { c: Change; status: Status }) => api.patch(`/change-requests/${c.id}`, { status }),
    onSuccess: refresh,
    onError: () => setError(t('common.error')),
  })
  const decide = useMutation({
    mutationFn: () => api.post(`/change-requests/${deciding!.change.id}/decide`, { decision: deciding!.decision, note: note || null }),
    onSuccess: async () => {
      setDeciding(null)
      setNote('')
      await refresh()
    },
    onError: (e) => setError(e instanceof ApiError && e.status === 403 ? t('payments.forbidden') : t('common.error')),
  })

  const btn = 'min-h-11 rounded-md border border-border px-3'

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('changes.title')}</h1>
        {canWrite && (
          <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setAdding(true)}>
            {t('changes.add')}
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && <p role="alert" className="text-danger">{t('common.error')}</p>}
      {data?.items.length === 0 && <p className="text-muted-foreground">{t('changes.none')}</p>}
      <ul className="space-y-2">
        {data?.items.map((c) => (
          <li key={c.id} className="space-y-2 rounded-md border border-border p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm text-muted-foreground">
                  {c.code} · {pkg(c.package_id)} · {t(`changes.types.${c.change_type}`)}
                </p>
                <p className="font-semibold">{c.description}</p>
              </div>
              <StatusBadge tone={TONE[c.status].tone} icon={TONE[c.status].icon}>
                {t(`changes.status.${c.status}`)}
              </StatusBadge>
            </div>
            {c.supervisor_opinion && <p className="text-sm">{t('changes.supervisorOpinion')}: {c.supervisor_opinion}</p>}
            {c.tvqlda_opinion && <p className="text-sm">{t('changes.tvqldaOpinion')}: {c.tvqlda_opinion}</p>}
            {c.decided_at && (
              <p className="text-sm text-muted-foreground">
                {t('changes.decidedAt')} {formatDate(c.decided_at.slice(0, 10))}
                {c.decision_note && ` – ${c.decision_note}`}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              {canWrite && c.status === 'proposed' && (
                <button type="button" className={btn} onClick={() => move.mutate({ c, status: 'reviewing' })}>
                  {t('changes.review')}
                </button>
              )}
              {canDecide && (c.status === 'proposed' || c.status === 'reviewing') && (
                <>
                  <button type="button" className={btn} onClick={() => setDeciding({ change: c, decision: 'approved' })}>
                    {t('changes.approve')}
                  </button>
                  <button type="button" className={btn} onClick={() => setDeciding({ change: c, decision: 'rejected' })}>
                    {t('changes.reject')}
                  </button>
                </>
              )}
              {canWrite && c.status === 'approved' && (
                <button type="button" className={btn} onClick={() => move.mutate({ c, status: 'appendix_signed' })}>
                  {t('changes.signAppendix')}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>

      {adding && (
        <BottomSheet title={t('changes.add')} onClose={() => setAdding(false)}>
          <NewChange onDone={() => setAdding(false)} />
        </BottomSheet>
      )}
      {deciding && (
        <BottomSheet title={deciding.decision === 'approved' ? t('changes.approve') : t('changes.reject')} onClose={() => setDeciding(null)}>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              decide.mutate()
            }}
          >
            <p className="font-medium">{deciding.change.description}</p>
            <div>
              {label('dc-note', t('changes.note'))}
              <input id="dc-note" className={inputClass} value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            <button type="submit" className={primaryButton} disabled={decide.isPending}>
              {deciding.decision === 'approved' ? t('changes.approve') : t('changes.reject')}
            </button>
          </form>
        </BottomSheet>
      )}
    </section>
  )
}
