import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { DecisionsPage } from './DecisionsPage'
import { DeliveryOverviewPage } from './DeliveryOverviewPage'
import { DeliveryRisksPage } from './DeliveryRisksPage'
import { levelOf, scoreOfLevel } from './meta'
import { SchedulePage } from './SchedulePage'
import type { Decision, DeliveryRisk, Overview, Task, Week } from './types'
import { WeeklyReportsPage } from './WeeklyReportsPage'

/** Writes to the API; the silent token refresh is a POST too and must not count. */
const isWrite = (method: string) => (c: { url: string; method: string }) =>
  c.method === method && !c.url.includes('/auth/')

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })

const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

const task = (over: Partial<Task>): Task => ({
  id: 't1',
  code: 'II.2',
  phase_code: 'II',
  phase_name: 'Khảo sát, thu thập và phân tích yêu cầu',
  name: 'Khảo sát hiện trạng',
  is_milestone: false,
  plan_start: '2026-10-01',
  plan_end: '2026-10-05',
  plan_days: 3,
  tracked: false,
  status: 'not_started',
  pct: 0,
  actual_start: null,
  actual_end: null,
  note: null,
  updated_at: '2026-10-08T00:00:00Z',
  state: 'stale',
  late_days: 1,
  ...over,
})

const TASKS: Task[] = [
  task({ id: 't1', code: 'I.1', phase_code: 'I', phase_name: 'Khởi động gói thầu', name: 'Họp khởi động', plan_start: '2026-09-25', plan_end: '2026-09-29', tracked: true, status: 'done', pct: 100, state: 'done', late_days: 0 }),
  task({ id: 't2' }),
  task({ id: 't3', code: 'M1', name: 'Hoàn thành khảo sát', is_milestone: true, plan_start: '2026-10-07', plan_end: '2026-10-07', plan_days: 0, state: 'stale' }),
]

const OVERVIEW: Overview = {
  today: '2026-10-08',
  project_start: '2026-09-25',
  project_end: '2026-12-09',
  has_progress: true,
  actual_pct: 12.4,
  plan_pct: 30.2,
  diff: -18,
  next_milestone: { id: 't3', code: 'M1', name: 'Hoàn thành khảo sát', date: '2026-10-07', days_left: -1 },
  late_count: 1,
  stale_count: 2,
  weeks_ended: 2,
  weeks_received: 1,
  pending_decisions: 1,
  attention: [
    { rank: 0, chip: 'bad', label: 'Trễ hạn', title: 'II.2 · Khảo sát hiện trạng', sub: 'Hạn 05/10, quá 3 ngày làm việc · hoàn thành 40%', target: 'task', ref: 't2' },
    { rank: 4, chip: 'warn', label: 'Báo cáo tuần', title: 'Chưa nhận báo cáo tuần 2', sub: '02/10 – 08/10', target: 'week', ref: '2026-10-02' },
  ],
  phases: [
    { code: 'I', name: 'Khởi động gói thầu', start: '2026-09-25', end: '2026-09-29', actual_pct: 100, plan_pct: 100, state: 'done' },
    { code: 'II', name: 'Khảo sát, thu thập và phân tích yêu cầu', start: '2026-09-28', end: '2026-10-07', actual_pct: 20, plan_pct: 90, state: 'late' },
  ],
  plan_curve: [
    { date: '2026-09-25', pct: 0 },
    { date: '2026-10-08', pct: 30.2 },
    { date: '2026-12-09', pct: 100 },
  ],
  report_points: [{ date: '2026-10-01', pct: 4 }],
}

const WEEKS: Week[] = [
  { no: 1, start: '2026-09-25', end: '2026-10-01', state: 'received', suggested_planned_pct: 6, suggested_actual_pct: 12, report: { id: 'r1', week_start: '2026-09-25', report_no: 'BC-01', status: 'received', submitted_on: '2026-10-02', link: null, planned_pct: 6, actual_pct: 4, done: null, issues: null, recommendations: null, next_plan: null, risk_ids: [], updated_at: '2026-10-02T00:00:00Z' } },
  { no: 2, start: '2026-10-02', end: '2026-10-08', state: 'missing', suggested_planned_pct: 30, suggested_actual_pct: 12, report: null },
]

const RISK: DeliveryRisk = {
  id: 'k1', code: 'R-001', title: 'Dữ liệu cũ không đồng nhất', group_name: 'Dữ liệu', owner_text: 'CĐT',
  mitigation: 'Làm sạch dữ liệu', note: null, status: 'open', due_date: '2026-10-30', probability: 5, impact: 5, score: 25,
}

const DECISION: Decision = {
  id: 'd1', no: 1, title: 'Chốt môi trường triển khai', reason: 'Cần để dựng hạ tầng', status: 'pending',
  due_date: '2026-10-05', decision: null, decided_on: null, updated_at: '2026-10-08T00:00:00Z', overdue: true,
}

