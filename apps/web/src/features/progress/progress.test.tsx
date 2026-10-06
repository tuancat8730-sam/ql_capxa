import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { Gantt } from './Gantt'
import { ProgressPage } from './ProgressPage'
import { StagesTab } from './StagesTab'
import type { Stages, Task, Timeline } from './types'

const res = (status: number, body?: unknown, headers?: Record<string, string>) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers })

const timeline: Timeline = {
  today: '2026-10-06',
  range_start: '2026-07-20',
  range_end: '2027-01-22',
  packages: [
    {
      id: 'p4',
      number: 4,
      name: 'Gói thầu số 04',
      health: 'grey',
      progress_pct: 20,
      contract: { contract_no: '71', start: '2026-09-14', end: '2026-11-13', end_date_override: false, extended_end_date: null },
      stages: [
        { id: 's2', stage_code: 'S2_SELECTION', name: 'Lựa chọn nhà thầu', planned_start: null, planned_end: null, actual_start: null, actual_end: null, progress_pct: 100, effective_status: 'done' },
        { id: 's3', stage_code: 'S3_EXECUTION', name: 'Thực hiện hợp đồng', planned_start: '2026-09-14', planned_end: '2026-11-13', actual_start: '2026-09-15', actual_end: null, progress_pct: 40, effective_status: 'in_progress' },
      ],
    },
    {
      id: 'p1',
      number: 1,
      name: 'Gói thầu số 01',
      health: 'red',
      progress_pct: 20,
      contract: null,
      stages: [
        { id: 'u3', stage_code: 'S3_EXECUTION', name: 'Thực hiện hợp đồng', planned_start: '2026-07-20', planned_end: '2026-09-18', actual_start: null, actual_end: null, progress_pct: 0, effective_status: 'delayed' },
      ],
    },
  ],
}

