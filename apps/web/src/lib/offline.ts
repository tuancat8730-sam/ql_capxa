/**
 * Offline-first daily log (SPEC 15.7): drafts and an outbox live in IndexedDB.
 *
 * Every queued log carries a client UUID used as the `Idempotency-Key`, so a retry after a flaky
 * connection can never create a second log. Photos are uploaded first (and remembered once done),
 * then the log is posted with the resulting document ids; a crash in between resumes where it left.
 */
import { type DBSchema, type IDBPDatabase, openDB } from 'idb'
import { api, ApiError, getProjectId, request } from './api'
import { UploadError, uploadFile } from './upload'

export interface DailyLogForm {
  package_id: string
  log_date: string
  progress_pct: number
  summary: string
  issues: string
  next_steps: string
  workers: number | null
  weather: string
}

/** Photos are stored as bytes: structured-cloning Blobs is not reliable everywhere. */
export interface PendingPhoto {
  id: string
  name: string
  type: string
  data: ArrayBuffer
  document_id?: string
}

export type OutboxStatus = 'pending' | 'sending' | 'sent' | 'error' | 'conflict'

export interface OutboxItem {
  client_id: string
  form: DailyLogForm
  photos: PendingPhoto[]
  status: OutboxStatus
  error?: string
  /** Set when the server already has a log for that package/day (status `conflict`). */
  existing_id?: string
  attempts: number
  created_at: number
  /** Project the log belongs to; it is sent to that one even after the user switches. */
  project_id?: string
}

export interface Draft {
  key: string
  form: DailyLogForm
  photos: PendingPhoto[]
  saved_at: number
}

interface QldaDb extends DBSchema {
  drafts: { key: string; value: Draft }
  outbox: { key: string; value: OutboxItem }
  meta: { key: string; value: string }
}

let dbPromise: Promise<IDBPDatabase<QldaDb>> | null = null

function db(): Promise<IDBPDatabase<QldaDb>> {
  dbPromise ??= openDB<QldaDb>('qlda', 1, {
    upgrade(database) {
      database.createObjectStore('drafts', { keyPath: 'key' })
      database.createObjectStore('outbox', { keyPath: 'client_id' })
      database.createObjectStore('meta')
    },
  })
  return dbPromise
}

/** Test helper: forget the cached connection and wipe every store. */
export async function resetOfflineStore(): Promise<void> {
  const database = await db()
  await Promise.all([database.clear('drafts'), database.clear('outbox'), database.clear('meta')])
  listeners.clear()
  flushing = false
}

// --- change notifications -----------------------------------------------------------------------

const listeners = new Set<() => void>()

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function emit() {
  for (const l of listeners) l()
}

// --- drafts ---------------------------------------------------------------------------------

export const draftKey = (packageId: string, date: string) => `${packageId}|${date}`

export async function saveDraft(form: DailyLogForm, photos: PendingPhoto[]): Promise<void> {
  await (await db()).put('drafts', {
    key: draftKey(form.package_id, form.log_date),
    form,
    photos,
    saved_at: Date.now(),
  })
}

export async function loadDraft(packageId: string, date: string): Promise<Draft | undefined> {
  return (await db()).get('drafts', draftKey(packageId, date))
}

export async function deleteDraft(packageId: string, date: string): Promise<void> {
  await (await db()).delete('drafts', draftKey(packageId, date))
}

export async function getLastPackage(): Promise<string | undefined> {
  return (await db()).get('meta', 'last_package')
}

export async function setLastPackage(id: string): Promise<void> {
  await (await db()).put('meta', id, 'last_package')
}

// --- outbox ---------------------------------------------------------------------------------

export async function listOutbox(): Promise<OutboxItem[]> {
  const items = await (await db()).getAll('outbox')
  return items.sort((a, b) => a.created_at - b.created_at)
}

async function put(item: OutboxItem): Promise<void> {
  await (await db()).put('outbox', item)
  emit()
}

export async function removeFromOutbox(clientId: string): Promise<void> {
  await (await db()).delete('outbox', clientId)
  emit()
}

export async function enqueue(form: DailyLogForm, photos: PendingPhoto[]): Promise<OutboxItem> {
  const item: OutboxItem = {
    client_id: crypto.randomUUID(),
    form,
    photos,
    status: 'pending',
    attempts: 0,
    created_at: Date.now(),
    project_id: getProjectId() ?? undefined,
  }
  await put(item)
  await deleteDraft(form.package_id, form.log_date)
  return item
}

/** Retry an item that ended in `error`. */
export async function retryItem(clientId: string): Promise<void> {
  const item = await (await db()).get('outbox', clientId)
  if (item && item.status === 'error') await put({ ...item, status: 'pending', error: undefined })
}

// --- sending --------------------------------------------------------------------------------

function isNetworkFailure(err: unknown): boolean {
  if (err instanceof UploadError) return err.status === 0 || err.status >= 500
  return err instanceof TypeError // fetch rejects with TypeError when offline
}

