import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ExportButton } from '@/components/ui/ExportButton'
import { primaryButton } from '@/features/auth/LoginPage'
import { ApiError, api } from '@/lib/api'
import { formatMoney } from '@/lib/format'

interface ImportResult {
  dry_run: boolean
  rows_total: number
  rows_valid: number
  errors: { row: number; field: string; message: string }[]
  total_amount: number
  contract_value: number | null
  matches_contract_value: boolean | null
  imported: number
}

/** Excel import of goods lines: check the file first, write only after the user confirms (SPEC 4.13). */
export function ImportItems({ contractId }: { contractId: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [replace, setReplace] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<number | null>(null)

  const send = useMutation({
    mutationFn: ({ commit }: { commit: boolean }) => {
      const form = new FormData()
      form.append('file', file as File)
      const q = new URLSearchParams({ contract_id: contractId, commit: String(commit), replace: String(replace) })
      return api.postForm<ImportResult>(`/import/contract-items?${q}`, form)
    },
    onSuccess: (r) => {
      setError(null)
      setResult(r)
      if (!r.dry_run) {
        setDone(r.imported)
        setFile(null)
        if (input.current) input.current.value = ''
        void queryClient.invalidateQueries({ queryKey: ['contracts'] })
      }
    },
    onError: (e) => {
      setResult(null)
      setError(e instanceof ApiError ? e.message : t('common.error'))
    },
  })

  const choose = (f: File | null) => {
    setFile(f)
    setResult(null)
    setError(null)
    setDone(null)
  }
  const clean = result !== null && result.dry_run && result.errors.length === 0 && result.rows_valid > 0

  return (
    <section aria-label={t('importItems.title')} className="space-y-3 rounded-md border border-border p-3">
      <h3 className="font-semibold">{t('importItems.title')}</h3>
      <p className="text-sm text-muted-foreground">{t('importItems.hint')}</p>
      <div className="flex flex-wrap items-center gap-2">
        <ExportButton path="/import/contract-items/template.xlsx" label={t('importItems.template')} />
        <label className="inline-flex min-h-11 cursor-pointer items-center rounded-md border border-border px-3">
          {t('importItems.choose')}
          <input
            ref={input}
            type="file"
            accept=".xlsx"
            aria-label={t('importItems.choose')}
            className="sr-only"
            onChange={(e) => choose(e.target.files?.[0] ?? null)}
          />
        </label>
        {file && <span className="text-sm">{file.name}</span>}
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
        {t('importItems.replace')}
      </label>
      <button type="button" className={`${primaryButton} !w-auto`} disabled={!file || send.isPending} onClick={() => send.mutate({ commit: false })}>
        {t('importItems.check')}
      </button>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {done !== null && (
        <p role="status" className="font-semibold text-success">
          {t('importItems.done', { n: done })}
        </p>
      )}
      {result && result.dry_run && (
        <div className="space-y-2 text-sm">
          <p>{t('importItems.result', { valid: result.rows_valid, total: result.rows_total, amount: formatMoney(result.total_amount) })}</p>
          <p className={result.matches_contract_value === false ? 'text-warning' : ''}>
            {result.matches_contract_value === null
              ? t('importItems.noValue')
              : result.matches_contract_value
                ? t('importItems.matches')
                : t('importItems.differs', { value: formatMoney(result.contract_value) })}
          </p>
          {result.errors.length > 0 && (
            <ul role="alert" className="space-y-1 text-danger">
              {result.errors.slice(0, 20).map((e) => (
                <li key={`${e.row}-${e.field}`}>{t('importItems.errors', { row: e.row, message: e.message })}</li>
              ))}
            </ul>
          )}
          {clean && (
            <button type="button" className={`${primaryButton} !w-auto`} disabled={send.isPending} onClick={() => send.mutate({ commit: true })}>
              {t('importItems.commit', { n: result.rows_valid })}
            </button>
          )}
        </div>
      )}
    </section>
  )
}
