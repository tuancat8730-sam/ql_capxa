import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setAccessToken } from './api'
import {
  deleteDraft,
  type DailyLogForm,
  enqueue,
  flushOutbox,
  getLastPackage,
  listOutbox,
  loadDraft,
  type PendingPhoto,
  removeFromOutbox,
  resetOfflineStore,
  resolveConflict,
  retryItem,
  saveDraft,
  setLastPackage,
  subscribe,
} from './offline'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const form = (over: Partial<DailyLogForm> = {}): DailyLogForm => ({
  package_id: 'p4',
  log_date: '2026-10-05',
  progress_pct: 35,
  summary: 'Lắp 3 xã',
  issues: '',
  next_steps: 'Lắp tiếp',
  workers: 12,
  weather: 'Nắng',
  ...over,
})

const photo = (id = 'ph1'): PendingPhoto => ({ id, name: `${id}.jpg`, type: 'image/jpeg', data: new Uint8Array([1, 2, 3]).buffer })

class FakeXhr {
  static puts: string[] = []
  static status = 200
  status = 0
  url = ''
  upload = { onprogress: null as null | (() => void) }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  open(_m: string, url: string) {
    this.url = url
  }
  setRequestHeader() {}
  send() {
    FakeXhr.puts.push(this.url)
    queueMicrotask(() => {
      this.status = FakeXhr.status
      this.onload?.()
    })
  }
}

