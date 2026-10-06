import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GlobalSearch } from './GlobalSearch'
import { hitLink } from './types'

const res = (body: unknown) => new Response(JSON.stringify(body), { status: 200 })

describe('hitLink', () => {
  it.each([
    [{ kind: 'package', id: 'p1', package_id: 'p1' }, '/packages/p1'],
    [{ kind: 'contract', id: 'c1', package_id: 'p1' }, '/packages/p1?tab=contracts'],
    [{ kind: 'document', id: 'd1', package_id: 'p1' }, '/packages/p1?tab=documents'],
    [{ kind: 'document', id: 'd1', package_id: null }, '/documents'],
    [{ kind: 'risk', id: 'r1', package_id: null }, '/risks'],
    [{ kind: 'issue', id: 'i1', package_id: 'p1' }, '/issues'],
  ] as const)('%j opens %s', (hit, to) => expect(hitLink(hit)).toBe(to))
})

describe('GlobalSearch', () => {
  const fetchMock = vi.fn()
  const urls: string[] = []
  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <GlobalSearch />
        </MemoryRouter>
      </QueryClientProvider>,
    )

  beforeEach(() => {
    urls.length = 0
    fetchMock.mockImplementation((url: string) => {
      urls.push(url)
      return Promise.resolve(
        res({
          query: 'lap thinh',
          groups: [
            {
              kind: 'package',
              total: 7,
              items: [{ kind: 'package', id: 'p1', title: 'Gói 01 · Thiết bị', snippet: 'Nhà thầu An Lập Thịnh', package_id: 'p1', package_number: 1, subtitle: 'An Lập Thịnh' }],
            },
          ],
        }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  it('opens from the button and with Ctrl+K, and closes with Escape', async () => {
    const user = userEvent.setup()
    wrap()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.keyboard('{Control>}k{/Control}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('waits for two characters, then shows grouped hits with an excerpt and a link', async () => {
    const user = userEvent.setup()
    wrap()
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    const box = screen.getByRole('searchbox')
    await user.type(box, 'l')
    await new Promise((r) => setTimeout(r, 350))
    expect(urls).toHaveLength(0)
    expect(screen.getByText(/Nhập ít nhất 2 ký tự/)).toBeInTheDocument()

    await user.type(box, 'ap thinh')
    const group = await screen.findByRole('region', { name: 'Gói thầu' })
    expect(within(group).getByText('Nhà thầu An Lập Thịnh')).toBeInTheDocument()
    expect(within(group).getByRole('link')).toHaveAttribute('href', '/packages/p1')
    expect(screen.getByText('và 6 kết quả khác')).toBeInTheDocument()
    expect(urls.at(-1)).toContain('q=lap+thinh')
  })

  it('closing after a click on a hit', async () => {
    const user = userEvent.setup()
    wrap()
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    await user.type(screen.getByRole('searchbox'), 'lap thinh')
    await user.click(await screen.findByRole('link', { name: /Gói 01/ }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('says so when nothing matches', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(res({ query: 'zz', groups: [] })))
    const user = userEvent.setup()
    wrap()
    await user.click(screen.getByRole('button', { name: 'Tìm kiếm' }))
    await user.type(screen.getByRole('searchbox'), 'zzz')
    expect(await screen.findByText('Không tìm thấy kết quả nào')).toBeInTheDocument()
  })
})
