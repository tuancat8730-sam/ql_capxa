import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { PackageDetailPage } from './PackageDetailPage'
import { daysUntil, PackagesPage } from './PackagesPage'
import type { ContractDetail, PackageItem, PackageOverview } from './types'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const pkg = (over: Partial<PackageItem> = {}): PackageItem => ({
  id: 'p4',
  number: 4,
  name: 'Gói thầu số 04',
  scope_summary: null,
  package_type: 'goods',
  package_price: 62_298_200_000,
  winning_price: 51_505_400_000,
  winning_org_text: 'Liên danh Nguyên Luân – TTB Mẫu Giáo Ti Ti',
  current_stage: 'S3_EXECUTION',
  status: 'contract_signed',
  progress_pct: 0,
  health: 'grey',
  health_reason: null,
  is_sensitive: false,
  notes: null,
  etbmt_no: null,
  approved_duration_days: null,
  ...over,
})

const contract = (over: Partial<ContractDetail> = {}): ContractDetail => ({
  id: 'c4',
  contract_no: '71',
  signed_date: '2026-09-14',
  effective_date: null,
  duration_days: 60,
  planned_end_date: '2026-11-13',
  extended_end_date: null,
  end_date_override: false,
  contract_type: null,
  price_adjustment: false,
  value: 51_505_400_000,
  advance_pct: 30,
  advance_amount: 15_451_620_000,
  performance_bond_pct: 3,
  performance_bond_amount: 1_545_162_000,
  warranty_bond_pct: null,
  warranty_bond_amount: null,
  penalty_rate_pct: null,
  penalty_unit: null,
  penalty_cap_pct: null,
  investor_account: null,
  status: 'signed',
  data_quality_note: 'Văn bản ghi kết thúc 13/11',
  consistency: [
    {
      code: 'END_DATE_MISMATCH',
      severity: 'warning',
      message: 'Ngày kết thúc khác (ngày bắt đầu + thời gian − 1)',
      expected: '2026-11-12',
      actual: '2026-11-13',
    },
  ],
  needs_review: true,
  parties: [
    { id: 'a', organization_name: 'Nguyên Luân', role: 'lead', share_pct: 60, share_amount: 30_903_240_000 },
    { id: 'b', organization_name: 'TTB Mẫu Giáo Ti Ti', role: 'member', share_pct: 40, share_amount: 20_602_160_000 },
  ],
  ...over,
})

const me = {
  id: 'me',
  email: 'v@example.test',
  full_name: 'V',
  phone: null,
  role: 'viewer',
  is_active: true,
  must_change_password: false,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
}

describe('packages UI', () => {
  const fetchMock = vi.fn()
  const route = (url: string) => {
    if (url.endsWith('/auth/refresh')) return res(200, { access_token: 't' })
    if (url.endsWith('/auth/me')) return res(200, me)
    return null
  }

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  const wrap = (initial: string) =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={[initial]}>
          <AuthProvider>
            <Routes>
              <Route path="/packages" element={<PackagesPage />} />
              <Route path="/packages/:id" element={<PackageDetailPage />} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

  it('daysUntil counts whole calendar days, negative once past', () => {
    const now = new Date(2026, 10, 1, 23, 59)
    expect(daysUntil('2026-11-12', now)).toBe(11)
    expect(daysUntil('2026-11-01', now)).toBe(0)
    expect(daysUntil('2026-10-30', now)).toBe(-2)
  })

  it('lists packages with health label, price and "Cần kiểm tra"', async () => {
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        route(url) ??
          res(200, {
            items: [
              pkg({ needs_review: true, contract_end_date: '2026-11-13', checklist_pct: 12.5 }),
              pkg({ id: 'p3', number: 3, name: 'Gói thầu số 03', winning_price: null, winning_org_text: null, health_reason: 'Chưa có hợp đồng' }),
            ],
            total: 2,
            page: 1,
            page_size: 100,
          }),
      ),
    )
    wrap('/packages')
    const cards = await screen.findAllByRole('listitem')
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByText('Cần kiểm tra')).toBeInTheDocument()
    expect(within(cards[0]).getByText(/Hồ sơ 12,5%/)).toBeInTheDocument()
    expect(within(cards[0]).getByText(/51\.505\.400\.000/)).toBeInTheDocument()
    expect(within(cards[1]).getAllByText(/Chưa có dữ liệu/).length).toBeGreaterThanOrEqual(1)
    expect(within(cards[1]).getByText('Chưa bắt đầu')).toBeInTheDocument()
  })

  it('filters by health through the API', async () => {
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(route(url) ?? res(200, { items: [], total: 0, page: 1, page_size: 100 })),
    )
    wrap('/packages')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Nguy cấp' }))
    const calls = fetchMock.mock.calls.map(([u]) => String(u))
    expect(calls.some((u) => u.startsWith('/api/v1/packages?') && u.includes('health=red'))).toBe(true)
    expect(await screen.findByText('Chưa có dữ liệu')).toBeInTheDocument()
  })

  it('detail page shows the data-consistency flag and the contract tab via ?tab=', async () => {
    const overview: PackageOverview = {
      package: pkg(),
      project: { name: 'Dự án', treasury_account: '9552.2.8200685' },
      contracts: [contract()],
      needs_review: true,
    }
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(route(url) ?? res(200, overview)),
    )
    wrap('/packages/p4?tab=contracts')
    expect(await screen.findByRole('heading', { name: /Gói 04/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Hợp đồng/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('Ngày kết thúc khác (ngày bắt đầu + thời gian − 1)')).toBeInTheDocument()
    expect(screen.getByText(/Kỳ vọng: 2026-11-12/)).toBeInTheDocument()
    expect(screen.getByText('Nguyên Luân')).toBeInTheDocument()
    expect(screen.getAllByText('Chưa có dữ liệu').length).toBeGreaterThan(0) // contract type etc.
  })

  it('detail page falls back to overview for unknown tabs and shows later-milestone tabs', async () => {
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(
        route(url) ??
          res(200, { package: pkg({ health: 'grey', health_reason: 'Chưa có hợp đồng' }), project: { name: 'x', treasury_account: null }, contracts: [], needs_review: false }),
      ),
    )
    wrap('/packages/p4?tab=bogus')
    expect(await screen.findByRole('tab', { name: 'Tổng quan' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('Lý do: Chưa có hợp đồng')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('tab', { name: 'Nhật ký' }))
    expect(await screen.findByText(/sẽ có ở các bản cập nhật sau/)).toBeInTheDocument()
  })

  it('detail page reports a missing package with a way back', async () => {
    fetchMock.mockImplementation((url: string) =>
      Promise.resolve(route(url) ?? res(404, { error: { code: 'not_found', message: 'x' } })),
    )
    wrap('/packages/ghost')
    expect(await screen.findByText('Không tìm thấy gói thầu')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Quay lại danh sách gói' })).toHaveAttribute('href', '/packages')
  })
})
