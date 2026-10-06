import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { DashboardPage } from './DashboardPage'

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })

const pkg = (n: number, over: Record<string, unknown> = {}) => ({
  id: `p${n}`, number: n, name: `Gói thầu số ${String(n).padStart(2, '0')}`, package_type: 'goods', status: 'contract_signed',
  contractor: n === 3 ? null : 'Nhà thầu A', winning_price: n === 3 ? null : 2_000_000_000, package_price: 3_000_000_000,
  current_stage: 'S3_EXECUTION', progress_pct: 20, health: 'green', health_reason: 'Không có cảnh báo', ...over,
})

const summary = {
  today: '2026-11-05',
  project: {
    name: 'Đầu tư trang thiết bị cấp xã', code: 'DA-1', investor_name: 'Sở Khoa học', total_investment: 219_000_000_000,
    funding_source: 'Ngân sách tỉnh', start_year: 2026, end_year: 2028, package_count: 8,
    tvqlda_end_date: '2027-01-22', tvqlda_days_left: 78,
  },
  packages: [pkg(1), pkg(2), pkg(3, { health: 'grey', health_reason: 'Chưa có hợp đồng', progress_pct: 0 }), pkg(5, { health: 'red', health_reason: '3 cảnh báo nghiêm trọng đang mở' })],
  finance: {
    total_package_price: 10, total_winning_price: 9, total_contract_value: 8, total_advance: 2_000_000, total_paid: 500_000,
    planned_total: 6_000_000, planned_to_date: 2_000_000, disbursement_rate_pct: 25,
  },
  milestones: [
    { date: '2026-11-10', days_left: 5, kind: 'guarantee_expiry', title: 'Hết hạn bảo lãnh advance', package_id: 'p5', package_number: 5, entity_type: 'guarantee', entity_id: 'g1' },
  ],
}

const risk = { id: 'r1', code: 'R-001', title: 'Gói 03 chậm hợp đồng', score: 20, level: 'high', probability: 4, impact: 5, status: 'open', needs_review: false }
const alertItem = {
  id: 'a1', alert_type: 'ADVANCE_GUARANTEE_SHORT', severity: 'critical', entity_type: 'guarantee', entity_id: 'g', package_id: 'p5',
  package_number: 5, title: 'Gói 05: bảo lãnh tạm ứng không đủ thời hạn', message: 'Hết hạn trước ngày kết thúc', due_date: null,
  status: 'open', assigned_to: null, first_seen_at: '2026-11-05T00:00:00Z', can_snooze: false,
}

