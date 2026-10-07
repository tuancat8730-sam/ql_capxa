import { useTranslation } from 'react-i18next'
import type { Finding } from './types'

/** Things in the plan that do not add up: shown, never blocking (the document is the contractor's). */
export function FindingsList({ findings }: { findings: Finding[] }) {
  const { t } = useTranslation()
  if (findings.length === 0) return null
  return (
    <section aria-label={t('plan.findings')} className="space-y-1 rounded-md border border-warning p-3">
      <h4 className="font-semibold text-warning">⚠ {t('plan.findings')}</h4>
      <ul className="space-y-1 text-sm">
        {findings.map((f, i) => (
          <li key={`${f.code}-${i}`}>
            <span aria-hidden>{f.severity === 'warning' ? '! ' : 'i '}</span>
            {f.message}
          </li>
        ))}
      </ul>
    </section>
  )
}
