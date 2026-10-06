/** Thin fetch wrapper: bearer token in memory, one silent refresh on 401, error envelope -> ApiError. */

export class ApiError extends Error {
  status: number
  code: string
  details?: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

const BASE = '/api/v1'

let accessToken: string | null = null
let refreshing: Promise<string | null> | null = null
let onSessionExpired: (() => void) | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler
}

async function refreshAccessToken(): Promise<string | null> {
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
      if (!res.ok) return null
      const data = (await res.json()) as { access_token: string }
      accessToken = data.access_token
      return accessToken
    } catch {
      return null
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

async function send(path: string, method: string, body: unknown): Promise<Response> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  return fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: { retryOn401?: boolean } = {},
): Promise<T> {
  const retry = opts.retryOn401 ?? true
  let res = await send(path, method, body)
  if (res.status === 401 && retry && (await refreshAccessToken())) {
    res = await send(path, method, body)
  }
  if (res.status === 401 && retry) onSessionExpired?.()
  if (!res.ok) {
    let code = 'error'
    let message = res.statusText
    let details: unknown
    try {
      const data = (await res.json()) as { error?: { code: string; message: string; details?: unknown } }
      if (data.error) ({ code, message, details } = data.error)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message, details)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown, opts?: { retryOn401?: boolean }) =>
    request<T>('POST', path, body, opts),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  refresh: refreshAccessToken,
}

export interface User {
  id: string
  email: string
  full_name: string
  phone: string | null
  role: string
  is_active: boolean
  must_change_password: boolean
  last_login_at: string | null
  created_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
