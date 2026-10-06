import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { ChangeRequestsPage } from './ChangeRequestsPage'
import { MeetingsPage } from './MeetingsPage'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

const meeting = {
  id: 'm1', package_id: null, meeting_type: 'weekly', meeting_date: '2026-10-05', location: 'Phòng họp Sở', chair: 'Giám đốc QLDA',
  attendees: [{ name: 'Nguyễn A', organization: null }, { name: 'Trần B', organization: null }],
  minutes: 'Thống nhất lịch giao hàng.', open_actions: 2,
}
const actions = [
  { id: 'a1', meeting_id: 'm1', title: 'Gửi lịch giao hàng', due_date: '2026-10-01', status: 'open', overdue: true },
  { id: 'a2', meeting_id: 'm1', title: 'Chốt mặt bằng xã A', due_date: null, status: 'open', overdue: false },
]

describe('meetings and change requests', () => {
  const fetchMock = vi.fn()

  function serve(role: string, extra?: (url: string, init?: RequestInit) => Response | null) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me(role)))
      if (url.startsWith('/api/v1/packages?')) return Promise.resolve(res(200, { items: [{ id: 'p4', number: 4 }], total: 1, page: 1, page_size: 100 }))
      return Promise.resolve(extra?.(url, init) ?? res(404, { error: { code: 'not_found', message: 'x' } }))
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
  const meetingRoutes = (url: string, init?: RequestInit) => {
    if (url.startsWith('/api/v1/meetings?')) return res(200, { items: [meeting], total: 1, page: 1, page_size: 100 })
    if (url.startsWith('/api/v1/action-items?overdue=true')) return res(200, { items: [actions[0]], total: 1, page: 1, page_size: 50 })
    if (url === '/api/v1/meetings/m1/action-items' && (init?.method ?? 'GET') === 'GET') return res(200, actions)
    if (url === '/api/v1/meetings/m1/action-items' && init?.method === 'POST') return res(201, actions[1])
    if (url === '/api/v1/action-items/a1' && init?.method === 'PATCH') return res(200, {})
    if (url === '/api/v1/meetings' && init?.method === 'POST') return res(201, meeting)
    return null
  }
  const body = (url: string, method = 'POST') => JSON.parse(fetchMock.mock.calls.filter(([u, i]) => u === url && i?.method === method).at(-1)![1].body)
  const sent = (url: string, method = 'POST') => fetchMock.mock.calls.some(([u, i]) => u === url && i?.method === method)

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('lists meetings, flags overdue actions at the top and expands minutes and actions', async () => {
    serve('technical', meetingRoutes)
    wrap(<MeetingsPage />)
    const banner = await screen.findByRole('region', { name: 'Việc quá hạn' })
    expect(within(banner).getByText(/Gửi lịch giao hàng · 01\/10\/2026/)).toBeInTheDocument()
    const toggle = await screen.findByRole('button', { name: /Họp tuần · 05\/10\/2026/ })
    expect(toggle).toHaveTextContent('2 việc chưa xong')
    await userEvent.setup().click(toggle)
    expect(await screen.findByText('Thống nhất lịch giao hàng.')).toBeInTheDocument()
    expect(screen.getByText('Nguyễn A, Trần B')).toBeInTheDocument()
    expect(await screen.findByText('Chốt mặt bằng xã A')).toBeInTheDocument()
  })

  it('writers add and complete actions; the new action is sent with its due date', async () => {
    serve('technical', meetingRoutes)
    wrap(<MeetingsPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /Họp tuần/ }))
    const row = (await screen.findByText('Gửi lịch giao hàng', { selector: 'span' })).closest('li')!
    expect(within(row).getByText('Quá hạn')).toBeInTheDocument()
    await user.click(within(row).getByRole('button', { name: 'Đánh dấu xong' }))
    await waitFor(() => expect(sent('/api/v1/action-items/a1', 'PATCH')).toBe(true))
    expect(body('/api/v1/action-items/a1', 'PATCH')).toEqual({ status: 'done' })
    await user.type(screen.getByLabelText('Nội dung việc'), 'Mời nhà thầu họp')
    await user.type(screen.getAllByLabelText('Hạn xử lý').at(-1)!, '2026-10-12')
    await user.click(screen.getByRole('button', { name: 'Thêm việc' }))
    await waitFor(() => expect(sent('/api/v1/meetings/m1/action-items')).toBe(true))
    expect(body('/api/v1/meetings/m1/action-items')).toEqual({ title: 'Mời nhà thầu họp', due_date: '2026-10-12' })
  })

  it('read-only roles get no add buttons', async () => {
    serve('cost', meetingRoutes)
    wrap(<MeetingsPage />)
    await userEvent.setup().click(await screen.findByRole('button', { name: /Họp tuần/ }))
    await screen.findByText('Chốt mặt bằng xã A')
    expect(screen.queryByRole('button', { name: 'Thêm cuộc họp' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Thêm việc' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Đánh dấu xong' })).not.toBeInTheDocument()
  })

  it('creates a meeting with attendees split on commas', async () => {
    serve('director', meetingRoutes)
    wrap(<MeetingsPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Thêm cuộc họp' }))
    const dialog = await screen.findByRole('dialog', { name: 'Thêm cuộc họp' })
    await user.type(within(dialog).getByLabelText('Ngày họp'), '2026-10-06')
    await user.type(within(dialog).getByLabelText(/Thành phần/), 'Nguyễn A, , Trần B ')
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(sent('/api/v1/meetings')).toBe(true))
    expect(body('/api/v1/meetings')).toMatchObject({ meeting_type: 'weekly', meeting_date: '2026-10-06', attendees: [{ name: 'Nguyễn A' }, { name: 'Trần B' }] })
  })

  const change = (over = {}) => ({
    id: 'c1', code: 'C-001', package_id: 'p4', change_type: 'model', description: 'Đổi model máy tính',
    supervisor_opinion: 'TVGS đồng ý', tvqlda_opinion: null, status: 'proposed', decided_at: null, decision_note: null, ...over,
  })
  const changeRoutes = (items: unknown[]) => (url: string, init?: RequestInit) => {
    if (url.startsWith('/api/v1/change-requests?')) return res(200, { items, total: items.length, page: 1, page_size: 100 })
    if (url === '/api/v1/change-requests/c1' && init?.method === 'PATCH') return res(200, {})
    if (url === '/api/v1/change-requests/c1/decide' && init?.method === 'POST') return res(200, {})
    return null
  }

  it('only the director sees approve and reject; writers can send a proposal for review', async () => {
    serve('technical', changeRoutes([change()]))
    const first = wrap(<ChangeRequestsPage />)
    const card = (await screen.findAllByRole('listitem'))[0]
    expect(within(card).getByText(/C-001 · Gói 04 · Model/)).toBeInTheDocument()
    expect(within(card).getByText('Đề xuất')).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: 'Duyệt' })).not.toBeInTheDocument()
    await userEvent.setup().click(within(card).getByRole('button', { name: 'Chuyển xem xét' }))
    await waitFor(() => expect(sent('/api/v1/change-requests/c1', 'PATCH')).toBe(true))
    expect(body('/api/v1/change-requests/c1', 'PATCH')).toEqual({ status: 'reviewing' })
    first.unmount()

    serve('director', changeRoutes([change({ status: 'reviewing' })]))
    wrap(<ChangeRequestsPage />)
    const dcard = (await screen.findAllByRole('listitem'))[0]
    expect(within(dcard).getByRole('button', { name: 'Duyệt' })).toBeInTheDocument()
    expect(within(dcard).getByRole('button', { name: 'Từ chối' })).toBeInTheDocument()
  })

  it('the director decides with a note; an approved request can then be marked appendix-signed', async () => {
    serve('director', changeRoutes([change({ status: 'reviewing' })]))
    const first = wrap(<ChangeRequestsPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Duyệt' }))
    const dialog = await screen.findByRole('dialog', { name: 'Duyệt' })
    await user.type(within(dialog).getByLabelText('Ghi chú quyết định'), 'Đồng ý, ký phụ lục')
    await user.click(within(dialog).getByRole('button', { name: 'Duyệt' }))
    await waitFor(() => expect(sent('/api/v1/change-requests/c1/decide')).toBe(true))
    expect(body('/api/v1/change-requests/c1/decide')).toEqual({ decision: 'approved', note: 'Đồng ý, ký phụ lục' })
    first.unmount()

    serve('technical', changeRoutes([change({ status: 'approved', decided_at: '2026-10-06T03:00:00Z', decision_note: 'Đồng ý' })]))
    wrap(<ChangeRequestsPage />)
    expect(await screen.findByText(/Quyết định lúc 06\/10\/2026 – Đồng ý/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Đã ký phụ lục' }))
    await waitFor(() => expect(body('/api/v1/change-requests/c1', 'PATCH')).toEqual({ status: 'appendix_signed' }))
  })

  it('creates a change request for a package', async () => {
    serve('technical', (url, init) => (url === '/api/v1/change-requests' && init?.method === 'POST' ? res(201, change()) : changeRoutes([])(url, init)))
    wrap(<ChangeRequestsPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Thêm yêu cầu' }))
    const dialog = await screen.findByRole('dialog', { name: 'Thêm yêu cầu' })
    await user.selectOptions(await within(dialog).findByLabelText('Gói thầu'), 'p4')
    await user.selectOptions(within(dialog).getByLabelText('Loại thay đổi'), 'origin')
    await user.type(within(dialog).getByLabelText('Nội dung đề xuất'), 'Đổi xuất xứ màn hình')
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(sent('/api/v1/change-requests')).toBe(true))
    expect(body('/api/v1/change-requests')).toEqual({ package_id: 'p4', change_type: 'origin', description: 'Đổi xuất xứ màn hình' })
  })
})
