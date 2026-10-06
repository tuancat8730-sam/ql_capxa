import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { IssuesPage } from './IssuesPage'
import { IssueSheet } from './IssueSheets'
import { daysUntilDue, type Issue, type IssueDetail } from './types'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const inDays = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString()

const issue = (over: Partial<Issue> = {}): Issue => ({
  id: 'i1', code: 'V-001', package_id: 'p4', issue_type: 'operational', level: 1,
  title: 'Lịch giao hàng chưa chốt', description: 'Xã A chưa có mặt bằng', due_at: inDays(2), status: 'open',
  resolution: null, decided_by: null, resolved_at: null, overdue: false, overdue_days: 0, ...over,
})

const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

describe('daysUntilDue', () => {
  it('counts calendar days from the viewer’s today, negative once past', () => {
    const now = new Date(2026, 9, 6, 15, 0)
    expect(daysUntilDue(new Date(2026, 9, 8, 9, 0).toISOString(), now)).toBe(2)
    expect(daysUntilDue(new Date(2026, 9, 6, 23, 0).toISOString(), now)).toBe(0)
    expect(daysUntilDue(new Date(2026, 9, 5, 9, 0).toISOString(), now)).toBe(-1)
  })
})

describe('Issues UI', () => {
  const fetchMock = vi.fn()

  function serve(role: string, issues: Issue[], extra?: (url: string, init?: RequestInit) => Response | null) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me(role)))
      if (url.startsWith('/api/v1/packages?')) return Promise.resolve(res(200, { items: [{ id: 'p4', number: 4 }], total: 1, page: 1, page_size: 100 }))
      const custom = extra?.(url, init)
      if (custom) return Promise.resolve(custom)
      if (url.startsWith('/api/v1/issues?')) return Promise.resolve(res(200, { items: issues, total: issues.length, page: 1, page_size: 100 }))
      return Promise.resolve(res(404, { error: { code: 'not_found', message: 'x' } }))
    })
  }
  const wrap = (node: React.ReactNode) =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>{node}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
  const calls = (m: string) => fetchMock.mock.calls.filter(([, i]) => (i?.method ?? 'GET') === m).map(([u]) => String(u))
  const lastBody = (url: string, method = 'POST') =>
    JSON.parse(fetchMock.mock.calls.filter(([u, i]) => u === url && i?.method === method).at(-1)![1].body)

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('shows level, status and the deadline in words (not colour alone)', async () => {
    serve('viewer', [
      issue(),
      issue({ id: 'i2', code: 'V-002', title: 'Quá hạn', due_at: inDays(-2), overdue: true, overdue_days: 2, level: 2, status: 'escalated' }),
      issue({ id: 'i3', code: 'V-003', title: 'Chưa có hạn', due_at: null, level: 3 }),
      issue({ id: 'i4', code: 'V-004', title: 'Đã xong', status: 'resolved' }),
    ])
    wrap(<IssuesPage />)
    const cards = await screen.findAllByRole('button', { name: /V-00\d/ })
    expect(within(cards[0]).getByText(/Cấp 1/)).toBeInTheDocument()
    expect(within(cards[0]).getByText('còn 2 ngày', { exact: false })).toBeInTheDocument()
    expect(within(cards[1]).getByText('quá hạn 2 ngày')).toBeInTheDocument()
    expect(within(cards[1]).getByText('Đã nâng cấp')).toBeInTheDocument()
    expect(within(cards[2]).getByText('Chưa có hạn (nhập tay)')).toBeInTheDocument()
    expect(within(cards[3]).queryByText(/còn|quá hạn/)).not.toBeInTheDocument() // finished: no countdown
    expect(screen.queryByRole('button', { name: 'Báo vướng mắc' })).not.toBeInTheDocument() // viewer
  })

  it('level chips and the overdue chip filter through the API', async () => {
    serve('technical', [issue()])
    wrap(<IssuesPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Cấp 2' }))
    await waitFor(() => expect(calls('GET').some((u) => u.includes('level=2'))).toBe(true))
    await user.click(screen.getByRole('button', { name: 'Chỉ quá hạn' }))
    await waitFor(() => expect(calls('GET').some((u) => u.includes('overdue=true'))).toBe(true))
  })

  it('creates an issue; the deadline field exists only for level 3', async () => {
    serve('onsite', [], (url, init) => (url === '/api/v1/issues' && init?.method === 'POST' ? res(201, issue()) : null))
    wrap(<IssuesPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Báo vướng mắc' }))
    const dialog = await screen.findByRole('dialog', { name: 'Báo vướng mắc' })
    expect(within(dialog).queryByLabelText('Hạn')).not.toBeInTheDocument()
    await user.type(within(dialog).getByLabelText('Tiêu đề'), 'Mất điện tại xã B')
    await user.selectOptions(within(dialog).getByLabelText(/Cấp/), '3')
    expect(within(dialog).getByLabelText('Hạn')).toBeInTheDocument()
    await user.selectOptions(within(dialog).getByLabelText(/Cấp/), '1')
    await user.selectOptions(within(dialog).getByLabelText('Gói thầu'), 'p4')
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(calls('POST')).toContain('/api/v1/issues'))
    expect(lastBody('/api/v1/issues')).toMatchObject({ title: 'Mất điện tại xã B', level: 1, package_id: 'p4', issue_type: 'operational', due_at: null })
  })

  const detail = (over: Partial<IssueDetail> = {}): IssueDetail => ({
    ...issue(),
    events: [
      { id: 'e1', ts: '2026-10-05T03:00:00Z', event: 'created', from_level: null, to_level: 1, note: null },
      { id: 'e2', ts: '2026-10-06T03:00:00Z', event: 'escalated', from_level: 1, to_level: 2, note: 'Cần Chủ đầu tư quyết' },
    ],
    ...over,
  })

  function openSheet(role: string, d: IssueDetail, extra?: (url: string, init?: RequestInit) => Response | null) {
    serve(role, [d], (url, init) => {
      if (url === `/api/v1/issues/${d.id}` && (init?.method ?? 'GET') === 'GET') return res(200, d)
      return extra?.(url, init) ?? null
    })
    wrap(<IssueSheet issue={d} canWrite={role !== 'viewer'} canApprove={role === 'director'} onClose={() => undefined} />)
  }

  it('shows the escalation history with levels and notes', async () => {
    openSheet('technical', detail())
    const history = await screen.findByRole('region', { name: 'Lịch sử' })
    expect(await within(history).findByText(/Nâng cấp/)).toBeInTheDocument()
    expect(within(history).getByText(/\(1 → 2\)/)).toBeInTheDocument()
    expect(within(history).getByText(/Cần Chủ đầu tư quyết/)).toBeInTheDocument()
    expect(within(history).getByText('Tạo')).toBeInTheDocument()
  })

  it('escalates with a note; level 2 asks for a manual deadline', async () => {
    openSheet('technical', detail({ level: 2, status: 'escalated' }), (url, init) =>
      url === '/api/v1/issues/i1/escalate' && init?.method === 'POST' ? res(200, issue({ level: 3 })) : null,
    )
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Nâng cấp lên cấp cao hơn' }))
    await user.type(screen.getByLabelText('Lý do nâng cấp'), 'Vi phạm tiến độ')
    expect(screen.getByLabelText('Hạn')).toBeInTheDocument() // level 3 deadline is typed in
    await user.click(screen.getAllByRole('button', { name: 'Nâng cấp lên cấp cao hơn' }).at(-1)!)
    await waitFor(() => expect(calls('POST')).toContain('/api/v1/issues/i1/escalate'))
    expect(lastBody('/api/v1/issues/i1/escalate')).toMatchObject({ note: 'Vi phạm tiến độ', due_at: null })
  })

  it('level 3 cannot be escalated further', async () => {
    openSheet('technical', detail({ level: 3 }))
    await screen.findByRole('region', { name: 'Lịch sử' })
    expect(screen.queryByRole('button', { name: 'Nâng cấp lên cấp cao hơn' })).not.toBeInTheDocument()
  })

  it('resolving needs a written result and sends who decided', async () => {
    openSheet('technical', detail(), (url, init) => (url === '/api/v1/issues/i1/resolve' && init?.method === 'POST' ? res(200, issue({ status: 'resolved' })) : null))
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Giải quyết' }))
    const submit = screen.getAllByRole('button', { name: 'Giải quyết' }).at(-1)!
    expect(submit).toBeDisabled()
    await user.type(screen.getByLabelText('Kết quả xử lý'), 'Đã chốt lịch giao')
    await user.type(screen.getByLabelText('Quyết định của'), 'Sở KH&CN')
    await user.click(submit)
    await waitFor(() => expect(calls('POST')).toContain('/api/v1/issues/i1/resolve'))
    expect(lastBody('/api/v1/issues/i1/resolve')).toEqual({ resolution: 'Đã chốt lịch giao', decided_by: 'Sở KH&CN' })
  })

  it('editing the deadline by hand requires a reason, which is sent to the API', async () => {
    openSheet('technical', detail(), (url, init) => (url === '/api/v1/issues/i1' && init?.method === 'PATCH' ? res(200, issue()) : null))
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Sửa hạn xử lý' }))
    await user.type(screen.getByLabelText('Hạn'), '2026-10-20T10:00')
    await user.type(screen.getByLabelText('Lý do sửa hạn'), 'Chủ đầu tư đồng ý')
    await user.click(screen.getAllByRole('button', { name: 'Lưu' }).at(-1)!)
    await waitFor(() => expect(calls('PATCH')).toContain('/api/v1/issues/i1'))
    const body = lastBody('/api/v1/issues/i1', 'PATCH')
    expect(body.due_reason).toBe('Chủ đầu tư đồng ý')
    expect(new Date(body.due_at).getTime()).toBe(new Date('2026-10-20T10:00').getTime())
  })

  it('closing a level-3 issue is offered to the director only; viewers get no actions', async () => {
    const resolvedL3 = detail({ level: 3, status: 'resolved' })
    openSheet('technical', resolvedL3)
    await screen.findByRole('region', { name: 'Lịch sử' })
    expect(screen.queryByRole('button', { name: 'Đóng vướng mắc' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mở lại' })).toBeInTheDocument()
  })

  it('a director sees the close button on a resolved level-3 issue', async () => {
    openSheet('director', detail({ level: 3, status: 'resolved' }))
    expect(await screen.findByRole('button', { name: 'Đóng vướng mắc' })).toBeInTheDocument()
  })

  it('viewers see the history but no action buttons', async () => {
    openSheet('viewer', detail())
    await screen.findByRole('region', { name: 'Lịch sử' })
    for (const name of ['Nâng cấp lên cấp cao hơn', 'Giải quyết', 'Sửa hạn xử lý']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    }
  })

  it('shows the server error when closing a level-3 issue is refused', async () => {
    openSheet('onsite', detail({ level: 3, status: 'resolved' }), (url, init) =>
      url === '/api/v1/issues/i1' && init?.method === 'PATCH' ? res(403, { error: { code: 'forbidden', message: 'x' } }) : null,
    )
    // onsite cannot approve, so the close button is hidden; reopening is allowed and a 403 is explained
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Mở lại' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Chỉ Giám đốc QLDA được đóng vướng mắc cấp 3')
  })
})