describe('offline store', () => {
  const fetchMock = vi.fn()
  const calls = () => fetchMock.mock.calls.map(([u, i]) => `${i?.method ?? 'GET'} ${u}`)
  const bodyOf = (match: string) => {
    const call = fetchMock.mock.calls.find(([u, i]) => `${i?.method ?? 'GET'} ${u}` === match)!
    return JSON.parse(call[1].body)
  }

  beforeEach(async () => {
    await resetOfflineStore()
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    FakeXhr.puts = []
    FakeXhr.status = 200
    setAccessToken('t')
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    setAccessToken(null)
  })

  const okLog = () => res(201, { id: 'log1' })

  it('drafts round-trip per package and day and are removed on demand', async () => {
    await saveDraft(form(), [photo()])
    const draft = await loadDraft('p4', '2026-10-05')
    expect(draft?.form.summary).toBe('Lắp 3 xã')
    expect(draft?.photos[0].data.byteLength).toBe(3)
    expect(await loadDraft('p4', '2026-10-06')).toBeUndefined()
    await deleteDraft('p4', '2026-10-05')
    expect(await loadDraft('p4', '2026-10-05')).toBeUndefined()
  })

  it('remembers the last package', async () => {
    expect(await getLastPackage()).toBeUndefined()
    await setLastPackage('p6')
    expect(await getLastPackage()).toBe('p6')
  })

  it('enqueue clears the draft, notifies subscribers and starts as pending', async () => {
    await saveDraft(form(), [])
    const seen = vi.fn()
    const off = subscribe(seen)
    const item = await enqueue(form(), [])
    off()
    expect(item.status).toBe('pending')
    expect(item.client_id).toMatch(/^[0-9a-f-]{36}$/)
    expect(seen).toHaveBeenCalled()
    expect(await loadDraft('p4', '2026-10-05')).toBeUndefined()
    expect((await listOutbox()).map((i) => i.status)).toEqual(['pending'])
  })

  it('sends the log with its client id as Idempotency-Key and marks it sent', async () => {
    fetchMock.mockResolvedValueOnce(okLog())
    const item = await enqueue(form(), [])
    await flushOutbox()
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['Idempotency-Key']).toBe(item.client_id)
    expect(bodyOf('POST /api/v1/packages/p4/progress-logs')).toMatchObject({
      log_date: '2026-10-05',
      progress_pct: 35,
      workers: 12,
      attachments: [],
      client_id: item.client_id,
    })
    expect((await listOutbox())[0].status).toBe('sent')
  })

  it('uploads photos first, then posts the log with their document ids', async () => {
    fetchMock
      .mockResolvedValueOnce(res(200, { document_id: 'doc1', file_key: 'k1', version: 1, upload: { url: 'https://s3.test/1', method: 'PUT', headers: {} }, expires_in: 600, max_bytes: 1 }))
      .mockResolvedValueOnce(res(201, { id: 'doc1' }))
      .mockResolvedValueOnce(okLog())
    await enqueue(form(), [photo()])
    await flushOutbox()
    expect(calls()).toEqual(['POST /api/v1/documents/upload-url', 'POST /api/v1/documents', 'POST /api/v1/packages/p4/progress-logs'])
    expect(FakeXhr.puts).toEqual(['https://s3.test/1'])
    expect(bodyOf('POST /api/v1/documents')).toMatchObject({ doc_type: 'photo', package_id: 'p4', document_id: 'doc1' })
    expect(bodyOf('POST /api/v1/packages/p4/progress-logs').attachments).toEqual(['doc1'])
  })

  it('stays pending when the connection drops and resumes without re-uploading photos', async () => {
    fetchMock
      .mockResolvedValueOnce(res(200, { document_id: 'doc1', file_key: 'k1', version: 1, upload: { url: 'https://s3.test/1', method: 'PUT', headers: {} }, expires_in: 600, max_bytes: 1 }))
      .mockResolvedValueOnce(res(201, { id: 'doc1' }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch')) // the log POST fails
    await enqueue(form(), [photo()])
    await flushOutbox()
    let [item] = await listOutbox()
    expect(item.status).toBe('pending')
    expect(item.attempts).toBe(1)
    expect(item.photos[0].document_id).toBe('doc1') // remembered

    fetchMock.mockResolvedValueOnce(okLog())
    await flushOutbox()
    ;[item] = await listOutbox()
    expect(item.status).toBe('sent')
    expect(calls().filter((c) => c.includes('upload-url'))).toHaveLength(1) // no second upload
    expect(FakeXhr.puts).toHaveLength(1)
  })

  it('reuses the existing document when the same photo was already confirmed', async () => {
    fetchMock
      .mockResolvedValueOnce(res(200, { document_id: 'doc2', file_key: 'k2', version: 1, upload: { url: 'https://s3.test/2', method: 'PUT', headers: {} }, expires_in: 600, max_bytes: 1 }))
      .mockResolvedValueOnce(res(409, { error: { code: 'duplicate_document', message: 'dup', details: { document_id: 'old-doc', title: 'x' } } }))
      .mockResolvedValueOnce(okLog())
    await enqueue(form(), [photo()])
    await flushOutbox()
    expect(bodyOf('POST /api/v1/packages/p4/progress-logs').attachments).toEqual(['old-doc'])
    expect((await listOutbox())[0].status).toBe('sent')
  })

  it('does nothing while offline and sends once back online', async () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
    await enqueue(form(), [])
    await flushOutbox()
    expect(fetchMock).not.toHaveBeenCalled()
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
    fetchMock.mockResolvedValueOnce(okLog())
    await flushOutbox()
    expect((await listOutbox())[0].status).toBe('sent')
  })

  it('does not run two flushes at once', async () => {
    let release!: () => void
    fetchMock.mockImplementationOnce(() => new Promise<Response>((r) => (release = () => r(okLog()))))
    await enqueue(form(), [])
    const first = flushOutbox()
    await new Promise((r) => setTimeout(r, 20))
    await flushOutbox() // ignored: one is already running
    release()
    await first
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('validation errors become "error" and can be retried', async () => {
    fetchMock.mockResolvedValueOnce(res(422, { error: { code: 'validation_error', message: 'Tiến độ không hợp lệ' } }))
    const { client_id } = await enqueue(form(), [])
    await flushOutbox()
    let [item] = await listOutbox()
    expect(item.status).toBe('error')
    expect(item.error).toBe('Tiến độ không hợp lệ')
    await flushOutbox()
    expect(fetchMock).toHaveBeenCalledTimes(1) // errors are not retried automatically
    await retryItem(client_id)
    fetchMock.mockResolvedValueOnce(okLog())
    await flushOutbox()
    ;[item] = await listOutbox()
    expect(item.status).toBe('sent')
  })

  it('an existing log for the same day becomes a conflict the user can resolve', async () => {
    fetchMock.mockResolvedValueOnce(res(409, { error: { code: 'log_exists', message: 'đã có', details: { id: 'log0' } } }))
    const { client_id } = await enqueue(form({ summary: 'Bản mới', issues: 'Mất điện' }), [])
    await flushOutbox()
    expect((await listOutbox())[0]).toMatchObject({ status: 'conflict', existing_id: 'log0' })

    fetchMock.mockResolvedValueOnce(res(200, { id: 'log0' }))
    await resolveConflict(client_id, 'overwrite')
    const patch = fetchMock.mock.calls.at(-1)!
    expect(patch[0]).toBe('/api/v1/progress-logs/log0')
    expect(JSON.parse(patch[1].body)).toMatchObject({ summary: 'Bản mới', issues: 'Mất điện', progress_pct: 35, attachments: [] })
    expect((await listOutbox())[0].status).toBe('sent')
  })

  it('merging appends the new text to the existing log instead of replacing it', async () => {
    fetchMock.mockResolvedValueOnce(res(409, { error: { code: 'log_exists', message: 'đã có', details: { id: 'log0' } } }))
    const { client_id } = await enqueue(form({ summary: 'Chiều: lắp thêm' }), [])
    await flushOutbox()
    fetchMock
      .mockResolvedValueOnce(res(200, { summary: 'Sáng: lắp 3 xã', issues: null, next_steps: null, attachments: ['a1'] }))
      .mockResolvedValueOnce(res(200, { id: 'log0' }))
    await resolveConflict(client_id, 'merge')
    const patch = fetchMock.mock.calls.at(-1)!
    const body = JSON.parse(patch[1].body)
    expect(body.summary).toBe('Sáng: lắp 3 xã\nChiều: lắp thêm')
    expect(body.attachments).toEqual(['a1'])
  })

  it('discarding a conflict drops the queued log without any request', async () => {
    fetchMock.mockResolvedValueOnce(res(409, { error: { code: 'log_exists', message: 'đã có', details: { id: 'log0' } } }))
    const { client_id } = await enqueue(form(), [])
    await flushOutbox()
    const before = fetchMock.mock.calls.length
    await resolveConflict(client_id, 'discard')
    expect(await listOutbox()).toEqual([])
    expect(fetchMock.mock.calls.length).toBe(before)
  })

  it('removeFromOutbox deletes a finished item', async () => {
    const { client_id } = await enqueue(form(), [])
    await removeFromOutbox(client_id)
    expect(await listOutbox()).toEqual([])
  })
})
