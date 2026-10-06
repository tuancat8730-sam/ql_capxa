import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MoneyInput, formatDigits, parseDigits } from '@/components/ui/MoneyInput'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { can } from '@/lib/permissions'
import { GuaranteesPage } from './GuaranteesPage'
import { PaymentsPage } from './PaymentsPage'
import type { GuaranteeRow, PaymentRow } from './types'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

describe('MoneyInput', () => {
  it('formats and parses VND digits', () => {
    expect(formatDigits(1_234_567)).toBe('1.234.567')
    expect(formatDigits(null)).toBe('')
    expect(parseDigits('1.234.567 đ')).toBe(1_234_567)
    expect(parseDigits('abc')).toBeNull()
  })

  it('groups thousands while typing and reports a number', async () => {
    const seen: (number | null)[] = []
    function Host() {
      const [v, setV] = useState<number | null>(null)
      return (
        <MoneyInput
          aria-label="Số tiền"
          value={v}
          onChange={(n) => {
            seen.push(n)
            setV(n)
          }}
        />
      )
    }
    render(<Host />)
    const input = screen.getByLabelText('Số tiền')
    await userEvent.setup().type(input, '1500000')
    expect(input).toHaveValue('1.500.000')
    expect(seen.at(-1)).toBe(1_500_000)
    expect(input).toHaveAttribute('inputmode', 'numeric')
  })
})

describe('client permission mirror (SPEC 8)', () => {
  it.each([
    ['director', 'payment', 'A', true],
    ['cost', 'payment', 'A', false],
    ['cost', 'payment', 'W', true],
    ['procurement', 'payment', 'W', false],
    ['onsite', 'payment', 'R', false],
    ['viewer', 'contract', 'R', true],
    ['viewer', 'contract', 'W', false],
    ['procurement', 'contract', 'W', true],
    ['clerk', 'doc_number', 'W', true],
    ['admin', 'audit_log', 'R', true],
    ['cost', 'audit_log', 'R', false],
  ] as const)('%s %s %s -> %s', (role, resource, level, expected) => {
    expect(can(role, resource, level)).toBe(expected)
  })

  it('denies unknown roles, resources and missing users', () => {
    expect(can('ghost', 'payment', 'R')).toBe(false)
    expect(can('admin', 'nope', 'R')).toBe(false)
    expect(can(undefined, 'payment', 'R')).toBe(false)
  })
})

const guarantee = (over: Partial<GuaranteeRow> = {}): GuaranteeRow => ({
  id: 'g1',
  contract_id: 'c5',
  contract_no: '72',
  package_id: 'p5',
  package_number: 5,
  package_name: 'Gói thầu số 05',
  guarantee_type: 'advance',
  bank_name: 'TPBank',
  guarantee_no: null,
  amount: 2_815_942_500,
  issue_date: '2026-09-15',
  expiry_date: '2026-11-13',
  validity_text: null,
  status: 'valid',
  effective_status: 'expiring',
  days_left: 8,
  required: true,
  verified: false,
  verify_note: 'Đọc từ bản scan [OCR]',
  findings: [
    { code: 'GUARANTEE_EXPIRING', severity: 'warning', message: 'Bảo lãnh còn 8 ngày hết hạn', guarantee_id: 'g1', due_date: '2026-11-13' },
    { code: 'ADVANCE_GUARANTEE_SHORT', severity: 'critical', message: 'Bảo lãnh tạm ứng hết hạn trước ngày kết thúc hợp đồng + 7 ngày thanh toán', guarantee_id: 'g1', due_date: '2026-11-19' },
  ],
  ...over,
})

const payment = (over: Partial<PaymentRow> = {}): PaymentRow => ({
  id: 'pay1',
  contract_id: 'c6',
  contract_no: '80',
  package_id: 'p6',
  package_number: 6,
  package_name: 'Gói thầu số 06',
  payment_type: 'payment',
  seq: 1,
  amount: 1_554_228_000,
  requested_date: null,
  paid_date: null,
  status: 'planned',
  invoice_no: null,
  treasury_ref: null,
  notes: null,
  ...over,
})

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

