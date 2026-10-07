import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { periodText } from './period'
import { PlanTab } from './PlanTab'
import type { ImportPreview, Plan, PlanStep } from './types'

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })
const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

const step = (n: number, over: Partial<PlanStep> = {}): PlanStep => ({
  id: `s${n}`, group_no: 1, group_title: 'KIỂM TRA HÀNG HÓA TẠI KHO', step_no: n,
  content: `- Công việc số ${n}.\n- Lập biên bản.`, time_text: null, start_date: '2026-11-01', end_date: '2026-11-05',
  estimated: false, time_note: null, participants: ['Nhà thầu'], status: 'not_started', effective_status: 'not_started',
  days_late: null, actual_start: null, actual_end: null, tracking_note: null, ...over,
})

const plan: Plan = {
  id: 'plan1', package_id: 'p4', addressee: 'Sở Khoa học và Công nghệ tỉnh Lâm Đồng',
  legal_basis: 'Căn cứ Hợp đồng số 71/2026 ký ngày 14/9/2026.', contract_text: '60 ngày',
  contract_start: '2026-09-14', contract_end: '2026-11-13', implement_text: null,
  implement_start: '2026-11-05', implement_end: '2026-11-13',
  locations: [{ label: 'Kiểm tra đầu vào', text: 'tại kho của Sở' }], signer: 'CÔNG TY TNHH A – Giám đốc',
  declared_total: 9, total_quantity: 9, source_file_name: 'ke-hoach.docx', imported_at: '2026-10-07T03:00:00Z',
  items: [
    { id: 'i1', line_no: 1, name: 'Cân phân tích 220 g', details: 'Hãng X\n- Bảo hành: 12 tháng', unit: 'Cái', quantity: 6, assignments: [{ org: 'CÔNG TY TNHH A', quantity: 6 }], note: null },
    { id: 'i2', line_no: 2, name: 'Bộ phần mềm', details: null, unit: 'Bộ', quantity: 3, assignments: [{ org: 'Công ty A', quantity: 1 }, { org: 'Công ty B', quantity: 2 }], note: 'Hàng nhập khẩu' },
  ],
  steps: [
    step(1, { status: 'done', effective_status: 'done', actual_start: '2026-11-01', actual_end: '2026-11-04', tracking_note: 'Đã nhập kho' }),
    step(2, { effective_status: 'delayed', days_late: 15, estimated: true, time_note: 'Tùy thuộc vào tổ chức kiểm định', participants: ['Tổ chức kiểm định (PA05, PA06)', 'Nhà thầu'] }),
    step(3, { group_no: 2, group_title: 'LẮP ĐẶT', start_date: null, end_date: null }),
  ],
  progress: { done: 1, total: 3, pct: 33.3 },
  findings: [
    { code: 'AFTER_CONTRACT_END', severity: 'warning', message: '7 bước kết thúc sau ngày kết thúc hợp đồng 13/11/2026 (muộn nhất 30/11/2026)' },
    { code: 'NO_TIME', severity: 'info', message: 'Chưa có thời gian ở bước 3' },
  ],
}

const preview = (over: Partial<ImportPreview> = {}): ImportPreview => ({
  dry_run: true, replaces_existing: false, addressee: 'Sở', contract_start: '2026-09-14', contract_end: '2026-11-13',
  implement_start: '2026-11-05', implement_end: '2026-11-13', locations: 2, total_quantity: 846,
  items: [{ line_no: 1, name: 'Cân', quantity: 85 }],
  steps: [
    { step_no: 1, group_no: 1, group_title: 'A', summary: '- Kiểm tra hàng tại kho.', start_date: '2026-10-30', end_date: '2026-11-05', estimated: false, keeps_tracking: true },
    { step_no: 2, group_no: 1, group_title: 'A', summary: '- Bàn giao hồ sơ.', start_date: null, end_date: null, estimated: false, keeps_tracking: false },
  ],
  kept_tracking: 1, findings: [{ code: 'NO_TIME', severity: 'info', message: 'Chưa có thời gian ở bước 2' }], ...over,
})

