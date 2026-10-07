import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuditPage } from './AuditPage'
import { SettingsPage } from '@/features/settings/SettingsPage'

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })
const row = (n: number, over = {}) => ({
  id: `00000000-0000-0000-0000-00000000000${n}`, ts: '2026-11-05T03:00:00Z', user_id: 'u1', user_name: 'Nguyễn Văn A',
  action: 'update', entity_type: 'contract', entity_id: 'abcdef12-0000-0000-0000-000000000000',
  changes: { value: { before: 100, after: 200 } }, ip: '127.0.0.1', ...over,
})
const facets = { actions: ['create', 'login', 'update'], entity_types: ['contract', 'user'], users: [{ id: 'u1', name: 'Nguyễn Văn A' }] }

function wrap(node: React.ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AuditPage', () => {
  const fetchMock = vi.fn()
  const urls: string[] = []
  const serve = (items = [row(1), row(2, { user_name: null, action: 'login', changes: null })], total = items.length) =>
    fetchMock.mockImplementation((url: string) => {
      urls.push(url)
      if (url.includes('/audit-log/facets')) return Promise.resolve(res(200, facets))
      return Promise.resolve(res(200, { items, total, page: 1, page_size: 20 }))
    })
  beforeEach(() => {
    urls.length = 0
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('lists who did what with Vietnamese action names and a readable diff', async () => {
    serve()
    wrap(<AuditPage />)
    expect(await screen.findAllByText('Nguyễn Văn A')).not.toHaveLength(0)
    expect(screen.getAllByText('Sửa').length).toBeGreaterThan(0)
    expect(screen.getByText('Hệ thống')).toBeInTheDocument() // no user: system
    expect(screen.getAllByText(/contract · abcdef12/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Chi tiết thay đổi')).toHaveLength(1) // only rows with a diff
    expect(screen.getByText('2 bản ghi')).toBeInTheDocument()
    expect(screen.getAllByText(/05\/11\/2026 10:00:00/)).toHaveLength(2) // UTC shown as Vietnam time
  })

  it('filters by action, entity, user and a whole Vietnamese day', async () => {
    serve()
    wrap(<AuditPage />)
    const user = userEvent.setup()
    await screen.findAllByText('Nguyễn Văn A')
    await waitFor(() => expect(screen.getByRole('option', { name: 'Đăng nhập' })).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Thao tác'), 'login')
    await user.selectOptions(screen.getByLabelText('Đối tượng'), 'contract')
    await user.selectOptions(screen.getByLabelText('Người dùng'), 'u1')
    await user.type(screen.getByLabelText('Từ ngày'), '2026-11-01')
    await user.type(screen.getByLabelText('Đến ngày'), '2026-11-05')
    await waitFor(() => {
      const last = decodeURIComponent(urls.at(-1) ?? '')
      expect(last).toContain('action=login')
      expect(last).toContain('entity_type=contract')
      expect(last).toContain('user_id=u1')
      expect(last).toContain('ts_from=2026-11-01T00:00:00+07:00')
      expect(last).toContain('ts_to=2026-11-05T23:59:59+07:00')
    })
  })

  it('pages through long logs and returns to page 1 when a filter changes', async () => {
    serve(Array.from({ length: 20 }, (_, i) => row(i % 9, { id: `id-${i}` })), 45)
    wrap(<AuditPage />)
    const user = userEvent.setup()
    expect(await screen.findByText('Trang 1/3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trang trước' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Trang sau' }))
    expect(await screen.findByText('Trang 2/3')).toBeInTheDocument()
    expect(urls.some((u) => u.includes('page=2'))).toBe(true)
    await user.selectOptions(screen.getByLabelText('Thao tác'), 'update')
    expect(await screen.findByText('Trang 1/3')).toBeInTheDocument()
  })

  it('says when there is nothing and offers a retry on failure', async () => {
    serve([])
    wrap(<AuditPage />)
    expect(await screen.findByText('Không có bản ghi nào')).toBeInTheDocument()
  })

  it('shows an error with retry', async () => {
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(url.includes('facets') ? res(200, facets) : res(500, { error: { code: 'x', message: 'x' } })),
    )
    wrap(<AuditPage />)
    expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeInTheDocument()
  })
})

describe('SettingsPage (holidays)', () => {
  const fetchMock = vi.fn()
  const calls: { url: string; method: string; body?: string }[] = []
  let holidays = [{ id: 'h1', day: '2026-09-02', name: 'Quốc khánh' }]
  beforeEach(() => {
    calls.length = 0
    holidays = [{ id: 'h1', day: '2026-09-02', name: 'Quốc khánh' }]
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? 'GET', body: init?.body as string | undefined })
      if (init?.method === 'POST') {
        const body = JSON.parse(init.body as string)
        if (holidays.some((h) => h.day === body.day)) return Promise.resolve(res(409, { error: { code: 'conflict', message: 'dup' } }))
        holidays = [...holidays, { id: 'h2', ...body }]
        return Promise.resolve(res(201, holidays.at(-1)))
      }
      if (init?.method === 'DELETE') {
        holidays = holidays.filter((h) => !url.endsWith(h.id))
        return Promise.resolve(res(204))
      }
      return Promise.resolve(res(200, holidays))
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('lists, adds and removes holidays', async () => {
    wrap(<SettingsPage />)
    const user = userEvent.setup()
    expect(await screen.findByText(/Quốc khánh/)).toBeInTheDocument()
    expect(screen.getByText('02/09/2026')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Ngày'), '2026-09-03')
    await user.type(screen.getByLabelText('Tên ngày nghỉ'), 'Nghỉ lễ bù')
    await user.click(screen.getByRole('button', { name: 'Thêm ngày nghỉ' }))
    expect(await screen.findByText(/Nghỉ lễ bù/)).toBeInTheDocument()
    expect(JSON.parse(calls.find((c) => c.method === 'POST')?.body ?? '{}')).toEqual({ day: '2026-09-03', name: 'Nghỉ lễ bù' })

    await user.click(screen.getAllByRole('button', { name: 'Xóa' })[0])
    await waitFor(() => expect(screen.queryByText(/Quốc khánh/)).not.toBeInTheDocument())
  })

  it('explains a duplicate day', async () => {
    wrap(<SettingsPage />)
    const user = userEvent.setup()
    await screen.findByText(/Quốc khánh/)
    await user.type(screen.getByLabelText('Ngày'), '2026-09-02')
    await user.type(screen.getByLabelText('Tên ngày nghỉ'), 'Trùng')
    await user.click(screen.getByRole('button', { name: 'Thêm ngày nghỉ' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ngày này đã có trong danh sách')
  })
})
