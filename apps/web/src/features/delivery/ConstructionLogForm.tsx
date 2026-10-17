import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError } from '@/lib/api'
import { joinNames, shownCode, splitNames, storedCode, weekdayOf, weekDays } from './logMeta'
import { useRefreshDelivery } from './queries'
import type {
  ConstructionLog,
  ConstructionLogInput,
  EntryState,
  LogCarryover,
  LogEntry,
  LogHeader,
  LogMemberWork,
} from './logTypes'
import { ENTRY_STATES } from './logTypes'
import { dm } from './meta'
import type { Task } from './types'

const blank = (v: string): string | null => (v.trim() ? v.trim() : null)

// Row keys only need to be unique among the rows of one open form.
let keySeq = 0
const nextKey = (): number => ++keySeq

interface EntryDraft {
  key: number
  entry_date: string
  phase_code: string
  task_code: string
  content: string
  personnel: string
  note: string
  state: '' | EntryState
  delay_days: string
}

interface CarryDraft {
  key: number
  phase_code: string
  task_code: string
  title: string
  result_to_date: string
  next_week: string
  note: string
}

interface MemberDraft {
  key: number
  member_name: string
  item: string
  plan_ref: string
  personnel: string
  result: string
  next_plan: string
  issues_actions: string
}

type HeaderDraft = { [K in keyof LogHeader]: string }

const HEADER_FIELDS: (keyof LogHeader)[] = [
  'report_date',
  'recipients',
  'reporter_org',
  'contract_ref',
  'coordinator',
  'environment_note',
  'overall_status',
  'key_results',
  'issues',
  'coordination_requests',
  'related_report',
]
const LONG_FIELDS = new Set<keyof LogHeader>([
  'recipients',
  'contract_ref',
  'environment_note',
  'overall_status',
  'key_results',
  'issues',
  'coordination_requests',
  'related_report',
])

function update<T extends { key: number }>(list: T[], key: number, change: Partial<T>): T[] {
  return list.map((row) => (row.key === key ? { ...row, ...change } : row))
}

