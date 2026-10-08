import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import type { ProjectSummary } from '@/features/projects/ProjectContext'
import { api, ApiError, type Page, type User } from '@/lib/api'

const ROLES = ['admin', 'director', 'procurement', 'technical', 'cost', 'onsite', 'clerk', 'viewer'] as const
const TYPES = ['procurement', 'software_delivery'] as const

interface Member {
  user_id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
}

function NewProject({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [shortName, setShortName] = useState('')
  const [type, setType] = useState<(typeof TYPES)[number]>('software_delivery')
  const [error, setError] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () =>
      api.post<ProjectSummary>('/projects', {
        code: code.trim(),
        name: name.trim(),
        short_name: shortName.trim() || null,
        project_type: type,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['projects'] })
      onDone()
    },
    onError: (err) =>
      setError(err instanceof ApiError && err.code === 'conflict' ? t('projects.duplicate') : t('common.error')),
  })

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        setError(null)
        create.mutate()
      }}
    >
      <div>
        <label htmlFor="p-code" className="mb-1 block text-sm font-medium">
          {t('projects.code')}
        </label>
        <input id="p-code" required className={inputClass} value={code} onChange={(e) => setCode(e.target.value)} />
      </div>
      <div>
        <label htmlFor="p-name" className="mb-1 block text-sm font-medium">
          {t('projects.name')}
        </label>
        <input id="p-name" required className={inputClass} value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div>
        <label htmlFor="p-short" className="mb-1 block text-sm font-medium">
          {t('projects.shortName')}
        </label>
        <input id="p-short" className={inputClass} value={shortName} onChange={(e) => setShortName(e.target.value)} />
      </div>
      <div>
        <label htmlFor="p-type" className="mb-1 block text-sm font-medium">
          {t('projects.type')}
        </label>
        <select
          id="p-type"
          className={inputClass}
          value={type}
          onChange={(e) => setType(e.target.value as (typeof TYPES)[number])}
        >
          {TYPES.map((v) => (
            <option key={v} value={v}>
              {t(`projects.types.${v}`)}
            </option>
          ))}
        </select>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" disabled={create.isPending} className={primaryButton}>
        {t('common.save')}
      </button>
    </form>
  )
}

function Members({ project }: { project: ProjectSummary }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const key = ['project-members', project.id]
  const [adding, setAdding] = useState('')

  const members = useQuery({ queryKey: key, queryFn: () => api.get<Member[]>(`/projects/${project.id}/members`) })
  const users = useQuery({
    queryKey: ['users', { all: true }],
    queryFn: () => api.get<Page<User>>('/users?page=1&page_size=100'),
  })

  const setRole = useMutation({
    mutationFn: (v: { userId: string; role: string }) =>
      api.put<Member>(`/projects/${project.id}/members/${v.userId}`, { role: v.role }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  })
  const remove = useMutation({
    mutationFn: (userId: string) => api.delete(`/projects/${project.id}/members/${userId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  })

  const seated = new Set((members.data ?? []).map((m) => m.user_id))
  const candidates = (users.data?.items ?? []).filter((u) => u.is_active && !seated.has(u.id) && u.role !== 'admin')

  return (
    <div className="space-y-3">
      {members.isPending && <p role="status">{t('common.loading')}</p>}
      {members.data?.length === 0 && <p className="text-sm text-muted-foreground">{t('projects.noMembers')}</p>}
      <ul className="space-y-2">
        {members.data?.map((m) => (
          <li key={m.user_id} className="flex flex-wrap items-center gap-2 rounded-md border border-border p-2">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{m.full_name}</p>
              <p className="truncate text-sm text-muted-foreground">{m.email}</p>
            </div>
            <select
              aria-label={`${t('users.role')} ${m.full_name}`}
              className="min-h-11 rounded-md border border-border bg-background px-2"
              value={m.role}
              onChange={(e) => setRole.mutate({ userId: m.user_id, role: e.target.value })}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`roles.${r}`)}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="min-h-11 rounded-md border border-border px-3"
              onClick={() => window.confirm(t('projects.confirmRemove')) && remove.mutate(m.user_id)}
            >
              {t('projects.remove')}
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <select
          aria-label={t('projects.chooseUser')}
          className={inputClass}
          value={adding}
          onChange={(e) => setAdding(e.target.value)}
        >
          <option value="">{t('projects.chooseUser')}</option>
          {candidates.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name} ({u.email})
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!adding}
          className="min-h-11 shrink-0 rounded-md border border-border px-3"
          onClick={() => {
            const user = candidates.find((u) => u.id === adding)
            if (user) setRole.mutate({ userId: user.id, role: user.role })
            setAdding('')
          }}
        >
          {t('projects.addMember')}
        </button>
      </div>
    </div>
  )
}

export function ProjectsPage() {
  const { t } = useTranslation()
  const [adding, setAdding] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const { data, isPending, isError } = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<ProjectSummary[]>('/projects'),
  })

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('projects.title')}</h1>
        <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setAdding(true)}>
          {t('projects.add')}
        </button>
      </div>
      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && <p role="alert">{t('common.error')}</p>}
      <ul className="space-y-3">
        {data?.map((p) => (
          <li key={p.id} className="rounded-lg border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="font-semibold">
                  {p.short_name ?? p.name} <span className="text-sm text-muted-foreground">· {p.code}</span>
                </p>
                <p className="text-sm text-muted-foreground">{t(`projects.types.${p.project_type}`)}</p>
              </div>
              <button
                type="button"
                aria-expanded={open === p.id}
                className="min-h-11 rounded-md border border-border px-3"
                onClick={() => setOpen(open === p.id ? null : p.id)}
              >
                {t('projects.members')}
              </button>
            </div>
            {open === p.id && (
              <div className="mt-3 border-t border-border pt-3">
                <Members project={p} />
              </div>
            )}
          </li>
        ))}
      </ul>
      {adding && (
        <BottomSheet title={t('projects.add')} onClose={() => setAdding(false)}>
          <NewProject onDone={() => setAdding(false)} />
        </BottomSheet>
      )}
    </section>
  )
}
