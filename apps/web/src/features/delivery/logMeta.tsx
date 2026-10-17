import { useTranslation } from 'react-i18next'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import type { Task } from './types'
import type { EntryState } from './logTypes'

const STATE_META: Record<EntryState, { tone: Tone; icon: string }> = {
  done: { tone: 'success', icon: '✓' },
  in_progress: { tone: 'info', icon: '●' },
  not_started: { tone: 'neutral', icon: '○' },
  blocked: { tone: 'danger', icon: '✕' },
}

export function EntryStateBadge({ state }: { state: EntryState }) {
  const { t } = useTranslation()
  const m = STATE_META[state]
  return (
    <StatusBadge tone={m.tone} icon={m.icon}>
      {t(`delivery.log.state.${state}`)}
    </StatusBadge>
  )
}

export function DelayBadge({ days }: { days: number }) {
  const { t } = useTranslation()
  return (
    <StatusBadge tone="warning" icon="!">
      {t('delivery.log.delay', { n: days })}
    </StatusBadge>
  )
}

/** The API shows a task as "III.4"; a log line stores the schedule's own code, "III-4". */
export const storedCode = (task: Pick<Task, 'code' | 'is_milestone'>): string =>
  task.is_milestone ? task.code : task.code.replace('.', '-')

/** "III-4" as "III.4" (milestones such as "M3" stay as they are). */
export const shownCode = (code: string): string => (/^M\d+$/.test(code) ? code : code.replace('-', '.'))

/** The 7 days of a reporting week, as ISO dates, starting on `start`. */
export function weekDays(start: string): string[] {
  const [y, m, d] = start.split('-').map(Number)
  return Array.from({ length: 7 }, (_, i) => new Date(Date.UTC(y, m - 1, d + i)).toISOString().slice(0, 10))
}

/** 0 = Sunday … 6 = Saturday, from an ISO date (no time zone involved). */
export function weekdayOf(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay()
}

export const splitNames = (text: string): string[] =>
  text
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean)

export const joinNames = (names: string[]): string => names.join(', ')
