import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { PackageLogTab } from './PackageLogTab'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role,
  is_active: true, must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

const entry = (n: number, over: Record<string, unknown> = {}) => ({
  id: `l${n}`, package_id: 'p5', log_date: `2026-10-${String(n).padStart(2, '0')}`, progress_pct: 10,
  summary: `Việc ${n}`, issues: null, next_steps: null, workers: null, weather: null,
  author_name: 'Admin', attachments: [], ...over,
})

describe('PackageLogTab', () => {
  const fetchMock = vi.fn()

  function serve(role: string, pages: Record<number, unknown[]>, total: number) {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me(role)))
      const m = /progress-logs\?page=(\d+)/.exec(url)
      if (m) return Promise.resolve(res(200, { items: pages[Number(m[1])] ?? [], total, page: Number(m[1]), page_size: 10 }))
      return Promise.resolve(res(404, { error: { code: 'not_found', message: 'x' } }))
    })
  }

  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <PackageLogTab packageId="p5" />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
  })

  it('shows every field of an entry and links to the form for this package', async () => {
    serve('onsite', { 1: [entry(13, { issues: 'Thiếu vân tay', next_steps: 'Bàn giao bổ sung', workers: 4, weather: 'Nắng', attachments: ['a', 'b'] })] }, 1)
    wrap()
    expect(await screen.findByText('Việc 13')).toBeInTheDocument()
    expect(screen.getByText('Thiếu vân tay')).toBeInTheDocument()
    expect(screen.getByText('Bàn giao bổ sung')).toBeInTheDocument()
    expect(screen.getByText('2 ảnh đính kèm')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Thêm nhật ký' })).toHaveAttribute('href', '/daily-log?package=p5')
  })

  it('says so when there is nothing yet, and hides the add link from read-only roles', async () => {
    serve('viewer', { 1: [] }, 0)
    wrap()
    expect(await screen.findByText('Chưa có nhật ký')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Thêm nhật ký' })).not.toBeInTheDocument()
  })

  it('loads the next page on request', async () => {
    const first = Array.from({ length: 10 }, (_, i) => entry(i + 1))
    serve('onsite', { 1: first, 2: [entry(20)] }, 11)
    wrap()
    await screen.findByText('Việc 1')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Xem thêm' }))
    expect(await screen.findByText('Việc 20')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Xem thêm' })).not.toBeInTheDocument()
  })
})