async function uploadPhoto(item: OutboxItem, photo: PendingPhoto): Promise<string> {
  const file = new File([photo.data], photo.name, { type: photo.type })
  const ref = await uploadFile(file, { packageId: item.form.package_id, projectId: item.project_id })
  try {
    const doc = await api.post<{ id: string }>(
      '/documents',
      {
        ...ref,
        package_id: item.form.package_id,
        doc_type: 'photo',
        title: `Ảnh nhật ký ${item.form.log_date}`,
      },
      pinned(item),
    )
    return doc.id
  } catch (err) {
    // The same bytes were already stored (e.g. we crashed after confirming): reuse that document.
    if (err instanceof ApiError && err.code === 'duplicate_document') {
      return (err.details as { document_id: string }).document_id
    }
    throw err
  }
}

/** Request options that keep a queued item on its own project. */
function pinned(item: OutboxItem): { headers?: Record<string, string> } {
  return item.project_id ? { headers: { 'X-Project-Id': item.project_id } } : {}
}

function logBody(item: OutboxItem, attachments: string[]) {
  const f = item.form
  return {
    log_date: f.log_date,
    progress_pct: f.progress_pct,
    summary: f.summary || null,
    issues: f.issues || null,
    next_steps: f.next_steps || null,
    workers: f.workers,
    weather: f.weather || null,
    attachments,
    client_id: item.client_id,
  }
}

async function send(item: OutboxItem): Promise<void> {
  let current: OutboxItem = { ...item, status: 'sending', error: undefined, attempts: item.attempts + 1 }
  await put(current)
  try {
    const photos = [...current.photos]
    for (let i = 0; i < photos.length; i++) {
      if (photos[i].document_id) continue
      photos[i] = { ...photos[i], document_id: await uploadPhoto(current, photos[i]) }
      current = { ...current, photos }
      await put(current) // remember progress so a retry does not upload twice
    }
    const attachments = photos.map((p) => p.document_id!)
    await request('POST', `/packages/${current.form.package_id}/progress-logs`, logBody(current, attachments), {
      headers: { 'Idempotency-Key': current.client_id, ...pinned(current).headers },
    })
    await put({ ...current, status: 'sent' })
  } catch (err) {
    if (err instanceof ApiError && err.code === 'log_exists') {
      const existing = (err.details as { id: string } | undefined)?.id
      await put({ ...current, status: 'conflict', existing_id: existing })
    } else if (isNetworkFailure(err) || (err instanceof ApiError && err.status === 401)) {
      await put({ ...current, status: 'pending' }) // try again when the connection is back
    } else {
      await put({ ...current, status: 'error', error: err instanceof Error ? err.message : String(err) })
    }
  }
}

let flushing = false

/** Send everything that is waiting; safe to call from several places at once. */
export async function flushOutbox(): Promise<void> {
  if (flushing || (typeof navigator !== 'undefined' && navigator.onLine === false)) return
  flushing = true
  try {
    for (const item of await listOutbox()) {
      if (item.status === 'pending' || item.status === 'sending') await send(item)
    }
  } finally {
    flushing = false
  }
}

/** Resolve a "log already exists for that day" conflict (SPEC 15.7). */
export async function resolveConflict(clientId: string, choice: 'overwrite' | 'merge' | 'discard'): Promise<void> {
  const item = await (await db()).get('outbox', clientId)
  if (!item) return
  if (choice === 'discard' || !item.existing_id) {
    await removeFromOutbox(clientId)
    return
  }
  const attachments = item.photos.map((p) => p.document_id).filter((d): d is string => !!d)
  const f = item.form
  let body: Record<string, unknown> = {
    progress_pct: f.progress_pct,
    summary: f.summary || null,
    issues: f.issues || null,
    next_steps: f.next_steps || null,
    workers: f.workers,
    weather: f.weather || null,
  }
  if (choice === 'merge') {
    const old = await request<{ summary: string | null; issues: string | null; next_steps: string | null; attachments: string[] }>(
      'GET',
      `/progress-logs/${item.existing_id}`,
      undefined,
      pinned(item),
    )
    const join = (a: string | null, b: string) => [a, b].filter(Boolean).join('\n')
    body = {
      ...body,
      summary: join(old.summary, f.summary) || null,
      issues: join(old.issues, f.issues) || null,
      next_steps: join(old.next_steps, f.next_steps) || null,
    }
    body.attachments = [...old.attachments, ...attachments]
  } else {
    body.attachments = attachments
  }
  try {
    await request('PATCH', `/progress-logs/${item.existing_id}`, body, pinned(item))
    await put({ ...item, status: 'sent', existing_id: undefined })
  } catch (err) {
    if (isNetworkFailure(err)) return // stays in conflict; the user can try again
    await put({ ...item, status: 'error', error: err instanceof Error ? err.message : String(err) })
  }
}

/** Sync on start, whenever the connection returns, and every 30 s while something is waiting. */
export function startAutoSync(): () => void {
  const run = () => void flushOutbox()
  window.addEventListener('online', run)
  const timer = window.setInterval(async () => {
    if ((await listOutbox()).some((i) => i.status === 'pending')) run()
  }, 30_000)
  run()
  return () => {
    window.removeEventListener('online', run)
    window.clearInterval(timer)
  }
}
