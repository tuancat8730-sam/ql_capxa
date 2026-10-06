import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/features/auth/AuthContext'
import { ChecklistTab } from '@/features/packages/ChecklistTab'
import { setAccessToken } from '@/lib/api'
import { DocumentsPage } from './DocumentsPage'
import { PreviewDialog } from './PreviewDialog'
import type { Checklist, DocumentItem } from './types'
import { fileIcon, formatSize } from './types'
import { UploadSheet } from './UploadSheet'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const doc = (over: Partial<DocumentItem> = {}): DocumentItem => ({
  id: 'd1',
  package_id: 'p4',
  restricted: false,
  title: 'Bảo lãnh tạm ứng',
  confidentiality: 'normal',
  category: 'contract',
  doc_type: 'guarantee_advance',
  doc_no: 'BL-001',
  doc_date: '2026-09-15',
  file_name: 'bl.pdf',
  mime_type: 'application/pdf',
  size_bytes: 1_572_864,
  version: 1,
  is_current: true,
  extraction_status: 'done',
  tags: [],
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

const DOC_TYPES = [
  { code: 'guarantee_advance', label: 'Bảo lãnh tạm ứng', category: 'contract' },
  { code: 'photo', label: 'Ảnh hiện trường', category: 'execution' },
  { code: 'other', label: 'Khác', category: 'other' },
]

class FakeXhr {
  static puts: { url: string; headers: Record<string, string> }[] = []
  static status = 200
  headers: Record<string, string> = {}
  url = ''
  status = 0
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  open(_m: string, url: string) {
    this.url = url
  }
  setRequestHeader(n: string, v: string) {
    this.headers[n] = v
  }
  send() {
    FakeXhr.puts.push({ url: this.url, headers: this.headers })
    queueMicrotask(() => {
      this.status = FakeXhr.status
      this.onload?.()
    })
  }
}

describe('documents UI', () => {
  const fetchMock = vi.fn()

  function serve(role: string, handler: (url: string, init?: RequestInit) => Response | null) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, user(role)))
      if (url === '/api/v1/doc-types') return Promise.resolve(res(200, DOC_TYPES))
      if (url.startsWith('/api/v1/packages?')) {
        return Promise.resolve(res(200, { items: [{ id: 'p4', number: 4 }, { id: 'p5', number: 5 }], total: 2, page: 1, page_size: 100 }))
      }
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
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    FakeXhr.puts = []
    FakeXhr.status = 200
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('formats sizes and picks icons', () => {
    expect(formatSize(null)).toBe('')
    expect(formatSize(900)).toBe('900 B')
    expect(formatSize(1_572_864)).toBe('1,5 MB')
    expect(fileIcon('application/pdf')).toBe('📕')
    expect(fileIcon('image/png')).toBe('🖼')
    expect(fileIcon(null)).toBe('📄')
  })

  it('lists documents and shows hidden ones only as a restricted stub', async () => {
    serve('viewer', (url) =>
      url.startsWith('/api/v1/documents?')
        ? res(200, {
            items: [
              doc({ version: 2 }),
              { ...doc({ id: 'd2' }), restricted: true, title: 'Tài liệu hạn chế', confidentiality: 'sensitive', doc_type: null, file_name: null, mime_type: null, size_bytes: null },
            ],
            total: 2,
            page: 1,
            page_size: 100,
          })
        : null,
    )
    wrap(<DocumentsPage />)
    const cards = await screen.findAllByRole('listitem')
    expect(within(cards[0]).getByText('Bảo lãnh tạm ứng')).toBeInTheDocument()
    expect(within(cards[0]).getByText(/Gói 04 · Bảo lãnh tạm ứng · 15\/09\/2026 · 1,5 MB/)).toBeInTheDocument()
    expect(within(cards[0]).getByText('Phiên bản 2')).toBeInTheDocument()
    expect(within(cards[1]).getByText(/Tài liệu hạn chế/)).toBeInTheDocument()
    expect(within(cards[1]).queryByRole('button')).not.toBeInTheDocument() // nothing to open
    // read-only role: no upload, no delete
    expect(screen.queryByRole('button', { name: 'Tải lên' })).not.toBeInTheDocument()
    expect(within(cards[0]).queryByRole('button', { name: 'Xóa' })).not.toBeInTheDocument()
  })

  it('searches after a short pause using the API (no client-side filtering)', async () => {
    serve('clerk', (url) =>
      url.startsWith('/api/v1/documents?') ? res(200, { items: [], total: 0, page: 1, page_size: 100 }) : null,
    )
    wrap(<DocumentsPage />)
    const input = await screen.findByLabelText('Tìm theo tiêu đề, số văn bản, nội dung')
    await userEvent.setup().type(input, 'bao lanh tam ung')
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes('q=bao+lanh+tam+ung'))).toBe(true),
    )
    // typing did not fire one request per keystroke
    const searches = fetchMock.mock.calls.filter(([u]) => String(u).includes('q='))
    expect(searches.length).toBeLessThanOrEqual(2)
  })

  it('writers can delete after confirming and download through a presigned URL', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    serve('clerk', (url, init) => {
      if (url.startsWith('/api/v1/documents?')) return res(200, { items: [doc()], total: 1, page: 1, page_size: 100 })
      if (url === '/api/v1/documents/d1/download-url') return res(200, { url: 'https://s3.test/d1', expires_in: 300, file_name: 'bl.pdf', mime_type: 'application/pdf', inline: false })
      if (url === '/api/v1/documents/d1' && init?.method === 'DELETE') return res(204)
      return null
    })
    wrap(<DocumentsPage />)
    const card = (await screen.findAllByRole('listitem'))[0]
    const u = userEvent.setup()
    await u.click(within(card).getByRole('button', { name: 'Tải về' }))
    await waitFor(() => expect(open).toHaveBeenCalledWith('https://s3.test/d1', '_blank', 'noopener'))
    await u.click(within(card).getByRole('button', { name: 'Xóa' }))
    expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'DELETE')).toBe(false) // declined
    await u.click(within(card).getByRole('button', { name: 'Xóa' }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, i]) => i?.method === 'DELETE')).toBe(true))
    expect(confirm).toHaveBeenCalledTimes(2)
  })

  it('preview shows PDFs in a frame and tells the user to download other formats', async () => {
    serve('viewer', (url) =>
      url === '/api/v1/documents/d1/download-url?inline=true'
        ? res(200, { url: 'https://s3.test/d1', expires_in: 300, file_name: 'bl.pdf', mime_type: 'application/pdf', inline: true })
        : url === '/api/v1/documents/d9/download-url?inline=true'
          ? res(200, { url: 'https://s3.test/d9', expires_in: 300, file_name: 'a.docx', mime_type: 'application/msword', inline: false })
          : null,
    )
    const first = wrap(<PreviewDialog doc={doc()} onClose={() => undefined} />)
    const frame = await screen.findByTitle('Bảo lãnh tạm ứng')
    expect(frame).toHaveAttribute('src', 'https://s3.test/d1')
    first.unmount()
    wrap(<PreviewDialog doc={doc({ id: 'd9', mime_type: 'application/msword' })} onClose={() => undefined} />)
    expect(await screen.findByText(/Không xem trước được/)).toBeInTheDocument()
  })

  it('preview closes on Escape', async () => {
    serve('viewer', () => res(200, { url: 'u', expires_in: 300, file_name: 'a.pdf', mime_type: 'application/pdf', inline: true }))
    const onClose = vi.fn()
    wrap(<PreviewDialog doc={doc()} onClose={onClose} />)
    await userEvent.setup().keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })

  it('upload sheet: requests a URL, PUTs the file, then confirms with the metadata', async () => {
    serve('clerk', (url, init) => {
      if (url === '/api/v1/documents/upload-url') {
        return res(200, {
          document_id: 'new1',
          file_key: 'projects/p/packages/p4/new1/v1/bl.pdf',
          version: 1,
          upload: { url: 'https://s3.test/put', method: 'PUT', headers: { 'Content-Type': 'application/pdf' } },
          expires_in: 600,
          max_bytes: 104857600,
        })
      }
      if (url === '/api/v1/documents' && init?.method === 'POST') return res(201, doc({ id: 'new1' }))
      return null
    })
    const onClose = vi.fn()
    wrap(<UploadSheet packageId="p4" docType="guarantee_advance" onClose={onClose} />)
    const user = userEvent.setup()
    const file = new File(['%PDF-1.4 test'], 'Bảo lãnh số 1.pdf', { type: 'application/pdf' })
    await user.upload(await screen.findByLabelText('Chọn tệp'), file)
    expect(screen.getByLabelText('Tiêu đề')).toHaveValue('Bảo lãnh số 1')
    await user.clear(screen.getByLabelText('Tiêu đề'))
    await user.type(screen.getByLabelText('Tiêu đề'), 'Bảo lãnh tạm ứng TPBank')
    await user.type(screen.getByLabelText('Số văn bản'), 'BL-001')
    await user.click(screen.getByRole('button', { name: 'Bắt đầu tải lên' }))
    expect(await screen.findByText(/Đã tải lên/)).toBeInTheDocument()
    expect(FakeXhr.puts).toEqual([{ url: 'https://s3.test/put', headers: { 'Content-Type': 'application/pdf' } }])
    const confirm = fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/documents' && i?.method === 'POST')!
    expect(JSON.parse(confirm[1].body)).toMatchObject({
      document_id: 'new1',
      file_key: 'projects/p/packages/p4/new1/v1/bl.pdf',
      package_id: 'p4',
      doc_type: 'guarantee_advance',
      title: 'Bảo lãnh tạm ứng TPBank',
      doc_no: 'BL-001',
      size_bytes: file.size,
    })
    const closers = screen.getAllByRole('button', { name: 'Đóng' })
    await user.click(closers.find((b) => b.textContent === 'Đóng')!) // the primary button, not the backdrop
    expect(onClose).toHaveBeenCalled()
  })

  it('upload sheet: rejects bad types and oversize files before any request, and explains duplicates', async () => {
    serve('clerk', (url, init) => {
      if (url === '/api/v1/documents/upload-url') {
        return res(200, { document_id: 'n', file_key: 'k', version: 1, upload: { url: 'https://s3.test/p', method: 'PUT', headers: {} }, expires_in: 600, max_bytes: 1 })
      }
      if (url === '/api/v1/documents' && init?.method === 'POST') {
        return res(409, { error: { code: 'duplicate_document', message: 'dup', details: { document_id: 'd1', title: 'Bảo lãnh tạm ứng' } } })
      }
      return null
    })
    wrap(<UploadSheet packageId="p4" onClose={() => undefined} />)
    const user = userEvent.setup({ applyAccept: false }) // drag-and-drop ignores the picker's filter
    const input = await screen.findByLabelText('Chọn tệp')
    await user.upload(input, new File(['MZ'], 'virus.exe', { type: 'application/x-msdownload' }))
    expect(await screen.findByText(/Định dạng tệp không được phép/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Bắt đầu tải lên' })).toBeDisabled() // nothing sendable
    await user.click(screen.getByRole('button', { name: /Bỏ tệp này: virus.exe/ }))
    const big = new File(['x'], 'big.pdf', { type: 'application/pdf' })
    Object.defineProperty(big, 'size', { value: 101 * 1024 * 1024 })
    await user.upload(input, big)
    expect(await screen.findByText('✕ Tệp vượt quá 100 MB')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u]) => u === '/api/v1/documents/upload-url')).toBe(false)
    await user.click(screen.getByRole('button', { name: /Bỏ tệp này: big.pdf/ }))

    await user.upload(input, new File(['%PDF'], 'trung.pdf', { type: 'application/pdf' }))
    await user.click(screen.getByRole('button', { name: 'Bắt đầu tải lên' }))
    expect(await screen.findByText(/Tệp trùng nội dung với "Bảo lãnh tạm ứng"/)).toBeInTheDocument()
  })

  it('upload sheet for a new version sends no metadata form and posts to /versions', async () => {
    serve('clerk', (url, init) => {
      if (url === '/api/v1/documents/upload-url') {
        return res(200, { document_id: 'v2', file_key: 'k2', version: 2, upload: { url: 'https://s3.test/p2', method: 'PUT', headers: {} }, expires_in: 600, max_bytes: 1 })
      }
      if (url === '/api/v1/documents/d1/versions' && init?.method === 'POST') return res(201, doc({ id: 'v2', version: 2 }))
      return null
    })
    wrap(<UploadSheet parent={doc()} onClose={() => undefined} />)
    const user = userEvent.setup()
    await user.upload(await screen.findByLabelText('Chọn tệp'), new File(['%PDF v2'], 'bl-v2.pdf', { type: 'application/pdf' }))
    expect(screen.queryByLabelText('Loại tài liệu')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Bắt đầu tải lên' }))
    expect(await screen.findByText(/Đã tải lên/)).toBeInTheDocument()
    const body = JSON.parse(fetchMock.mock.calls.find(([u]) => u === '/api/v1/documents/d1/versions')![1].body)
    expect(body).toMatchObject({ document_id: 'v2', file_key: 'k2' })
    const req = JSON.parse(fetchMock.mock.calls.find(([u]) => u === '/api/v1/documents/upload-url')![1].body)
    expect(req.parent_document_id).toBe('d1')
  })

  it('photo capture compresses nothing it cannot decode and still hands files to the sheet', async () => {
    serve('onsite', () => null)
    wrap(<UploadSheet packageId="p4" onClose={() => undefined} />)
    const photo = new File(['jpeg bytes'], 'IMG_1.jpg', { type: 'image/jpeg' })
    const input = await screen.findByTestId('photo-input')
    await act(async () => {
      await userEvent.setup().upload(input, photo)
    })
    expect(await screen.findByText(/IMG_1\.jpg/)).toBeInTheDocument()
    expect(screen.getByLabelText('Loại tài liệu')).toHaveValue('photo') // photos default to "Ảnh hiện trường"
  })
})

