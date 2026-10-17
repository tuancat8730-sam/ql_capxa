import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useTaskLogHistory } from './logQueries'
import { DelayBadge, EntryStateBadge, storedCode } from './logMeta'
import { dm } from './meta'
import type { Task } from './types'

const SHOWN = 8

/** What the contractor's construction log said about one task, newest first. Silent when nothing was written. */
export function TaskLogHistory({ task }: { task: Task }) {
  const { t } = useTranslation()
  const history = useTaskLogHistory(storedCode(task))
  if (!history.data || history.data.length === 0) return null

  const rows = [...history.data].reverse().slice(0, SHOWN)
  return (
    <section className="mt-6 space-y-2 border-t border-border pt-4" aria-label={t('delivery.log.history.title')}>
      <h3 className="font-medium">{t('delivery.log.history.title')}</h3>
      <ul className="space-y-2">
        {rows.map((h, i) => (
          <li key={`${h.entry_date}-${i}`} className="space-y-1 rounded-md border border-border p-2 text-sm">
            <p className="flex flex-wrap items-center gap-2">
              <Link to={`/construction-log/${h.week_start}`} className="font-medium text-primary">
                {dm(h.entry_date)}
              </Link>
              {h.state && <EntryStateBadge state={h.state} />}
              {h.delay_days != null && h.delay_days > 0 && <DelayBadge days={h.delay_days} />}
            </p>
            <p className="line-clamp-3 whitespace-pre-line break-words">{h.content}</p>
            {h.note && <p className="whitespace-pre-line break-words text-muted-foreground">{h.note}</p>}
          </li>
        ))}
      </ul>
      {history.data.length > SHOWN && (
        <p className="text-xs text-muted-foreground">{t('delivery.log.history.more', { n: history.data.length - SHOWN })}</p>
      )}
    </section>
  )
}
