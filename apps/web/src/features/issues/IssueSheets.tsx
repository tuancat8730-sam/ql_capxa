import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { FINISHED, type Issue, type IssueDetail, ISSUE_TYPES, type IssueType } from './types'

const label = (id: string, text: string) => (
  <label htmlFor={id} className="mb-1 block text-sm font-medium">
    {text}
  </label>
)

const refreshKeys = ['issues', 'issue']

export function useRefreshIssues() {
  const qc = useQueryClient()
  return () => Promise.all(refreshKeys.map((k) => qc.invalidateQueries({ queryKey: [k] })))
}

/** Local `datetime-local` value -> ISO with the browser's offset (the API stores UTC). */
const toIso = (local: string) => (local ? new Date(local).toISOString() : null)

export function NewIssueSheet({ packageId, onClose }: { packageId?: string; onClose: () => void }) {
  const { t } = useTranslation()
  const refresh = useRefreshIssues()
  const [v, setV] = useState({ title: '', description: '', issue_type: 'operational' as IssueType, level: 1, package_id: packageId ?? '', due_at: '' })
  const [error, setError] = useState<string | null>(null)
  const packages = useQuery({
    queryKey: ['packages', 'options'],
    queryFn: () => api.get<Page<{ id: string; number: number }>>('/packages?page_size=100'),
  })
  const create = useMutation({
    mutationFn: () =>
      api.post('/issues', {
        title: v.title.trim(),
        description: v.description || null,
        issue_type: v.issue_type,
        level: v.level,
        package_id: v.package_id || null,
        due_at: v.level === 3 ? toIso(v.due_at) : null,
      }),
    onSuccess: async () => {
      await refresh()
      onClose()
    },
    onError: () => setError(t('common.error')),
  })

  return (
    <BottomSheet title={t('issues.add')} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (v.title.trim()) create.mutate()
        }}
      >
        <div>
          {label('is-title', t('issues.titleField'))}
          <input id="is-title" className={inputClass} value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} required />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            {label('is-package', t('documents.package'))}
            <select id="is-package" className={inputClass} value={v.package_id} onChange={(e) => setV({ ...v, package_id: e.target.value })}>
              <option value="">{t('issues.noPackage')}</option>
              {packages.data?.items.map((p) => (
                <option key={p.id} value={p.id}>
                  {t('packages.number', { n: String(p.number).padStart(2, '0') })}
                </option>
              ))}
            </select>
          </div>
          <div>
            {label('is-type', t('issues.type'))}
            <select id="is-type" className={inputClass} value={v.issue_type} onChange={(e) => setV({ ...v, issue_type: e.target.value as IssueType })}>
              {ISSUE_TYPES.map((x) => (
                <option key={x} value={x}>
                  {t(`issues.types.${x}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          {label('is-level', t('issues.level', { n: v.level }))}
          <select id="is-level" className={inputClass} value={v.level} onChange={(e) => setV({ ...v, level: Number(e.target.value) })}>
            {[1, 2, 3].map((n) => (
              <option key={n} value={n}>
                {t('issues.level', { n })} – {t(`issues.levelHelp.${n}`)}
              </option>
            ))}
          </select>
        </div>
        {v.level === 3 && (
          <div>
            {label('is-due', t('issues.due'))}
            <input id="is-due" type="datetime-local" className={inputClass} value={v.due_at} onChange={(e) => setV({ ...v, due_at: e.target.value })} />
          </div>
        )}
        <div>
          {label('is-desc', t('issues.description'))}
          <textarea id="is-desc" rows={3} className={`${inputClass} py-2`} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />
        </div>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <button type="submit" className={primaryButton} disabled={create.isPending || !v.title.trim()}>
          {t('common.save')}
        </button>
      </form>
    </BottomSheet>
  )
}

type Panel = null | 'escalate' | 'resolve' | 'due'

export function IssueSheet({ issue, canWrite, canApprove, onClose }: { issue: Issue; canWrite: boolean; canApprove: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const refresh = useRefreshIssues()
  const [panel, setPanel] = useState<Panel>(null)
  const [note, setNote] = useState('')
  const [resolution, setResolution] = useState('')
  const [decidedBy, setDecidedBy] = useState('')
  const [due, setDue] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const detail = useQuery({ queryKey: ['issue', issue.id], queryFn: () => api.get<IssueDetail>(`/issues/${issue.id}`) })
  const cur = detail.data ?? { ...issue, events: [] }
  const finished = FINISHED.includes(cur.status)

  const act = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: async () => {
      setError(null)
      setPanel(null)
      await refresh()
    },
    onError: (e) =>
      setError(e instanceof ApiError && e.status === 403 ? t('issues.onlyDirectorL3') : e instanceof ApiError ? e.message : t('common.error')),
  })
  const patch = (body: Record<string, unknown>) => act.mutate(() => api.patch(`/issues/${issue.id}`, body))

  const btn = 'min-h-11 rounded-md border border-border px-3'

  return (
    <BottomSheet title={`${cur.code} · ${cur.title}`} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {t('issues.level', { n: cur.level })} · {t(`issues.types.${cur.issue_type}`)} · {t(`issues.status.${cur.status}`)}
          {cur.due_at && ` · ${t('issues.due')} ${formatDate(cur.due_at.slice(0, 10))}`}
        </p>
        {cur.description && <p>{cur.description}</p>}
        {cur.resolution && (
          <p className="rounded-md bg-muted p-2">
            <span className="font-medium">{t('issues.resolution')}:</span> {cur.resolution}
            {cur.decided_by && ` (${cur.decided_by})`}
          </p>
        )}

        {canWrite && (
          <div className="flex flex-wrap gap-2">
            {!finished && cur.level < 3 && (
              <button type="button" className={btn} onClick={() => setPanel('escalate')}>
                {t('issues.escalate')}
              </button>
            )}
            {!finished && (
              <button type="button" className={btn} onClick={() => setPanel('resolve')}>
                {t('issues.resolve')}
              </button>
            )}
            {!finished && (
              <button type="button" className={btn} onClick={() => setPanel('due')}>
                {t('issues.editDue')}
              </button>
            )}
            {cur.status === 'open' && (
              <button type="button" className={btn} onClick={() => patch({ status: 'in_progress' })}>
                {t('issues.markInProgress')}
              </button>
            )}
            {finished && (
              <button type="button" className={btn} onClick={() => patch({ status: 'open' })}>
                {t('issues.reopen')}
              </button>
            )}
            {cur.status === 'resolved' && (cur.level < 3 || canApprove) && (
              <button type="button" className={btn} onClick={() => patch({ status: 'closed' })}>
                {t('issues.close')}
              </button>
            )}
          </div>
        )}

        {panel === 'escalate' && (
          <form
            className="space-y-2 rounded-md border border-border p-3"
            onSubmit={(e) => {
              e.preventDefault()
              act.mutate(() => api.post(`/issues/${issue.id}/escalate`, { note: note || null, due_at: cur.level === 2 ? toIso(due) : null }))
            }}
          >
            {label('es-note', t('issues.escalateNote'))}
            <input id="es-note" className={inputClass} value={note} onChange={(e) => setNote(e.target.value)} />
            {cur.level === 2 && (
              <>
                {label('es-due', t('issues.due'))}
                <input id="es-due" type="datetime-local" className={inputClass} value={due} onChange={(e) => setDue(e.target.value)} />
              </>
            )}
            <button type="submit" className={primaryButton}>
              {t('issues.escalate')}
            </button>
          </form>
        )}
        {panel === 'resolve' && (
          <form
            className="space-y-2 rounded-md border border-border p-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (resolution.trim()) act.mutate(() => api.post(`/issues/${issue.id}/resolve`, { resolution: resolution.trim(), decided_by: decidedBy || null }))
            }}
          >
            {label('rs-text', t('issues.resolution'))}
            <textarea id="rs-text" rows={3} className={`${inputClass} py-2`} value={resolution} onChange={(e) => setResolution(e.target.value)} required />
            {label('rs-by', t('issues.decidedBy'))}
            <input id="rs-by" className={inputClass} value={decidedBy} onChange={(e) => setDecidedBy(e.target.value)} />
            <button type="submit" className={primaryButton} disabled={!resolution.trim()}>
              {t('issues.resolve')}
            </button>
          </form>
        )}
        {panel === 'due' && (
          <form
            className="space-y-2 rounded-md border border-border p-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (due && reason.trim().length >= 3) patch({ due_at: toIso(due), due_reason: reason.trim() })
            }}
          >
            {label('du-at', t('issues.due'))}
            <input id="du-at" type="datetime-local" className={inputClass} value={due} onChange={(e) => setDue(e.target.value)} required />
            {label('du-reason', t('issues.dueReason'))}
            <input id="du-reason" className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} required minLength={3} />
            <button type="submit" className={primaryButton}>
              {t('common.save')}
            </button>
          </form>
        )}

        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}

        <section aria-label={t('issues.history')} className="space-y-1">
          <h3 className="font-semibold">{t('issues.history')}</h3>
          <ol className="space-y-1 text-sm">
            {cur.events.map((e) => (
              <li key={e.id} className="text-muted-foreground">
                {formatDate(e.ts.slice(0, 10))} · <span className="text-foreground">{t(`issues.events.${e.event}`, e.event)}</span>
                {e.from_level !== null && e.to_level !== null && ` (${e.from_level} → ${e.to_level})`}
                {e.note && ` – ${e.note}`}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </BottomSheet>
  )
}
