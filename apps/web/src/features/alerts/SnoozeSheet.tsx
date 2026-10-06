import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { type Alert, MAX_SNOOZE_DAYS } from './types'

interface SnoozeSheetProps {
  alert: Alert
  busy: boolean
  error: string | null
  onSubmit: (days: number, reason: string) => void
  onClose: () => void
}

export function SnoozeSheet({ alert, busy, error, onSubmit, onClose }: SnoozeSheetProps) {
  const { t } = useTranslation()
  const [days, setDays] = useState(1)
  const [reason, setReason] = useState('')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (reason.trim()) onSubmit(days, reason.trim())
  }

  return (
    <BottomSheet title={t('alerts.snoozeTitle')} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-muted-foreground">{alert.title}</p>
        <label className="block space-y-1">
          <span className="text-sm">{t('alerts.snoozeDays')}</span>
          <input
            type="number"
            min={1}
            max={MAX_SNOOZE_DAYS}
            value={days}
            onChange={(e) => setDays(Math.min(MAX_SNOOZE_DAYS, Math.max(1, Number(e.target.value) || 1)))}
            className={inputClass}
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm">{t('alerts.snoozeReason')}</span>
          <textarea required value={reason} onChange={(e) => setReason(e.target.value)} className={inputClass} rows={3} />
        </label>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex gap-2">
          <button type="submit" disabled={busy || !reason.trim()} className={primaryButton}>
            {t('alerts.snooze')}
          </button>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={onClose}>
            {t('common.cancel')}
          </button>
        </div>
      </form>
    </BottomSheet>
  )
}