describe('DashboardPage', () => {
  const fetchMock = vi.fn()
  const serve = (overrides: Record<string, () => Response> = {}) =>
    fetchMock.mockImplementation((url: string) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, { id: 'me', email: 'v@example.test', full_name: 'v', role: 'viewer', is_active: true, must_change_password: false }))
      const key = Object.keys(overrides).find((k) => url.endsWith(k))
      if (key) return Promise.resolve(overrides[key]())
      if (url.endsWith('/dashboard/summary')) return Promise.resolve(res(200, summary))
      if (url.endsWith('/dashboard/cashflow')) return Promise.resolve(res(200, { months: [{ year: 2026, month: 11, planned: 100, actual: 60 }] }))
      if (url.endsWith('/dashboard/alerts')) return Promise.resolve(res(200, { counts: { critical: 1, warning: 2, info: 0, total: 3 }, items: [alertItem] }))
      if (url.endsWith('/dashboard/top-risks')) return Promise.resolve(res(200, { items: [risk], matrix: { total: 1, cells: [{ probability: 4, impact: 5, count: 1, risk_ids: ['r1'] }] } }))
      if (url.endsWith('/dashboard/documents')) return Promise.resolve(res(200, { total_missing: 5, packages: [{ package_id: 'p5', number: 5, name: 'x', required: 20, missing: 5 }, { package_id: 'p1', number: 1, name: 'y', required: 20, missing: 0 }] }))
      if (url.endsWith('/dashboard/timeline')) return Promise.resolve(res(200, { today: '2026-11-05', range_start: '2026-07-20', range_end: '2027-01-22', packages: [{ id: 'p6', number: 6, name: 'g', health: 'green', progress_pct: 20, stages: [], contract: { contract_no: '80', start: '2026-09-24', end: '2027-01-22', end_date_override: true, extended_end_date: null } }] }))
      return Promise.resolve(res(404, { error: { code: 'not_found', message: 'x' } }))
    })
  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <DashboardPage />
          </AuthProvider>
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

  it('shows the project card with the Package 06 countdown', async () => {
    serve()
    wrap()
    const card = await screen.findByRole('region', { name: 'Đầu tư trang thiết bị cấp xã' })
    expect(within(card).getByText('Sở Khoa học')).toBeInTheDocument()
    expect(within(card).getByText('78 ngày')).toBeInTheDocument()
    expect(within(card).getByText('219,00 tỷ')).toBeInTheDocument()
  })

  it('package cards link to the package and print the health reason (no hover needed)', async () => {
    serve()
    wrap()
    const strip = await screen.findByRole('region', { name: 'Tám gói thầu' })
    const link = within(strip).getByRole('link', { name: /Gói 05/ })
    expect(link).toHaveAttribute('href', '/packages/p5')
    expect(within(link).getByText('3 cảnh báo nghiêm trọng đang mở')).toBeInTheDocument()
    expect(within(link).getByText('Nguy cấp')).toBeInTheDocument()
    expect(within(strip).getByRole('link', { name: /Gói 03/ })).toHaveTextContent('Chưa có hợp đồng')
  })

  it('finance block shows totals, the disbursement rate and the monthly bars', async () => {
    serve()
    wrap()
    const block = await screen.findByRole('region', { name: 'Tài chính' })
    expect(within(block).getByText('25%')).toBeInTheDocument()
    expect(within(block).getByText('500.000 đ')).toBeInTheDocument()
    expect(await within(block).findByRole('img', { name: 'Kế hoạch và thực tế theo tháng' })).toBeInTheDocument()
    expect(within(block).getByText('11/26')).toBeInTheDocument()
  })

  it('says there is no plan when the rate is null', async () => {
    serve({ '/dashboard/summary': () => res(200, { ...summary, finance: { ...summary.finance, disbursement_rate_pct: null } }) })
    wrap()
    expect(await screen.findByText('Chưa có kế hoạch giải ngân')).toBeInTheDocument()
  })

  it('milestones, alerts, risks, missing documents and the timeline each render', async () => {
    serve()
    wrap()
    const ms = await screen.findByRole('region', { name: 'Mốc sắp tới (30 ngày)' })
    expect(within(ms).getByText(/Hết hạn bảo lãnh advance/)).toBeInTheDocument()
    expect(within(ms).getByText('Còn 5 ngày')).toBeInTheDocument()

    const alerts = await screen.findByRole('region', { name: 'Cảnh báo đang mở' })
    expect(await within(alerts).findByText('Gói 05: bảo lãnh tạm ứng không đủ thời hạn')).toBeInTheDocument()
    expect(within(alerts).getByRole('link', { name: /bảo lãnh tạm ứng/ })).toHaveAttribute('href', '/packages/p5?tab=contracts')

    const risks = await screen.findByRole('region', { name: 'Rủi ro hàng đầu' })
    expect(await within(risks).findByText('Gói 03 chậm hợp đồng')).toBeInTheDocument()
    expect(within(risks).getAllByRole('gridcell')).toHaveLength(25)

    const docs = await screen.findByRole('region', { name: 'Hồ sơ còn thiếu' })
    expect(await within(docs).findByText('Thiếu 5/20')).toBeInTheDocument()
    expect(within(docs).queryByText('Thiếu 0/20')).not.toBeInTheDocument() // only packages that miss something

    const tl = await screen.findByRole('region', { name: 'Đường găng đơn giản' })
    expect(await within(tl).findByText(/Gói 06/)).toBeInTheDocument()
    expect(within(tl).getByLabelText(/Hôm nay 05\/11\/2026/)).toBeInTheDocument()
  })

  it('a failing summary shows a retry button, the rest of the app keeps working', async () => {
    serve({ '/dashboard/summary': () => res(500, { error: { code: 'x', message: 'x' } }) })
    wrap()
    expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeInTheDocument()
  })

  it('empty states are written out', async () => {
    serve({
      '/dashboard/summary': () => res(200, { ...summary, milestones: [] }),
      '/dashboard/alerts': () => res(200, { counts: { critical: 0, warning: 0, info: 0, total: 0 }, items: [] }),
      '/dashboard/documents': () => res(200, { total_missing: 0, packages: [] }),
    })
    wrap()
    expect(await screen.findByText('Không có mốc nào trong 30 ngày tới')).toBeInTheDocument()
    expect(await screen.findByText('Không có cảnh báo nào đang mở')).toBeInTheDocument()
    expect(await screen.findByText('Không thiếu hồ sơ bắt buộc')).toBeInTheDocument()
  })
})
