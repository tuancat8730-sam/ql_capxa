import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { ConstructionLogDetailPage } from './ConstructionLogDetailPage'
import { ConstructionLogPage } from './ConstructionLogPage'
import { shownCode, splitNames, storedCode, weekdayOf, weekDays } from './logMeta'
import type { ConstructionLog, LogHistoryItem, LogWeek } from './logTypes'
import { TaskLogHistory } from './TaskLogHistory'
import type { Task } from './types'

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })

const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

const task = (over: Partial<Task>): Task => ({
  id: 't1', code: 'II.1', phase_code: 'II', phase_name: 'Khảo sát, thu thập và phân tích yêu cầu',
  name: 'Lập kế hoạch khảo sát', is_milestone: false, plan_start: '2026-09-28', plan_end: '2026-09-30',
  plan_days: 3, tracked: false, status: 'not_started', pct: 0, actual_start: null, actual_end: null,
  note: null, updated_at: '2026-10-08T00:00:00Z', state: 'stale', late_days: 0, ...over,
})

const TASKS: Task[] = [
  task({ id: 't0', code: 'I.1', phase_code: 'I', phase_name: 'Khởi động gói thầu', name: 'Họp khởi động' }),
  task({ id: 't1' }),
  task({ id: 't2', code: 'M1', name: 'Hoàn thành khảo sát', is_milestone: true, plan_days: 0 }),
]

const WEEKS: LogWeek[] = [
  { no: 1, week_start: '2026-09-25', week_end: '2026-10-01', has_log: true, has_report: true, report_date: '2026-10-02', entry_count: 2, max_delay_days: 1 },
  { no: 2, week_start: '2026-10-02', week_end: '2026-10-08', has_log: false, has_report: false, report_date: null, entry_count: 0, max_delay_days: 0 },
]

const LOG: ConstructionLog = {
  id: 'l1', week_start: '2026-09-25', week_end: '2026-10-01', report_date: '2026-10-02',
  recipients: 'Sở GD&ĐT TP.HCM (CĐT)', reporter_org: 'Liên danh DVN', contract_ref: 'Số 29/HĐKT-DVN',
  coordinator: 'Nguyễn Thị Thúy Hiệp', environment_note: null, overall_status: 'Bám sát tiến độ',
  key_results: 'Đang phân tích yêu cầu', issues: 'Chưa có đầu mối', coordination_requests: '- Ban hành kế hoạch',
  related_report: 'BC tuần 25/9 – 01/10',
  entries: [
    { id: 'e1', entry_date: '2026-09-25', phase_code: 'I', task_code: 'I-1', content: 'Họp khởi động xong', personnel: [], note: 'Cần CĐT xác nhận', state: 'done', delay_days: null },
    { id: 'e2', entry_date: '2026-09-28', phase_code: 'II', task_code: 'II-1', content: 'Lập kế hoạch khảo sát', personnel: ['Nguyễn Duy Khánh'], note: null, state: 'in_progress', delay_days: 1 },
  ],
  carryovers: [
    { id: 'c1', phase_code: 'I', task_code: 'I-1', title: 'Kế hoạch chi tiết', result_to_date: 'Đã gửi, chờ CĐT', next_week: 'Tiếp nhận ý kiến', note: null },
  ],
  member_work: [
    { id: 'm1', member_name: 'VietFuture', item: 'Mô-đun Quản lý mã định danh', plan_ref: '5.4', personnel: ['Đỗ Ngọc Khánh'], result: 'Đang thực hiện', next_plan: null, issues_actions: null },
  ],
  updated_at: '2026-10-02T03:00:00.123456Z',
}

const HISTORY: LogHistoryItem[] = [
  { week_start: '2026-09-25', entry_date: '2026-09-28', content: 'Lập kế hoạch khảo sát', note: 'Chậm 01 ngày', state: 'in_progress', delay_days: 1, personnel: [] },
  { week_start: '2026-10-09', entry_date: '2026-10-14', content: 'Đã gửi CĐT kế hoạch', note: null, state: null, delay_days: null, personnel: [] },
]

