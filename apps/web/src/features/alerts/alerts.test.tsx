import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { alertLink } from './alertLink'
import { AlertsPage } from './AlertsPage'
import { SwipeRow } from './SwipeRow'
import type { Alert } from './types'

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })

const alert = (over: Partial<Alert> = {}): Alert => ({
  id: 'a1',
  alert_type: 'GUARANTEE_EXPIRING',
  severity: 'warning',
  entity_type: 'guarantee',
  entity_id: 'g1',
  package_id: 'p5',
  package_number: 5,
  title: 'Gói 05: bảo lãnh sắp hết hạn',
  message: 'Bảo lãnh còn 8 ngày hết hạn',
  due_date: '2026-11-13',
  status: 'open',
  assigned_to: null,
  first_seen_at: '2026-11-05T03:00:00Z',
  resolved_at: null,
  acknowledged_by: null,
  acknowledged_at: null,
  snoozed_until: null,
  snooze_reason: null,
  can_snooze: true,
  ...over,
})

const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

describe('alertLink', () => {
  it.each([
    ['GUARANTEE_EXPIRING', '/packages/p?tab=contracts'],
    ['ADVANCE_GUARANTEE_SHORT', '/packages/p?tab=contracts'],
    ['PAYMENT_DUE', '/packages/p?tab=payments'],
    ['PLAN_STEP_OVERDUE', '/packages/p?tab=plan'],
    ['STAGE_DELAYED', '/packages/p?tab=progress'],
    ['PROGRESS_BEHIND', '/packages/p?tab=progress'],
    ['DOC_MISSING', '/packages/p?tab=documents'],
    ['ISSUE_SLA', '/issues'],
    ['DAILY_LOG_MISSING', '/daily-log'],
    ['REPORT_DUE', '/progress'],
    ['CROSS_PKG_DEPENDENCY', '/packages/p'],
  ])('%s opens %s', (alert_type, to) => {
    expect(alertLink({ alert_type, entity_type: 'x', package_id: 'p' })).toBe(to)
  })

  it('falls back to list pages without a package', () => {
    expect(alertLink({ alert_type: 'GUARANTEE_MISSING', entity_type: 'x', package_id: null })).toBe('/contracts')
    expect(alertLink({ alert_type: 'WHATEVER', entity_type: 'x', package_id: null })).toBe('/alerts')
  })
})

describe('SwipeRow', () => {
  const swipe = (el: HTMLElement, from: number, to: number) => {
    fireEvent.pointerDown(el, { pointerType: 'touch', clientX: from, clientY: 0 })
    fireEvent.pointerMove(el, { pointerType: 'touch', clientX: to, clientY: 0 })
    fireEvent.pointerUp(el, { pointerType: 'touch', clientX: to, clientY: 0 })
  }

  it('left swipe past the threshold fires onSwipeLeft, right fires onSwipeRight', () => {
    const left = vi.fn()
    const right = vi.fn()
    render(<SwipeRow onSwipeLeft={left} onSwipeRight={right}>x</SwipeRow>)
    const el = screen.getByTestId('swipe-row')
    swipe(el, 200, 100)
    expect(left).toHaveBeenCalledTimes(1)
    swipe(el, 100, 200)
    expect(right).toHaveBeenCalledTimes(1)
  })

  it('short, vertical and mouse gestures do nothing', () => {
    const left = vi.fn()
    render(<SwipeRow onSwipeLeft={left}>x</SwipeRow>)
    const el = screen.getByTestId('swipe-row')
    swipe(el, 200, 150)
    fireEvent.pointerDown(el, { pointerType: 'touch', clientX: 200, clientY: 0 })
    fireEvent.pointerMove(el, { pointerType: 'touch', clientX: 100, clientY: 300 })
    fireEvent.pointerUp(el, { pointerType: 'touch' })
    fireEvent.pointerDown(el, { pointerType: 'mouse', clientX: 200, clientY: 0 })
    fireEvent.pointerMove(el, { pointerType: 'mouse', clientX: 50, clientY: 0 })
    fireEvent.pointerUp(el, { pointerType: 'mouse' })
    expect(left).not.toHaveBeenCalled()
  })
})

