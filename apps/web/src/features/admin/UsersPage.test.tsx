import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setAccessToken } from '@/lib/api'
import { AuthProvider } from '@/features/auth/AuthContext'
import { UsersPage } from './UsersPage'

const u = (over: Record<string, unknown> = {}) => ({
  id: 'u2',
  email: 'b@example.test',
  full_name: 'Trần B',
  phone: null,
  role: 'technical',
  is_active: true,
  must_change_password: false,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
  ...over,
})
const me = u({ id: 'me', email: 'admin@example.test', full_name: 'Admin', role: 'admin' })
const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })
const page = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 20 })

describe('UsersPage', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me))
      if (url.endsWith('/reset-password'))
        return Promise.resolve(res(200, { temporary_password: 'Temp1234abcd' }))
      if (url.startsWith('/api/v1/users') && method === 'GET') return Promise.resolve(res(200, page([me, u()])))
      if (url === '/api/v1/users' && method === 'POST')
        return Promise.resolve(res(201, { ...u({ id: 'u3' }), temporary_password: 'NewPass12345x' }))
      return Promise.resolve(res(200, u()))
    })
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  const renderPage = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <UsersPage />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

  it('lists users with localized role names', async () => {
    renderPage()
    expect((await screen.findAllByText('Trần B')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Kỹ thuật').length).toBeGreaterThan(0)
  })

  it('never offers to deactivate your own account', async () => {
    renderPage()
    await screen.findAllByText('Admin')
    const cards = screen.getAllByRole('listitem')
    const mine = cards.find((c) => within(c).queryByText('admin@example.test'))!
    expect(within(mine).queryByRole('button', { name: 'Khóa tài khoản' })).not.toBeInTheDocument()
    const other = cards.find((c) => within(c).queryByText('b@example.test'))!
    expect(within(other).getByRole('button', { name: 'Khóa tài khoản' })).toBeInTheDocument()
  })

  it('creates a user and shows the temporary password once', async () => {
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Thêm người dùng' }))
    const dialog = await screen.findByRole('dialog', { name: 'Thêm người dùng' })
    await user.type(within(dialog).getByLabelText('Họ và tên'), 'Lê C')
    await user.type(within(dialog).getByLabelText('Email'), 'c@example.test')
    await user.selectOptions(within(dialog).getByLabelText('Vai trò'), 'cost')
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }))
    expect(await screen.findByTestId('temp-password')).toHaveTextContent('NewPass12345x')
    const post = fetchMock.mock.calls.find(([url, init]) => url === '/api/v1/users' && init?.method === 'POST')!
    expect(JSON.parse(post[1].body)).toMatchObject({ email: 'c@example.test', role: 'cost' })
  })

  it('asks for confirmation before resetting a password', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    renderPage()
    const user = userEvent.setup()
    const cards = await screen.findAllByRole('listitem')
    const other = cards.find((c) => within(c).queryByText('b@example.test'))!
    await user.click(within(other).getByRole('button', { name: 'Cấp lại mật khẩu' }))
    expect(screen.queryByTestId('temp-password')).not.toBeInTheDocument()
    await user.click(within(other).getByRole('button', { name: 'Cấp lại mật khẩu' }))
    expect(await screen.findByTestId('temp-password')).toHaveTextContent('Temp1234abcd')
    confirm.mockRestore()
  })

  it('shows an error state with retry when loading fails', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me))
      return Promise.resolve(res(500, { error: { code: 'error', message: 'boom' } }))
    })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeInTheDocument()
  })
})
