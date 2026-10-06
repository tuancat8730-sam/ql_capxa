import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, setAccessToken, setSessionExpiredHandler } from './api'

const json = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

describe('api', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
    setSessionExpiredHandler(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('sends bearer token and parses JSON', async () => {
    setAccessToken('tok')
    fetchMock.mockResolvedValueOnce(json(200, { ok: 1 }))
    expect(await api.get('/x')).toEqual({ ok: 1 })
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBe('Bearer tok')
    expect(init.credentials).toBe('include')
  })

  it('maps the error envelope to ApiError', async () => {
    fetchMock.mockResolvedValueOnce(
      json(403, { error: { code: 'forbidden', message: 'Không có quyền', details: null } }),
    )
    const err = await api.get('/x').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 403, code: 'forbidden', message: 'Không có quyền' })
  })

  it('refreshes once on 401 and retries with the new token', async () => {
    setAccessToken('old')
    fetchMock
      .mockResolvedValueOnce(json(401, { error: { code: 'unauthorized', message: 'x' } }))
      .mockResolvedValueOnce(json(200, { access_token: 'new' }))
      .mockResolvedValueOnce(json(200, { ok: 2 }))
    expect(await api.get('/x')).toEqual({ ok: 2 })
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/auth/refresh')
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer new')
  })

  it('shares one refresh between concurrent 401s', async () => {
    let refreshed = false
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh')) {
        refreshed = true
        return Promise.resolve(json(200, { access_token: 'n' }))
      }
      return Promise.resolve(
        refreshed
          ? json(200, { ok: 1 })
          : json(401, { error: { code: 'unauthorized', message: 'x' } }),
      )
    })
    await Promise.all([api.get('/a'), api.get('/b')])
    const refreshCalls = fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/auth/refresh'))
    expect(refreshCalls).toHaveLength(1)
  })

  it('signals session expiry when refresh fails', async () => {
    const expired = vi.fn()
    setSessionExpiredHandler(expired)
    fetchMock
      .mockResolvedValueOnce(json(401, { error: { code: 'unauthorized', message: 'x' } }))
      .mockResolvedValueOnce(json(401, { error: { code: 'unauthorized', message: 'x' } }))
    await expect(api.get('/x')).rejects.toBeInstanceOf(ApiError)
    expect(expired).toHaveBeenCalledOnce()
  })

  it('does not refresh or signal expiry when retryOn401 is false (login)', async () => {
    const expired = vi.fn()
    setSessionExpiredHandler(expired)
    fetchMock.mockResolvedValueOnce(
      json(401, { error: { code: 'invalid_credentials', message: 'sai' } }),
    )
    await expect(api.post('/auth/login', {}, { retryOn401: false })).rejects.toMatchObject({
      code: 'invalid_credentials',
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(expired).not.toHaveBeenCalled()
  })

  it('returns undefined for 204', async () => {
    fetchMock.mockResolvedValueOnce(json(204))
    expect(await api.post('/auth/logout')).toBeUndefined()
  })
})
