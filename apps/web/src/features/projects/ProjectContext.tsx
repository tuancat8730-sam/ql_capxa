import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/features/auth/AuthContext'
import { api, setProjectId } from '@/lib/api'

export interface ProjectSummary {
  id: string
  code: string
  name: string
  short_name: string | null
  project_type: 'procurement' | 'software_delivery'
  /** The caller's role in this project (a system admin is "admin" everywhere). */
  role: string
  /** Menu modules the project's type switches on. */
  modules: string[]
  is_archived: boolean
}

interface ProjectValue {
  projects: ProjectSummary[]
  current: ProjectSummary | null
  select: (id: string) => void
}

const STORAGE_KEY = 'qlda.project'
const ProjectContext = createContext<ProjectValue | null>(null)

function remembered(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function remember(id: string) {
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch {
    /* private mode: the choice just is not kept */
  }
}

/**
 * Loads the projects of the signed-in user and keeps one of them selected.
 * Every API call carries the selected project (X-Project-Id), so children render only once it is set.
 */
export function ProjectProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { status, user } = useAuth()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(remembered)

  const { data, isPending, isError } = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<ProjectSummary[]>('/projects'),
    enabled: status === 'authed',
    staleTime: 5 * 60_000,
  })

  const projects = useMemo(() => (data ?? []).filter((p) => !p.is_archived), [data])
  const current = projects.find((p) => p.id === selectedId) ?? projects[0] ?? null
  // Set while rendering, not in an effect: children's effects run before the parent's.
  setProjectId(current?.id ?? null)

  const select = useCallback(
    (id: string) => {
      remember(id)
      setSelectedId(id)
      // data of the old project must not show up in the new one
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'projects' })
    },
    [queryClient],
  )

  const value = useMemo(() => ({ projects, current, select }), [projects, current, select])

  if (status === 'loading' || (status === 'authed' && isPending)) {
    return (
      <p role="status" className="p-6 text-muted-foreground">
        {t('common.loading')}
      </p>
    )
  }
  if (isError) {
    return (
      <p role="alert" className="p-6 text-danger">
        {t('common.error')}
      </p>
    )
  }
  if (!current && user?.role !== 'admin') {
    return (
      <p role="alert" className="p-6">
        {t('projects.none')}
      </p>
    )
  }
  return (
    <ProjectContext.Provider value={value}>
      {/* a fresh subtree per project: no local state survives a switch */}
      <div key={current?.id ?? 'none'} className="contents">
        {children}
      </div>
    </ProjectContext.Provider>
  )
}

/** The projects and the selected one; outside a provider (tests, login) there are none. */
export function useProjects(): ProjectValue {
  return useContext(ProjectContext) ?? { projects: [], current: null, select: () => undefined }
}

/** The role that counts for permissions: the one in the selected project, else the account's. */
export function useRole(): string | undefined {
  const { current } = useProjects()
  const { user } = useAuth()
  return current?.role ?? user?.role
}
