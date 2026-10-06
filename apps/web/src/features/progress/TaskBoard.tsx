import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type DragEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { type StagePlan, TASK_STATUSES, type Task, type TaskStatus } from './types'

interface TaskBoardProps {
  packageId: string
  stages: StagePlan[]
  canWrite: boolean
}

export function TaskBoard({ packageId, stages, canWrite }: TaskBoardProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)
  const [suggest, setSuggest] = useState<StagePlan | null>(null)
  const [dragging, setDragging] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [stageId, setStageId] = useState('')
  const [priority, setPriority] = useState<Task['priority']>('normal')
  const [plannedEnd, setPlannedEnd] = useState('')

  const { data } = useQuery({
    queryKey: ['tasks', packageId],
    queryFn: () => api.get<Task[]>(`/packages/${packageId}/tasks`),
  })
  const stageName = (id: string | null) => stages.find((s) => s.id === id)?.name ?? t('progress.noStage')

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['tasks', packageId] }),
      queryClient.invalidateQueries({ queryKey: ['stages', packageId] }),
    ])

  const move = useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) => api.patch<Task>(`/tasks/${id}`, { status }),
    onSuccess: async (task) => {
      await refresh()
      const stage = stages.find((s) => s.id === task.stage_plan_id)
      // SPEC 4.4: when every task of a stage is done we only *suggest* closing it.
      if (task.stage_all_done && stage && stage.status !== 'done') setSuggest(stage)
    },
  })
  const create = useMutation({
    mutationFn: () =>
      api.post(`/packages/${packageId}/tasks`, {
        title: title.trim(),
        stage_plan_id: stageId || null,
        priority,
        planned_end: plannedEnd || null,
      }),
    onSuccess: async () => {
      setAdding(false)
      setTitle('')
      setPlannedEnd('')
      await refresh()
    },
  })
  const remove = useMutation({
    mutationFn: (id: string) => api.request('DELETE', `/tasks/${id}`),
    onSuccess: refresh,
  })
  const closeStage = useMutation({
    mutationFn: (id: string) => api.patch(`/stage-plans/${id}`, { status: 'done' }),
    onSuccess: async () => {
      setSuggest(null)
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ['timeline'] })])
    },
  })

  const onDrop = (e: DragEvent, status: TaskStatus) => {
    e.preventDefault()
    const id = e.dataTransfer.getData('text/plain') || dragging
    setDragging(null)
    const task = data?.find((x) => x.id === id)
    if (id && task && task.status !== status && canWrite) move.mutate({ id, status })
  }

  return (
    <section className="space-y-3" aria-label={t('progress.tasks')}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{t('progress.tasks')}</h3>
        {canWrite && (
          <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setAdding(true)}>
            {t('progress.addTask')}
          </button>
        )}
      </div>

      {suggest && (
        <div role="alert" className="space-y-2 rounded-md border border-info p-3">
          <p>{t('progress.stageDoneSuggestion')}</p>
          <p className="font-medium">{suggest.name}</p>
          <div className="flex gap-2">
            <button type="button" className={`${primaryButton} !w-auto`} onClick={() => closeStage.mutate(suggest.id)}>
              {t('progress.markStageDone')}
            </button>
            <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => setSuggest(null)}>
              {t('progress.later')}
            </button>
          </div>
        </div>
      )}

      {data && data.length === 0 && <p className="text-muted-foreground">{t('progress.noTasks')}</p>}
      <div className="grid gap-3 lg:grid-cols-4">
        {TASK_STATUSES.map((status) => {
          const column = (data ?? []).filter((x) => x.status === status)
          return (
            <div
              key={status}
              role="group"
              aria-label={t(`progress.taskStatus.${status}`)}
              className="space-y-2 rounded-md bg-muted p-2"
              onDragOver={(e) => canWrite && e.preventDefault()}
              onDrop={(e) => onDrop(e, status)}
            >
              <h4 className="px-1 text-sm font-semibold">
                {t(`progress.taskStatus.${status}`)} <span className="text-muted-foreground">({column.length})</span>
              </h4>
              {column.map((task) => (
                <article
                  key={task.id}
                  draggable={canWrite}
                  onDragStart={(e) => {
                    e.dataTransfer.setData('text/plain', task.id)
                    setDragging(task.id)
                  }}
                  className="space-y-1 rounded-md border border-border bg-background p-2"
                >
                  <p className="font-medium">{task.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {stageName(task.stage_plan_id)}
                    {task.planned_end && ` · ${formatDate(task.planned_end)}`}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {task.priority === 'high' && <StatusBadge tone="danger" icon="!">{t('progress.priorities.high')}</StatusBadge>}
                    {canWrite && (
                      <>
                        <select
                          aria-label={`${t('contract.status')}: ${task.title}`}
                          className="min-h-11 rounded-md border border-border bg-background px-2 text-sm"
                          value={task.status}
                          onChange={(e) => move.mutate({ id: task.id, status: e.target.value as TaskStatus })}
                        >
                          {TASK_STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {t(`progress.taskStatus.${s}`)}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          aria-label={`${t('progress.deleteTask')}: ${task.title}`}
                          className="min-h-11 min-w-11"
                          onClick={() => window.confirm(t('progress.confirmDeleteTask')) && remove.mutate(task.id)}
                        >
                          ✕
                        </button>
                      </>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )
        })}
      </div>

      {adding && (
        <BottomSheet title={t('progress.addTask')} onClose={() => setAdding(false)}>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              if (title.trim()) create.mutate()
            }}
          >
            <div>
              <label htmlFor="task-title" className="mb-1 block text-sm font-medium">
                {t('progress.taskTitle')}
              </label>
              <input id="task-title" className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div>
              <label htmlFor="task-stage" className="mb-1 block text-sm font-medium">
                {t('progress.stage')}
              </label>
              <select id="task-stage" className={inputClass} value={stageId} onChange={(e) => setStageId(e.target.value)}>
                <option value="">{t('progress.noStage')}</option>
                {stages.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="task-priority" className="mb-1 block text-sm font-medium">
                  {t('progress.priority')}
                </label>
                <select id="task-priority" className={inputClass} value={priority} onChange={(e) => setPriority(e.target.value as Task['priority'])}>
                  {(['low', 'normal', 'high'] as const).map((p) => (
                    <option key={p} value={p}>
                      {t(`progress.priorities.${p}`)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="task-end" className="mb-1 block text-sm font-medium">
                  {t('progress.plannedEnd')}
                </label>
                <input id="task-end" type="date" className={inputClass} value={plannedEnd} onChange={(e) => setPlannedEnd(e.target.value)} />
              </div>
            </div>
            <button type="submit" className={primaryButton} disabled={create.isPending || !title.trim()}>
              {t('common.save')}
            </button>
          </form>
        </BottomSheet>
      )}
    </section>
  )
}
