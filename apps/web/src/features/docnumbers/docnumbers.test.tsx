import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { OutgoingDocsPage } from './OutgoingDocsPage'

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })
const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})
const row = (over = {}) => ({
  id: 'n1', year: 2026, doc_kind: 'CV', seq: 12, doc_no: '012/CV-QLDA-SGM', subject: 'V/v bổ sung hồ sơ',
  issued_date: '2026-10-05', created_by_name: 'Văn thư', ...over,
})

describe('OutgoingDocsPage', () => {
  const fetchMock = vi.fn()
  const calls: { url: string; method: string; body?: string }[] = []
  const serve = (role: string, post?: () => Response) =>
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? 'GET', body: init?.body as string | undefined })
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me(role)))
      if (init?.method === 'POST') return Promise.resolve(post?.() ?? res(201, row({ seq: 13, doc_no: '013/CV-QLDA-SGM' })))
      return Promise.resolve(res(200, { items: [row()], total: 1, page: 1, page_size: 100 }))
    })
  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <OutgoingDocsPage />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

  beforeEach(() => {
    calls.length = 0
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('lists numbers with subject, date and who took them', async () => {
    serve('viewer')
    wrap()
    expect(await screen.findByText('012/CV-QLDA-SGM')).toBeInTheDocument()
    expect(screen.getByText('V/v bổ sung hồ sơ')).toBeInTheDocument()
    expect(screen.getByText(/05\/10\/2026/)).toBeInTheDocument()
  })

  it('only clerks and admins get the form', async () => {
    serve('viewer')
    wrap()
    await screen.findByText('012/CV-QLDA-SGM')
    expect(screen.queryByRole('form', { name: 'Lấy số mới' })).not.toBeInTheDocument()
  })

  it('issues a number and shows it', async () => {
    serve('clerk')
    wrap()
    const user = userEvent.setup()
    await screen.findByText('012/CV-QLDA-SGM')
    const submit = screen.getByRole('button', { name: 'Lấy số' })
    expect(submit).toBeDisabled() // subject required
    const form = screen.getByRole('form', { name: 'Lấy số mới' })
    await user.selectOptions(within(form).getByRole('combobox', { name: 'Loại văn bản' }), 'BC')
    await user.type(screen.getByLabelText('Trích yếu', { selector: 'textarea' }), 'Báo cáo tuần 41')
    await user.click(submit)
    expect(await screen.findByText('Đã cấp số 013/CV-QLDA-SGM')).toBeInTheDocument()
    const post = calls.find((c) => c.url === '/api/v1/outgoing-doc-numbers' && c.method === 'POST')
    expect(JSON.parse(post?.body ?? '{}')).toEqual({ doc_kind: 'BC', subject: 'Báo cáo tuần 41' })
  })

  it('shows the server error', async () => {
    serve('clerk', () => res(422, { error: { code: 'validation_error', message: 'Trích yếu không hợp lệ' } }))
    wrap()
    const user = userEvent.setup()
    await screen.findByText('012/CV-QLDA-SGM')
    await user.type(screen.getByLabelText('Trích yếu', { selector: 'textarea' }), 'x')
    await user.click(screen.getByRole('button', { name: 'Lấy số' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Trích yếu không hợp lệ')
  })

  it('filters by kind and search text', async () => {
    serve('viewer')
    wrap()
    const user = userEvent.setup()
    await screen.findByText('012/CV-QLDA-SGM')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Loại văn bản' }), 'BC')
    await user.type(screen.getByRole('searchbox'), 'bao cao')
    await waitFor(() => expect(calls.some((c) => c.url.includes('doc_kind=BC') && c.url.includes('q=bao+cao'))).toBe(true))
  })
})