describe('finance pages', () => {
  const fetchMock = vi.fn()

  function serve(role: string, routes: Record<string, unknown>) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, user(role)))
      const key = Object.keys(routes).find((k) => `${method} ${url}`.startsWith(k))
      return Promise.resolve(key ? res(200, routes[key]) : res(404, { error: { code: 'not_found', message: 'x' } }))
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

  it('guarantees page surfaces critical findings first and labels status by text and icon', async () => {
    serve('viewer', {
      'GET /api/v1/guarantees': {
        items: [guarantee(), guarantee({ id: 'g2', bank_name: 'ABBank', expiry_date: null, effective_status: 'valid', days_left: null, findings: [], verified: true, verify_note: null })],
        total: 2,
        page: 1,
        page_size: 100,
      },
    })
    wrap(<GuaranteesPage />)
    const region = await screen.findByRole('region', { name: 'Cần xử lý' })
    expect(within(region).getByText(/Bảo lãnh tạm ứng hết hạn trước ngày kết thúc/)).toBeInTheDocument()
    expect(within(region).getByText(/Gói 05 · HĐ 72/)).toBeInTheDocument()
    const list = screen.getByRole('list', { name: 'Hợp đồng và bảo lãnh' })
    const cards = Array.from(list.children) as HTMLElement[]
    expect(within(cards[0]).getByText('Sắp hết hạn')).toBeInTheDocument()
    // once in the countdown, once in the "expiring" finding
    expect(within(cards[0]).getAllByText(/còn 8 ngày/)).toHaveLength(2)
    expect(within(cards[0]).getByText('Chưa đối chiếu bản gốc')).toBeInTheDocument()
    expect(within(cards[1]).getByText(/Không ghi hạn/)).toBeInTheDocument()
    // read-only roles get no edit button
    expect(screen.queryByRole('button', { name: 'Sửa bảo lãnh' })).not.toBeInTheDocument()
  })

  it('guarantees page filters by effective status through the API and lets writers edit', async () => {
    serve('procurement', {
      'GET /api/v1/guarantees': { items: [guarantee()], total: 1, page: 1, page_size: 100 },
    })
    wrap(<GuaranteesPage />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Sắp hết hạn' }))
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('status=expiring'))).toBe(true)
    await user.click((await screen.findAllByRole('button', { name: 'Sửa bảo lãnh' }))[0])
    expect(await screen.findByRole('dialog', { name: 'Sửa bảo lãnh' })).toBeInTheDocument()
    expect(screen.getByLabelText('Ngân hàng')).toHaveValue('TPBank')
  })

  it('payments: cost can request but not approve; director approves', async () => {
    const listing = {
      items: [payment(), payment({ id: 'pay2', seq: 2, status: 'requested' })],
      total: 2,
      page: 1,
      page_size: 100,
    }
    serve('cost', {
      'GET /api/v1/payments': listing,
      'GET /api/v1/project/disbursement-plan': { items: [], planned_total: 0, actual_total: 0 },
    })
    const first = wrap(<PaymentsPage />)
    const cards = await screen.findAllByRole('listitem')
    expect(within(cards[0]).getByRole('button', { name: 'Đề nghị' })).toBeInTheDocument()
    expect(within(cards[1]).queryByRole('button', { name: 'Duyệt' })).not.toBeInTheDocument()
    first.unmount()

    serve('director', {
      'GET /api/v1/payments': listing,
      'GET /api/v1/project/disbursement-plan': { items: [], planned_total: 0, actual_total: 0 },
      'PATCH /api/v1/payments/pay2': {},
    })
    wrap(<PaymentsPage />)
    const rows = await screen.findAllByRole('listitem')
    await userEvent.setup().click(within(rows[1]).getByRole('button', { name: 'Duyệt' }))
    const patch = fetchMock.mock.calls.find(([u, i]) => String(u) === '/api/v1/payments/pay2' && i?.method === 'PATCH')!
    expect(JSON.parse(patch[1].body)).toEqual({ status: 'approved' })
  })

  it('payments: an approved payment is marked paid through a sheet', async () => {
    serve('cost', {
      'GET /api/v1/payments': { items: [payment({ status: 'approved' })], total: 1, page: 1, page_size: 100 },
      'GET /api/v1/project/disbursement-plan': { items: [], planned_total: 0, actual_total: 0 },
      'POST /api/v1/payments/pay1/mark-paid': {},
    })
    wrap(<PaymentsPage />)
    const user = userEvent.setup()
    await user.click((await screen.findAllByRole('button', { name: 'Ghi nhận đã thanh toán' }))[0])
    const dialog = await screen.findByRole('dialog', { name: 'Ghi nhận đã thanh toán' })
    await user.type(within(dialog).getByLabelText('Số chứng từ kho bạc'), 'KB-77')
    await user.click(within(dialog).getByRole('button', { name: 'Xác nhận đã thanh toán' }))
    const call = fetchMock.mock.calls.find(([u]) => String(u) === '/api/v1/payments/pay1/mark-paid')!
    expect(JSON.parse(call[1].body)).toMatchObject({ treasury_ref: 'KB-77' })
  })

  it('payments: viewers see no action buttons and the disbursement plan is read-only', async () => {
    serve('viewer', {
      'GET /api/v1/payments': { items: [payment({ status: 'requested' })], total: 1, page: 1, page_size: 100 },
      'GET /api/v1/project/disbursement-plan': {
        items: [{ package_id: null, year: 2026, month: 11, planned_amount: 1_000_000, actual_amount: null }],
        planned_total: 1_000_000,
        actual_total: 0,
      },
    })
    wrap(<PaymentsPage />)
    expect(await screen.findByText('11/2026')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Duyệt' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Thêm kỳ' })).not.toBeInTheDocument()
  })

  it('payments: writers add a disbursement period which replaces the whole plan', async () => {
    serve('cost', {
      'GET /api/v1/payments': { items: [], total: 0, page: 1, page_size: 100 },
      'GET /api/v1/project/disbursement-plan': { items: [], planned_total: 0, actual_total: 0 },
      'PUT /api/v1/project/disbursement-plan': { items: [], planned_total: 0, actual_total: 0 },
    })
    wrap(<PaymentsPage />)
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Kế hoạch'), '2500000')
    await user.click(screen.getByRole('button', { name: 'Thêm kỳ' }))
    const put = fetchMock.mock.calls.find(([, i]) => i?.method === 'PUT')!
    const body = JSON.parse(put[1].body)
    expect(body.items).toHaveLength(1)
    expect(body.items[0]).toMatchObject({ planned_amount: 2_500_000, package_id: null })
  })
})
