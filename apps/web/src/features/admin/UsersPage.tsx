import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { useAuth } from '@/features/auth/AuthContext'
import { api, ApiError, type Page, type User } from '@/lib/api'

const ROLES = ['admin', 'director', 'procurement', 'technical', 'cost', 'onsite', 'clerk', 'viewer'] as const

const formSchema = z.object({
  email: z.string().trim().regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, 'auth.emailInvalid'),
  full_name: z.string().trim().min(1, 'auth.passwordRequired'),
  phone: z.string().trim().optional(),
  role: z.enum(ROLES),
})
type FormValues = z.infer<typeof formSchema>

function UserForm({ user, onDone }: { user?: User; onDone: (temp?: string) => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: user?.email ?? '',
      full_name: user?.full_name ?? '',
      phone: user?.phone ?? '',
      role: (user?.role as FormValues['role']) ?? 'viewer',
    },
  })

  const onSubmit = async (v: FormValues) => {
    setError(null)
    const payload = { ...v, phone: v.phone || null }
    try {
      if (user) {
        await api.patch<User>(`/users/${user.id}`, {
          full_name: payload.full_name,
          phone: payload.phone,
          role: payload.role,
        })
        onDone()
      } else {
        const created = await api.post<User & { temporary_password: string }>('/users', payload)
        onDone(created.temporary_password)
      }
      await queryClient.invalidateQueries({ queryKey: ['users'] })
    } catch (err) {
      if (err instanceof ApiError && err.code === 'conflict') setError(t('users.conflict'))
      else if (err instanceof ApiError && err.status === 400) setError(t('users.self'))
      else setError(t('common.error'))
    }
  }

  const err = (name: keyof FormValues) =>
    errors[name] && (
      <p role="alert" className="mt-1 text-sm text-danger">
        {t(errors[name]?.message ?? '')}
      </p>
    )

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <div>
        <label htmlFor="u-name" className="mb-1 block text-sm font-medium">
          {t('users.fullName')}
        </label>
        <input id="u-name" className={inputClass} {...register('full_name')} />
        {err('full_name')}
      </div>
      <div>
        <label htmlFor="u-email" className="mb-1 block text-sm font-medium">
          {t('auth.email')}
        </label>
        <input
          id="u-email"
          type="email"
          inputMode="email"
          readOnly={!!user}
          className={inputClass}
          {...register('email')}
        />
        {err('email')}
      </div>
      <div>
        <label htmlFor="u-phone" className="mb-1 block text-sm font-medium">
          {t('users.phone')}
        </label>
        <input id="u-phone" type="tel" inputMode="tel" className={inputClass} {...register('phone')} />
      </div>
      <div>
        <label htmlFor="u-role" className="mb-1 block text-sm font-medium">
          {t('users.role')}
        </label>
        <select id="u-role" className={inputClass} {...register('role')}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`roles.${r}`)}
            </option>
          ))}
        </select>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" disabled={isSubmitting} className={primaryButton}>
        {t('common.save')}
      </button>
    </form>
  )
}

function TempPassword({ value, onClose }: { value: string; onClose: () => void }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  return (
    <BottomSheet title={t('users.tempPasswordTitle')} onClose={onClose}>
      <p className="mb-3 text-sm text-muted-foreground">{t('users.tempPasswordNote')}</p>
      <p className="mb-4 select-all break-all rounded-md bg-muted p-3 font-mono text-lg" data-testid="temp-password">
        {value}
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          className="min-h-11 rounded-md border border-border px-4"
          onClick={() => {
            void navigator.clipboard?.writeText(value)
            setCopied(true)
          }}
        >
          {copied ? t('users.copied') : t('users.copy')}
        </button>
        <button type="button" className={primaryButton} onClick={onClose}>
          {t('common.close')}
        </button>
      </div>
    </BottomSheet>
  )
}

function StatusBadge({ user }: { user: User }) {
  const { t } = useTranslation()
  if (!user.is_active) return <span className="text-danger">✕ {t('users.locked')}</span>
  if (user.must_change_password) return <span className="text-warning">⚠ {t('users.mustChange')}</span>
  return <span className="text-success">✓ {t('users.active')}</span>
}

