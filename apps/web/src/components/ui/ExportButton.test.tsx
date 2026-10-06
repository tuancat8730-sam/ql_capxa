import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setAccessToken } from '@/lib/api'
import { ExportButton } from './ExportButton'

describe('ExportButton', () => {
  const fetchMock = vi.fn()
  const click = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:x', revokeObjectURL: vi.fn() })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(click)
    setAccessToken('tok')
  })
  afterEach(() => {
    fetchMock.mockReset()
    click.mockReset()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('downloads the workbook with the bearer token and the server file name', async () => {
    fetchMock.mockResolvedValue(
      new Response(new Blob(['x']), {
        status: 200,
        headers: { 'Content-Disposition': `attachment; filename="rui-ro.xlsx"; filename*=UTF-8''rui-ro-20261105.xlsx` },
      }),
    )
    render(<ExportButton path="/export/risks.xlsx" />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Xuất Excel' }))
    await waitFor(() => expect(click).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/export/risks.xlsx')
    expect((init as RequestInit).headers).toMatchObject({ Authorization: 'Bearer tok' })
  })

  it('uses a custom label and shows an error when the download fails', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 403 }))
    render(<ExportButton path="/export/ql07.xlsx" label="Xuất QL-07 (Excel)" />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Xuất QL-07 (Excel)' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Không xuất được tệp')
    expect(click).not.toHaveBeenCalled()
    expect(screen.getByRole('button')).not.toBeDisabled()
  })
})
