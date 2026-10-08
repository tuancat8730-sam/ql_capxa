import { useTranslation } from 'react-i18next'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { toDay } from '@/lib/gantt'
import type { DecisionStatus, DeliveryRisk, TaskState, WeekState } from './types'

/** "2026-10-07" as "07/10"; the project spans a few months of one year, so the year is left out. */
export function dm(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [, m, d] = iso.split('-')
  return `${d}/${m}`
}

/** "2026-10-07" as "07/10/2026". */
export function dmy(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

/** Whole days from `a` to `b` (negative when b is earlier). */
export function daysFrom(a: string, b: string): number {
  return toDay(b) - toDay(a)
}

const STATE_META: Record<TaskState, { tone: Tone; icon: string }> = {
  done: { tone: 'success', icon: '✓' },
  progress: { tone: 'info', icon: '●' },
  behind: { tone: 'warning', icon: '!' },
  late: { tone: 'danger', icon: '✕' },
  stale: { tone: 'neutral', icon: '?' },
  todo: { tone: 'neutral', icon: '○' },
  paused: { tone: 'warning', icon: '‖' },
}

export function StateBadge({ state }: { state: TaskState }) {
  const { t } = useTranslation()
  const m = STATE_META[state]
  return (
    <StatusBadge tone={m.tone} icon={m.icon}>
      {t(`delivery.state.${state}`)}
    </StatusBadge>
  )
}

/** CSS colour of a state, for bars and dots in the Gantt chart. */
export const STATE_COLOR: Record<TaskState, string> = {
  done: 'var(--success)',
  progress: 'var(--primary)',
  behind: 'var(--warning)',
  late: 'var(--danger)',
  stale: 'var(--neutral)',
  todo: 'var(--border)',
  paused: 'var(--warning)',
}

const WEEK_META: Record<WeekState, { tone: Tone; icon: string }> = {
  received: { tone: 'success', icon: '✓' },
  needs_more: { tone: 'warning', icon: '!' },
  missing: { tone: 'danger', icon: '✕' },
  current: { tone: 'info', icon: '●' },
  future: { tone: 'neutral', icon: '○' },
}

export function WeekBadge({ state }: { state: WeekState }) {
  const { t } = useTranslation()
  const m = WEEK_META[state]
  return (
    <StatusBadge tone={m.tone} icon={m.icon}>
      {t(`delivery.week.${state}`)}
    </StatusBadge>
  )
}

const DECISION_META: Record<DecisionStatus, { tone: Tone; icon: string }> = {
  pending: { tone: 'warning', icon: '!' },
  decided: { tone: 'success', icon: '✓' },
  not_applicable: { tone: 'neutral', icon: '–' },
}

export function DecisionBadge({ status }: { status: DecisionStatus }) {
  const { t } = useTranslation()
  const m = DECISION_META[status]
  return (
    <StatusBadge tone={m.tone} icon={m.icon}>
      {t(`delivery.decision.${status}`)}
    </StatusBadge>
  )
}

// --- risk levels ---------------------------------------------------------------------------------

export type Level = 'very_high' | 'high' | 'medium' | 'low'

export const LEVELS: Level[] = ['very_high', 'high', 'medium', 'low']

/** The shared risks API scores probability x impact; this project speaks in four levels. */
const LEVEL_SCORE: Record<Level, { probability: number; impact: number }> = {
  very_high: { probability: 5, impact: 5 },
  high: { probability: 4, impact: 4 },
  medium: { probability: 3, impact: 3 },
  low: { probability: 2, impact: 2 },
}

export function levelOf(score: number): Level {
  if (score >= 25) return 'very_high'
  if (score >= 13) return 'high'
  if (score >= 6) return 'medium'
  return 'low'
}

export function scoreOfLevel(level: Level): { probability: number; impact: number } {
  return LEVEL_SCORE[level]
}

const LEVEL_META: Record<Level, { tone: Tone; icon: string }> = {
  very_high: { tone: 'danger', icon: '✕' },
  high: { tone: 'warning', icon: '!' },
  medium: { tone: 'info', icon: '●' },
  low: { tone: 'neutral', icon: '○' },
}

export function LevelBadge({ risk }: { risk: Pick<DeliveryRisk, 'score'> }) {
  const { t } = useTranslation()
  const level = levelOf(risk.score)
  const m = LEVEL_META[level]
  return (
    <StatusBadge tone={m.tone} icon={m.icon}>
      {t(`delivery.level.${level}`)}
    </StatusBadge>
  )
}
