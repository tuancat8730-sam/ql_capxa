import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { HealthBadge, StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { api, ApiError, download } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'
import { Gantt } from './Gantt'
import type { StageStatus, Timeline } from './types'

export const STAGE_TONE: Record<StageStatus, { tone: Tone; icon: string }> = {
  not_started: { tone: 'neutral', icon: '○' },
  in_progress: { tone: 'info', icon: '→' },
  done: { tone: 'success', icon: '✓' },
  delayed: { tone: 'danger', icon: '!' },
  blocked: { tone: 'warning', icon: '✕' },
}

export function StageStatusBadge({ status }: { status: StageStatus }) {
  const { t } = useTranslation()
  return (
    <StatusBadge tone={STAGE_TONE[status].tone} icon={STAGE_TONE[status].icon}>
      {t(`progress.stageStatus.${status}`)}
    </StatusBadge>
  )
}

export function ProgressPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const canEdit = can(user?.role, 'progress', 'W')
  const [zoom, setZoom] = useState<'month' | 'week'>('month')
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['timeline'],
    queryFn: () => api.get<Timeline>('/dashboard/timeline'),
  })

  const change = useMutation({
    mutationFn: ({ id, dates }: { id: string; dates: { planned_start: string; planned_end: string } }) =>
      api.patch(`/stage-plans/${id}`, dates),
    onSuccess: () => {
      setError(null)
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ['timeline'] }),
        queryClient.invalidateQueries({ queryKey: ['stages'] }),
      ])
    },
    onError: (e) => setError(e instanceof ApiError && e.status === 403 ? t('payments.forbidden') : t('common.error')),
  })

  const exportQl06 = async () => {
    setExporting(true)
    try {
      const { blob, filename } = await download('/export/ql06.xlsx')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError(t('common.error'))
    } finally {
      setExporting(false)
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('progress.title')}</h1>
        <div className="flex flex-wrap gap-2">
          <div role="group" aria-label={t('progress.zoom')} className="hidden gap-1 lg:flex">
            {(['month', 'week'] as const).map((z) => (
              <button
                key={z}
                type="button"
                aria-pressed={zoom === z}
                onClick={() => setZoom(z)}
                className={`min-h-11 rounded-md border px-4 text-sm ${zoom === z ? 'border-primary bg-primary text-primary-foreground' : 'border-border'}`}
              >
                {z === 'month' ? t('progress.zoomMonth') : t('progress.zoomWeek')}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="min-h-11 rounded-md border border-border px-4 disabled:opacity-60"
            onClick={() => void exportQl06()}
            disabled={exporting}
          >
            {exporting ? t('progress.exporting') : t('progress.exportQl06')}
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}

      {data && (
        <>
          {/* phones and tablets: a list timeline, no drag and drop (SPEC 15.4) */}
          <div className="space-y-3 lg:hidden" aria-label={t('progress.ganttTitle')}>
            {data.packages.map((p) => (
              <article key={p.id} className="space-y-2 rounded-md border border-border p-3">
                <div className="flex items-start justify-between gap-2">
                  <Link to={`/packages/${p.id}?tab=progress`} className="font-semibold text-primary">
                    {t('packages.number', { n: String(p.number).padStart(2, '0') })} · {p.name}
                  </Link>
                  <HealthBadge health={p.health} />
                </div>
                <div role="progressbar" aria-label={t('progress.packageProgress')} aria-valuenow={p.progress_pct} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${p.progress_pct}%` }} />
                </div>
                <ul className="space-y-2">
                  {p.stages.map((s) => (
                    <li key={s.id} className="space-y-1 rounded-md bg-muted p-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium">{s.name}</span>
                        <StageStatusBadge status={s.effective_status} />
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {s.planned_start && s.planned_end ? `${formatDate(s.planned_start)} – ${formatDate(s.planned_end)}` : t('progress.noDates')}
                        {' · '}
                        {s.progress_pct}%
                      </p>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>

          {/* large screens: the Gantt chart, draggable for people who may edit */}
          <div className="hidden space-y-2 lg:block">
            {canEdit && <p className="text-sm text-muted-foreground">{t('progress.dragHint')}</p>}
            <Gantt
              timeline={data}
              zoom={zoom}
              editable={canEdit}
              onChangeStage={(id, dates) => change.mutate({ id, dates })}
            />
          </div>
        </>
      )}
    </section>
  )
}
