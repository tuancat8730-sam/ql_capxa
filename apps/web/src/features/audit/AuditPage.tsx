import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { inputClass } from '@/features/auth/LoginPage'
import { api, type Page } from '@/lib/api'
import { formatDateTime } from '@/lib/format'

interface AuditRow {
  id: string
  ts: string
  user_id: string | null
  user_name: string | null
  action: string
  entity_type: string
  entity_id: string | null
  changes: Record<string, unknown> | null
  ip: string | null
}

interface Facets {
  actions: string[]
  entity_types: string[]
  users: { id: string; name: string }[]
}

const PAGE_SIZE = 20
// The API compares timestamps, so a picked day becomes a whole Vietnamese day (UTC+7).
const dayStart = (d: string) => `${d}T00:00:00+07:00`
const dayEnd = (d: string) => `${d}T23:59:59+07:00`

/** Who changed what and when (SPEC 4.14, 4.18); admins and the director only. */
export function AuditPage() {
  const { t } = useTranslation()
  const [action, setAction] = useState('')
  const [entity, setEntity] = useState('')
  const [userId, setUserId] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [page, setPage] = useState(1)

  const facets = useQuery({ queryKey: ['audit-facets'], queryFn: () => api.get<Facets>('/audit-log/facets') })
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['audit', { action, entity, userId, from, to, page }],
    queryFn: () => {
      const p = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
      if (action) p.set('action', action)
      if (entity) p.set('entity_type', entity)
      if (userId) p.set('user_id', userId)
      if (from) p.set('ts_from', dayStart(from))
      if (to) p.set('ts_to', dayEnd(to))
      return api.get<Page<AuditRow>>(`/audit-log?${p}`)
    },
  })

  // changing a filter always goes back to the first page
  const filter = (set: (v: string) => void) => (v: string) => {
    set(v)
    setPage(1)
  }
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const actionLabel = (a: string) => (['create', 'update', 'delete', 'login', 'download', 'export'].includes(a) ? t(`audit.actions.${a}`) : a)

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold md:text-2xl">{t('audit.title')}</h1>

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <label className="space-y-1 text-sm">
          <span>{t('audit.action')}</span>
          <select className={inputClass} value={action} onChange={(e) => filter(setAction)(e.target.value)}>
            <option value="">{t('audit.all')}</option>
            {facets.data?.actions.map((a) => (
              <option key={a} value={a}>
                {actionLabel(a)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span>{t('audit.entity')}</span>
          <select className={inputClass} value={entity} onChange={(e) => filter(setEntity)(e.target.value)}>
            <option value="">{t('audit.all')}</option>
            {facets.data?.entity_types.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span>{t('audit.user')}</span>
          <select className={inputClass} value={userId} onChange={(e) => filter(setUserId)(e.target.value)}>
            <option value="">{t('audit.all')}</option>
            {facets.data?.users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span>{t('audit.from')}</span>
          <input type="date" className={inputClass} value={from} onChange={(e) => filter(setFrom)(e.target.value)} />
        </label>
        <label className="space-y-1 text-sm">
          <span>{t('audit.to')}</span>
          <input type="date" className={inputClass} value={to} onChange={(e) => filter(setTo)(e.target.value)} />
        </label>
      </div>

      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('audit.none')}</p>}
      {data && data.items.length > 0 && <p className="text-sm text-muted-foreground">{t('audit.total', { n: data.total })}</p>}

      <ul className="space-y-2">
        {data?.items.map((r) => (
          <li key={r.id} className="space-y-1 rounded-md border border-border p-3 text-sm">
            <p className="flex flex-wrap items-center gap-x-3">
              <time dateTime={r.ts} className="font-medium">
                {formatDateTime(r.ts)}
              </time>
              <span>{r.user_name ?? t('audit.system')}</span>
              <span className="rounded-full border border-border px-2 text-xs">{actionLabel(r.action)}</span>
              <span className="text-muted-foreground">
                {r.entity_type}
                {r.entity_id && ` · ${r.entity_id.slice(0, 8)}`}
              </span>
            </p>
            {r.changes && Object.keys(r.changes).length > 0 && (
              <details>
                <summary className="min-h-11 cursor-pointer py-2">{t('audit.details')}</summary>
                <pre className="overflow-x-auto rounded-md bg-muted p-2 text-xs">{JSON.stringify(r.changes, null, 2)}</pre>
              </details>
            )}
          </li>
        ))}
      </ul>

      {data && pages > 1 && (
        <nav className="flex items-center justify-between gap-2" aria-label={t('audit.title')}>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            {t('audit.prev')}
          </button>
          <span className="text-sm">{t('audit.page', { page, pages })}</span>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            {t('audit.next')}
          </button>
        </nav>
      )}
    </section>
  )
}