function move<T>(list: T[], index: number, by: -1 | 1): T[] {
  const target = index + by
  if (target < 0 || target >= list.length) return list
  const next = [...list]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

interface Props {
  weekStart: string
  weekEnd: string
  log: ConstructionLog | null
  tasks: Task[]
  onCancel: () => void
  onSaved: () => void
  onReload: () => void
}

/** Edit one week's log as a whole: the header, the day-by-day lines, the carry-over and the member's work. */
export function ConstructionLogForm({ weekStart, weekEnd, log, tasks, onCancel, onSaved, onReload }: Props) {
  const { t } = useTranslation()
  const refresh = useRefreshDelivery()

  const phases = tasks.reduce<{ code: string; name: string }[]>(
    (acc, task) => (acc.some((p) => p.code === task.phase_code) ? acc : [...acc, { code: task.phase_code, name: task.phase_name }]),
    [],
  )
  const days = weekDays(weekStart)
  // The version this editor started from: a refetch while it is open must not change it.
  const [loadedAt] = useState(() => log?.updated_at ?? null)

  const [header, setHeader] = useState<HeaderDraft>(() =>
    Object.fromEntries(HEADER_FIELDS.map((f) => [f, log?.[f] ?? ''])) as HeaderDraft,
  )
  const [entries, setEntries] = useState<EntryDraft[]>(() =>
    (log?.entries ?? []).map((e) => ({
      key: nextKey(),
      entry_date: e.entry_date,
      phase_code: e.phase_code,
      task_code: e.task_code ?? '',
      content: e.content,
      personnel: joinNames(e.personnel),
      note: e.note ?? '',
      state: e.state ?? '',
      delay_days: e.delay_days == null ? '' : String(e.delay_days),
    })),
  )
  const [carryovers, setCarryovers] = useState<CarryDraft[]>(() =>
    (log?.carryovers ?? []).map((c) => ({
      key: nextKey(),
      phase_code: c.phase_code,
      task_code: c.task_code ?? '',
      title: c.title,
      result_to_date: c.result_to_date ?? '',
      next_week: c.next_week ?? '',
      note: c.note ?? '',
    })),
  )
  const [members, setMembers] = useState<MemberDraft[]>(() =>
    (log?.member_work ?? []).map((m) => ({
      key: nextKey(),
      member_name: m.member_name,
      item: m.item,
      plan_ref: m.plan_ref ?? '',
      personnel: joinNames(m.personnel),
      result: m.result ?? '',
      next_plan: m.next_plan ?? '',
      issues_actions: m.issues_actions ?? '',
    })),
  )
  const [error, setError] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [busy, setBusy] = useState(false)

  const tasksOf = (phase: string) => tasks.filter((task) => task.phase_code === phase && !task.is_milestone)

  const taskSelect = (id: string, phase: string, value: string, set: (v: string) => void) => (
    <select id={id} className={inputClass} value={value} onChange={(e) => set(e.target.value)}>
      <option value="">{t('delivery.log.form.noTask')}</option>
      {value && !tasksOf(phase).some((task) => storedCode(task) === value) && (
        <option value={value}>{shownCode(value)}</option>
      )}
      {tasksOf(phase).map((task) => (
        <option key={task.id} value={storedCode(task)}>
          {task.code} · {task.name}
        </option>
      ))}
    </select>
  )

  const phaseSelect = (id: string, value: string, set: (v: string) => void) => (
    <select id={id} className={inputClass} value={value} onChange={(e) => set(e.target.value)}>
      {phases.map((p) => (
        <option key={p.code} value={p.code}>
          {p.code} · {p.name}
        </option>
      ))}
    </select>
  )

  const area = (id: string, label: string, value: string, set: (v: string) => void, rows = 3) => (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
      </label>
      <textarea id={id} rows={rows} className={inputClass} value={value} onChange={(e) => set(e.target.value)} />
    </div>
  )

  const rowButtons = (index: number, count: number, swap: (by: -1 | 1) => void, remove: () => void, label: string) => (
    <div className="flex flex-wrap gap-2">
      <button type="button" className="min-h-11 rounded-md border border-border px-3" disabled={index === 0} onClick={() => swap(-1)} aria-label={t('delivery.log.form.up', { name: label })}>
        ↑
      </button>
      <button type="button" className="min-h-11 rounded-md border border-border px-3" disabled={index === count - 1} onClick={() => swap(1)} aria-label={t('delivery.log.form.down', { name: label })}>
        ↓
      </button>
      <button type="button" className="min-h-11 rounded-md border border-danger px-3 text-danger" onClick={remove} aria-label={t('delivery.log.form.remove', { name: label })}>
        {t('delivery.log.form.removeShort')}
      </button>
    </div>
  )

  const firstPhase = phases[0]?.code ?? ''
  const addEntry = () =>
    setEntries((rows) => [
      ...rows,
      { key: nextKey(), entry_date: rows.at(-1)?.entry_date ?? weekStart, phase_code: rows.at(-1)?.phase_code ?? firstPhase, task_code: '', content: '', personnel: '', note: '', state: '', delay_days: '' },
    ])
  const addCarry = () =>
    setCarryovers((rows) => [
      ...rows,
      { key: nextKey(), phase_code: rows.at(-1)?.phase_code ?? firstPhase, task_code: '', title: '', result_to_date: '', next_week: '', note: '' },
    ])
  const addMember = () =>
    setMembers((rows) => [
      ...rows,
      { key: nextKey(), member_name: rows.at(-1)?.member_name ?? '', item: '', plan_ref: '', personnel: '', result: '', next_plan: '', issues_actions: '' },
    ])

  const save = async () => {
    if (entries.some((e) => !e.content.trim()) || carryovers.some((c) => !c.title.trim()) || members.some((m) => !m.item.trim() || !m.member_name.trim())) {
      setError(t('delivery.log.form.invalid'))
      return
    }
    const body: ConstructionLogInput = {
      report_date: header.report_date || null,
      recipients: blank(header.recipients ?? ''),
      reporter_org: blank(header.reporter_org ?? ''),
      contract_ref: blank(header.contract_ref ?? ''),
      coordinator: blank(header.coordinator ?? ''),
      environment_note: blank(header.environment_note ?? ''),
      overall_status: blank(header.overall_status ?? ''),
      key_results: blank(header.key_results ?? ''),
      issues: blank(header.issues ?? ''),
      coordination_requests: blank(header.coordination_requests ?? ''),
      related_report: blank(header.related_report ?? ''),
      entries: entries.map(
        (e): LogEntry => ({
          entry_date: e.entry_date,
          phase_code: e.phase_code,
          task_code: e.task_code || null,
          content: e.content.trim(),
          personnel: splitNames(e.personnel),
          note: blank(e.note),
          state: e.state || null,
          delay_days: e.delay_days === '' ? null : Math.max(0, Math.round(Number(e.delay_days))),
        }),
      ),
      carryovers: carryovers.map(
        (c): LogCarryover => ({
          phase_code: c.phase_code,
          task_code: c.task_code || null,
          title: c.title.trim(),
          result_to_date: blank(c.result_to_date),
          next_week: blank(c.next_week),
          note: blank(c.note),
        }),
      ),
      member_work: members.map(
        (m): LogMemberWork => ({
          member_name: m.member_name.trim(),
          item: m.item.trim(),
          plan_ref: blank(m.plan_ref),
          personnel: splitNames(m.personnel),
          result: blank(m.result),
          next_plan: blank(m.next_plan),
          issues_actions: blank(m.issues_actions),
        }),
      ),
      expected_updated_at: loadedAt,
    }
    setBusy(true)
    setError(null)
    try {
      await api.put(`/delivery/logs/${weekStart}`, body)
      await refresh()
      onSaved()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setStale(true)
      else setError(err instanceof ApiError && err.status === 422 ? err.message : t('common.error'))
      setBusy(false)
    }
  }

  const section = (title: string) => <h2 className="text-lg font-semibold">{title}</h2>

  return (
    <form
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault()
        void save()
      }}
    >
      <p className="text-sm text-muted-foreground">
        {t('delivery.log.form.period', { from: dm(weekStart), to: dm(weekEnd) })}
      </p>

      <fieldset disabled={busy} className="space-y-4">
        {section(t('delivery.log.form.general'))}
        <div className="grid gap-3 sm:grid-cols-2">
          {HEADER_FIELDS.filter((f) => !LONG_FIELDS.has(f)).map((f) => (
            <div key={f}>
              <label htmlFor={`h-${f}`} className="mb-1 block text-sm font-medium">
                {t(`delivery.log.header.${f}`)}
              </label>
              <input
                id={`h-${f}`}
                type={f === 'report_date' ? 'date' : 'text'}
                className={inputClass}
                value={header[f] ?? ''}
                onChange={(e) => setHeader((h) => ({ ...h, [f]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        {(['recipients', 'contract_ref', 'environment_note'] as const).map((f) =>
          area(`h-${f}`, t(`delivery.log.header.${f}`), header[f] ?? '', (v) => setHeader((h) => ({ ...h, [f]: v })), 2),
        )}

        {section(t('delivery.log.sectionDays'))}
        {entries.length === 0 && <p className="text-sm text-muted-foreground">{t('delivery.log.form.noEntries')}</p>}
        {entries.map((e, i) => (
          <div key={e.key} className="space-y-3 rounded-md border border-border p-3">
            <p className="font-medium">{t('delivery.log.form.entryN', { n: i + 1 })}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor={`e-day-${e.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.day')}</label>
                <select id={`e-day-${e.key}`} className={inputClass} value={e.entry_date} onChange={(ev) => setEntries((r) => update(r, e.key, { entry_date: ev.target.value }))}>
                  {days.map((d) => (
                    <option key={d} value={d}>
                      {t(`delivery.log.weekday.${weekdayOf(d)}`)} {dm(d)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={`e-phase-${e.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.phase')}</label>
                {phaseSelect(`e-phase-${e.key}`, e.phase_code, (v) => setEntries((r) => update(r, e.key, { phase_code: v, task_code: '' })))}
              </div>
              <div className="sm:col-span-2">
                <label htmlFor={`e-task-${e.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.task')}</label>
                {taskSelect(`e-task-${e.key}`, e.phase_code, e.task_code, (v) => setEntries((r) => update(r, e.key, { task_code: v })))}
              </div>
            </div>
            {area(`e-content-${e.key}`, t('delivery.log.form.content'), e.content, (v) => setEntries((r) => update(r, e.key, { content: v })), 4)}
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor={`e-people-${e.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.personnel')}</label>
                <input id={`e-people-${e.key}`} className={inputClass} value={e.personnel} onChange={(ev) => setEntries((r) => update(r, e.key, { personnel: ev.target.value }))} />
                <p className="mt-1 text-xs text-muted-foreground">{t('delivery.log.form.personnelHint')}</p>
              </div>
              <div>
                <label htmlFor={`e-state-${e.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.state')}</label>
                <select id={`e-state-${e.key}`} className={inputClass} value={e.state} onChange={(ev) => setEntries((r) => update(r, e.key, { state: ev.target.value as '' | EntryState }))}>
                  <option value="">—</option>
                  {ENTRY_STATES.map((s) => (
                    <option key={s} value={s}>{t(`delivery.log.state.${s}`)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={`e-delay-${e.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.delayDays')}</label>
                <input id={`e-delay-${e.key}`} type="number" min={0} inputMode="numeric" className={inputClass} value={e.delay_days} onChange={(ev) => setEntries((r) => update(r, e.key, { delay_days: ev.target.value }))} />
              </div>
            </div>
            {area(`e-note-${e.key}`, t('delivery.log.form.note'), e.note, (v) => setEntries((r) => update(r, e.key, { note: v })), 2)}
            {rowButtons(i, entries.length, (by) => setEntries((r) => move(r, i, by)), () => setEntries((r) => r.filter((x) => x.key !== e.key)), t('delivery.log.form.entryN', { n: i + 1 }))}
          </div>
        ))}
        <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={addEntry}>
          {t('delivery.log.form.addEntry')}
        </button>

        {section(t('delivery.log.sectionSummary'))}
        {(['overall_status', 'key_results', 'issues', 'coordination_requests', 'related_report'] as const).map((f) =>
          area(`h-${f}`, t(`delivery.log.header.${f}`), header[f] ?? '', (v) => setHeader((h) => ({ ...h, [f]: v })), f === 'related_report' ? 2 : 4),
        )}

        {section(t('delivery.log.sectionCarry'))}
        {carryovers.map((c, i) => (
          <div key={c.key} className="space-y-3 rounded-md border border-border p-3">
            <p className="font-medium">{t('delivery.log.form.carryN', { n: i + 1 })}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor={`c-phase-${c.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.phase')}</label>
                {phaseSelect(`c-phase-${c.key}`, c.phase_code, (v) => setCarryovers((r) => update(r, c.key, { phase_code: v, task_code: '' })))}
              </div>
              <div>
                <label htmlFor={`c-task-${c.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.task')}</label>
                {taskSelect(`c-task-${c.key}`, c.phase_code, c.task_code, (v) => setCarryovers((r) => update(r, c.key, { task_code: v })))}
              </div>
            </div>
            {area(`c-title-${c.key}`, t('delivery.log.form.carryTitle'), c.title, (v) => setCarryovers((r) => update(r, c.key, { title: v })), 2)}
            {area(`c-result-${c.key}`, t('delivery.log.form.carryResult'), c.result_to_date, (v) => setCarryovers((r) => update(r, c.key, { result_to_date: v })), 2)}
            {area(`c-next-${c.key}`, t('delivery.log.form.carryNext'), c.next_week, (v) => setCarryovers((r) => update(r, c.key, { next_week: v })), 2)}
            {area(`c-note-${c.key}`, t('delivery.log.form.note'), c.note, (v) => setCarryovers((r) => update(r, c.key, { note: v })), 2)}
            {rowButtons(i, carryovers.length, (by) => setCarryovers((r) => move(r, i, by)), () => setCarryovers((r) => r.filter((x) => x.key !== c.key)), t('delivery.log.form.carryN', { n: i + 1 }))}
          </div>
        ))}
        <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={addCarry}>
          {t('delivery.log.form.addCarry')}
        </button>

        {section(t('delivery.log.sectionMember'))}
        {members.map((m, i) => (
          <div key={m.key} className="space-y-3 rounded-md border border-border p-3">
            <p className="font-medium">{t('delivery.log.form.memberN', { n: i + 1 })}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor={`m-name-${m.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.memberName')}</label>
                <input id={`m-name-${m.key}`} className={inputClass} value={m.member_name} onChange={(ev) => setMembers((r) => update(r, m.key, { member_name: ev.target.value }))} />
              </div>
              <div>
                <label htmlFor={`m-people-${m.key}`} className="mb-1 block text-sm font-medium">{t('delivery.log.form.personnel')}</label>
                <input id={`m-people-${m.key}`} className={inputClass} value={m.personnel} onChange={(ev) => setMembers((r) => update(r, m.key, { personnel: ev.target.value }))} />
              </div>
            </div>
            {area(`m-item-${m.key}`, t('delivery.log.form.memberItem'), m.item, (v) => setMembers((r) => update(r, m.key, { item: v })), 2)}
            {area(`m-plan-${m.key}`, t('delivery.log.form.memberPlan'), m.plan_ref, (v) => setMembers((r) => update(r, m.key, { plan_ref: v })), 2)}
            {area(`m-result-${m.key}`, t('delivery.log.form.memberResult'), m.result, (v) => setMembers((r) => update(r, m.key, { result: v })), 3)}
            {area(`m-next-${m.key}`, t('delivery.log.form.memberNext'), m.next_plan, (v) => setMembers((r) => update(r, m.key, { next_plan: v })), 3)}
            {area(`m-issues-${m.key}`, t('delivery.log.form.memberIssues'), m.issues_actions, (v) => setMembers((r) => update(r, m.key, { issues_actions: v })), 3)}
            {rowButtons(i, members.length, (by) => setMembers((r) => move(r, i, by)), () => setMembers((r) => r.filter((x) => x.key !== m.key)), t('delivery.log.form.memberN', { n: i + 1 }))}
          </div>
        ))}
        <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={addMember}>
          {t('delivery.log.form.addMember')}
        </button>
      </fieldset>

      {stale && (
        <div role="alert" className="space-y-2 rounded-md border border-warning p-3">
          <p className="text-warning">{t('delivery.log.form.stale')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={onReload}>
            {t('delivery.log.form.reload')}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <div className="flex flex-col gap-2 sm:flex-row">
        <button type="submit" disabled={busy} className={primaryButton}>
          {t('common.save')}
        </button>
        <button type="button" disabled={busy} className="min-h-11 rounded-md border border-border px-4" onClick={onCancel}>
          {t('common.cancel')}
        </button>
      </div>
    </form>
  )
}
