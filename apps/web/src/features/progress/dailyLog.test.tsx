import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { OfflineBanner } from '@/components/layout/OfflineBanner'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { flushOutbox, listOutbox, loadDraft, resetOfflineStore } from '@/lib/offline'
import { DailyLogPage } from './DailyLogPage'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const me = (role: string) => ({
  id: 'me',
  email: `${role}@example.test`,
  full_name: role,
  phone: null,
  role,
  is_active: true,
  must_change_password: false,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
})

const PACKAGES = { items: [{ id: 'p4', number: 4 }, { id: 'p6', number: 6 }], total: 2, page: 1, page_size: 100 }

function today(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const setOnline = (value: boolean) =>
  Object.defineProperty(navigator, 'onLine', { value, configurable: true })

describe('DailyLogPage', () => {
  const fetchMock = vi.fn()
  let logPosts: { url: string; init: RequestInit }[]
  let postResponse: () => Response | Promise<Response>

  function serve(role = 'onsite') {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me(role)))
      if (url.startsWith('/api/v1/packages?')) return Promise.resolve(res(200, PACKAGES))
      if (url.startsWith('/api/v1/packages/p4/progress-logs?')) {
        return Promise.resolve(res(200, { items: [{ id: 'old', package_id: 'p4', log_date: '2026-10-03', progress_pct: 20, summary: 'Lắp 2 xã', issues: 'Mất điện', next_steps: null, workers: 8, weather: null, author_name: 'Nam', attachments: [] }], total: 1, page: 1, page_size: 10 }))
      }
      if (url === '/api/v1/packages/p4/progress-logs' && init?.method === 'POST') {
        logPosts.push({ url, init })
        return Promise.resolve(postResponse())
      }
      if (url.startsWith('/api/v1/progress-logs/') && init?.method === 'PATCH') return Promise.resolve(res(200, {}))
      return Promise.resolve(res(404, { error: { code: 'not_found', message: 'x' } }))
    })
  }

  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <OfflineBanner />
            <DailyLogPage />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

  beforeEach(async () => {
    await resetOfflineStore()
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
    setOnline(true)
    logPosts = []
    postResponse = () => res(201, { id: 'log1' })
    serve()
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    setOnline(true)
  })

  async function fill(user: ReturnType<typeof userEvent.setup>, summary = 'Lắp 3 xã') {
    await user.selectOptions(await screen.findByLabelText('Gói thầu'), 'p4')
    fireInput(screen.getAllByLabelText('Tiến độ hoàn thành (%)')[1], '35')
    await user.type(screen.getByLabelText('Công việc đã làm'), summary)
    await user.type(screen.getByLabelText('Nhân lực (số người)'), '12')
    await user.selectOptions(screen.getByLabelText('Thời tiết'), 'Nắng')
  }
  function fireInput(el: HTMLElement, value: string) {
    // number inputs are easier to drive by setting the value directly
    const input = el as HTMLInputElement
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!
    setter.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }

  it('only roles that may write progress can use it', async () => {
    serve('viewer')
    wrap()
    expect(await screen.findByRole('alert')).toHaveTextContent('không có quyền')
    expect(screen.queryByRole('button', { name: 'Gửi nhật ký' })).not.toBeInTheDocument()
  })

  it('submits a log: queued with an Idempotency-Key, then sent, and the form resets', async () => {
    wrap()
    const user = userEvent.setup()
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Gửi nhật ký' }))
    const queue = await screen.findByRole('region', { name: 'Đã ghi, đang gửi' })
    await waitFor(() => expect(within(queue).getByText('Đã gửi')).toBeInTheDocument())
    expect(logPosts).toHaveLength(1)
    const headers = logPosts[0].init.headers as Record<string, string>
    expect(headers['Idempotency-Key']).toMatch(/^[0-9a-f-]{36}$/)
    expect(JSON.parse(logPosts[0].init.body as string)).toMatchObject({
      log_date: today(),
      progress_pct: 35,
      summary: 'Lắp 3 xã',
      workers: 12,
      weather: 'Nắng',
      attachments: [],
    })
    expect(screen.getByLabelText('Công việc đã làm')).toHaveValue('') // ready for the next entry
  })

  it('works offline: shows the banner, keeps the log "Chưa gửi" and sends it when back online', async () => {
    setOnline(false)
    wrap()
    const user = userEvent.setup()
    expect(await screen.findByText(/Đang ngoại tuyến/)).toBeInTheDocument()
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Gửi nhật ký' }))
    const queue = await screen.findByRole('region', { name: 'Đã ghi, đang gửi' })
    expect(within(queue).getByText('Chưa gửi')).toBeInTheDocument()
    expect(logPosts).toHaveLength(0)

    setOnline(true)
    await flushOutbox()
    await waitFor(() => expect(within(queue).getByText('Đã gửi')).toBeInTheDocument())
    expect(logPosts).toHaveLength(1)
    expect((await listOutbox())[0].status).toBe('sent')
  })

  it('a network failure keeps the log queued instead of losing it', async () => {
    postResponse = () => Promise.reject(new TypeError('Failed to fetch')) as unknown as Response
    wrap()
    const user = userEvent.setup()
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Gửi nhật ký' }))
    const queue = await screen.findByRole('region', { name: 'Đã ghi, đang gửi' })
    await waitFor(() => expect(within(queue).getByText('Chưa gửi')).toBeInTheDocument())
    expect(await listOutbox()).toHaveLength(1)
  })

  it('validation errors are shown as "Lỗi – thử lại" with a retry button', async () => {
    postResponse = () => res(422, { error: { code: 'validation_error', message: 'Tiến độ không hợp lệ' } })
    wrap()
    const user = userEvent.setup()
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Gửi nhật ký' }))
    const queue = await screen.findByRole('region', { name: 'Đã ghi, đang gửi' })
    await waitFor(() => expect(within(queue).getByText('Lỗi – thử lại')).toBeInTheDocument())
    expect(within(queue).getByRole('alert')).toHaveTextContent('Tiến độ không hợp lệ')
    postResponse = () => res(201, { id: 'log1' })
    await user.click(within(queue).getByRole('button', { name: 'Thử lại' }))
    await waitFor(() => expect(within(queue).getByText('Đã gửi')).toBeInTheDocument())
  })

  it('an existing log for the same day offers merge / overwrite / discard', async () => {
    postResponse = () => res(409, { error: { code: 'log_exists', message: 'đã có', details: { id: 'log0' } } })
    wrap()
    const user = userEvent.setup()
    await fill(user, 'Chiều: lắp thêm')
    await user.click(screen.getByRole('button', { name: 'Gửi nhật ký' }))
    const queue = await screen.findByRole('region', { name: 'Đã ghi, đang gửi' })
    expect(await within(queue).findByText('Đã có nhật ký ngày này')).toBeInTheDocument()
    expect(within(queue).getByText(/Chọn cách xử lý/)).toBeInTheDocument()
    await user.click(within(queue).getByRole('button', { name: 'Ghi đè' }))
    await waitFor(() => expect(within(queue).getByText('Đã gửi')).toBeInTheDocument())
    const patch = fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/progress-logs/log0' && i?.method === 'PATCH')!
    expect(JSON.parse(patch[1].body)).toMatchObject({ summary: 'Chiều: lắp thêm', progress_pct: 35 })
  })

  it('discarding a conflict removes it from the queue', async () => {
    postResponse = () => res(409, { error: { code: 'log_exists', message: 'đã có', details: { id: 'log0' } } })
    wrap()
    const user = userEvent.setup()
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Gửi nhật ký' }))
    const queue = await screen.findByRole('region', { name: 'Đã ghi, đang gửi' })
    await user.click(await within(queue).findByRole('button', { name: 'Bỏ bản mới' }))
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Đã ghi, đang gửi' })).not.toBeInTheDocument())
  })

  it('autosaves a draft and restores it the next time the screen opens', async () => {
    const first = wrap()
    const user = userEvent.setup()
    await fill(user, 'Đang viết dở')
    await waitFor(async () => expect((await loadDraft('p4', today()))?.form.summary).toBe('Đang viết dở'), { timeout: 3000 })
    expect(await screen.findByText('Đã lưu nháp')).toBeInTheDocument()
    first.unmount()

    wrap()
    await waitFor(() => expect(screen.getByLabelText('Gói thầu')).toHaveValue('p4')) // last package remembered?
  })

  it('restores the draft text for the remembered package after a reload', async () => {
    const first = wrap()
    const user = userEvent.setup()
    await fill(user, 'Bản nháp quan trọng')
    await waitFor(async () => expect((await loadDraft('p4', today()))?.form.summary).toBe('Bản nháp quan trọng'), { timeout: 3000 })
    first.unmount()

    wrap()
    const select = await screen.findByLabelText('Gói thầu')
    await user.selectOptions(select, 'p4')
    await waitFor(() => expect(screen.getByLabelText('Công việc đã làm')).toHaveValue('Bản nháp quan trọng'))
  })

  it('lists the latest logs of the chosen package while online', async () => {
    wrap()
    await userEvent.setup().selectOptions(await screen.findByLabelText('Gói thầu'), 'p4')
    const recent = await screen.findByRole('region', { name: 'Nhật ký gần đây' })
    expect(await within(recent).findByText(/03\/10\/2026 · 20%/)).toBeInTheDocument()
    expect(within(recent).getByText(/bởi Nam/)).toBeInTheDocument()
    expect(within(recent).getByText(/Mất điện/)).toBeInTheDocument()
  })

  it('caps photos at 10 and lets the user remove one', async () => {
    wrap()
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText('Gói thầu'), 'p4')
    const files = Array.from({ length: 12 }, (_, i) => new File([`img${i}`], `a${i}.jpg`, { type: 'image/jpeg' }))
    const picker = screen.getByLabelText('Chọn ảnh')
    await user.upload(picker, files)
    await waitFor(() => expect(screen.getByText('(10/10)')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Bỏ ảnh: a0.jpg' }))
    expect(screen.getByText('(9/10)')).toBeInTheDocument()
  })
})
