import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { primaryButton } from '@/features/auth/LoginPage'
import { ApiError, api } from '@/lib/api'
import { FindingsList } from './FindingsList'
import { periodText } from './period'
import type { ImportPreview } from './types'

/** Upload a plan document: read and preview first, save only after the user confirms. */
export function PlanImportSheet({ packageId, onClose }: { packageId: string; onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [error, setError] = useState<string | null>(null)

  const send = useMutation({
    mutationFn: ({ commit }: { commit: boolean }) => {
      const form = new FormData()
      form.append('file', file as File)
      return api.postForm<ImportPreview>(`/packages/${packageId}/plan/import?commit=${commit}`, form)
    },
    onSuccess: async (r) => {
      setError(null)
      setPreview(r)
      if (!r.dry_run) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['plan', packageId] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ])
        onClose()
      }
    },
    onError: (e) => {
      setPreview(null)
      setError(e instanceof ApiError ? e.message : t('common.error'))
    },
  })

  const choose = (f: File | null) => {
    setFile(f)
    setPreview(null)
    setError(null)
  }

  return (
    <BottomSheet title={t('plan.importTitle')} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">{t('plan.importHint')}</p>
        <label className="inline-flex min-h-11 cursor-pointer items-center rounded-md border border-border px-3">
          {t('plan.choose')}
          <input
            ref={input}
            type="file"
            accept=".docx,.doc"
            aria-label={t('plan.choose')}
            className="sr-only"
            onChange={(e) => choose(e.target.files?.[0] ?? null)}
          />
        </label>
        {file && <span className="ml-2 text-sm">{file.name}</span>}
        <div>
          <button type="button" className={`${primaryButton} !w-auto`} disabled={!file || send.isPending} onClick={() => send.mutate({ commit: false })}>
            {t('plan.check')}
          </button>
        </div>

        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}

        {preview && (
          <div className="space-y-3 text-sm">
            <p className="font-medium">
              {t('plan.previewCounts', {
                items: preview.items.length,
                qty: preview.total_quantity,
                steps: preview.steps.length,
                places: preview.locations,
              })}
            </p>
            <p className="text-muted-foreground">
              {t('plan.contractPeriod')}: {periodText(preview.contract_start, preview.contract_end) ?? '–'} · {t('plan.implementPeriod')}:{' '}
              {periodText(preview.implement_start, preview.implement_end) ?? '–'}
            </p>
            {preview.replaces_existing && (
              <p role="status" className="rounded-md bg-muted p-2">
                {t('plan.replacesNote', { n: preview.kept_tracking })}
              </p>
            )}
            <FindingsList findings={preview.findings} />
            <ul className="max-h-48 space-y-1 overflow-y-auto" aria-label={t('plan.steps')}>
              {preview.steps.map((s) => (
                <li key={s.step_no} className="flex justify-between gap-2">
                  <span className="truncate">
                    {s.step_no}. {s.summary.replace(/^[-–]\s*/, '')}
                  </span>
                  <span className="shrink-0 text-muted-foreground">
                    {s.start_date || s.end_date ? periodText(s.start_date, s.end_date) : t('plan.noTime')}
                    {s.keeps_tracking && ` · ${t('plan.keeps')}`}
                  </span>
                </li>
              ))}
            </ul>
            <button type="button" className={`${primaryButton} !w-auto`} disabled={send.isPending} onClick={() => send.mutate({ commit: true })}>
              {t('plan.save')}
            </button>
          </div>
        )}
      </div>
    </BottomSheet>
  )
}

