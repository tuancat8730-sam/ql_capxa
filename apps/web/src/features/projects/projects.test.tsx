import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ProjectSwitcher } from '@/components/layout/ProjectSwitcher'
import { navFor } from '@/components/layout/nav'
import { AuthProvider } from '@/features/auth/AuthContext'
import { api, setAccessToken, setProjectId } from '@/lib/api'
import { type ProjectSummary, ProjectProvider, useRole } from './ProjectContext'

const res = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status })

const me = (role: string) => ({
  id: 'me', email: `${role}@example.test`, full_name: role, phone: null, role, is_active: true,
  must_change_password: false, last_login_at: null, created_at: '2026-01-01T00:00:00Z',
})

const project = (over: Partial<ProjectSummary>): ProjectSummary => ({
  id: 'p1',
  code: 'CX',
  name: 'Quản lý cấp xã',
  short_name: 'Cấp xã',
  project_type: 'procurement',
  role: 'director',
  modules: ['dashboard', 'packages', 'alerts'],
  is_archived: false,
  ...over,
})

const capxa = project({})
const sgd = project({
  id: 'p2',
  code: 'SGD',
  name: 'Theo dõi tiến độ SGD-HCM',
  short_name: 'SGD-HCM',
  project_type: 'software_delivery',
  role: 'viewer',
  modules: ['dashboard', 'schedule', 'weekly_reports', 'alerts'],
})

/** Shows what a page would see: its role and a project-scoped query. */
function Probe() {
  const role = useRole()
  const { data } = useQuery({ queryKey: ['things'], queryFn: () => api.get<{ n: number }>('/things') })
  return (
    <p>
      role:{role} things:{data?.n ?? '-'}
    </p>
  )
}

describe('projects', () => {
  const fetchMock = vi.fn()
  const seen: { url: string; project: string | null }[] = []

  function serve(role: string, projects: ProjectSummary[]) {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const headers = (init?.headers ?? {}) as Record<string, string>
      seen.push({ url, project: headers['X-Project-Id'] ?? null })
      if (url === '/api/v1/auth/refresh') return Promise.resolve(res(200, { access_token: 't' }))
      if (url === '/api/v1/auth/me') return Promise.resolve(res(200, me(role)))
      if (url === '/api/v1/projects') return Promise.resolve(res(200, projects))
      if (url === '/api/v1/things') return Promise.resolve(res(200, { n: headers['X-Project-Id'] === 'p2' ? 2 : 1 }))
      return Promise.resolve(res(404))
    })
  }

  function renderApp() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <AuthProvider>
            <ProjectProvider>
              <ProjectSwitcher />
              <Probe />
            </ProjectProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
  }

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    localStorage.clear()
    seen.length = 0
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    setAccessToken(null)
    setProjectId(null)
  })

  it('selects the first project and sends it with every request', async () => {
    serve('director', [capxa, sgd])
    renderApp()
    expect(await screen.findByText(/things:1/)).toBeInTheDocument()
    expect(seen.find((s) => s.url === '/api/v1/things')?.project).toBe('p1')
    expect(screen.getByRole('combobox', { name: 'Chuyển dự án' })).toHaveValue('p1')
  })

  it('uses the role of the selected project, not the account role', async () => {
    serve('director', [capxa, sgd])
    renderApp()
    expect(await screen.findByText(/role:director/)).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Chuyển dự án' }), 'p2')
    expect(await screen.findByText(/role:viewer/)).toBeInTheDocument()
  })

  it('switching drops the old project data and reloads with the new project', async () => {
    serve('director', [capxa, sgd])
    renderApp()
    await screen.findByText(/things:1/)
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Chuyển dự án' }), 'p2')
    expect(await screen.findByText(/things:2/)).toBeInTheDocument()
    expect(seen.filter((s) => s.url === '/api/v1/things').map((s) => s.project)).toEqual(['p1', 'p2'])
    expect(localStorage.getItem('qlda.project')).toBe('p2')
  })

  it('opens the project remembered from the last visit', async () => {
    localStorage.setItem('qlda.project', 'p2')
    serve('director', [capxa, sgd])
    renderApp()
    expect(await screen.findByText(/things:2/)).toBeInTheDocument()
    expect(seen.find((s) => s.url === '/api/v1/things')?.project).toBe('p2')
  })

  it('ignores a remembered project the user no longer has', async () => {
    localStorage.setItem('qlda.project', 'gone')
    serve('director', [capxa])
    renderApp()
    expect(await screen.findByText(/things:1/)).toBeInTheDocument()
  })

  it('with a single project shows its name and no switcher', async () => {
    serve('director', [capxa])
    renderApp()
    expect(await screen.findByText('Cấp xã')).toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('tells a user without any project to ask the administrator', async () => {
    serve('viewer', [])
    renderApp()
    expect(await screen.findByRole('alert')).toHaveTextContent('chưa được thêm vào dự án nào')
    await waitFor(() => expect(seen.some((s) => s.url === '/api/v1/things')).toBe(false))
  })
})

describe('navFor', () => {
  it('shows only the entries the project type enables', () => {
    const paths = navFor(sgd.modules).all.map((i) => i.to)
    expect(paths).toEqual(expect.arrayContaining(['/', '/schedule', '/weekly-reports', '/alerts']))
    expect(paths).not.toContain('/packages')
    expect(paths).not.toContain('/contracts')
  })

  it('fills the four bottom-bar slots from the enabled primary entries', () => {
    expect(navFor(sgd.modules).primary.map((i) => i.to)).toEqual(['/', '/schedule', '/weekly-reports', '/alerts'])
    expect(navFor(capxa.modules).primary.map((i) => i.to)).toEqual(['/', '/packages', '/alerts'])
  })

  it('keeps entries that belong to no module (profile, administration)', () => {
    const paths = navFor(sgd.modules).more.map((i) => i.to)
    expect(paths).toEqual(expect.arrayContaining(['/profile', '/admin/users', '/admin/projects']))
  })

  it('shows everything while the modules are not known yet', () => {
    expect(navFor(undefined).all.length).toBeGreaterThan(navFor(sgd.modules).all.length)
  })
})
