import { useTranslation } from 'react-i18next'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { formatDate, formatMoney, NO_DATA } from '@/lib/format'
import type { EffectiveGuaranteeStatus, Guarantee } from './types'

const STATUS_TONE: Record<EffectiveGuaranteeStatus, { tone: Tone; icon: string }> = {
  valid: { tone: 'success', icon: '✓' },
  pending: { tone: 'neutral', icon: '…' },
  expiring: { tone: 'warning', icon: '!' },
  expired: { tone: 'danger', icon: '✕' },
  missing: { tone: 'danger', icon: '✕' },
  released: { tone: 'neutral', icon: '↩' },
}

export function GuaranteeStatusBadge({ status }: { status: EffectiveGuaranteeStatus }) {
  const { t } = useTranslation()
  const meta = STATUS_TONE[status]
  return (
    <StatusBadge tone={meta.tone} icon={meta.icon}>
      {t(`guarantees.status.${status}`)}
    </StatusBadge>
  )
}

export function Countdown({ g }: { g: Pick<Guarantee, 'expiry_date' | 'days_left' | 'effective_status'> }) {
  const { t } = useTranslation()
  if (!g.expiry_date) return <span>{t('guarantees.noExpiry')}</span>
  const left = g.days_left ?? 0
  return (
    <span>
      {formatDate(g.expiry_date)} (
      {left >= 0 ? t('guarantees.daysLeft', { count: left }) : t('guarantees.expired', { count: -left })})
    </span>
  )
}

interface GuaranteeCardProps {
  g: Guarantee
  /** Shown above the title on the cross-contract list, e.g. "Gói 05 · HĐ 72". */
  context?: string
  onEdit?: () => void
}

export function GuaranteeCard({ g, context, onEdit }: GuaranteeCardProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          {context && <p className="text-sm text-muted-foreground">{context}</p>}
          <p className="font-semibold">{t(`guarantees.types.${g.guarantee_type}`)}</p>
        </div>
        <GuaranteeStatusBadge status={g.effective_status} />
      </div>
      <p className="text-sm">
        {g.bank_name ?? NO_DATA} · {g.amount === null ? NO_DATA : formatMoney(g.amount)}
      </p>
      {g.effective_status !== 'missing' && (
        <p className="text-sm text-muted-foreground">
          {t('guarantees.expiryDate')}: <Countdown g={g} />
        </p>
      )}
      {g.findings.length > 0 && (
        <ul className="space-y-1">
          {g.findings.map((f) => (
            <li key={f.code} className={`text-sm ${f.severity === 'critical' ? 'text-danger' : 'text-warning'}`}>
              {f.severity === 'critical' ? '✕' : '!'} {f.message}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        {!g.verified && g.effective_status !== 'missing' && (
          <StatusBadge tone="info" icon="ℹ">
            {t('guarantees.unverified')}
          </StatusBadge>
        )}
        {g.verify_note && <span>{g.verify_note}</span>}
      </div>
      {onEdit && (
        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={onEdit}>
          {t('guarantees.edit')}
        </button>
      )}
    </div>
  )
}
