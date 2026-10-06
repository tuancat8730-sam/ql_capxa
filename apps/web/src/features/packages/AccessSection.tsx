import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { primaryButton } from '@/features/auth/LoginPage'
import { api, type Page, type User } from '@/lib/api'

interface AccessOut {
  users: Pick<User, 'id' | 'full_name' | 'email' | 'role'>[]
}

/** Admin-only: choose who may open the sensitive documents of a package (SPEC section 8). */
export function AccessSection({ packageId }: { packageId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [saved, setSaved] = useState(false)

  const current = useQuery({
    queryKey: ['package-access', packageId],
    queryFn: () => api.get<AccessOut>(`/packages/${packageId}/access`),
  })
  const candidates = useQuery({
    queryKey: ['access-candidates'],
    queryFn: async () => {
      const [a, b] = await Promise.all([
        api.get<Page<User>>('/users?role=procurement&is_active=true&page_size=100'),
        api.get<Page<User>>('/users?role=technical&is_active=true&page_size=100'),
      ])
      return [...a.items, ...b.items]
    },
  })

  useEffect(() => {
    if (current.data) setSelected(new Set(current.data.users.map((u) => u.id)))
  }, [current.data])

  const save = useMutation({
    mutationFn: () => api.put<AccessOut>(`/packages/${packageId}/access`, { user_ids: [...selected] }),
    onSuccess: async () => {
      setSaved(true)
      await queryClient.invalidateQueries({ queryKey: ['package-access', packageId] })
    },
  })

  const toggle = (id: string) => {
    setSaved(false)
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <section className="space-y-3 rounded-md border border-border p-3" aria-label={t('access.title')}>
      <h3 className="font-semibold">🔒 {t('access.title')}</h3>
      <p className="text-sm text-muted-foreground">{t('access.hint')}</p>
      {candidates.data?.length === 0 && <p className="text-muted-foreground">{t('access.none')}</p>}
      <ul className="space-y-1">
        {candidates.data?.map((u) => (
          <li key={u.id}>
            <label className="flex min-h-11 items-center gap-3">
              <input type="checkbox" className="size-5" checked={selected.has(u.id)} onChange={() => toggle(u.id)} />
              <span>
                {u.full_name} <span className="text-sm text-muted-foreground">· {t(`roles.${u.role}`)}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <button type="button" className={`${primaryButton} !w-auto`} onClick={() => save.mutate()} disabled={save.isPending}>
        {t('access.save')}
      </button>
      {saved && <p role="status" className="text-sm text-success">✓ {t('access.saved')}</p>}
    </section>
  )
}
