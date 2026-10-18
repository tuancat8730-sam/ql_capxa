import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { navFor } from '@/components/layout/nav'
import { AuthProvider } from '@/features/auth/AuthContext'
import { setAccessToken } from '@/lib/api'
import { ProjectDocumentsPage } from './ProjectDocumentsPage'
import type { DocumentItem, FolderItem } from './types'

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

const FOLDERS: FolderItem[] = [
  { code: 'chung', group: 'Chung', label: 'Tài liệu chung', doc_type: 'project_doc', count: 1 },
  { code: 'nha-thau-4', group: 'Nhà thầu', label: '4. Phần mềm (Yêu cầu, Đặc tả)', doc_type: 'software_doc', count: 2 },
  { code: 'giam-sat', group: 'Giám sát', label: 'Giám sát', doc_type: 'project_doc', count: 0 },
]

const DOC_TYPES = [
  { code: 'software_doc', label: 'Tài liệu phần mềm', category: 'execution' },
  { code: 'project_doc', label: 'Tài liệu dự án', category: 'other' },
]

const doc = (over: Partial<DocumentItem> = {}): DocumentItem => ({
  id: 'd1',
  package_id: null,
  restricted: false,
  title: 'Thuyet minh ky thuat',
  confidentiality: 'normal',
  category: 'execution',
  doc_type: 'software_doc',
  doc_no: null,
  doc_date: '2026-10-06',
  file_name: 'Thuyet-minh-ky-thuat_06102026.pdf',
  mime_type: 'application/pdf',
  size_bytes: 2_097_152,
  version: 1,
  is_current: true,
  extraction_status: 'done',
  tags: ['folder:nha-thau-4'],
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

class FakeXhr {
  static puts: string[] = []
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
    FakeXhr.puts.push(this.url)
    queueMicrotask(() => {
      this.status = 200
      this.onload?.()
    })
  }
}

describe('project documents (archive)', () => {
  const fetchMock = vi.fn()

  function serve(role: string, handler: (url: string, init?: RequestInit) => Response | null = () => null) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith('/auth/refresh')) return Promise.resolve(res(200, { access_token: 't' }))
      if (url.endsWith('/auth/me')) return Promise.resolve(res(200, user(role)))
      if (url === '/api/v1/doc-types') return Promise.resolve(res(200, DOC_TYPES))
      if (url === '/api/v1/document-folders') return Promise.resolve(res(200, FOLDERS))
      if (url.startsWith('/api/v1/documents?')) {
        const folder = new URL(url, 'http://x').searchParams.get('folder')
        const items = folder === 'nha-thau-4' || !folder ? [doc()] : []
        return Promise.resolve(res(200, { items, total: items.length, page: 1, page_size: 100 }))
      }
      return Promise.resolve(handler(url, init) ?? res(404, { error: { code: 'not_found', message: 'x' } }))
    })
  }

  const wrap = () =>
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <AuthProvider>
            <ProjectDocumentsPage />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    FakeXhr.puts = []
    setAccessToken(null)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('groups the folders with their counts and lists the documents', async () => {
    serve('viewer')
    wrap()
    const tree = await screen.findByRole('navigation', { name: 'Các thư mục' })
    expect(within(tree).getByText('Nhà thầu')).toBeInTheDocument()
    expect(within(tree).getByRole('button', { name: /4\. Phần mềm.*2/ })).toBeInTheDocument()
    expect(within(tree).getByRole('button', { name: /Giám sát.*0/ })).toBeInTheDocument()
    const cards = await screen.findAllByRole('listitem')
    expect(within(cards[0]).getByText('Thuyet minh ky thuat')).toBeInTheDocument()
    expect(within(cards[0]).getByText(/Tài liệu phần mềm · 06\/10\/2026 · 2,0 MB/)).toBeInTheDocument()
  })

  it('asks the API for the chosen folder only', async () => {
    serve('viewer')
    wrap()
    await userEvent.setup().click(await screen.findByRole('button', { name: /Giám sát.*0/ }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes('folder=giam-sat'))).toBe(true))
    expect(await screen.findByText('Thư mục này chưa có tài liệu')).toBeInTheDocument()
  })

  it('opens a presigned link and never offers to delete, even to an administrator', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    serve('admin', (url) =>
      url === '/api/v1/documents/d1/download-url'
        ? res(200, { url: 'https://s3.test/d1', expires_in: 300, file_name: 'a.pdf', mime_type: 'application/pdf', inline: false })
        : null,
    )
    wrap()
    const card = (await screen.findAllByRole('listitem'))[0]
    await userEvent.setup().click(within(card).getByRole('button', { name: 'Tải về' }))
    await waitFor(() => expect(open).toHaveBeenCalledWith('https://s3.test/d1', '_blank', 'noopener'))
    expect(screen.queryByRole('button', { name: 'Xóa' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Phiên bản mới' })).not.toBeInTheDocument()
  })

  it('readers cannot upload', async () => {
    serve('viewer')
    wrap()
    await screen.findAllByRole('listitem')
    expect(screen.queryByRole('button', { name: 'Tải lên' })).not.toBeInTheDocument()
  })

  it('writers upload into the selected folder, without a package', async () => {
    serve('clerk', (url, init) => {
      if (url === '/api/v1/documents/upload-url') {
        return res(200, {
          document_id: 'new1',
          file_key: 'projects/p/packages/project/new1/v1/a.pdf',
          version: 1,
          upload: { url: 'https://s3.test/put', method: 'PUT', headers: {} },
          expires_in: 600,
          max_bytes: 104857600,
        })
      }
      if (url === '/api/v1/documents' && init?.method === 'POST') return res(201, doc({ id: 'new1' }))
      return null
    })
    wrap()
    const u = userEvent.setup()
    await u.click(await screen.findByRole('button', { name: /4\. Phần mềm.*2/ }))
    await u.click(screen.getByRole('button', { name: 'Tải lên' }))
    expect(screen.getByLabelText('Thư mục')).toHaveValue('nha-thau-4')
    expect(screen.queryByLabelText('Gói thầu')).not.toBeInTheDocument()
    await u.upload(await screen.findByLabelText('Chọn tệp'), new File(['%PDF-1.4'], 'Kien-truc.pdf', { type: 'application/pdf' }))
    await u.click(screen.getByRole('button', { name: 'Bắt đầu tải lên' }))
    expect(await screen.findByText(/Đã tải lên/)).toBeInTheDocument()
    const post = fetchMock.mock.calls.find(([url, init]) => url === '/api/v1/documents' && init?.method === 'POST')!
    expect(JSON.parse(post[1].body)).toMatchObject({
      package_id: null,
      doc_type: 'software_doc',
      tags: ['folder:nha-thau-4'],
      title: 'Kien-truc',
    })
    const upload = fetchMock.mock.calls.find(([url]) => url === '/api/v1/documents/upload-url')!
    expect(JSON.parse(upload[1].body).package_id).toBeNull()
  })

  it('has its own menu entry, only for projects that enable the module', () => {
    expect(navFor(['dashboard', 'project_documents']).all.map((i) => i.to)).toContain('/project-documents')
    expect(navFor(['dashboard', 'documents']).all.map((i) => i.to)).not.toContain('/project-documents')
  })
})
