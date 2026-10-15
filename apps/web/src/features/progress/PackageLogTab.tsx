import { useInfiniteQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { primaryButton } from '@/features/auth/LoginPage'
import { useRole } from '@/features/projects/ProjectContext'
import { api, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'
import type { ProgressLog } from './types'

const PAGE_SIZE = 10

function Line({ label, children, tone }: { label: string; children: string; tone?: string }) {
  return (
    <div>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={`whitespace-pre-line break-words ${tone ?? ''}`}>{children}</dd>
    </div>
  )
}

/** The site diary of one package (SPEC 4.3 tab 8): every entry, newest first. */
export function PackageLogTab({ packageId }: { packageId: string }) {
  const { t } = useTranslation()
  const role = useRole()
  const canWrite = can(role, 'progress', 'W')
  const logs = useInfiniteQuery({
    queryKey: ['progress-logs', packageId, 'all'],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      api.get<Page<ProgressLog>>(`/packages/${packageId}/progress-logs?page=${pageParam}&page_size=${PAGE_SIZE}`),
    getNextPageParam: (last, pages) =>
      pages.reduce((n, p) => n + p.items.length, 0) < last.total ? pages.length + 1 : undefined,
  })
  const items = logs.data?.pages.flatMap((p) => p.items) ?? []
  const total = logs.data?.pages[0]?.total ?? 0

  return (
    <section className="space-y-3" aria-label={t('packages.log.title')}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">
          {t('packages.log.title')}
          {total > 0 && <span className="font-normal text-muted-foreground"> ({total})</span>}
        </h2>
        {canWrite && (
          <Link to={`/daily-log?package=${packageId}`} className={primaryButton}>
            {t('packages.log.add')}
          </Link>
        )}
      </div>
      {logs.isPending && <p className="text-muted-foreground">{t('common.loading')}</p>}
      {logs.isError && <p role="alert" className="text-danger">{t('common.error')}</p>}
      {logs.isSuccess && items.length === 0 && <p className="text-muted-foreground">{t('dailyLog.noRecent')}</p>}
      <ul className="space-y-3">
        {items.map((l) => (
          <li key={l.id} className="space-y-2 rounded-md border border-border p-3">
            <p className="font-medium">
              {formatDate(l.log_date)} · {l.progress_pct}%
              {l.author_name && (
                <span className="font-normal text-muted-foreground"> · {t('dailyLog.by', { name: l.author_name })}</span>
              )}
            </p>
            <dl className="space-y-2">
              {l.summary && <Line label={t('dailyLog.summary')}>{l.summary}</Line>}
              {l.issues && (
                <Line label={t('dailyLog.issues')} tone="text-warning">
                  {l.issues}
                </Line>
              )}
              {l.next_steps && <Line label={t('dailyLog.nextSteps')}>{l.next_steps}</Line>}
              {l.workers !== null && <Line label={t('dailyLog.workers')}>{String(l.workers)}</Line>}
              {l.weather && <Line label={t('dailyLog.weather')}>{l.weather}</Line>}
            </dl>
            {l.attachments.length > 0 && (
              <p className="text-sm text-muted-foreground">{t('packages.log.photos', { count: l.attachments.length })}</p>
            )}
          </li>
        ))}
      </ul>
      {logs.hasNextPage && (
        <button
          type="button"
          className="min-h-11 rounded-md border border-border px-4"
          disabled={logs.isFetchingNextPage}
          onClick={() => void logs.fetchNextPage()}
        >
          {t('packages.log.more')}
        </button>
      )}
    </section>
  )
}
