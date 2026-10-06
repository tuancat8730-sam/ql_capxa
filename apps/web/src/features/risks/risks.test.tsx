import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { RiskForm } from './RiskForm'
import { RiskMatrix } from './RiskMatrix'
import { RisksPage } from './RisksPage'
import { levelOf, type Matrix, type Risk } from './types'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const matrix: Matrix = {
  total: 3,
  cells: [
    { probability: 5, impact: 4, count: 1, risk_ids: ['a'] },
    { probability: 3, impact: 4, count: 2, risk_ids: ['b', 'c'] },
  ],
}

const risk = (over: Partial<Risk> = {}): Risk => ({
  id: 'r1',
  code: 'R-001',
  package_id: null,
  title: 'Gói 03 chậm ký hợp đồng',
  description: null,
  category: 'schedule',
  probability: 4,
  impact: 5,
  score: 20,
  level: 'high',
  mitigation: null,
  contingency: null,
  status: 'open',
  due_date: null,
  last_reviewed_at: null,
  needs_review: false,
  ...over,
})

const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

describe('levelOf', () => {
  it.each([[1, 'low'], [5, 'low'], [6, 'medium'], [12, 'medium'], [13, 'high'], [25, 'high']] as const)(
    'score %i is %s',
    (score, level) => expect(levelOf(score)).toBe(level),
  )
})

describe('RiskMatrix', () => {
  it('renders a 5x5 grid with counts and the score in every cell, level legend in words', () => {
    render(<RiskMatrix matrix={matrix} selected={null} onSelect={() => undefined} />)
    expect(screen.getAllByRole('gridcell')).toHaveLength(25)
    const cell = screen.getByRole('gridcell', { name: 'Xác suất 3, tác động 4: 2 rủi ro' })
    expect(cell).toHaveTextContent('2')
    expect(cell).toHaveTextContent('12')
    expect(screen.getByText(/Thấp 1–5 · Trung bình 6–12 · Cao 13–25/)).toBeInTheDocument()
  })

  it('empty cells are disabled; tapping a populated cell selects it, tapping again clears', async () => {
    const onSelect = vi.fn()
    const { rerender } = render(<RiskMatrix matrix={matrix} selected={null} onSelect={onSelect} />)
    expect(screen.getByRole('gridcell', { name: 'Xác suất 1, tác động 1: 0 rủi ro' })).toBeDisabled()
    const user = userEvent.setup()
    await user.click(screen.getByRole('gridcell', { name: /Xác suất 5, tác động 4/ }))
    expect(onSelect).toHaveBeenLastCalledWith({ probability: 5, impact: 4 })
    rerender(<RiskMatrix matrix={matrix} selected={{ probability: 5, impact: 4 }} onSelect={onSelect} />)
    expect(screen.getByRole('gridcell', { name: /Xác suất 5, tác động 4/ })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('gridcell', { name: /Xác suất 5, tác động 4/ }))
    expect(onSelect).toHaveBeenLastCalledWith(null)
    await user.click(screen.getByRole('button', { name: 'Bỏ lọc ô' }))
    expect(onSelect).toHaveBeenLastCalledWith(null)
  })
})