export function UsersPage() {
  const { t } = useTranslation()
  const { user: me } = useAuth()
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [role, setRole] = useState('')
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<User | 'new' | null>(null)
  const [temp, setTemp] = useState<string | null>(null)

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['users', { q, role, page }],
    queryFn: () => {
      const p = new URLSearchParams({ page: String(page), page_size: '20' })
      if (q.trim()) p.set('q', q.trim())
      if (role) p.set('role', role)
      return api.get<Page<User>>(`/users?${p}`)
    },
  })

  const toggleActive = useMutation({
    mutationFn: (u: User) => api.patch<User>(`/users/${u.id}`, { is_active: !u.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  })
  const reset = useMutation({
    mutationFn: (u: User) => api.post<{ temporary_password: string }>(`/users/${u.id}/reset-password`),
    onSuccess: (r) => {
      setTemp(r.temporary_password)
      void queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })

  const actions = (u: User) => (
    <div className="flex flex-wrap gap-2">
      <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setEditing(u)}>
        {t('users.edit')}
      </button>
      <button
        type="button"
        className="min-h-11 rounded-md border border-border px-3"
        onClick={() => window.confirm(t('users.confirmReset')) && reset.mutate(u)}
      >
        {t('users.resetPassword')}
      </button>
      {u.id !== me?.id && (
        <button
          type="button"
          className="min-h-11 rounded-md border border-border px-3"
          onClick={() => (!u.is_active || window.confirm(t('users.confirmDeactivate'))) && toggleActive.mutate(u)}
        >
          {u.is_active ? t('users.deactivate') : t('users.activate')}
        </button>
      )}
    </div>
  )

  const lastLogin = (u: User) =>
    u.last_login_at
      ? new Date(u.last_login_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })
      : t('users.never')

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('users.title')}</h1>
        <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setEditing('new')}>
          {t('users.add')}
        </button>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 md:max-w-2xl">
        <input
          type="search"
          aria-label={t('users.search')}
          placeholder={t('users.search')}
          className={inputClass}
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setPage(1)
          }}
        />
        <select
          aria-label={t('users.role')}
          className={inputClass}
          value={role}
          onChange={(e) => {
            setRole(e.target.value)
            setPage(1)
          }}
        >
          <option value="">{t('users.allRoles')}</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`roles.${r}`)}
            </option>
          ))}
        </select>
      </div>

      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('common.empty')}</p>}
      {data && data.items.length > 0 && (
        <>
          <ResponsiveList
            caption={t('users.title')}
            rows={data.items}
            rowKey={(u) => u.id}
            renderCard={(u) => (
              <div className="space-y-2">
                <div>
                  <p className="font-semibold">{u.full_name}</p>
                  <p className="break-all text-sm text-muted-foreground">{u.email}</p>
                </div>
                <p className="text-sm">
                  {t(`roles.${u.role}`)} · <StatusBadge user={u} />
                </p>
                {actions(u)}
              </div>
            )}
            columns={[
              { key: 'name', header: t('users.fullName'), cell: (u) => <span className="font-medium">{u.full_name}</span> },
              { key: 'email', header: t('auth.email'), cell: (u) => u.email },
              { key: 'role', header: t('users.role'), cell: (u) => t(`roles.${u.role}`) },
              { key: 'status', header: t('users.status'), cell: (u) => <StatusBadge user={u} /> },
              { key: 'last', header: t('users.lastLogin'), cell: lastLogin, secondary: true },
              { key: 'actions', header: t('users.more'), cell: actions },
            ]}
          />
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{t('users.total', { count: data.total })}</span>
            <span className="flex gap-2">
              <button
                type="button"
                className="min-h-11 rounded-md border border-border px-3 disabled:opacity-50"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ‹
              </button>
              <button
                type="button"
                className="min-h-11 rounded-md border border-border px-3 disabled:opacity-50"
                disabled={page * data.page_size >= data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                ›
              </button>
            </span>
          </div>
        </>
      )}

      {editing && (
        <BottomSheet title={editing === 'new' ? t('users.add') : t('users.edit')} onClose={() => setEditing(null)}>
          <UserForm
            user={editing === 'new' ? undefined : editing}
            onDone={(tempPassword) => {
              setEditing(null)
              if (tempPassword) setTemp(tempPassword)
            }}
          />
        </BottomSheet>
      )}
      {temp && <TempPassword value={temp} onClose={() => setTemp(null)} />}
    </section>
  )
}