describe('construction log', () => {
  const fetchMock = vi.fn()
  const calls: { url: string; method: string; body: any }[] = [] // eslint-disable-line @typescript-eslint/no-explicit-any
  let putResponse: () => Response

  function serve(role = 'director') {
    putResponse = () => res(200, LOG)
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      if (url === '/api/v1/auth/refresh') return Promise.resolve(res(200, { access_token: 't' }))
      if (url === '/api/v1/auth/me') return Promise.resolve(res(200, me(role)))
      if (method === 'PUT') return Promise.resolve(putResponse())
      if (method === 'GET') {
        if (url === '/api/v1/delivery/logs') return Promise.resolve(res(200, WEEKS))
        if (url === '/api/v1/delivery/logs/2026-09-25') return Promise.resolve(res(200, LOG))
        if (url === '/api/v1/delivery/logs/2026-10-02')
          return Promise.resolve(res(404, { error: { code: 'not_found', message: 'Chưa có nhật ký cho tuần này' } }))
        if (url === '/api/v1/delivery/tasks') return Promise.resolve(res(200, TASKS))
        if (url === '/api/v1/delivery/tasks/II-1/log-history') return Promise.resolve(res(200, HISTORY))
      }
      return Promise.resolve(res(200, {}))
    })
  }

  function renderAt(path: string) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[path]}>
          <AuthProvider>
            <Routes>
              <Route path="/construction-log" element={<ConstructionLogPage />} />
              <Route path="/construction-log/:week" element={<ConstructionLogDetailPage />} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
  }

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    calls.length = 0
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    setAccessToken(null)
  })

  describe('week list', () => {
    it('shows which weeks have a log and links to them', async () => {
      serve()
      renderAt('/construction-log')
      expect(await screen.findByText('Đã có nhật ký 1/2 tuần')).toBeInTheDocument()
      const open = screen.getAllByRole('link', { name: 'Mở' })
      expect(open[0]).toHaveAttribute('href', '/construction-log/2026-09-25')
      const create = screen.getAllByRole('link', { name: 'Tạo nhật ký' })
      expect(create[0]).toHaveAttribute('href', '/construction-log/2026-10-02')
      expect(screen.getAllByText('Chậm 1 ngày').length).toBeGreaterThan(0)
    })

    it('does not offer a viewer to create a log', async () => {
      serve('viewer')
      renderAt('/construction-log')
      await screen.findByText('Đã có nhật ký 1/2 tuần')
      expect(screen.queryByRole('link', { name: 'Tạo nhật ký' })).not.toBeInTheDocument()
      expect(screen.getAllByRole('link', { name: 'Mở' }).length).toBeGreaterThan(0)
    })
  })

  describe('one week', () => {
    it('reads the log day by day', async () => {
      serve()
      renderAt('/construction-log/2026-09-25')
      expect(await screen.findByText('Họp khởi động xong')).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Thứ Sáu 25/09' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'Thứ Bảy 26/09' })).toBeInTheDocument()
      expect(screen.getAllByText('Không có hoạt động.').length).toBeGreaterThanOrEqual(2)
      expect(screen.getByText('II.1')).toBeInTheDocument()
      expect(screen.getByText('Chậm 1 ngày')).toBeInTheDocument()
      expect(screen.getByText('Cần CĐT xác nhận')).toBeInTheDocument()
      expect(screen.getByText('Bám sát tiến độ')).toBeInTheDocument()
      expect(screen.getByText('Kế hoạch chi tiết')).toBeInTheDocument()
      expect(screen.getByRole('region', { name: 'III. Phần việc của thành viên liên danh' })).toHaveTextContent('VietFuture')
    })

    it('says so when the date is not a reporting week', async () => {
      serve()
      renderAt('/construction-log/2026-09-26')
      expect(await screen.findByRole('alert')).toHaveTextContent('Không có kỳ báo cáo bắt đầu ngày này')
    })

    it('does not offer a viewer the edit button', async () => {
      serve('viewer')
      renderAt('/construction-log/2026-09-25')
      await screen.findByText('Họp khởi động xong')
      expect(screen.queryByRole('button', { name: 'Sửa nhật ký' })).not.toBeInTheDocument()
    })

    it('saves a corrected line together with the version it was loaded at', async () => {
      serve()
      renderAt('/construction-log/2026-09-25')
      await userEvent.click(await screen.findByRole('button', { name: 'Sửa nhật ký' }))
      const contents = await screen.findAllByLabelText('Nội dung và kết quả')
      await userEvent.type(contents[0], ' (đã xác nhận)')
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
      const put = calls.find((c) => c.method === 'PUT')!
      expect(put.url).toBe('/api/v1/delivery/logs/2026-09-25')
      expect(put.body.expected_updated_at).toBe(LOG.updated_at)
      expect(put.body.entries).toHaveLength(2)
      expect(put.body.entries[0]).toMatchObject({
        entry_date: '2026-09-25', phase_code: 'I', task_code: 'I-1', content: 'Họp khởi động xong (đã xác nhận)', state: 'done',
      })
      expect(put.body.entries[1]).toMatchObject({ personnel: ['Nguyễn Duy Khánh'], delay_days: 1 })
      expect(put.body.member_work[0]).toMatchObject({ member_name: 'VietFuture', personnel: ['Đỗ Ngọc Khánh'] })
      await waitFor(() => expect(screen.queryByRole('button', { name: 'Lưu' })).not.toBeInTheDocument())
    })

    it('starts a log for a week that has none', async () => {
      serve()
      renderAt('/construction-log/2026-10-02')
      expect(await screen.findByText('Tuần này chưa có nhật ký.')).toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Tạo nhật ký' }))
      await userEvent.click(await screen.findByRole('button', { name: 'Thêm dòng diễn biến' }))
      await userEvent.type(screen.getByLabelText('Nội dung và kết quả'), 'Khảo sát tại trường A')
      await userEvent.type(screen.getByLabelText('Nhân sự'), 'An, Bình')
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
      const put = calls.find((c) => c.method === 'PUT')!
      expect(put.url).toBe('/api/v1/delivery/logs/2026-10-02')
      expect(put.body.expected_updated_at).toBeNull()
      expect(put.body.entries).toEqual([
        {
          entry_date: '2026-10-02', phase_code: 'I', task_code: null, content: 'Khảo sát tại trường A',
          personnel: ['An', 'Bình'], note: null, state: null, delay_days: null,
        },
      ])
    })

    it('does not send a line without content', async () => {
      serve()
      renderAt('/construction-log/2026-10-02')
      await userEvent.click(await screen.findByRole('button', { name: 'Tạo nhật ký' }))
      await userEvent.click(await screen.findByRole('button', { name: 'Thêm dòng diễn biến' }))
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('Mỗi dòng phải có nội dung')
      expect(calls.some((c) => c.method === 'PUT')).toBe(false)
    })

    it('offers to reload when someone else saved first', async () => {
      serve()
      putResponse = () => res(409, { error: { code: 'log_changed', message: 'Nhật ký đã được người khác sửa' } })
      renderAt('/construction-log/2026-09-25')
      await userEvent.click(await screen.findByRole('button', { name: 'Sửa nhật ký' }))
      await userEvent.click(await screen.findByRole('button', { name: 'Lưu' }))
      const alert = await screen.findByText(/vừa được người khác sửa/)
      expect(alert).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Tải lại' })).toBeInTheDocument()
    })

    it('removes a line and keeps the order of the others', async () => {
      serve()
      renderAt('/construction-log/2026-09-25')
      await userEvent.click(await screen.findByRole('button', { name: 'Sửa nhật ký' }))
      await userEvent.click(await screen.findByRole('button', { name: 'Xóa Dòng diễn biến 1' }))
      await userEvent.click(screen.getByRole('button', { name: 'Lưu' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
      const put = calls.find((c) => c.method === 'PUT')!
      expect(put.body.entries.map((e: { task_code: string }) => e.task_code)).toEqual(['II-1'])
    })
  })

  describe('task history', () => {
    it('lists what the log said about the task, newest first', async () => {
      serve()
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      render(
        <QueryClientProvider client={qc}>
          <MemoryRouter>
            <AuthProvider>
              <TaskLogHistory task={task({})} />
            </AuthProvider>
          </MemoryRouter>
        </QueryClientProvider>,
      )
      const region = await screen.findByRole('region', { name: 'Nhật ký thi công' })
      const items = within(region).getAllByRole('listitem')
      expect(items[0]).toHaveTextContent('Đã gửi CĐT kế hoạch')
      expect(items[1]).toHaveTextContent('Chậm 1 ngày')
      expect(within(items[1]).getByRole('link', { name: '28/09' })).toHaveAttribute('href', '/construction-log/2026-09-25')
    })
  })

  describe('helpers', () => {
    it('shows and stores task codes the way the schedule does', () => {
      expect(storedCode(task({ code: 'III.4' }))).toBe('III-4')
      expect(storedCode(task({ code: 'M3', is_milestone: true }))).toBe('M3')
      expect(shownCode('III-4')).toBe('III.4')
      expect(shownCode('M3')).toBe('M3')
    })

    it('lists the 7 days of a week starting on Friday', () => {
      const days = weekDays('2026-09-25')
      expect(days).toHaveLength(7)
      expect(days[0]).toBe('2026-09-25')
      expect(days[6]).toBe('2026-10-01')
      expect(weekdayOf('2026-09-25')).toBe(5)
      expect(weekdayOf('2026-09-27')).toBe(0)
    })

    it('splits names on commas and new lines', () => {
      expect(splitNames('An, Bình\n Chi ,, ')).toEqual(['An', 'Bình', 'Chi'])
    })
  })
})
