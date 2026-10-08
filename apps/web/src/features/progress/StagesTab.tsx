import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError } from '@/lib/api'
import { formatDate, NO_DATA } from '@/lib/format'
import { can } from '@/lib/permissions'
import { StageStatusBadge } from './ProgressPage'
import { TaskBoard } from './TaskBoard'
import type { StagePlan, Stages } from './types'
import { useRole } from '@/features/projects/ProjectContext'

function StageForm({ stage, onDone }: { stage: StagePlan; onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [v, setV] = useState({
    planned_start: stage.planned_start ?? '',
    planned_end: stage.planned_end ?? '',
    actual_start: stage.actual_start ?? '',
    actual_end: stage.actual_end ?? '',
    progress_pct: stage.progress_pct,
    weight: stage.weight,
    status: stage.status,
    notes: stage.notes ?? '',
  })
  const [error, setError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () =>
      api.patch(`/stage-plans/${stage.id}`, {
        planned_start: v.planned_start || null,
        planned_end: v.planned_end || null,
        actual_start: v.actual_start || null,
        actual_end: v.actual_end || null,
        progress_pct: v.progress_pct,
        weight: v.weight,
        status: v.status,
        notes: v.notes || null,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['stages'] }),
        queryClient.invalidateQueries({ queryKey: ['timeline'] }),
        queryClient.invalidateQueries({ queryKey: ['packages'] }),
      ])
      onDone()
    },
    onError: (e) => setError(e instanceof ApiError && e.status === 422 ? e.message : t('common.error')),
  })

  const field = (id: string, label: string, el: React.ReactNode) => (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      {el}
    </div>
  )
  const date = (key: 'planned_start' | 'planned_end' | 'actual_start' | 'actual_end', label: string) =>
    field(
      `st-${key}`,
      label,
      <input id={`st-${key}`} type="date" className={inputClass} value={v[key]} onChange={(e) => setV({ ...v, [key]: e.target.value })} />,
    )

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate()
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {date('planned_start', t('progress.plannedStart'))}
        {date('planned_end', t('progress.plannedEnd'))}
        {date('actual_start', t('progress.actualStart'))}
        {date('actual_end', t('progress.actualEnd'))}
      </div>
      {field(
        'st-progress',
        t('progress.progressPct'),
        <div className="flex items-center gap-3">
          <input
            id="st-progress"
            type="range"
            min={0}
            max={100}
            className="min-h-11 flex-1"
            value={v.progress_pct}
            onChange={(e) => setV({ ...v, progress_pct: Number(e.target.value) })}
          />
          <span className="w-12 text-right">{v.progress_pct}%</span>
        </div>,
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {field(
          'st-weight',
          t('progress.weight'),
          <input id="st-weight" type="number" min={0} max={100} step="0.5" inputMode="decimal" className={inputClass} value={v.weight} onChange={(e) => setV({ ...v, weight: Number(e.target.value) })} />,
        )}
        {field(
          'st-status',
          t('contract.status'),
          <select id="st-status" className={inputClass} value={v.status} onChange={(e) => setV({ ...v, status: e.target.value as StagePlan['status'] })}>
            {(['not_started', 'in_progress', 'done', 'blocked'] as const).map((s) => (
              <option key={s} value={s}>
                {t(`progress.stageStatus.${s}`)}
              </option>
            ))}
          </select>,
        )}
      </div>
      {field('st-notes', t('guarantees.verifyNote'), <input id="st-notes" className={inputClass} value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />)}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" className={primaryButton} disabled={save.isPending}>
        {t('common.save')}
      </button>
    </form>
  )
}

export function StagesTab({ packageId }: { packageId: string }) {
  const { t } = useTranslation()
  const role = useRole()
  const canWrite = can(role, 'progress', 'W')
  const [editing, setEditing] = useState<StagePlan | null>(null)

  const { data, isPending, isError } = useQuery({
    queryKey: ['stages', packageId],
    queryFn: () => api.get<Stages>(`/packages/${packageId}/stages`),
  })

  if (isPending) return <p role="status">{t('common.loading')}</p>
  if (isError) return <p role="alert" className="text-danger">{t('common.error')}</p>

  const range = (s: StagePlan) =>
    s.planned_start && s.planned_end ? `${formatDate(s.planned_start)} – ${formatDate(s.planned_end)}` : NO_DATA

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="font-medium">
          {t('progress.packageProgress')}: {data.package_progress}%
        </p>
        <div role="progressbar" aria-label={t('progress.packageProgress')} aria-valuenow={data.package_progress} aria-valuemin={0} aria-valuemax={100} className="h-3 overflow-hidden rounded-full bg-muted">
          <div className="h-full bg-primary" style={{ width: `${data.package_progress}%` }} />
        </div>
      </div>

      <ul className="space-y-2">
        {data.stages.map((s) => (
          <li key={s.id} className="space-y-2 rounded-md border border-border p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-semibold">
                  {s.name}
                  {data.current_stage === s.stage_code && <span className="text-sm font-normal text-primary"> ◀</span>}
                </p>
                <p className="text-sm text-muted-foreground">
                  {t('progress.planned')}: {range(s)} · {t('progress.weight')} {s.weight}
                </p>
              </div>
              <StageStatusBadge status={s.effective_status} />
            </div>
            <div role="progressbar" aria-label={s.name} aria-valuenow={s.progress_pct} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full bg-primary" style={{ width: `${s.progress_pct}%` }} />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
              <span>
                {s.progress_pct}%
                {s.task_count > 0 && ` · ${s.tasks_done}/${s.task_count} ${t('progress.tasks').toLowerCase()}`}
                {s.actual_end && ` · ${t('progress.actualEnd')}: ${formatDate(s.actual_end)}`}
              </span>
              {canWrite && (
                <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setEditing(s)}>
                  {t('progress.editStage')}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>

      <TaskBoard packageId={packageId} stages={data.stages} canWrite={canWrite} />

      {editing && (
        <BottomSheet title={`${t('progress.editStage')}: ${editing.name}`} onClose={() => setEditing(null)}>
          <StageForm stage={editing} onDone={() => setEditing(null)} />
        </BottomSheet>
      )}
    </div>
  )
}
