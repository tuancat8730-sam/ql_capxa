import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { ApiError, api } from '@/lib/api'
import { formatDate } from '@/lib/format'

interface Holiday {
  id: string
  day: string
  name: string
}

/** Admin settings: the holiday list that the level-2 issue deadline skips (SPEC 7.4). */
export function SettingsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [day, setDay] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data, isPending, isError, refetch } = useQuery({ queryKey: ['holidays'], queryFn: () => api.get<Holiday[]>('/admin/holidays') })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['holidays'] })
  const fail = (e: unknown) => setError(e instanceof ApiError && e.status === 409 ? t('settings.duplicate') : t('common.error'))

  const add = useMutation({
    mutationFn: () => api.post('/admin/holidays', { day, name: name.trim() }),
    onSuccess: () => {
      setError(null)
      setDay('')
      setName('')
      return refresh()
    },
    onError: fail,
  })
  const remove = useMutation({
    mutationFn: (id: string) => api.request<void>('DELETE', `/admin/holidays/${id}`),
    onSuccess: refresh,
    onError: fail,
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (day && name.trim()) add.mutate()
  }

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold md:text-2xl">{t('settings.title')}</h1>
      <h2 className="text-lg font-semibold">{t('settings.holidays')}</h2>
      <p className="text-sm text-muted-foreground">{t('settings.holidaysHint')}</p>

      <form onSubmit={submit} className="grid gap-2 sm:grid-cols-[10rem_1fr_auto]" aria-label={t('settings.add')}>
        <label className="space-y-1 text-sm">
          <span>{t('settings.day')}</span>
          <input type="date" required className={inputClass} value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label className="space-y-1 text-sm">
          <span>{t('settings.name')}</span>
          <input required maxLength={200} className={inputClass} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <button type="submit" className={`${primaryButton} !w-auto self-end`} disabled={add.isPending || !day || !name.trim()}>
          {t('settings.add')}
        </button>
      </form>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && (
        <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
          {t('common.retry')}
        </button>
      )}
      {data && data.length === 0 && <p className="text-muted-foreground">{t('settings.none')}</p>}
      <ul className="space-y-2">
        {data?.map((h) => (
          <li key={h.id} className="flex items-center justify-between gap-2 rounded-md border border-border p-3">
            <span>
              <span className="font-medium">{formatDate(h.day)}</span> · {h.name}
            </span>
            <button type="button" className="min-h-11 rounded-md border border-border px-3 text-sm" onClick={() => remove.mutate(h.id)}>
              {t('settings.remove')}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
