import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError } from '@/lib/api'
import { dmy, StateBadge } from './meta'
import { useRefreshDelivery } from './queries'
import type { Task, TaskPatch, TaskStatus } from './types'

const STATUSES: TaskStatus[] = ['not_started', 'in_progress', 'done', 'on_hold']
const QUICK = [0, 25, 50, 75, 100]

interface Props {
  task: Task
  canWrite: boolean
  onClose: () => void
}

/** Record progress on one line of the schedule: status, percent, real dates and a note. */
export function TaskSheet({ task, canWrite, onClose }: Props) {
  const { t } = useTranslation()
  const refresh = useRefreshDelivery()
  const milestone = task.is_milestone
  const [status, setStatus] = useState<TaskStatus>(task.status)
  const [pct, setPct] = useState(task.pct)
  const [start, setStart] = useState(task.actual_start ?? '')
  const [end, setEnd] = useState(task.actual_end ?? '')
  const [note, setNote] = useState(task.note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (call: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await call()
      await refresh()
      onClose()
    } catch (err) {
      setError(err instanceof ApiError && err.status === 422 ? err.message : t('common.error'))
      setBusy(false)
    }
  }

  const save = () => {
    const body: TaskPatch = {
      status,
      actual_start: milestone ? undefined : start || null,
      actual_end: end || null,
      note: note.trim() || null,
    }
    if (!milestone) body.pct = pct
    return run(() => api.patch(`/delivery/tasks/${task.id}`, body))
  }

  const period = milestone
    ? t('delivery.task.milestoneDay', { date: dmy(task.plan_start) })
    : t('delivery.task.period', { from: dmy(task.plan_start), to: dmy(task.plan_end), days: task.plan_days })

  return (
    <BottomSheet title={`${task.code} · ${task.name}`} onClose={onClose}>
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <StateBadge state={task.state} />
        {task.late_days > 0 && task.state !== 'done' && (
          <span className="text-danger">{t('delivery.task.lateDays', { n: task.late_days })}</span>
        )}
        <span className="text-muted-foreground">{period}</span>
      </div>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (canWrite) void save()
        }}
      >
        <fieldset disabled={!canWrite || busy} className="space-y-4">
          <div>
            <label htmlFor="t-status" className="mb-1 block text-sm font-medium">
              {t('delivery.task.status')}
            </label>
            <select
              id="t-status"
              className={inputClass}
              value={status}
              onChange={(e) => setStatus(e.target.value as TaskStatus)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`delivery.task.statuses.${milestone && s === 'done' ? 'reached' : s}`)}
                </option>
              ))}
            </select>
          </div>
          {!milestone && (
            <div>
              <label htmlFor="t-pct" className="mb-1 block text-sm font-medium">
                {t('delivery.task.pct')}
              </label>
              <input
                id="t-pct"
                type="number"
                min={0}
                max={100}
                step={1}
                inputMode="numeric"
                className={inputClass}
                value={pct}
                onChange={(e) => setPct(Math.max(0, Math.min(100, Math.round(Number(e.target.value) || 0))))}
              />
              <div className="mt-2 flex flex-wrap gap-2">
                {QUICK.map((v) => (
                  <button
                    key={v}
                    type="button"
                    className="min-h-11 min-w-11 rounded-md border border-border px-3"
                    onClick={() => setPct(v)}
                  >
                    {v}%
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className={milestone ? '' : 'grid gap-3 sm:grid-cols-2'}>
            {!milestone && (
              <div>
                <label htmlFor="t-start" className="mb-1 block text-sm font-medium">
                  {t('delivery.task.actualStart')}
                </label>
                <input id="t-start" type="date" className={inputClass} value={start} onChange={(e) => setStart(e.target.value)} />
              </div>
            )}
            <div>
              <label htmlFor="t-end" className="mb-1 block text-sm font-medium">
                {milestone ? t('delivery.task.reachedOn') : t('delivery.task.actualEnd')}
              </label>
              <input id="t-end" type="date" className={inputClass} value={end} onChange={(e) => setEnd(e.target.value)} />
            </div>
          </div>
          <div>
            <label htmlFor="t-note" className="mb-1 block text-sm font-medium">
              {t('delivery.task.note')}
            </label>
            <textarea
              id="t-note"
              rows={3}
              className={inputClass}
              placeholder={t('delivery.task.notePlaceholder')}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
        </fieldset>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        {canWrite && (
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="submit" disabled={busy} className={primaryButton}>
              {t('common.save')}
            </button>
            {task.tracked && (
              <button
                type="button"
                disabled={busy}
                className="min-h-11 rounded-md border border-border px-4"
                onClick={() =>
                  window.confirm(t('delivery.task.confirmReset')) &&
                  void run(() => api.post(`/delivery/tasks/${task.id}/reset`))
                }
              >
                {t('delivery.task.reset')}
              </button>
            )}
          </div>
        )}
      </form>
    </BottomSheet>
  )
}
