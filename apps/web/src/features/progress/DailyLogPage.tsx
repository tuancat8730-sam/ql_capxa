import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useOnline } from '@/components/layout/OfflineBanner'
import { PhotoCapture } from '@/components/ui/PhotoCapture'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import {
  type DailyLogForm,
  enqueue,
  flushOutbox,
  getLastPackage,
  listOutbox,
  loadDraft,
  type OutboxItem,
  type OutboxStatus,
  type PendingPhoto,
  removeFromOutbox,
  resolveConflict,
  retryItem,
  saveDraft,
  setLastPackage,
  subscribe,
} from '@/lib/offline'
import { can } from '@/lib/permissions'
import type { ProgressLog } from './types'

const MAX_PHOTOS = 10
const WEATHERS = ['sunny', 'cloudy', 'rain', 'storm'] as const

const STATUS_TONE: Record<OutboxStatus, { tone: Tone; icon: string }> = {
  pending: { tone: 'neutral', icon: '○' },
  sending: { tone: 'info', icon: '→' },
  sent: { tone: 'success', icon: '✓' },
  error: { tone: 'danger', icon: '✕' },
  conflict: { tone: 'warning', icon: '!' },
}

/** Local calendar date (the site's day), not UTC. */
function today(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const emptyForm = (packageId: string, date: string): DailyLogForm => ({
  package_id: packageId,
  log_date: date,
  progress_pct: 0,
  summary: '',
  issues: '',
  next_steps: '',
  workers: null,
  weather: '',
})

function useOutbox(): OutboxItem[] {
  const [items, setItems] = useState<OutboxItem[]>([])
  useEffect(() => {
    let alive = true
    const load = () => void listOutbox().then((i) => alive && setItems(i))
    load()
    const off = subscribe(load)
    return () => {
      alive = false
      off()
    }
  }, [])
  return items
}

function Thumb({ photo, onRemove, label }: { photo: PendingPhoto; onRemove: () => void; label: string }) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    if (typeof URL.createObjectURL !== 'function') return
    const u = URL.createObjectURL(new Blob([photo.data], { type: photo.type }))
    setUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [photo])
  return (
    <li className="relative size-20 overflow-hidden rounded-md border border-border bg-muted">
      {url ? <img src={url} alt={photo.name} className="size-full object-cover" /> : <span className="p-1 text-xs">{photo.name}</span>}
      <button
        type="button"
        aria-label={`${label}: ${photo.name}`}
        className="absolute right-0 top-0 min-h-8 min-w-8 rounded-bl-md bg-background/90"
        onClick={onRemove}
      >
        ✕
      </button>
    </li>
  )
}

