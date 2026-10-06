import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setAccessToken } from './api'
import {
  compressImage,
  fitWithin,
  guessMime,
  isRetryable,
  putWithRetry,
  RETRY_DELAYS_MS,
  UploadError,
  uploadFile,
} from './upload'

const target = { url: 'http://s3.test/obj', method: 'PUT', headers: { 'Content-Type': 'application/pdf' } }

class FakeXhr {
  static queue: number[] = [] // status codes (0 = network error) handed out per send()
  static instances: FakeXhr[] = []
  status = 0
  headers: Record<string, string> = {}
  opened: [string, string] | null = null
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = {
    onprogress: null,
  }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor() {
    FakeXhr.instances.push(this)
  }
  open(method: string, url: string) {
    this.opened = [method, url]
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }
  send() {
    const status = FakeXhr.queue.shift() ?? 200
    queueMicrotask(() => {
      this.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 })
      if (status === 0) this.onerror?.()
      else {
        this.status = status
        this.onload?.()
      }
    })
  }
}

describe('putWithRetry', () => {
  beforeEach(() => {
    FakeXhr.queue = []
    FakeXhr.instances = []
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('sends the signed headers and reports progress', async () => {
    const progress = vi.fn()
    await putWithRetry(new Blob(['x']), target, { onProgress: progress })
    expect(FakeXhr.instances[0].opened).toEqual(['PUT', target.url])
    expect(FakeXhr.instances[0].headers).toEqual({ 'Content-Type': 'application/pdf' })
    expect(progress).toHaveBeenCalledWith(0.5)
  })

  it('retries network errors and 5xx with growing delays, then succeeds', async () => {
    FakeXhr.queue = [0, 503, 200]
    const waits: number[] = []
    await putWithRetry(new Blob(['x']), target, { wait: async (ms) => void waits.push(ms) })
    expect(waits).toEqual([1_000, 2_000])
    expect(FakeXhr.instances).toHaveLength(3)
  })

  it('gives up after 5 retries (6 attempts) and surfaces the last error', async () => {
    FakeXhr.queue = [500, 500, 500, 500, 500, 500, 200]
    const waits: number[] = []
    await expect(
      putWithRetry(new Blob(['x']), target, { wait: async (ms) => void waits.push(ms) }),
    ).rejects.toMatchObject({ status: 500 })
    expect(waits).toEqual(RETRY_DELAYS_MS)
    expect(FakeXhr.instances).toHaveLength(6)
  })

  it('does not retry client errors such as an expired signature (403)', async () => {
    FakeXhr.queue = [403, 200]
    const wait = vi.fn()
    await expect(putWithRetry(new Blob(['x']), target, { wait })).rejects.toBeInstanceOf(UploadError)
    expect(wait).not.toHaveBeenCalled()
    expect(FakeXhr.instances).toHaveLength(1)
  })

  it('classifies retryable failures', () => {
    expect(isRetryable(new UploadError(0))).toBe(true)
    expect(isRetryable(new UploadError(502))).toBe(true)
    expect(isRetryable(new UploadError(403))).toBe(false)
    expect(isRetryable(new Error('x'))).toBe(false)
  })
})

describe('uploadFile', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    FakeXhr.queue = []
    FakeXhr.instances = []
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken('t')
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    setAccessToken(null)
  })

  it('requests a URL, PUTs the file and returns the reference to confirm', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          document_id: 'd1',
          file_key: 'projects/p/packages/k/d1/v1/a.pdf',
          version: 1,
          upload: target,
          expires_in: 600,
          max_bytes: 100,
        }),
        { status: 200 },
      ),
    )
    const file = new File(['hello'], 'Bảo lãnh.pdf', { type: 'application/pdf' })
    const done = await uploadFile(file, { packageId: 'pkg-4' })
    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body).toEqual({
      file_name: 'Bảo lãnh.pdf',
      mime_type: 'application/pdf',
      size_bytes: 5,
      package_id: 'pkg-4',
      parent_document_id: null,
    })
    expect(done).toMatchObject({ document_id: 'd1', file_key: 'projects/p/packages/k/d1/v1/a.pdf', size_bytes: 5 })
    expect(FakeXhr.instances).toHaveLength(1)
  })

  it('surfaces the API error (e.g. file too large) without uploading', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { code: 'validation_error', message: 'Tệp vượt quá 100 MB' } }), { status: 422 }),
    )
    await expect(uploadFile(new File(['x'], 'big.pdf', { type: 'application/pdf' }))).rejects.toMatchObject({
      status: 422,
    })
    expect(FakeXhr.instances).toHaveLength(0)
  })
})

describe('helpers', () => {
  it('guesses MIME types from the extension when the browser gives none', () => {
    expect(guessMime({ name: 'a.DOCX', type: '' })).toContain('wordprocessingml')
    expect(guessMime({ name: 'a.xlsx', type: '' })).toContain('spreadsheetml')
    expect(guessMime({ name: 'a.jpeg', type: '' })).toBe('image/jpeg')
    expect(guessMime({ name: 'a.bin', type: '' })).toBe('application/octet-stream')
    expect(guessMime({ name: 'a.pdf', type: 'application/pdf' })).toBe('application/pdf')
  })

  it('fits images within 1600 px without scaling up', () => {
    expect(fitWithin(4000, 3000)).toEqual({ width: 1600, height: 1200 })
    expect(fitWithin(3000, 4000)).toEqual({ width: 1200, height: 1600 })
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 })
    expect(fitWithin(1600, 1600)).toEqual({ width: 1600, height: 1600 })
  })

  it('leaves non-images and undecodable files untouched', async () => {
    const pdf = new File(['x'], 'a.pdf', { type: 'application/pdf' })
    expect(await compressImage(pdf)).toBe(pdf)
    const img = new File(['not really an image'], 'a.jpg', { type: 'image/jpeg' })
    expect(await compressImage(img)).toBe(img) // jsdom cannot decode: falls back to the original
  })
})
