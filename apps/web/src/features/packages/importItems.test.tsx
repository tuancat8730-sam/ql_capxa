import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setAccessToken } from '@/lib/api'
import { ImportItems } from './ImportItems'

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })
const dry = (over = {}) => ({
  dry_run: true, rows_total: 2, rows_valid: 2, errors: [], total_amount: 170_000_000,
  contract_value: 170_000_000, matches_contract_value: true, imported: 0, ...over,
})

describe('ImportItems', () => {
  const fetchMock = vi.fn()
  const calls: { url: string; body: unknown }[] = []
  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ImportItems contractId="c1" />
      </QueryClientProvider>,
    )
  const pick = async (name = 'hang.xlsx') => {
    const file = new File(['x'], name, { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    await userEvent.setup().upload(screen.getByLabelText('Chọn tệp Excel'), file)
  }

  beforeEach(() => {
    calls.length = 0
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken('tok')
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('checks first, shows the totals and only then offers to import', async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      calls.push({ url, body: init?.body })
      return Promise.resolve(res(200, url.includes('commit=true') ? dry({ dry_run: false, imported: 2 }) : dry()))
    })
    wrap()
    const check = screen.getByRole('button', { name: 'Kiểm tra tệp' })
    expect(check).toBeDisabled()
    expect(screen.queryByRole('button', { name: /Nhập \d+ dòng/ })).not.toBeInTheDocument()
    await pick()
    await userEvent.setup().click(check)

    expect(await screen.findByText(/2\/2 dòng hợp lệ, tổng 170\.000\.000 đ/)).toBeInTheDocument()
    expect(screen.getByText('Khớp giá trị hợp đồng')).toBeInTheDocument()
    expect(calls[0].url).toContain('commit=false')
    expect(calls[0].body).toBeInstanceOf(FormData)

    await userEvent.setup().click(screen.getByRole('button', { name: 'Nhập 2 dòng' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Đã nhập 2 dòng hàng hóa')
    expect(calls[1].url).toContain('commit=true')
  })

  it('lists row errors and never offers to import a file with errors', async () => {
    fetchMock.mockResolvedValue(
      res(200, dry({ rows_valid: 1, errors: [{ row: 4, field: 'name', message: 'Thiếu tên hàng hóa' }] })),
    )
    wrap()
    await pick()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Kiểm tra tệp' }))
    expect(await screen.findByText('Dòng 4: Thiếu tên hàng hóa')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Nhập \d+ dòng/ })).not.toBeInTheDocument()
  })

  it('warns when the lines do not add up to the contract value', async () => {
    fetchMock.mockResolvedValue(res(200, dry({ matches_contract_value: false, total_amount: 150_000_000 })))
    wrap()
    await pick()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Kiểm tra tệp' }))
    expect(await screen.findByText('Không khớp giá trị hợp đồng (170.000.000 đ)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Nhập 2 dòng' })).toBeInTheDocument()
  })

  it('says so when the contract has no value to compare with', async () => {
    fetchMock.mockResolvedValue(res(200, dry({ matches_contract_value: null, contract_value: null })))
    wrap()
    await pick()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Kiểm tra tệp' }))
    expect(await screen.findByText('Hợp đồng chưa có giá trị để đối chiếu')).toBeInTheDocument()
  })

  it('sends replace=true when asked and shows server errors', async () => {
    fetchMock.mockImplementation((url: string) => {
      calls.push({ url, body: null })
      return Promise.resolve(res(422, { error: { code: 'invalid_import_file', message: 'Không đọc được tệp Excel (.xlsx)' } }))
    })
    wrap()
    await pick()
    await userEvent.setup().click(screen.getByRole('checkbox', { name: 'Thay toàn bộ danh sách hiện có' }))
    await userEvent.setup().click(screen.getByRole('button', { name: 'Kiểm tra tệp' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Không đọc được tệp Excel')
    await waitFor(() => expect(calls[0].url).toContain('replace=true'))
  })
})
