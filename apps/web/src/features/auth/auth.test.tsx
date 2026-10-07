import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setAccessToken } from '@/lib/api'
import { AuthProvider } from './AuthContext'
import { LoginPage } from './LoginPage'
import { RequireAuth } from './RequireAuth'

const user = (over: Record<string, unknown> = {}) => ({
  id: 'u1',
  email: 'a@example.test',
  full_name: 'Nguyễn A',
  phone: null,
  role: 'viewer',
  is_active: true,
  must_change_password: false,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
  ...over,
})

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

function renderApp(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/change-password" element={<p>change-pw-page</p>} />
            <Route element={<RequireAuth />}>
              <Route path="/" element={<p>home-page</p>} />
            </Route>
            <Route element={<RequireAuth roles={['admin']} />}>
              <Route path="/admin" element={<p>admin-page</p>} />
            </Route>
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('auth flow', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('redirects anonymous visitors to /login', async () => {
    fetchMock.mockResolvedValueOnce(res(401, { error: { code: 'unauthorized', message: 'x' } }))
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument()
  })

  it('restores the session from the refresh cookie', async () => {
    fetchMock
      .mockResolvedValueOnce(res(200, { access_token: 't' }))
      .mockResolvedValueOnce(res(200, user()))
    renderApp('/')
    expect(await screen.findByText('home-page')).toBeInTheDocument()
  })

  it('logs in and lands on the requested page', async () => {
    fetchMock
      .mockResolvedValueOnce(res(401, { error: { code: 'unauthorized', message: 'x' } }))
      .mockResolvedValueOnce(res(200, { access_token: 't', token_type: 'bearer', user: user() }))
    renderApp('/login')
    const u = userEvent.setup()
    await u.type(await screen.findByLabelText('Email'), 'a@example.test')
    await u.type(screen.getByLabelText('Mật khẩu'), 'Str0ng-Passw0rd!')
    await u.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByText('home-page')).toBeInTheDocument()
    const loginCall = fetchMock.mock.calls[1]
    expect(loginCall[0]).toBe('/api/v1/auth/login')
    expect(JSON.parse(loginCall[1].body)).toEqual({ email: 'a@example.test', password: 'Str0ng-Passw0rd!' })
  })

  it('shows a localized error for bad credentials and for lockout', async () => {
    fetchMock
      .mockResolvedValueOnce(res(401, { error: { code: 'unauthorized', message: 'x' } }))
      .mockResolvedValueOnce(res(401, { error: { code: 'invalid_credentials', message: 'sai' } }))
      .mockResolvedValueOnce(res(429, { error: { code: 'account_locked', message: 'khoa' } }))
    renderApp('/login')
    const u = userEvent.setup()
    await u.type(await screen.findByLabelText('Email'), 'a@example.test')
    await u.type(screen.getByLabelText('Mật khẩu'), 'wrong')
    await u.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByText('Email hoặc mật khẩu không đúng')).toBeInTheDocument()
    await u.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByText(/tạm khóa 15 phút/)).toBeInTheDocument()
  })

  it('validates the email client-side without calling the API', async () => {
    fetchMock.mockResolvedValueOnce(res(401, { error: { code: 'unauthorized', message: 'x' } }))
    renderApp('/login')
    const u = userEvent.setup()
    await u.type(await screen.findByLabelText('Email'), 'not-an-email')
    await u.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByText('Email không hợp lệ')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1) // only the bootstrap refresh
  })

  it('no longer forces a first login to change the temporary password', async () => {
    fetchMock
      .mockResolvedValueOnce(res(200, { access_token: 't' }))
      .mockResolvedValueOnce(res(200, user({ must_change_password: true })))
    renderApp('/')
    expect(await screen.findByText('home-page')).toBeInTheDocument()
    expect(screen.queryByText('change-pw-page')).not.toBeInTheDocument()
  })

  it('blocks non-admin roles from admin routes', async () => {
    fetchMock
      .mockResolvedValueOnce(res(200, { access_token: 't' }))
      .mockResolvedValueOnce(res(200, user({ role: 'technical' })))
    renderApp('/admin')
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('không có quyền'))
    expect(screen.queryByText('admin-page')).not.toBeInTheDocument()
  })

  it('lets admins into admin routes', async () => {
    fetchMock
      .mockResolvedValueOnce(res(200, { access_token: 't' }))
      .mockResolvedValueOnce(res(200, user({ role: 'admin' })))
    renderApp('/admin')
    expect(await screen.findByText('admin-page')).toBeInTheDocument()
  })
})
