import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useRole } from '@/features/projects/ProjectContext'
import { can } from '@/lib/permissions'
import { useLogWeeks } from './logQueries'
import type { LogWeek } from './logTypes'
import { dm, dmy } from './meta'

const linkClass = 'inline-flex min-h-11 items-center rounded-md border border-border px-3'

function LogBadge({ week }: { week: LogWeek }) {
  const { t } = useTranslation()
  return week.has_log ? (
    <StatusBadge tone="success" icon="✓">
      {t('delivery.log.has')}
    </StatusBadge>
  ) : (
    <StatusBadge tone="neutral" icon="○">
      {t('delivery.log.none')}
    </StatusBadge>
  )
}

/** The contractor's weekly construction log: one row per reporting week. */
export function ConstructionLogPage() {
  const { t } = useTranslation()
  const role = useRole()
  const weeks = useLogWeeks()

  if (weeks.isPending) return <p role="status">{t('common.loading')}</p>
  if (weeks.isError || !weeks.data) {
    return (
      <div role="alert" className="space-y-2">
        <p className="text-danger">{t('common.error')}</p>
        <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void weeks.refetch()}>
          {t('common.retry')}
        </button>
      </div>
    )
  }

  const canWrite = can(role, 'construction_log', 'W')
  const action = (w: LogWeek) =>
    w.has_log || canWrite ? (
      <Link to={`/construction-log/${w.week_start}`} className={linkClass}>
        {w.has_log ? t('delivery.log.open') : t('delivery.log.create')}
      </Link>
    ) : null
  const written = weeks.data.filter((w) => w.has_log).length

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold md:text-2xl">{t('delivery.log.title')}</h1>
        <p className="text-sm text-muted-foreground">{t('delivery.log.subtitle')}</p>
      </div>
      <p className="text-sm">
        <span className="rounded-full border border-success px-2 text-success">
          {t('delivery.log.count', { got: written, total: weeks.data.length })}
        </span>
      </p>
      <ResponsiveList
        rows={weeks.data}
        rowKey={(w) => w.week_start}
        caption={t('delivery.log.title')}
        columns={[
          { key: 'no', header: t('delivery.reports.period'), cell: (w) => `${w.no} · ${dm(w.week_start)} – ${dm(w.week_end)}` },
          { key: 'state', header: t('delivery.reports.state'), cell: (w) => <LogBadge week={w} /> },
          { key: 'on', header: t('delivery.log.reportDate'), cell: (w) => dmy(w.report_date), secondary: true },
          { key: 'n', header: t('delivery.log.entries'), cell: (w) => (w.has_log ? w.entry_count : '—'), secondary: true },
          {
            key: 'delay',
            header: t('delivery.log.maxDelay'),
            cell: (w) => (w.max_delay_days > 0 ? t('delivery.log.delay', { n: w.max_delay_days }) : '—'),
          },
          { key: 'act', header: '', cell: action },
        ]}
        renderCard={(w) => (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <p className="font-medium">
                {t('delivery.report.title', { no: w.no })} · {dm(w.week_start)} – {dm(w.week_end)}
              </p>
              <LogBadge week={w} />
            </div>
            {w.has_log && (
              <p className="text-sm text-muted-foreground">
                {t('delivery.log.entriesCount', { n: w.entry_count })}
                {w.max_delay_days > 0 && ` · ${t('delivery.log.delay', { n: w.max_delay_days })}`}
              </p>
            )}
            {action(w)}
          </div>
        )}
      />
    </section>
  )
}
