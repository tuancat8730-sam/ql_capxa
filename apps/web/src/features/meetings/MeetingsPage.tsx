import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'

const TYPES = ['kickoff', 'package_kickoff', 'weekly', 'issue_resolution', 'other'] as const

interface Meeting {
  id: string
  package_id: string | null
  meeting_type: (typeof TYPES)[number]
  meeting_date: string
  location: string | null
  chair: string | null
  attendees: { name: string; organization: string | null }[]
  minutes: string | null
  open_actions: number
}

interface Action {
  id: string
  meeting_id: string | null
  title: string
  due_date: string | null
  status: 'open' | 'done' | 'cancelled'
  overdue: boolean
}

const label = (id: string, text: string) => (
  <label htmlFor={id} className="mb-1 block text-sm font-medium">
    {text}
  </label>
)

function MeetingForm({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [v, setV] = useState({ meeting_type: 'weekly', meeting_date: '', location: '', chair: '', attendees: '', minutes: '' })
  const create = useMutation({
    mutationFn: () =>
      api.post('/meetings', {
        meeting_type: v.meeting_type,
        meeting_date: v.meeting_date,
        location: v.location || null,
        chair: v.chair || null,
        attendees: v.attendees
          .split(',')
          .map((n) => n.trim())
          .filter(Boolean)
          .map((name) => ({ name })),
        minutes: v.minutes || null,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['meetings'] })
      onDone()
    },
  })
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (v.meeting_date) create.mutate()
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          {label('mt-type', t('meetings.type'))}
          <select id="mt-type" className={inputClass} value={v.meeting_type} onChange={(e) => setV({ ...v, meeting_type: e.target.value })}>
            {TYPES.map((x) => (
              <option key={x} value={x}>
                {t(`meetings.types.${x}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          {label('mt-date', t('meetings.date'))}
          <input id="mt-date" type="date" className={inputClass} value={v.meeting_date} onChange={(e) => setV({ ...v, meeting_date: e.target.value })} required />
        </div>
        <div>
          {label('mt-loc', t('meetings.location'))}
          <input id="mt-loc" className={inputClass} value={v.location} onChange={(e) => setV({ ...v, location: e.target.value })} />
        </div>
        <div>
          {label('mt-chair', t('meetings.chair'))}
          <input id="mt-chair" className={inputClass} value={v.chair} onChange={(e) => setV({ ...v, chair: e.target.value })} />
        </div>
      </div>
      <div>
        {label('mt-att', t('meetings.attendees'))}
        <input id="mt-att" className={inputClass} value={v.attendees} onChange={(e) => setV({ ...v, attendees: e.target.value })} />
      </div>
      <div>
        {label('mt-min', t('meetings.minutes'))}
        <textarea id="mt-min" rows={4} className={`${inputClass} py-2`} value={v.minutes} onChange={(e) => setV({ ...v, minutes: e.target.value })} />
      </div>
      <button type="submit" className={primaryButton} disabled={create.isPending || !v.meeting_date}>
        {t('common.save')}
      </button>
    </form>
  )
}

function MeetingDetail({ meeting, canWrite }: { meeting: Meeting; canWrite: boolean }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const actions = useQuery({
    queryKey: ['meeting-actions', meeting.id],
    queryFn: () => api.get<Action[]>(`/meetings/${meeting.id}/action-items`),
  })
  const refresh = () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ['meeting-actions', meeting.id] }),
      qc.invalidateQueries({ queryKey: ['meetings'] }),
      qc.invalidateQueries({ queryKey: ['action-items'] }),
    ])
  const add = useMutation({
    mutationFn: () => api.post(`/meetings/${meeting.id}/action-items`, { title: title.trim(), due_date: due || null }),
    onSuccess: async () => {
      setTitle('')
      setDue('')
      await refresh()
    },
  })
  const done = useMutation({
    mutationFn: (a: Action) => api.patch(`/action-items/${a.id}`, { status: 'done' }),
    onSuccess: refresh,
  })

  return (
    <div className="space-y-3 border-t border-border pt-3">
      {meeting.minutes && <p className="whitespace-pre-wrap text-sm">{meeting.minutes}</p>}
      {meeting.attendees.length > 0 && <p className="text-sm text-muted-foreground">{meeting.attendees.map((a) => a.name).join(', ')}</p>}
      <h3 className="font-semibold">{t('meetings.actions')}</h3>
      {actions.data?.length === 0 && <p className="text-sm text-muted-foreground">{t('meetings.noActions')}</p>}
      <ul className="space-y-2">
        {actions.data?.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted p-2">
            <span>
              {a.title}
              {a.due_date && <span className="text-sm text-muted-foreground"> · {formatDate(a.due_date)}</span>}
            </span>
            <span className="flex items-center gap-2">
              {a.overdue && <StatusBadge tone="danger" icon="!">{t('meetings.overdue')}</StatusBadge>}
              <span className="text-sm">{t(`meetings.actionStatus.${a.status}`)}</span>
              {canWrite && a.status === 'open' && (
                <button type="button" className="min-h-11 rounded-md border border-border px-3 text-sm" onClick={() => done.mutate(a)}>
                  {t('meetings.markDone')}
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>
      {canWrite && (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (title.trim()) add.mutate()
          }}
        >
          <div className="min-w-48 flex-1">
            {label(`ai-${meeting.id}`, t('meetings.actionTitle'))}
            <input id={`ai-${meeting.id}`} className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            {label(`ad-${meeting.id}`, t('risks.dueDate'))}
            <input id={`ad-${meeting.id}`} type="date" className={inputClass} value={due} onChange={(e) => setDue(e.target.value)} />
          </div>
          <button type="submit" className={`${primaryButton} !w-auto`} disabled={!title.trim()}>
            {t('meetings.addAction')}
          </button>
        </form>
      )}
    </div>
  )
}

export function MeetingsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const canWrite = can(user?.role, 'meeting', 'W')
  const [adding, setAdding] = useState(false)
  const [open, setOpen] = useState<string | null>(null)

  const meetings = useQuery({ queryKey: ['meetings'], queryFn: () => api.get<Page<Meeting>>('/meetings?page_size=100') })
  const late = useQuery({ queryKey: ['action-items', 'overdue'], queryFn: () => api.get<Page<Action>>('/action-items?overdue=true&page_size=50') })

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('meetings.title')}</h1>
        {canWrite && (
          <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setAdding(true)}>
            {t('meetings.add')}
          </button>
        )}
      </div>

      {late.data && late.data.items.length > 0 && (
        <div role="region" aria-label={t('meetings.overdueBanner')} className="rounded-md border border-danger p-3">
          <h2 className="mb-1 font-semibold text-danger">! {t('meetings.overdueBanner')} ({late.data.total})</h2>
          <ul className="space-y-1 text-sm">
            {late.data.items.map((a) => (
              <li key={a.id}>
                {a.title}
                {a.due_date && ` · ${formatDate(a.due_date)}`}
              </li>
            ))}
          </ul>
        </div>
      )}

      {meetings.isPending && <p role="status">{t('common.loading')}</p>}
      {meetings.isError && <p role="alert" className="text-danger">{t('common.error')}</p>}
      {meetings.data?.items.length === 0 && <p className="text-muted-foreground">{t('meetings.none')}</p>}
      <ul className="space-y-2">
        {meetings.data?.items.map((m) => (
          <li key={m.id} className="space-y-2 rounded-md border border-border p-3">
            <button type="button" aria-expanded={open === m.id} className="block w-full text-left" onClick={() => setOpen(open === m.id ? null : m.id)}>
              <p className="font-semibold">
                {t(`meetings.types.${m.meeting_type}`)} · {formatDate(m.meeting_date)}
              </p>
              <p className="text-sm text-muted-foreground">
                {[m.location, m.chair].filter(Boolean).join(' · ')}
                {m.open_actions > 0 && ` · ${t('meetings.openActions', { count: m.open_actions })}`}
              </p>
            </button>
            {open === m.id && <MeetingDetail meeting={m} canWrite={canWrite} />}
          </li>
        ))}
      </ul>

      {adding && (
        <BottomSheet title={t('meetings.add')} onClose={() => setAdding(false)}>
          <MeetingForm onDone={() => setAdding(false)} />
        </BottomSheet>
      )}
    </section>
  )
}