describe('AlertsPage', () => {
  const fetchMock = vi.fn()
  const calls: { url: string; method: string; body?: string }[] = []

  function serve(role: string, items: Alert[], extra?: (url: string, init?: RequestInit) => Response | null) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? 'GET', body: init?.body as string | undefined })
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me(role)))
      const custom = extra?.(url, init)
      if (custom) return Promise.resolve(custom)
      if (url.startsWith('/api/v1/alerts?')) return Promise.resolve(res(200, { items, total: items.length, page: 1, page_size: 100 }))
      return Promise.resolve(res(200, {}))
    })
  }
  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <AlertsPage />
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

  it('shows severity in words, the message, due date and a link to the source', async () => {
    serve('viewer', [alert(), alert({ id: 'a2', severity: 'critical', title: 'Thiếu bảo lãnh', can_snooze: false })])
    wrap()
    expect(await screen.findByText('Gói 05: bảo lãnh sắp hết hạn')).toBeInTheDocument()
    // each severity appears as a filter chip and as a badge on its card
    expect(screen.getAllByText('Nghiêm trọng')).toHaveLength(2)
    expect(screen.getAllByText('Cần chú ý')).toHaveLength(2)
    expect(screen.getAllByRole('link', { name: 'Mở' })[0]).toHaveAttribute('href', '/packages/p5?tab=contracts')
    expect(screen.getAllByText(/Hạn 13\/11\/2026/).length).toBeGreaterThan(0)
  })

  it('viewers get no action buttons', async () => {
    serve('viewer', [alert()])
    wrap()
    await screen.findByText('Gói 05: bảo lãnh sắp hết hạn')
    expect(screen.queryByRole('button', { name: 'Xác nhận' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Hoãn' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Kiểm tra lại ngay' })).not.toBeInTheDocument()
  })

  it('acknowledges an alert', async () => {
    serve('technical', [alert()])
    wrap()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Xác nhận' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url === '/api/v1/alerts/a1/ack')).toBe(true))
  })

  it('critical alerts have no snooze button and swiping right explains why', async () => {
    serve('technical', [alert({ id: 'c', severity: 'critical', can_snooze: false })])
    wrap()
    await screen.findByText('Gói 05: bảo lãnh sắp hết hạn')
    expect(screen.queryByRole('button', { name: 'Hoãn' })).not.toBeInTheDocument()
    const row = screen.getByTestId('swipe-row')
    fireEvent.pointerDown(row, { pointerType: 'touch', clientX: 0, clientY: 0 })
    fireEvent.pointerMove(row, { pointerType: 'touch', clientX: 120, clientY: 0 })
    fireEvent.pointerUp(row, { pointerType: 'touch' })
    expect(await screen.findByRole('alert')).toHaveTextContent('Cảnh báo nghiêm trọng không thể hoãn')
  })

  it('snoozes a warning with days and a reason', async () => {
    serve('director', [alert()])
    wrap()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Hoãn' }))
    const dialog = await screen.findByRole('dialog', { name: 'Hoãn cảnh báo' })
    const days = dialog.querySelector('input[type=number]') as HTMLInputElement
    await user.clear(days)
    await user.type(days, '9')
    expect(days.value).toBe('7') // capped at 7
    expect(dialog.querySelector('button[type=submit]')).toBeDisabled() // reason required
    await user.type(dialog.querySelector('textarea') as HTMLTextAreaElement, 'Chờ phản hồi')
    await user.click(dialog.querySelector('button[type=submit]') as HTMLButtonElement)
    await waitFor(() => {
      const post = calls.find((c) => c.url === '/api/v1/alerts/a1/snooze')
      expect(JSON.parse(post?.body ?? '{}')).toEqual({ days: 7, reason: 'Chờ phản hồi' })
    })
  })

  it('assigns to me and back', async () => {
    serve('technical', [alert({ assigned_to: 'me' })])
    wrap()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Bỏ giao' }))
    await waitFor(() => {
      const patch = calls.find((c) => c.method === 'PATCH')
      expect(JSON.parse(patch?.body ?? '{}')).toEqual({ assigned_to: null })
    })
  })

  it('history toggle asks for all statuses and resolved alerts have no actions', async () => {
    serve('director', [alert({ status: 'resolved' })])
    wrap()
    await screen.findByText('Gói 05: bảo lãnh sắp hết hạn')
    expect(screen.queryByRole('button', { name: 'Xác nhận' })).not.toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('checkbox', { name: 'Cả cảnh báo đã đóng' }))
    await waitFor(() => expect(calls.some((c) => c.url.includes('status=all'))).toBe(true))
  })

  it('severity chips filter and the refresh button is for admin and director', async () => {
    serve('director', [alert()], (url) => (url === '/api/v1/alerts/refresh' ? res(200, { created: 2, resolved: 1 }) : null))
    wrap()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Nghiêm trọng' }))
    await waitFor(() => expect(calls.some((c) => c.url.includes('severity=critical'))).toBe(true))
    await user.click(screen.getByRole('button', { name: 'Kiểm tra lại ngay' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Đã kiểm tra: 2 mới, 1 đã đóng')
  })

  it('says so when there is nothing open', async () => {
    serve('viewer', [])
    wrap()
    expect(await screen.findByText('Không có cảnh báo nào đang mở')).toBeInTheDocument()
  })
})