describe('Risks UI', () => {
  const fetchMock = vi.fn()

  function serve(role: string, risks: Risk[] = [risk()], extra?: (url: string, init?: RequestInit) => Response | null) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, me(role)))
      if (url.startsWith('/api/v1/packages?')) return Promise.resolve(res(200, { items: [{ id: 'p3', number: 3 }], total: 1, page: 1, page_size: 100 }))
      if (url === '/api/v1/risks/matrix') return Promise.resolve(res(200, matrix))
      const custom = extra?.(url, init)
      if (custom) return Promise.resolve(custom)
      if (url.startsWith('/api/v1/risks?')) return Promise.resolve(res(200, { items: risks, total: risks.length, page: 1, page_size: 100 }))
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

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('lists risks with level in words and score, and filters by the tapped matrix cell', async () => {
    serve('viewer')
    wrap(<RisksPage />)
    const cards = await screen.findAllByRole('listitem')
    expect(within(cards[0]).getByText('Cao · 20')).toBeInTheDocument()
    await userEvent.setup().click(await screen.findByRole('gridcell', { name: /Xác suất 5, tác động 4/ }))
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes('probability=5') && String(u).includes('impact=4'))).toBe(true),
    )
  })

  it('viewers can only read; writers edit and mark reviewed; only the director closes', async () => {
    serve('viewer')
    const first = wrap(<RisksPage />)
    await screen.findAllByRole('listitem')
    expect(screen.queryByRole('button', { name: 'Thêm rủi ro' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sửa rủi ro' })).not.toBeInTheDocument()
    first.unmount()

    serve('technical', [risk({ needs_review: true })], (url, init) => (url === '/api/v1/risks/r1/review' && init?.method === 'POST' ? res(200, {}) : null))
    const second = wrap(<RisksPage />)
    const card = (await screen.findAllByRole('listitem'))[0]
    expect(within(card).getByText('Cần rà soát')).toBeInTheDocument()
    expect(within(card).queryByRole('button', { name: 'Đóng rủi ro' })).not.toBeInTheDocument()
    await userEvent.setup().click(within(card).getByRole('button', { name: 'Đã rà soát' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/v1/risks/r1/review' && i?.method === 'POST')).toBe(true))
    second.unmount()

    serve('director', [risk()], (url, init) => (url === '/api/v1/risks/r1' && init?.method === 'PATCH' ? res(200, {}) : null))
    wrap(<RisksPage />)
    const dcard = (await screen.findAllByRole('listitem'))[0]
    await userEvent.setup().click(within(dcard).getByRole('button', { name: 'Đóng rủi ro' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/v1/risks/r1' && i?.method === 'PATCH')).toBe(true))
    const patch = fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/risks/r1' && i?.method === 'PATCH')!
    expect(JSON.parse(patch[1].body)).toEqual({ status: 'closed' })
  })

  it('form shows the live score and level as probability and impact change, then posts', async () => {
    serve('technical', [], (url, init) => (url === '/api/v1/risks' && init?.method === 'POST' ? res(201, risk()) : null))
    wrap(<RiskForm canClose={false} onDone={() => undefined} />)
    const user = userEvent.setup()
    expect(await screen.findByText('Điểm 9 · Trung bình')).toBeInTheDocument() // 3 x 3 default
    await user.selectOptions(screen.getByLabelText('Xác suất (1–5)'), '5')
    await user.selectOptions(screen.getByLabelText('Tác động (1–5)'), '4')
    expect(screen.getByText('Điểm 20 · Cao')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Xác suất (1–5)'), '1')
    await user.selectOptions(screen.getByLabelText('Tác động (1–5)'), '2')
    expect(screen.getByText('Điểm 2 · Thấp')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Tiêu đề'), 'Mất điện tại xã')
    await user.click(screen.getByRole('button', { name: 'Lưu' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/v1/risks' && i?.method === 'POST')).toBe(true))
    const body = JSON.parse(fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/risks' && i?.method === 'POST')![1].body)
    expect(body).toMatchObject({ title: 'Mất điện tại xã', probability: 1, impact: 2, category: 'schedule', status: 'open', package_id: null })
    expect(body).not.toHaveProperty('score') // the server computes it
  })

  it('"closed" is not selectable unless the user may close risks', async () => {
    serve('technical', [])
    const first = wrap(<RiskForm canClose={false} onDone={() => undefined} />)
    expect(await screen.findByRole('option', { name: 'Đã đóng' }, { timeout: 500 }).catch(() => null)).toBeNull()
    first.unmount()
    serve('director', [])
    wrap(<RiskForm canClose onDone={() => undefined} />)
    expect(await screen.findByRole('option', { name: 'Đã đóng' })).toBeEnabled()
  })
})
