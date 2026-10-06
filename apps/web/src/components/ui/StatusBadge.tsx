import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const toneClass: Record<Tone, string> = {
  success: 'border-success text-success',
  warning: 'border-warning text-warning',
  danger: 'border-danger text-danger',
  info: 'border-info text-info',
  neutral: 'border-neutral text-neutral',
}

/** Status is never conveyed by colour alone (SPEC 15.4): every badge has an icon and a label. */
export function StatusBadge({ tone, icon, children }: { tone: Tone; icon: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex min-h-6 items-center gap-1 rounded-full border px-2 text-xs font-medium ${toneClass[tone]}`}
    >
      <span aria-hidden>{icon}</span>
      {children}
    </span>
  )
}

const healthMeta = {
  green: { tone: 'success', icon: '✓' },
  amber: { tone: 'warning', icon: '!' },
  red: { tone: 'danger', icon: '✕' },
  grey: { tone: 'neutral', icon: '–' },
} as const

export function HealthBadge({ health }: { health: keyof typeof healthMeta }) {
  const { t } = useTranslation()
  const meta = healthMeta[health]
  return (
    <StatusBadge tone={meta.tone} icon={meta.icon}>
      {t(`health.${health}`)}
    </StatusBadge>
  )
}
