import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { ApiError, api } from '@/lib/api'
import { periodText } from './period'
import { type EffectiveStatus, type PlanStep, STEP_STATUSES, type StepStatus } from './types'

const META: Record<EffectiveStatus, { tone: Tone; icon: string }> = {
  not_started: { tone: 'neutral', icon: '○' },
  in_progress: { tone: 'info', icon: '▶' },
  done: { tone: 'success', icon: '✓' },
  blocked: { tone: 'warning', icon: '!' },
  delayed: { tone: 'danger', icon: '✕' },
}

export function StepStatusBadge({ step }: { step: Pick<PlanStep, 'effective_status' | 'days_late'> }) {
  const { t } = useTranslation()
  const m = META[step.effective_status]
  return (
    <StatusBadge tone={m.tone} icon={m.icon}>
      {t(`plan.status.${step.effective_status}`, { n: step.days_late ?? 0 })}
    </StatusBadge>
  )
}

function StepSheet({ step, packageId, onClose }: { step: PlanStep; packageId: string; onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<StepStatus>(step.status)
  const [start, setStart] = useState(step.actual_start ?? '')
  const [end, setEnd] = useState(step.actual_end ?? '')
  const [note, setNote] = useState(step.tracking_note ?? '')
  const [error, setError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () =>
      api.patch(`/plan-steps/${step.id}`, {
        status,
        actual_start: start || null,
        actual_end: end || null,
        tracking_note: note || null,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['plan', packageId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      ])
      onClose()
    },
    onError: (e) => setError(e instanceof ApiError && e.status === 422 ? e.message : t('common.error')),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <BottomSheet title={t('plan.updateTitle', { n: step.step_no })} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="line-clamp-3 text-sm text-muted-foreground">{step.content.split('\n')[0]}</p>
        <label className="block space-y-1">
          <span className="text-sm">{t('plan.statusLabel')}</span>
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value as StepStatus)}>
            {STEP_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`plan.status.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block space-y-1">
            <span className="text-sm">{t('plan.actualStart')}</span>
            <input type="date" className={inputClass} value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label className="block space-y-1">
            <span className="text-sm">{t('plan.actualEnd')}</span>
            <input type="date" className={inputClass} value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
        </div>
        <label className="block space-y-1">
          <span className="text-sm">{t('plan.note')}</span>
          <textarea rows={3} maxLength={2000} className={inputClass} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex gap-2">
          <button type="submit" className={primaryButton} disabled={save.isPending}>
            {t('common.save')}
          </button>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={onClose}>
            {t('common.cancel')}
          </button>
        </div>
      </form>
    </BottomSheet>
  )
}

export function PlanSteps({ steps, packageId, canTrack }: { steps: PlanStep[]; packageId: string; canTrack: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<PlanStep | null>(null)

  const complete = useMutation({
    mutationFn: (s: PlanStep) => api.patch(`/plan-steps/${s.id}`, { status: 'done' }),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ['plan', packageId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      ]),
  })

  const groups = [...new Set(steps.map((s) => s.group_no))]
  return (
    <section aria-label={t('plan.steps')} className="space-y-4">
      <h3 className="text-lg font-semibold">{t('plan.steps')}</h3>
      {groups.map((g) => {
        const inGroup = steps.filter((s) => s.group_no === g)
        const done = inGroup.filter((s) => s.status === 'done').length
        const title = inGroup[0].group_title
        return (
          <section key={String(g)} aria-label={g == null ? t('plan.steps') : t('plan.stage', { n: g })} className="space-y-2">
            {g != null && (
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="font-semibold">
                  {t('plan.stage', { n: g })}
                  {title && <span className="font-normal text-muted-foreground"> · {title}</span>}
                </h4>
                <span className="text-sm text-muted-foreground">{t('plan.stageDone', { done, total: inGroup.length })}</span>
              </div>
            )}
            <ul className="space-y-2">
              {inGroup.map((s) => {
                const period = periodText(s.start_date, s.end_date)
                return (
                  <li key={s.id} className="space-y-2 rounded-md border border-border p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-semibold">
                        <span className="mr-2 inline-flex size-7 items-center justify-center rounded-full bg-muted text-sm">{s.step_no}</span>
                        {t('plan.updateTitle', { n: s.step_no })}
                      </p>
                      <StepStatusBadge step={s} />
                    </div>
                    <ul className="list-none space-y-1 text-sm">
                      {s.content.split('\n').map((line, i) => (
                        <li key={i}>{line}</li>
                      ))}
                    </ul>
                    <p className="text-sm">
                      <span className="text-muted-foreground">{t('plan.time')}: </span>
                      {period ? (
                        <>
                          {period}
                          {s.estimated && <span className="text-muted-foreground"> ({t('plan.estimated')})</span>}
                        </>
                      ) : (
                        <span className="text-muted-foreground">{t('plan.noTime')}</span>
                      )}
                      {s.time_note && <span className="text-muted-foreground"> · {s.time_note}</span>}
                    </p>
                    {s.participants.length > 0 && (
                      <p className="text-sm">
                        <span className="text-muted-foreground">{t('plan.participants')}: </span>
                        {s.participants.join(' · ')}
                      </p>
                    )}
                    {(s.actual_start || s.actual_end || s.tracking_note) && (
                      <p className="rounded-md bg-muted p-2 text-sm">
                        <span className="font-medium">{t('plan.actual')}: </span>
                        {periodText(s.actual_start, s.actual_end)}
                        {s.tracking_note && <span> · {s.tracking_note}</span>}
                      </p>
                    )}
                    {canTrack && (
                      <div className="flex flex-wrap gap-2">
                        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setEditing(s)}>
                          {t('plan.update')}
                        </button>
                        {s.status !== 'done' && (
                          <button
                            type="button"
                            className="min-h-11 rounded-md border border-border px-3"
                            disabled={complete.isPending}
                            aria-label={`${t('plan.markDone')}: ${s.step_no}`}
                            onClick={() => complete.mutate(s)}
                          >
                            {t('plan.markDone')}
                          </button>
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </section>
        )
      })}
      {editing && <StepSheet key={editing.id} step={editing} packageId={packageId} onClose={() => setEditing(null)} />}
    </section>
  )
}