describe('ChecklistTab', () => {
  const fetchMock = vi.fn()
  const checklist: Checklist = {
    required_total: 3,
    required_done: 1,
    completion_pct: 33.3,
    items: [
      { id: 'i1', package_id: 'p4', stage_code: 'S3_EXECUTION', doc_type: 'contract', title: 'Hợp đồng', required: true, status: 'received', document_id: 'd1', document_title: 'Hợp đồng số 71', document_restricted: false, due_date: null, overdue: false, note: null },
      { id: 'i2', package_id: 'p4', stage_code: 'S3_EXECUTION', doc_type: 'guarantee_performance', title: 'Bảo lãnh thực hiện hợp đồng', required: true, status: 'missing', document_id: null, document_title: null, document_restricted: false, due_date: '2026-09-21', overdue: true, note: null },
      { id: 'i3', package_id: 'p4', stage_code: 'S4_ACCEPTANCE', doc_type: 'other', title: 'Biên bản vận hành thử', required: false, status: 'missing', document_id: null, document_title: null, document_restricted: false, due_date: null, overdue: false, note: null },
    ],
  }

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
  })

  const serve = (role: string) =>
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, user(role)))
      if (url === '/api/v1/packages/p4/checklist') return Promise.resolve(res(200, checklist))
      if (url === '/api/v1/checklist-items/i3' && init?.method === 'PATCH') return Promise.resolve(res(200, {}))
      return Promise.resolve(res(404, { error: { code: 'not_found', message: 'x' } }))
    })

  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <ChecklistTab packageId="p4" />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

  it('shows progress, stage groups, overdue and linked document titles', async () => {
    serve('viewer')
    wrap()
    expect(await screen.findByText('Đã đủ 1/3 hạng mục bắt buộc (33,3%)')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Danh mục hồ sơ' })).toHaveAttribute('aria-valuenow', '33.3')
    const s3 = screen.getByRole('region', { name: 'Thực hiện hợp đồng' })
    expect(within(s3).getByText(/Hợp đồng số 71/)).toBeInTheDocument()
    expect(within(s3).getByText('Quá hạn')).toBeInTheDocument()
    expect(within(s3).getByText(/Hạn: 21\/09\/2026/)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Nghiệm thu bàn giao' })).toBeInTheDocument()
    expect(screen.getByText(/Không bắt buộc/)).toBeInTheDocument()
    // viewers cannot act
    expect(screen.queryByRole('button', { name: 'Tải lên' })).not.toBeInTheDocument()
  })

  it('writers can mark an item not applicable and open the upload sheet for it', async () => {
    serve('clerk')
    wrap()
    const user = userEvent.setup()
    const optional = (await screen.findByText('Biên bản vận hành thử')).closest('li')!
    await user.click(within(optional).getByRole('button', { name: 'Không áp dụng' }))
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([u, i]) => u === '/api/v1/checklist-items/i3' && i?.method === 'PATCH')).toBe(true),
    )
    const patch = fetchMock.mock.calls.find(([u, i]) => u === '/api/v1/checklist-items/i3' && i?.method === 'PATCH')!
    expect(JSON.parse(patch[1].body)).toEqual({ status: 'not_applicable' })
    const missing = screen.getByText('Bảo lãnh thực hiện hợp đồng').closest('li')!
    await user.click(within(missing).getByRole('button', { name: 'Tải lên' }))
    expect(await screen.findByRole('dialog', { name: 'Tải lên' })).toBeInTheDocument()
  })
})
