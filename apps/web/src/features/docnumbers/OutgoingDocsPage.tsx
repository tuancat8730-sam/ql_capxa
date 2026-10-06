import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/features/auth/AuthContext'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { ApiError, api, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { can } from '@/lib/permissions'

const DOC_KINDS = ['CV', 'BC', 'TB', 'BB', 'QD', 'TT', 'KH'] as const
type DocKind = (typeof DOC_KINDS)[number]

interface DocNumber {
  id: string
  year: number
  doc_kind: DocKind
  seq: number
  doc_no: string
  subject: string
  issued_date: string
  created_by_name: string | null
}

export function OutgoingDocsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = can(user?.role, 'doc_number', 'W')
  const [kind, setKind] = useState<DocKind>('CV')
  const [subject, setSubject] = useState('')
  const [issuedDate, setIssuedDate] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fYear, setFYear] = useState('')
  const [fKind, setFKind] = useState('')
  const [q, setQ] = useState('')

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['doc-numbers', { fYear, fKind, q }],
    queryFn: () => {
      const p = new URLSearchParams({ page_size: '100' })
      if (fYear) p.set('year', fYear)
      if (fKind) p.set('doc_kind', fKind)
      if (q.trim()) p.set('q', q.trim())
      return api.get<Page<DocNumber>>(`/outgoing-doc-numbers?${p}`)
    },
  })

  const issue = useMutation({
    mutationFn: () =>
      api.post<DocNumber>('/outgoing-doc-numbers', {
        doc_kind: kind,
        subject,
        ...(issuedDate ? { issued_date: issuedDate } : {}),
      }),
    onSuccess: (row) => {
      setError(null)
      setMessage(t('docNumbers.issued', { no: row.doc_no }))
      setSubject('')
      return queryClient.invalidateQueries({ queryKey: ['doc-numbers'] })
    },
    onError: (e) => {
      setMessage(null)
      setError(e instanceof ApiError ? e.message : t('common.error'))
    },
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (subject.trim()) issue.mutate()
  }
  const copy = async (no: string) => {
    try {
      await navigator.clipboard.writeText(no)
      setMessage(t('docNumbers.copied'))
    } catch {
      setMessage(no)
    }
  }
  const years = [...new Set((data?.items ?? []).map((r) => r.year))]

  return (
    <section className="space-y-4">
      <h1 className="text-xl font-semibold md:text-2xl">{t('docNumbers.title')}</h1>

      {canWrite && (
        <form onSubmit={submit} className="space-y-3 rounded-md border border-border p-3" aria-label={t('docNumbers.new')}>
          <h2 className="text-lg font-semibold">{t('docNumbers.new')}</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="space-y-1">
              <span className="text-sm">{t('docNumbers.kind')}</span>
              <select value={kind} onChange={(e) => setKind(e.target.value as DocKind)} className={inputClass}>
                {DOC_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {k} · {t(`docNumbers.kinds.${k}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-sm">{t('docNumbers.issuedDate')}</span>
              <input type="date" value={issuedDate} onChange={(e) => setIssuedDate(e.target.value)} className={inputClass} />
            </label>
          </div>
          <label className="block space-y-1">
            <span className="text-sm">{t('docNumbers.subject')}</span>
            <textarea required rows={2} maxLength={500} value={subject} onChange={(e) => setSubject(e.target.value)} className={inputClass} />
          </label>
          <button type="submit" disabled={issue.isPending || !subject.trim()} className={primaryButton}>
            {t('docNumbers.issue')}
          </button>
        </form>
      )}

      {message && (
        <p role="status" className="font-semibold text-success">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t('docNumbers.search')}
          aria-label={t('docNumbers.search')}
          className={`${inputClass} flex-1 sm:max-w-sm`}
        />
        <select aria-label={t('docNumbers.year')} value={fYear} onChange={(e) => setFYear(e.target.value)} className={`${inputClass} sm:w-40`}>
          <option value="">{t('docNumbers.allYears')}</option>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
        <select aria-label={t('docNumbers.kind')} value={fKind} onChange={(e) => setFKind(e.target.value)} className={`${inputClass} sm:w-44`}>
          <option value="">{t('docNumbers.allKinds')}</option>
          {DOC_KINDS.map((k) => (
            <option key={k} value={k}>
              {k} · {t(`docNumbers.kinds.${k}`)}
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
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('docNumbers.none')}</p>}
      <ul className="space-y-2">
        {data?.items.map((r) => (
          <li key={r.id} className="flex items-start justify-between gap-2 rounded-md border border-border p-3">
            <div className="space-y-1">
              <p className="font-mono text-base font-semibold">{r.doc_no}</p>
              <p className="text-sm">{r.subject}</p>
              <p className="text-xs text-muted-foreground">
                {formatDate(r.issued_date)}
                {r.created_by_name && ` · ${t('docNumbers.createdBy')}: ${r.created_by_name}`}
              </p>
            </div>
            <button type="button" className="min-h-11 shrink-0 rounded-md border border-border px-3 text-sm" onClick={() => void copy(r.doc_no)}>
              {t('docNumbers.copy')}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
