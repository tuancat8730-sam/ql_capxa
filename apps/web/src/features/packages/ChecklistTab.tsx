import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { primaryButton } from '@/features/auth/LoginPage'
import { UploadSheet } from '@/features/documents/UploadSheet'
import type { Checklist, ChecklistItem } from '@/features/documents/types'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'

const TONE: Record<ChecklistItem['status'], { tone: Tone; icon: string }> = {
  received: { tone: 'success', icon: '✓' },
  missing: { tone: 'danger', icon: '✕' },
  not_applicable: { tone: 'neutral', icon: '–' },
}

export function ChecklistTab({ packageId }: { packageId: string }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = can(user?.role, 'document', 'W')
  const [uploadFor, setUploadFor] = useState<ChecklistItem | null>(null)

  const { data, isPending, isError } = useQuery({
    queryKey: ['checklist', packageId],
    queryFn: () => api.get<Checklist>(`/packages/${packageId}/checklist`),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['checklist', packageId] })
  const instantiate = useMutation({
    mutationFn: () => api.post<Checklist>(`/packages/${packageId}/checklist/instantiate`),
    onSuccess: refresh,
  })
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ChecklistItem['status'] }) =>
      api.patch(`/checklist-items/${id}`, { status }),
    onSuccess: refresh,
  })

  if (isPending) return <p role="status">{t('common.loading')}</p>
  if (isError) return <p role="alert" className="text-danger">{t('common.error')}</p>

  const stages = [...new Set(data.items.map((i) => i.stage_code))]

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold">{t('checklist.title')}</h2>
        {data.items.length > 0 && (
          <>
            <p>
              {t('checklist.progress', { done: data.required_done, total: data.required_total, pct: String(data.completion_pct).replace('.', ',') })}
            </p>
            <div
              role="progressbar"
              aria-label={t('checklist.title')}
              aria-valuenow={data.completion_pct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="h-2 w-full overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full bg-success" style={{ width: `${data.completion_pct}%` }} />
            </div>
          </>
        )}
        <Link to={`/documents?package=${packageId}`} className="inline-block min-h-11 py-2 text-primary">
          {t('checklist.allDocuments')} ›
        </Link>
      </div>

      {data.items.length === 0 && (
        <div className="space-y-2">
          <p className="text-muted-foreground">{t('checklist.empty')}</p>
          {canWrite && (
            <button type="button" className={`${primaryButton} !w-auto`} onClick={() => instantiate.mutate()}>
              {t('checklist.create')}
            </button>
          )}
        </div>
      )}

      {stages.map((stage) => (
        <section key={stage} aria-label={t(`checklist.stages.${stage}`)} className="space-y-2">
          <h3 className="font-semibold">{t(`checklist.stages.${stage}`)}</h3>
          <ul className="space-y-2">
            {data.items
              .filter((i) => i.stage_code === stage)
              .map((i) => (
                <li key={i.id} className="space-y-2 rounded-md border border-border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium">
                      {i.title}
                      {!i.required && <span className="text-sm font-normal text-muted-foreground"> · {t('checklist.optional')}</span>}
                    </p>
                    <StatusBadge tone={TONE[i.status].tone} icon={TONE[i.status].icon}>
                      {t(`checklist.status.${i.status}`)}
                    </StatusBadge>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                    {i.due_date && (
                      <span>
                        {t('checklist.due')}: {formatDate(i.due_date)}
                      </span>
                    )}
                    {i.overdue && <StatusBadge tone="danger" icon="!">{t('checklist.overdue')}</StatusBadge>}
                    {i.document_restricted ? <span>🔒 {t('documents.restricted')}</span> : i.document_title && <span>📎 {i.document_title}</span>}
                    {i.note && <span>{i.note}</span>}
                  </div>
                  {canWrite && (
                    <div className="flex flex-wrap gap-2">
                      {i.status === 'missing' && (
                        <>
                          <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setUploadFor(i)}>
                            {t('checklist.upload')}
                          </button>
                          <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setStatus.mutate({ id: i.id, status: 'not_applicable' })}>
                            {t('checklist.markNa')}
                          </button>
                        </>
                      )}
                      {i.status === 'not_applicable' && (
                        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setStatus.mutate({ id: i.id, status: 'missing' })}>
                          {t('checklist.undo')}
                        </button>
                      )}
                    </div>
                  )}
                </li>
              ))}
          </ul>
        </section>
      ))}

      {uploadFor && (
        <UploadSheet packageId={packageId} docType={uploadFor.doc_type} onClose={() => setUploadFor(null)} />
      )}
    </div>
  )
}