describe('periodText', () => {
  it('formats one day, a range, and nothing', () => {
    expect(periodText('2026-11-05', '2026-11-05')).toBe('05/11/2026')
    expect(periodText('2026-11-05', '2026-11-13')).toBe('05/11/2026 – 13/11/2026')
    expect(periodText(null, '2026-11-13')).toBe('13/11/2026')
    expect(periodText(null, null)).toBeNull()
  })
})

describe('PlanTab', () => {
  const fetchMock = vi.fn()
  const calls: { url: string; method: string; body?: unknown }[] = []

  function serve(role: string, current: Plan | null = plan, extra?: (url: string, init?: RequestInit) => Response | null) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? 'GET', body: init?.body })
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me(role)))
      const custom = extra?.(url, init)
      if (custom) return Promise.resolve(custom)
      if (url === '/api/v1/packages/p4/plan') return Promise.resolve(res(200, current))
      return Promise.resolve(res(404, { error: { code: 'not_found', message: 'x' } }))
    })
  }
  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <PlanTab packageId="p4" />
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
    vi.restoreAllMocks()
  })

  it('without a plan: says so, and only uploaders get the upload button', async () => {
    serve('viewer', null)
    const { unmount } = wrap()
    expect(await screen.findByText('Gói thầu này chưa có kế hoạch triển khai.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Tải kế hoạch' })).not.toBeInTheDocument()
    unmount()
    serve('procurement', null)
    wrap()
    expect(await screen.findByRole('button', { name: 'Tải kế hoạch' })).toBeInTheDocument()
  })

  it('shows the general information, locations and the legal basis', async () => {
    serve('viewer')
    wrap()
    const info = await screen.findByRole('region', { name: 'Thông tin chung' })
    expect(within(info).getByText('Sở Khoa học và Công nghệ tỉnh Lâm Đồng')).toBeInTheDocument()
    expect(within(info).getByText('14/09/2026 – 13/11/2026')).toBeInTheDocument()
    expect(within(info).getByText('05/11/2026 – 13/11/2026')).toBeInTheDocument()
    expect(within(info).getByText(/Kiểm tra đầu vào/)).toBeInTheDocument()
    expect(within(info).getByText('CÔNG TY TNHH A – Giám đốc')).toBeInTheDocument()
    expect(within(info).getByText(/Căn cứ Hợp đồng số 71\/2026/)).toBeInTheDocument()
    expect(screen.getByText(/Từ tệp ke-hoach\.docx/)).toBeInTheDocument()
  })

  it('shows progress and the findings of the document', async () => {
    serve('viewer')
    wrap()
    expect(await screen.findByText('Đã xong 1/3 bước (33,3%)')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Kế hoạch triển khai' })).toHaveAttribute('aria-valuenow', '33.3')
    const findings = screen.getByRole('region', { name: 'Cần lưu ý' })
    expect(within(findings).getByText(/7 bước kết thúc sau ngày kết thúc hợp đồng/)).toBeInTheDocument()
    expect(within(findings).getByText('Chưa có thời gian ở bước 3')).toBeInTheDocument()
  })

  it('groups steps by stage with their dates, status, participants and tracking', async () => {
    serve('viewer')
    wrap()
    const stage1 = await screen.findByRole('region', { name: 'Giai đoạn 1' })
    expect(within(stage1).getByText(/KIỂM TRA HÀNG HÓA TẠI KHO/)).toBeInTheDocument()
    expect(within(stage1).getByText('1/2 bước xong')).toBeInTheDocument()
    const first = within(stage1).getAllByRole('listitem')[0]
    expect(within(first).getByText('Hoàn thành')).toBeInTheDocument()
    expect(within(first).getByText('01/11/2026 – 05/11/2026')).toBeInTheDocument()
    expect(within(first).getByText(/Đã nhập kho/)).toBeInTheDocument()
    expect(within(first).getByText(/01\/11\/2026 – 04\/11\/2026/)).toBeInTheDocument()
    const second = stage1.querySelectorAll(':scope > ul > li')[1] as HTMLElement
    expect(within(second).getByText('Trễ 15 ngày')).toBeInTheDocument()
    expect(within(second).getByText('(dự kiến)')).toBeInTheDocument()
    expect(within(second).getByText(/Tùy thuộc vào tổ chức kiểm định/)).toBeInTheDocument()
    expect(within(second).getByText(/Tổ chức kiểm định \(PA05, PA06\) · Nhà thầu/)).toBeInTheDocument()
  })

  it('a step without a time says so and is not marked late', async () => {
    serve('viewer')
    wrap()
    const stage2 = await screen.findByRole('region', { name: 'Giai đoạn 2' })
    expect(within(stage2).getByText('Chưa có thời gian')).toBeInTheDocument()
    expect(within(stage2).getByText('Chưa làm')).toBeInTheDocument()
  })

  it('lists the equipment with totals, the split between contractors and the details', async () => {
    serve('viewer')
    wrap()
    const eq = await screen.findByRole('region', { name: 'Thiết bị theo hợp đồng' })
    expect(within(eq).getByText('2 hạng mục, tổng 9')).toBeInTheDocument()
    expect(within(eq).getAllByText('Cân phân tích 220 g').length).toBeGreaterThan(0) // card and table
    expect(within(eq).getAllByText(/Công ty B/).length).toBeGreaterThan(0)
    expect(within(eq).getAllByText('Hàng nhập khẩu').length).toBeGreaterThan(0)
    expect(within(eq).getAllByText('Thông số và chi tiết').length).toBe(2) // one item with details, in card and table
  })

  it('only people who may track progress see the step buttons', async () => {
    serve('procurement') // may upload, may not track
    const { unmount } = wrap()
    await screen.findByRole('region', { name: 'Giai đoạn 1' })
    expect(screen.queryByRole('button', { name: 'Cập nhật' })).not.toBeInTheDocument()
    unmount()
    serve('technical') // may track, may not upload
    wrap()
    expect((await screen.findAllByRole('button', { name: 'Cập nhật' })).length).toBe(3)
    expect(screen.queryByRole('button', { name: 'Tải bản mới' })).not.toBeInTheDocument()
    // finished steps have no "mark done"
    expect(screen.getAllByRole('button', { name: /Đánh dấu hoàn thành/ }).length).toBe(2)
  })

  it('marks a step done with one tap', async () => {
    serve('onsite', plan, (url, init) => (url === '/api/v1/plan-steps/s2' && init?.method === 'PATCH' ? res(200, {}) : null))
    wrap()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Đánh dấu hoàn thành: 2' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH' && c.url === '/api/v1/plan-steps/s2')).toBe(true))
    const patch = calls.find((c) => c.method === 'PATCH')
    expect(JSON.parse(patch?.body as string)).toEqual({ status: 'done' })
  })

  it('updates a step with status, actual dates and a note', async () => {
    serve('director', plan, (url, init) => (url === '/api/v1/plan-steps/s2' && init?.method === 'PATCH' ? res(200, {}) : null))
    wrap()
    const user = userEvent.setup()
    await user.click((await screen.findAllByRole('button', { name: 'Cập nhật' }))[1])
    const dialog = await screen.findByRole('dialog', { name: 'Cập nhật bước 2' })
    await user.selectOptions(within(dialog).getByLabelText('Trạng thái'), 'blocked')
    await user.type(within(dialog).getByLabelText('Ngày bắt đầu thực tế'), '2026-11-10')
    await user.type(within(dialog).getByLabelText('Ghi chú'), 'Chờ đơn vị kiểm định')
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(JSON.parse(calls.find((c) => c.method === 'PATCH')?.body as string)).toEqual({
      status: 'blocked', actual_start: '2026-11-10', actual_end: null, tracking_note: 'Chờ đơn vị kiểm định',
    })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Cập nhật bước 2' })).not.toBeInTheDocument())
  })

  it('shows the server message when a step update is refused', async () => {
    serve('director', plan, (url, init) =>
      url === '/api/v1/plan-steps/s2' && init?.method === 'PATCH'
        ? res(422, { error: { code: 'validation_error', message: 'Ngày kết thúc thực tế trước ngày bắt đầu' } })
        : null,
    )
    wrap()
    const user = userEvent.setup()
    await user.click((await screen.findAllByRole('button', { name: 'Cập nhật' }))[1])
    const dialog = await screen.findByRole('dialog', { name: 'Cập nhật bước 2' })
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Ngày kết thúc thực tế trước ngày bắt đầu')
  })

  describe('uploading a plan document', () => {
    const pick = async (user: ReturnType<typeof userEvent.setup>, name = 'ke-hoach.docx') => {
      const file = new File(['x'], name, { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
      await user.upload(screen.getByLabelText('Chọn tệp kế hoạch'), file)
    }

    it('reads the file first, shows the preview, and saves only after confirmation', async () => {
      serve('procurement', null, (url) =>
        url.startsWith('/api/v1/packages/p4/plan/import')
          ? res(200, preview({ dry_run: !url.includes('commit=true') }))
          : null,
      )
      wrap()
      const user = userEvent.setup()
      await user.click(await screen.findByRole('button', { name: 'Tải kế hoạch' }))
      const dialog = await screen.findByRole('dialog', { name: 'Tải kế hoạch triển khai' })
      expect(within(dialog).getByRole('button', { name: 'Kiểm tra tệp' })).toBeDisabled()
      await pick(user)
      await user.click(within(dialog).getByRole('button', { name: 'Kiểm tra tệp' }))

      expect(await within(dialog).findByText('1 hạng mục (tổng 846), 2 bước, 2 địa điểm')).toBeInTheDocument()
      expect(within(dialog).getByText('Chưa có thời gian ở bước 2')).toBeInTheDocument()
      expect(within(dialog).getByText(/giữ trạng thái/)).toBeInTheDocument()
      const check = calls.find((c) => c.url.includes('plan/import'))
      expect(check?.url).toContain('commit=false')
      expect(check?.body).toBeInstanceOf(FormData)
      expect(calls.filter((c) => c.url.includes('commit=true'))).toHaveLength(0) // nothing saved yet

      await user.click(within(dialog).getByRole('button', { name: 'Lưu kế hoạch' }))
      await waitFor(() => expect(calls.some((c) => c.url.includes('commit=true'))).toBe(true))
      await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Tải kế hoạch triển khai' })).not.toBeInTheDocument())
    })

    it('says when it will replace the current plan and how many steps keep their status', async () => {
      serve('admin', plan, (url) => (url.startsWith('/api/v1/packages/p4/plan/import') ? res(200, preview({ replaces_existing: true, kept_tracking: 4 })) : null))
      wrap()
      const user = userEvent.setup()
      await user.click(await screen.findByRole('button', { name: 'Tải bản mới' }))
      await pick(user)
      await user.click(await screen.findByRole('button', { name: 'Kiểm tra tệp' }))
      expect(await screen.findByRole('status')).toHaveTextContent('Sẽ thay kế hoạch hiện tại. 4 bước giữ nguyên trạng thái đã cập nhật.')
    })

    it('shows why a file was refused and offers no save', async () => {
      serve('admin', null, (url) =>
        url.startsWith('/api/v1/packages/p4/plan/import')
          ? res(422, { error: { code: 'invalid_plan_file', message: 'Chỉ nhận tệp Word (.docx hoặc .doc)' } })
          : null,
      )
      wrap()
      // the file dialog's accept list is only a hint: a user can still choose any file
      const user = userEvent.setup({ applyAccept: false })
      await user.click(await screen.findByRole('button', { name: 'Tải kế hoạch' }))
      await pick(user, 'ke-hoach.pdf')
      await user.click(await screen.findByRole('button', { name: 'Kiểm tra tệp' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Chỉ nhận tệp Word')
      expect(screen.queryByRole('button', { name: 'Lưu kế hoạch' })).not.toBeInTheDocument()
    })
  })

  it('removes the plan after a confirmation', async () => {
    serve('director', plan, (url, init) => (url === '/api/v1/packages/p4/plan' && init?.method === 'DELETE' ? res(204) : null))
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    wrap()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Xóa kế hoạch' }))
    expect(confirm).toHaveBeenCalled()
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
  })

  it('does not remove anything when the confirmation is declined', async () => {
    serve('director')
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    wrap()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Xóa kế hoạch' }))
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
  })
})
