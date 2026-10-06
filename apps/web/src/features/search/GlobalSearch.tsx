import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { hitLink, type SearchResult } from './types'

const MIN_LENGTH = 2
const DEBOUNCE_MS = 250

/** Search button in the top bar (Ctrl+K) opening a full-screen search over all record kinds. */
export function GlobalSearch() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (open) input.current?.focus()
  }, [open])

  useEffect(() => {
    const id = setTimeout(() => setQuery(text.trim()), DEBOUNCE_MS)
    return () => clearTimeout(id)
  }, [text])

  const enabled = open && query.length >= MIN_LENGTH
  const { data, isFetching, isError } = useQuery({
    queryKey: ['search', query],
    queryFn: () => api.get<SearchResult>(`/search?${new URLSearchParams({ q: query, limit: '5' })}`),
    enabled,
  })

  const close = () => setOpen(false)
  return (
    <>
      <button
        type="button"
        aria-label={t('search.open')}
        onClick={() => setOpen(true)}
        className="flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-md border border-border px-3 text-sm text-muted-foreground"
      >
        <Search size={18} aria-hidden />
        <span className="hidden sm:inline">{t('search.open')}</span>
        <kbd className="hidden rounded border border-border px-1 text-xs lg:inline">Ctrl K</kbd>
      </button>

      {open && (
        <div role="dialog" aria-modal="true" aria-label={t('search.open')} className="fixed inset-0 z-50 bg-background">
          <div className="mx-auto flex h-full max-w-2xl flex-col gap-3 p-4">
            <div className="flex gap-2">
              <input
                ref={input}
                type="search"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={t('search.placeholder')}
                aria-label={t('search.placeholder')}
                className="min-h-11 flex-1 rounded-md border border-border bg-background px-3"
              />
              <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={close}>
                {t('common.close')}
              </button>
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto pb-8">
              {!enabled && <p className="text-sm text-muted-foreground">{t('search.hint')}</p>}
              {enabled && isFetching && !data && <p role="status">{t('common.loading')}</p>}
              {isError && (
                <p role="alert" className="text-danger">
                  {t('common.error')}
                </p>
              )}
              {enabled && data && data.groups.length === 0 && <p className="text-muted-foreground">{t('search.none')}</p>}
              {enabled &&
                data?.groups.map((g) => (
                  <section key={g.kind} aria-label={t(`search.kinds.${g.kind}`)} className="space-y-1">
                    <h2 className="text-sm font-semibold text-muted-foreground">
                      {t(`search.kinds.${g.kind}`)} ({g.total})
                    </h2>
                    <ul className="space-y-1">
                      {g.items.map((h) => (
                        <li key={h.id}>
                          <Link to={hitLink(h)} onClick={close} className="block rounded-md border border-border p-2">
                            <span className="font-medium">{h.title}</span>
                            {h.subtitle && <span className="text-sm text-muted-foreground"> · {h.subtitle}</span>}
                            {h.snippet && <p className="text-sm text-muted-foreground">{h.snippet}</p>}
                          </Link>
                        </li>
                      ))}
                    </ul>
                    {g.total > g.items.length && (
                      <p className="text-xs text-muted-foreground">{t('search.more', { n: g.total - g.items.length })}</p>
                    )}
                  </section>
                ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