const user = (role: string) => ({
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

describe('Gantt', () => {
  it('draws a bar per dated stage with a text label, plus the today and contract-end markers', () => {
    render(<Gantt timeline={timeline} zoom="month" editable={false} onChangeStage={() => undefined} />)
    expect(screen.getByRole('img', { name: 'Dòng thời gian các gói' })).toBeInTheDocument()
    expect(screen.getByTestId('bar-s3')).toHaveAttribute('aria-label', 'Gói 04 – Thực hiện hợp đồng: 14/09/2026 đến 13/11/2026')
    expect(screen.queryByTestId('bar-s2')).not.toBeInTheDocument() // no planned dates: nothing to draw
    expect(screen.getByText(/Hôm nay: 06\/10\/2026/)).toBeInTheDocument()
    expect(screen.getByText(/Hết hạn hợp đồng: 13\/11\/2026/)).toBeInTheDocument()
    expect(screen.queryByTestId('handle-end-s3')).not.toBeInTheDocument() // read-only: no drag handles
  })

  it('moves a bar with the arrow keys and resizes it with Shift', () => {
    const onChange = vi.fn()
    render(<Gantt timeline={timeline} zoom="week" editable onChangeStage={onChange} />)
    const bar = screen.getByTestId('bar-s3')
    fireEvent.keyDown(bar, { key: 'ArrowRight' })
    expect(onChange).toHaveBeenLastCalledWith('s3', { planned_start: '2026-09-15', planned_end: '2026-11-14' })
    fireEvent.keyDown(bar, { key: 'ArrowLeft' })
    expect(onChange).toHaveBeenLastCalledWith('s3', { planned_start: '2026-09-13', planned_end: '2026-11-12' })
    fireEvent.keyDown(bar, { key: 'ArrowRight', shiftKey: true })
    expect(onChange).toHaveBeenLastCalledWith('s3', { planned_start: '2026-09-14', planned_end: '2026-11-14' })
    fireEvent.keyDown(bar, { key: 'Enter' })
    expect(onChange).toHaveBeenCalledTimes(3)
  })

  it('ignores keys when read-only', () => {
    const onChange = vi.fn()
    render(<Gantt timeline={timeline} zoom="month" editable={false} onChangeStage={onChange} />)
    fireEvent.keyDown(screen.getByTestId('bar-s3'), { key: 'ArrowRight' })
    expect(onChange).not.toHaveBeenCalled()
  })

  it('drags a bar sideways: 12 px per day when zoomed to weeks', () => {
    const onChange = vi.fn()
    render(<Gantt timeline={timeline} zoom="week" editable onChangeStage={onChange} />)
    const bar = screen.getByTestId('bar-s3')
    fireEvent.pointerDown(bar, { clientX: 100, pointerId: 1 })
    fireEvent.pointerMove(bar, { clientX: 136, pointerId: 1 }) // +36 px = +3 days
    fireEvent.pointerUp(bar, { clientX: 136, pointerId: 1 })
    expect(onChange).toHaveBeenCalledWith('s3', { planned_start: '2026-09-17', planned_end: '2026-11-16' })
  })

  it('dragging the end handle changes only the end date; a click without movement changes nothing', () => {
    const onChange = vi.fn()
    render(<Gantt timeline={timeline} zoom="week" editable onChangeStage={onChange} />)
    const handle = screen.getByTestId('handle-end-s3')
    fireEvent.pointerDown(handle, { clientX: 500, pointerId: 1 })
    fireEvent.pointerMove(handle, { clientX: 464, pointerId: 1 }) // -3 days
    fireEvent.pointerUp(handle, { clientX: 464, pointerId: 1 })
    expect(onChange).toHaveBeenCalledWith('s3', { planned_start: '2026-09-14', planned_end: '2026-11-10' })
    onChange.mockClear()
    const bar = screen.getByTestId('bar-s3')
    fireEvent.pointerDown(bar, { clientX: 50, pointerId: 1 })
    fireEvent.pointerUp(bar, { clientX: 50, pointerId: 1 })
    expect(onChange).not.toHaveBeenCalled()
  })
})

describe('progress screens', () => {
  const fetchMock = vi.fn()

  function serve(role: string, handler: (url: string, init?: RequestInit) => Response | null) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, user(role)))
      return Promise.resolve(handler(url, init) ?? res(404, { error: { code: 'not_found', message: 'x' } }))
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

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('/progress lists packages with stage status in words, and the Gantt for writers', async () => {
    serve('technical', (url) => (url === '/api/v1/dashboard/timeline' ? res(200, timeline) : null))
    wrap(<ProgressPage />)
    const list = await screen.findByLabelText('Dòng thời gian các gói', { selector: 'div' })
    expect(within(list).getByText(/Gói 04 · Gói thầu số 04/)).toBeInTheDocument()
    expect(within(list).getByText('Chậm')).toBeInTheDocument() // delayed stage of package 1: icon + text
    expect(within(list).getByText('Hoàn thành')).toBeInTheDocument()
    expect(within(list).getByText(/14\/09\/2026 – 13\/11\/2026 · 40%/)).toBeInTheDocument()
    expect(within(list).getByText(/Chưa có ngày kế hoạch · 100%/)).toBeInTheDocument()
    expect(screen.getByText(/Kéo thanh để đổi ngày/)).toBeInTheDocument()
  })

  it('/progress: a Gantt edit is sent as a PATCH on the stage', async () => {
    serve('director', (url, init) => {
      if (url === '/api/v1/dashboard/timeline') return res(200, timeline)
      if (url === '/api/v1/stage-plans/s3' && init?.method === 'PATCH') return res(200, {})
      return null
    })
    wrap(<ProgressPage />)
    const bar = await screen.findByTestId('bar-s3')
    fireEvent.keyDown(bar, { key: 'ArrowRight' })
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/v1/stage-plans/s3' && i?.method === 'PATCH')).toBe(true))
    const patch = fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/stage-plans/s3' && i?.method === 'PATCH')!
    expect(JSON.parse(patch[1].body)).toEqual({ planned_start: '2026-09-15', planned_end: '2026-11-14' })
  })

  it('/progress: viewers get no drag hint and cannot edit', async () => {
    serve('viewer', (url) => (url === '/api/v1/dashboard/timeline' ? res(200, timeline) : null))
    wrap(<ProgressPage />)
    await screen.findByTestId('bar-s3')
    expect(screen.queryByText(/Kéo thanh để đổi ngày/)).not.toBeInTheDocument()
    expect(screen.queryByTestId('handle-end-s3')).not.toBeInTheDocument()
  })

  it('/progress: exports QL-06 as a download with the server file name', async () => {
    serve('viewer', (url) => {
      if (url === '/api/v1/dashboard/timeline') return res(200, timeline)
      if (url === '/api/v1/export/ql06.xlsx') {
        return new Response(new Blob(['xlsx']), {
          status: 200,
          headers: { 'Content-Disposition': `attachment; filename="QL-06-20261006.xlsx"; filename*=UTF-8''QL-06-20261006.xlsx` },
        })
      }
      return null
    })
    const createUrl = vi.fn(() => 'blob:x')
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() }))
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    wrap(<ProgressPage />)
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Xuất QL-06 (Excel)' }))
    await waitFor(() => expect(click).toHaveBeenCalled())
    expect(createUrl).toHaveBeenCalled()
    const call = fetchMock.mock.calls.find(([u]) => u === '/api/v1/export/ql06.xlsx')!
    expect(call[1].headers.Authorization).toBe('Bearer t')
  })

  const stages: Stages = {
    package_progress: 20,
    current_stage: 'S3_EXECUTION',
    stages: [
      { id: 's2', package_id: 'p4', stage_code: 'S2_SELECTION', name: 'Lựa chọn nhà thầu', planned_start: null, planned_end: null, actual_start: null, actual_end: null, progress_pct: 100, weight: 20, status: 'done', effective_status: 'done', notes: null, task_count: 0, tasks_done: 0 },
      { id: 's3', package_id: 'p4', stage_code: 'S3_EXECUTION', name: 'Thực hiện hợp đồng', planned_start: '2026-09-14', planned_end: '2026-11-13', actual_start: null, actual_end: null, progress_pct: 0, weight: 40, status: 'not_started', effective_status: 'not_started', notes: null, task_count: 2, tasks_done: 1 },
    ],
  }
  const task = (over: Partial<Task> = {}): Task => ({
    id: 't1', package_id: 'p4', stage_plan_id: 's3', title: 'Lắp đặt', status: 'doing', priority: 'normal', planned_end: '2026-10-30', weight: 1, stage_all_done: false, ...over,
  })

  it('package progress tab shows weighted progress and stage cards; writers can edit a stage', async () => {
    serve('technical', (url, init) => {
      if (url === '/api/v1/packages/p4/stages') return res(200, stages)
      if (url === '/api/v1/packages/p4/tasks') return res(200, [])
      if (url === '/api/v1/stage-plans/s3' && init?.method === 'PATCH') return res(200, {})
      return null
    })
    wrap(<StagesTab packageId="p4" />)
    expect(await screen.findByText('Tiến độ gói: 20%')).toBeInTheDocument()
    const s3 = (await screen.findByText('Thực hiện hợp đồng')).closest('li')!
    expect(within(s3).getByText(/14\/09\/2026 – 13\/11\/2026/)).toBeInTheDocument()
    expect(within(s3).getByText(/1\/2 đầu việc/)).toBeInTheDocument()
    const user = userEvent.setup()
    await user.click(within(s3).getByRole('button', { name: 'Sửa giai đoạn' }))
    const dialog = await screen.findByRole('dialog', { name: /Sửa giai đoạn: Thực hiện hợp đồng/ })
    fireEvent.change(within(dialog).getByLabelText('Hoàn thành (%)'), { target: { value: '50' } })
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/v1/stage-plans/s3' && i?.method === 'PATCH')).toBe(true))
    const body = JSON.parse(fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/stage-plans/s3' && i?.method === 'PATCH')![1].body)
    expect(body).toMatchObject({ progress_pct: 50, planned_start: '2026-09-14', planned_end: '2026-11-13', status: 'not_started' })
  })

  it('read-only roles cannot edit stages or tasks', async () => {
    serve('viewer', (url) => {
      if (url === '/api/v1/packages/p4/stages') return res(200, stages)
      if (url === '/api/v1/packages/p4/tasks') return res(200, [task()])
      return null
    })
    wrap(<StagesTab packageId="p4" />)
    await screen.findByText('Lắp đặt')
    expect(screen.queryByRole('button', { name: 'Sửa giai đoạn' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Thêm đầu việc' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: /Trạng thái: Lắp đặt/ })).not.toBeInTheDocument()
  })

  it('finishing the last task only suggests closing the stage; the user confirms', async () => {
    serve('technical', (url, init) => {
      if (url === '/api/v1/packages/p4/stages') return res(200, stages)
      if (url === '/api/v1/packages/p4/tasks') return res(200, [task()])
      if (url === '/api/v1/tasks/t1' && init?.method === 'PATCH') return res(200, task({ status: 'done', stage_all_done: true }))
      if (url === '/api/v1/stage-plans/s3' && init?.method === 'PATCH') return res(200, {})
      return null
    })
    wrap(<StagesTab packageId="p4" />)
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByRole('combobox', { name: /Trạng thái: Lắp đặt/ }), 'done')
    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('Tất cả đầu việc của giai đoạn đã xong')
    expect(fetchMock.mock.calls.some(([u]) => u === '/api/v1/stage-plans/s3')).toBe(false) // nothing closed yet
    await user.click(within(banner).getByRole('button', { name: 'Đánh dấu hoàn thành' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/v1/stage-plans/s3' && i?.method === 'PATCH')).toBe(true))
    expect(JSON.parse(fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/stage-plans/s3' && i?.method === 'PATCH')![1].body)).toEqual({ status: 'done' })
  })

  it('"later" dismisses the suggestion without touching the stage', async () => {
    serve('technical', (url, init) => {
      if (url === '/api/v1/packages/p4/stages') return res(200, stages)
      if (url === '/api/v1/packages/p4/tasks') return res(200, [task()])
      if (url === '/api/v1/tasks/t1' && init?.method === 'PATCH') return res(200, task({ status: 'done', stage_all_done: true }))
      return null
    })
    wrap(<StagesTab packageId="p4" />)
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByRole('combobox', { name: /Trạng thái: Lắp đặt/ }), 'done')
    await user.click(within(await screen.findByRole('alert')).getByRole('button', { name: 'Để sau' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u]) => u === '/api/v1/stage-plans/s3')).toBe(false)
  })

  it('adds a task through the sheet with the chosen stage and priority', async () => {
    serve('onsite', (url, init) => {
      if (url === '/api/v1/packages/p4/stages') return res(200, stages)
      if (url === '/api/v1/packages/p4/tasks' && init?.method === 'POST') return res(201, task())
      if (url === '/api/v1/packages/p4/tasks') return res(200, [])
      return null
    })
    wrap(<StagesTab packageId="p4" />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Thêm đầu việc' }))
    const dialog = await screen.findByRole('dialog', { name: 'Thêm đầu việc' })
    await user.type(within(dialog).getByLabelText('Tên đầu việc'), 'Kiểm tra mặt bằng')
    await user.selectOptions(within(dialog).getByLabelText('Giai đoạn'), 's3')
    await user.selectOptions(within(dialog).getByLabelText('Ưu tiên'), 'high')
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/v1/packages/p4/tasks' && i?.method === 'POST')).toBe(true))
    const body = JSON.parse(fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/packages/p4/tasks' && i?.method === 'POST')![1].body)
    expect(body).toEqual({ title: 'Kiểm tra mặt bằng', stage_plan_id: 's3', priority: 'high', planned_end: null })
  })
})