export function DailyLogPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const online = useOnline()
  const canWrite = can(user?.role, 'progress', 'W')
  const outbox = useOutbox()
  const queryClient = useQueryClient()

  // A log that has just reached the server must show in the "recent" list without a reload.
  const sentCount = outbox.filter((i) => i.status === 'sent').length
  useEffect(() => {
    if (sentCount > 0) {
      void queryClient.invalidateQueries({ queryKey: ['progress-logs'] })
      void queryClient.invalidateQueries({ queryKey: ['timeline'] })
    }
  }, [sentCount, queryClient])

  const [packageId, setPackageId] = useState('')
  const [form, setForm] = useState<DailyLogForm>(emptyForm('', today()))
  const [photos, setPhotos] = useState<PendingPhoto[]>([])
  const [draftSaved, setDraftSaved] = useState(false)
  const ready = useRef(false) // set once the draft for the current package/day has been loaded

  const packages = useQuery({
    queryKey: ['packages', 'options'],
    queryFn: () => api.get<Page<{ id: string; number: number }>>('/packages?page_size=100'),
  })
  const recent = useQuery({
    queryKey: ['progress-logs', packageId],
    queryFn: () => api.get<Page<ProgressLog>>(`/packages/${packageId}/progress-logs?page_size=10`),
    enabled: !!packageId && online,
  })

  // start from the package used last time (SPEC 15.5d)
  useEffect(() => {
    void getLastPackage().then((id) => id && setPackageId((cur) => cur || id))
  }, [])

  // load the draft whenever the package or day changes
  useEffect(() => {
    if (!packageId) return
    ready.current = false
    let alive = true
    void loadDraft(packageId, form.log_date).then((draft) => {
      if (!alive) return
      setForm(draft ? draft.form : { ...emptyForm(packageId, form.log_date) })
      setPhotos(draft ? draft.photos : [])
      ready.current = true
    })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [packageId, form.log_date])

  // autosave the draft shortly after the last change
  useEffect(() => {
    if (!ready.current || !packageId) return
    const id = setTimeout(() => {
      void saveDraft({ ...form, package_id: packageId }, photos).then(() => setDraftSaved(true))
    }, 600)
    return () => clearTimeout(id)
  }, [form, photos, packageId])

  const set = <K extends keyof DailyLogForm>(key: K, value: DailyLogForm[K]) => {
    setDraftSaved(false)
    setForm((f) => ({ ...f, [key]: value }))
  }

  const addPhotos = useCallback(async (files: File[]) => {
    const fresh = await Promise.all(
      files.map(
        async (f): Promise<PendingPhoto> => ({
          id: crypto.randomUUID(),
          name: f.name,
          type: f.type || 'image/jpeg',
          data: await f.arrayBuffer(),
        }),
      ),
    )
    setPhotos((cur) => [...cur, ...fresh].slice(0, MAX_PHOTOS))
  }, [])

  const submit = async () => {
    if (!packageId) return
    await setLastPackage(packageId)
    await enqueue({ ...form, package_id: packageId }, photos)
    setForm(emptyForm(packageId, form.log_date))
    setPhotos([])
    setDraftSaved(false)
    void flushOutbox()
  }

  if (!canWrite) {
    return (
      <section className="space-y-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('dailyLog.title')}</h1>
        <p role="alert" className="text-danger">
          {t('auth.forbidden')}
        </p>
      </section>
    )
  }

  const label = (id: string, text: string) => (
    <label htmlFor={id} className="mb-1 block text-sm font-medium">
      {text}
    </label>
  )

  return (
    <section className="space-y-6 pb-24">
      <h1 className="text-xl font-semibold md:text-2xl">{t('dailyLog.title')}</h1>

      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            {label('dl-package', t('dailyLog.package'))}
            <select id="dl-package" className={inputClass} value={packageId} onChange={(e) => {
                setPackageId(e.target.value)
                if (e.target.value) void setLastPackage(e.target.value) // reopen on the same package
              }}
              required
            >
              <option value="">{t('dailyLog.chooseFirst')}</option>
              {packages.data?.items.map((p) => (
                <option key={p.id} value={p.id}>
                  {t('packages.number', { n: String(p.number).padStart(2, '0') })}
                </option>
              ))}
            </select>
          </div>
          <div>
            {label('dl-date', t('dailyLog.date'))}
            <input id="dl-date" type="date" max={today()} className={inputClass} value={form.log_date} onChange={(e) => set('log_date', e.target.value)} required />
          </div>
        </div>

        <div>
          {label('dl-progress', t('dailyLog.progress'))}
          <div className="flex items-center gap-3">
            <input
              id="dl-progress"
              type="range"
              min={0}
              max={100}
              className="min-h-11 flex-1"
              value={form.progress_pct}
              onChange={(e) => set('progress_pct', Number(e.target.value))}
            />
            <input
              aria-label={t('dailyLog.progress')}
              type="number"
              min={0}
              max={100}
              inputMode="numeric"
              className={`${inputClass} !w-20`}
              value={form.progress_pct}
              onChange={(e) => set('progress_pct', Math.min(100, Math.max(0, Number(e.target.value) || 0)))}
            />
          </div>
        </div>

        <div>
          {label('dl-summary', t('dailyLog.summary'))}
          <textarea id="dl-summary" rows={3} className={`${inputClass} py-2`} value={form.summary} onChange={(e) => set('summary', e.target.value)} />
        </div>
        <div>
          {label('dl-issues', t('dailyLog.issues'))}
          <textarea id="dl-issues" rows={2} className={`${inputClass} py-2`} value={form.issues} onChange={(e) => set('issues', e.target.value)} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            {label('dl-workers', t('dailyLog.workers'))}
            <input
              id="dl-workers"
              type="number"
              min={0}
              inputMode="numeric"
              className={inputClass}
              value={form.workers ?? ''}
              onChange={(e) => set('workers', e.target.value === '' ? null : Number(e.target.value))}
            />
          </div>
          <div>
            {label('dl-weather', t('dailyLog.weather'))}
            <select id="dl-weather" className={inputClass} value={form.weather} onChange={(e) => set('weather', e.target.value)}>
              <option value="" />
              {WEATHERS.map((w) => (
                <option key={w} value={t(`dailyLog.weathers.${w}`)}>
                  {t(`dailyLog.weathers.${w}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          {label('dl-next', t('dailyLog.nextSteps'))}
          <textarea id="dl-next" rows={2} className={`${inputClass} py-2`} value={form.next_steps} onChange={(e) => set('next_steps', e.target.value)} />
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">
            {t('dailyLog.photos')} <span className="text-muted-foreground">({photos.length}/{MAX_PHOTOS})</span>
          </p>
          <div className="flex flex-wrap gap-2">
            <PhotoCapture onFiles={(files) => void addPhotos(files)} disabled={photos.length >= MAX_PHOTOS} />
            <label className="inline-flex min-h-11 cursor-pointer items-center rounded-md border border-border px-4">
              {t('dailyLog.addPhotos')}
              <input
                type="file"
                accept="image/*"
                multiple
                hidden
                aria-label={t('dailyLog.addPhotos')}
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? [])
                  e.target.value = ''
                  void addPhotos(files)
                }}
              />
            </label>
          </div>
          {photos.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {photos.map((p) => (
                <Thumb key={p.id} photo={p} label={t('dailyLog.removePhoto')} onRemove={() => setPhotos((cur) => cur.filter((x) => x.id !== p.id))} />
              ))}
            </ul>
          )}
        </div>

        {/* sticky submit bar, thumb-reachable (SPEC 15.4) */}
        <div className="fixed inset-x-0 bottom-14 z-20 border-t border-border bg-background p-3 md:static md:border-0 md:p-0">
          <div className="mx-auto flex max-w-xl items-center gap-3">
            <button type="submit" className={`${primaryButton} flex-1 md:flex-none`} disabled={!packageId}>
              {t('dailyLog.submit')}
            </button>
            {draftSaved && (
              <span role="status" className="text-sm text-muted-foreground">
                {t('dailyLog.draftSaved')}
              </span>
            )}
          </div>
        </div>
      </form>

      {outbox.length > 0 && (
        <section className="space-y-2" aria-label={t('dailyLog.queue')}>
          <h2 className="text-lg font-semibold">{t('dailyLog.queue')}</h2>
          <ul className="space-y-2">
            {outbox.map((item) => {
              const pkg = packages.data?.items.find((p) => p.id === item.form.package_id)
              return (
                <li key={item.client_id} className="space-y-2 rounded-md border border-border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium">
                      {pkg ? t('packages.number', { n: String(pkg.number).padStart(2, '0') }) : ''} · {formatDate(item.form.log_date)} ·{' '}
                      {item.form.progress_pct}%
                      {item.photos.length > 0 && ` · 📷 ${item.photos.length}`}
                    </p>
                    <StatusBadge tone={STATUS_TONE[item.status].tone} icon={STATUS_TONE[item.status].icon}>
                      {t(`dailyLog.status.${item.status}`)}
                    </StatusBadge>
                  </div>
                  {item.status === 'error' && (
                    <div className="space-y-2">
                      <p role="alert" className="text-sm text-danger">
                        {item.error}
                      </p>
                      <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => void retryItem(item.client_id).then(flushOutbox)}>
                        {t('dailyLog.retry')}
                      </button>
                    </div>
                  )}
                  {item.status === 'conflict' && (
                    <div className="space-y-2">
                      <p className="text-sm">{t('dailyLog.conflictHelp')}</p>
                      <div className="flex flex-wrap gap-2">
                        {(['merge', 'overwrite', 'discard'] as const).map((choice) => (
                          <button key={choice} type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => void resolveConflict(item.client_id, choice)}>
                            {t(`dailyLog.${choice}`)}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {item.status === 'sent' && (
                    <button type="button" className="min-h-11 rounded-md border border-border px-3 text-sm" onClick={() => void removeFromOutbox(item.client_id)}>
                      {t('common.close')}
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {packageId && online && (
        <section className="space-y-2" aria-label={t('dailyLog.recent')}>
          <h2 className="text-lg font-semibold">{t('dailyLog.recent')}</h2>
          {recent.data && recent.data.items.length === 0 && <p className="text-muted-foreground">{t('dailyLog.noRecent')}</p>}
          <ul className="space-y-2">
            {recent.data?.items.map((l) => (
              <li key={l.id} className="rounded-md border border-border p-3 text-sm">
                <p className="font-medium">
                  {formatDate(l.log_date)} · {l.progress_pct}%
                  {l.author_name && <span className="font-normal text-muted-foreground"> · {t('dailyLog.by', { name: l.author_name })}</span>}
                </p>
                {l.summary && <p>{l.summary}</p>}
                {l.issues && <p className="text-warning">⚠ {l.issues}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}