describe('delivery pages', () => {
  const fetchMock = vi.fn()
  const calls: { url: string; method: string; body: unknown }[] = []

  function serve(role = 'director') {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      if (url === '/api/v1/auth/refresh') return Promise.resolve(res(200, { access_token: 't' }))
      if (url === '/api/v1/auth/me') return Promise.resolve(res(200, me(role)))
      if (method === 'GET') {
        if (url === '/api/v1/delivery/overview') return Promise.resolve(res(200, OVERVIEW))
        if (url === '/api/v1/delivery/tasks') return Promise.resolve(res(200, TASKS))
        if (url === '/api/v1/delivery/weeks') return Promise.resolve(res(200, WEEKS))
        if (url === '/api/v1/delivery/decisions') return Promise.resolve(res(200, [DECISION]))
        if (url.startsWith('/api/v1/risks')) return Promise.resolve(res(200, { items: [RISK], total: 1, page: 1, page_size: 100 }))
      }
      return Promise.resolve(res(200, {}))
    })
  }

  function renderPage(ui: React.ReactNode, path = '/') {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[path]}>
          <AuthProvider>{ui}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
  }

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    calls.length = 0
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    setAccessToken(null)
  })

  describe('overview', () => {
    it('shows the figures, the attention list and the phases', async () => {
      serve()
      renderPage(<DeliveryOverviewPage />)
      expect(await screen.findByText('Tiến độ thực tế')).toBeInTheDocument()
      expect(screen.getByText('Chậm 18 điểm so với kế hoạch')).toBeInTheDocument()
      expect(screen.getByText('M1')).toBeInTheDocument()
      expect(screen.getByText('Quá hạn 1 ngày · Hoàn thành khảo sát')).toBeInTheDocument()
      expect(screen.getByText('1 trễ/chậm · 2 chưa cập nhật')).toBeInTheDocument()
      expect(screen.getByText('II.2 · Khảo sát hiện trạng')).toBeInTheDocument()
      expect(screen.getByRole('progressbar', { name: 'II Thực tế' })).toHaveAttribute('aria-valuenow', '20')
      expect(screen.getByRole('img', { name: /Đường tiến độ/ })).toBeInTheDocument()
    })

    it('opens the task from the attention list and saves progress', async () => {
      serve()
      renderPage(<DeliveryOverviewPage />)
      await userEvent.click(await screen.findByRole('button', { name: /II\.2 · Khảo sát hiện trạng/ }))
      const dialog = await screen.findByRole('dialog')
      await userEvent.click(within(dialog).getByRole('button', { name: '75%' }))
      await userEvent.click(within(dialog).getByRole('button', { name: 'Lưu' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
      const patch = calls.find((c) => c.method === 'PATCH')!
      expect(patch.url).toBe('/api/v1/delivery/tasks/t2')
      expect(patch.body).toMatchObject({ pct: 75 })
    })

    it('a viewer can read the task but not save it', async () => {
      serve('viewer')
      renderPage(<DeliveryOverviewPage />)
      await userEvent.click(await screen.findByRole('button', { name: /II\.2 · Khảo sát hiện trạng/ }))
      const dialog = await screen.findByRole('dialog')
      expect(within(dialog).queryByRole('button', { name: 'Lưu' })).not.toBeInTheDocument()
      expect(within(dialog).getByLabelText('Phần trăm hoàn thành')).toBeDisabled()
    })
  })

  describe('schedule', () => {
    it('lists the phases and tasks, collapses a phase and hides finished work', async () => {
      serve()
      renderPage(<SchedulePage />)
      expect(await screen.findByRole('button', { name: /II\.2 Khảo sát hiện trạng/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /I\.1 Họp khởi động/ })).toBeInTheDocument()

      await userEvent.click(screen.getByLabelText('Ẩn việc đã hoàn thành'))
      expect(screen.queryByRole('button', { name: /I\.1 Họp khởi động/ })).not.toBeInTheDocument()

      await userEvent.click(screen.getByRole('button', { name: 'Thu gọn II' }))
      expect(screen.queryByRole('button', { name: /II\.2 Khảo sát hiện trạng/ })).not.toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Mở rộng tất cả' }))
      expect(screen.getByRole('button', { name: /II\.2 Khảo sát hiện trạng/ })).toBeInTheDocument()
    })

    it('opens a task with the keyboard', async () => {
      serve()
      renderPage(<SchedulePage />)
      const row = await screen.findByRole('button', { name: /M1 Hoàn thành khảo sát/ })
      row.focus()
      await userEvent.keyboard('{Enter}')
      expect(await screen.findByRole('dialog')).toHaveAccessibleName(/M1 · Hoàn thành khảo sát/)
    })
  })

  describe('weekly reports', () => {
    it('lists the periods with their state', async () => {
      serve()
      renderPage(<WeeklyReportsPage />)
      expect(await screen.findByText('Đã nhận 1/2 kỳ đã kết thúc')).toBeInTheDocument()
      expect(screen.getByText('1 kỳ chưa nhận')).toBeInTheDocument()
    })

    it('records the report of a missing period', async () => {
      serve()
      renderPage(<WeeklyReportsPage />)
      const buttons = await screen.findAllByRole('button', { name: 'Ghi nhận' })
      await userEvent.click(buttons[0])
      const dialog = await screen.findByRole('dialog')
      await userEvent.type(within(dialog).getByLabelText('Số/ký hiệu báo cáo'), 'BC-02')
      await userEvent.type(within(dialog).getByLabelText('Tiến độ thực tế (%)'), '15')
      await userEvent.click(within(dialog).getByRole('button', { name: 'Lưu' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
      const put = calls.find((c) => c.method === 'PUT')!
      expect(put.url).toBe('/api/v1/delivery/reports/2026-10-02')
      expect(put.body).toMatchObject({ report_no: 'BC-02', actual_pct: 15, planned_pct: 30, status: 'received' })
    })

    it('opens the period named in the address', async () => {
      serve()
      renderPage(<WeeklyReportsPage />, '/weekly-reports?week=2026-10-02')
      expect(await screen.findByRole('dialog', { name: 'Báo cáo tuần 2' })).toBeInTheDocument()
    })
  })

  describe('decisions', () => {
    it('lists the open matters with an overdue due date', async () => {
      serve()
      renderPage(<DecisionsPage />)
      expect(await screen.findAllByText('Chốt môi trường triển khai')).not.toHaveLength(0)
      expect(screen.getAllByText('05/10/2026')[0]).toHaveClass('text-danger')
    })

    it('adds a matter', async () => {
      serve()
      renderPage(<DecisionsPage />)
      await userEvent.click(await screen.findByRole('button', { name: 'Thêm việc tồn đọng' }))
      const dialog = await screen.findByRole('dialog')
      await userEvent.type(within(dialog).getByLabelText('Nội dung cần chốt'), 'Chốt phạm vi')
      await userEvent.click(within(dialog).getByRole('button', { name: 'Lưu' }))
      await waitFor(() => expect(calls.some(isWrite('POST'))).toBe(true))
      expect(calls.find(isWrite('POST'))!.body).toMatchObject({ title: 'Chốt phạm vi', status: 'pending' })
    })

    it('a viewer sees the matters but cannot add one', async () => {
      serve('viewer')
      renderPage(<DecisionsPage />)
      await screen.findAllByText('Chốt môi trường triển khai')
      expect(screen.queryByRole('button', { name: 'Thêm việc tồn đọng' })).not.toBeInTheDocument()
    })
  })

  describe('risks', () => {
    it('shows the level a score stands for', async () => {
      serve()
      renderPage(<DeliveryRisksPage />)
      expect(await screen.findAllByText('Rất cao')).not.toHaveLength(0)
      expect(screen.getAllByText('Dữ liệu')[0]).toBeInTheDocument()
    })

    it('adds a risk by level, sent as probability x impact', async () => {
      serve()
      renderPage(<DeliveryRisksPage />)
      await userEvent.click(await screen.findByRole('button', { name: 'Thêm rủi ro' }))
      const dialog = await screen.findByRole('dialog')
      await userEvent.type(within(dialog).getByLabelText('Rủi ro'), 'Chậm bàn giao dữ liệu')
      await userEvent.selectOptions(within(dialog).getByLabelText('Mức ưu tiên'), 'high')
      await userEvent.type(within(dialog).getByLabelText('Nhóm'), 'Tiến độ')
      await userEvent.click(within(dialog).getByRole('button', { name: 'Lưu' }))
      await waitFor(() => expect(calls.some(isWrite('POST'))).toBe(true))
      expect(calls.find(isWrite('POST'))!.body).toMatchObject({
        title: 'Chậm bàn giao dữ liệu',
        group_name: 'Tiến độ',
        category: 'other',
        probability: 4,
        impact: 4,
      })
    })
  })
})

describe('risk levels', () => {
  it.each([
    [25, 'very_high'],
    [20, 'high'],
    [13, 'high'],
    [12, 'medium'],
    [6, 'medium'],
    [5, 'low'],
    [1, 'low'],
  ] as const)('score %i is %s', (score, level) => {
    expect(levelOf(score)).toBe(level)
  })

  it('every level maps to a score that reads back as the same level', () => {
    for (const level of ['very_high', 'high', 'medium', 'low'] as const) {
      const { probability, impact } = scoreOfLevel(level)
      expect(levelOf(probability * impact)).toBe(level)
    }
  })
})
