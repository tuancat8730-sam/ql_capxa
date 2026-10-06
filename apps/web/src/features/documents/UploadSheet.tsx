import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type ChangeEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { PhotoCapture } from '@/components/ui/PhotoCapture'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError, type Page } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { guessMime, uploadFile } from '@/lib/upload'
import type { DocType, DocumentItem } from './types'
import { formatSize } from './types'

const MAX_BYTES = 100 * 1024 * 1024
const ACCEPT = '.pdf,.docx,.xlsx,.doc,.xls,.jpg,.jpeg,.png,.zip'
const ALLOWED = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/msword',
  'application/vnd.ms-excel',
  'image/jpeg',
  'image/png',
  'application/zip',
  'application/x-zip-compressed',
])

interface Row {
  id: number
  file: File
  title: string
  docType: string
  docNo: string
  docDate: string
  state: 'waiting' | 'uploading' | 'done' | 'failed'
  progress: number
  error?: string
  /** Rejected on the client (type/size): never sent, only removable. */
  invalid: boolean
}

interface UploadSheetProps {
  /** Fix the package (opened from a package page); otherwise the user picks one per batch. */
  packageId?: string | null
  /** Pre-select the document type, e.g. from a checklist item. */
  docType?: string
  /** Upload a new version of this document instead of a new document. */
  parent?: DocumentItem
  onClose: () => void
}

const stem = (name: string) => name.replace(/\.[^.]+$/, '')
const sendable = (r: Row) => !r.invalid && (r.state === 'waiting' || r.state === 'failed')

export function UploadSheet({ packageId: fixedPackage, docType, parent, onClose }: UploadSheetProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<Row[]>([])
  const [packageId, setPackageId] = useState<string>(fixedPackage ?? parent?.package_id ?? '')
  const [running, setRunning] = useState(false)
  const [nextId, setNextId] = useState(1)

  const types = useQuery({ queryKey: ['doc-types'], queryFn: () => api.get<DocType[]>('/doc-types'), staleTime: Infinity })
  const packages = useQuery({
    queryKey: ['packages', 'options'],
    queryFn: () => api.get<Page<{ id: string; number: number; name: string }>>('/packages?page_size=100'),
    enabled: !fixedPackage && !parent,
  })

  const patch = (id: number, change: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...change } : r)))

  const addFiles = (files: File[]) => {
    const fresh = files.slice(parent ? 0 : undefined, parent ? 1 : undefined).map((file, i): Row => {
      const mime = guessMime(file)
      const error = file.size > MAX_BYTES ? t('documents.tooLarge') : ALLOWED.has(mime) ? undefined : t('documents.badType')
      return {
        id: nextId + i,
        file,
        title: parent?.title ?? stem(file.name),
        docType: docType ?? parent?.doc_type ?? (mime.startsWith('image/') ? 'photo' : 'other'),
        docNo: '',
        docDate: '',
        state: error ? 'failed' : 'waiting',
        progress: 0,
        error,
        invalid: !!error,
      }
    })
    setNextId((n) => n + fresh.length)
    setRows((rs) => (parent ? fresh : [...rs, ...fresh]))
  }

  const onPick = (e: ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(e.target.files ?? []))
    e.target.value = ''
  }

  const send = async (row: Row) => {
    patch(row.id, { state: 'uploading', progress: 0, error: undefined })
    try {
      const ref = await uploadFile(row.file, {
        packageId: packageId || null,
        parentDocumentId: parent?.id ?? null,
        onProgress: (p) => patch(row.id, { progress: p }),
      })
      if (parent) {
        await api.post(`/documents/${parent.id}/versions`, { ...ref })
      } else {
        await api.post('/documents', {
          ...ref,
          package_id: packageId || null,
          doc_type: row.docType,
          title: row.title.trim() || stem(row.file.name),
          doc_no: row.docNo || null,
          doc_date: row.docDate || null,
        })
      }
      patch(row.id, { state: 'done', progress: 1 })
    } catch (err) {
      const message =
        err instanceof ApiError && err.code === 'duplicate_document'
          ? t('documents.duplicate', { title: (err.details as { title?: string } | undefined)?.title ?? '' })
          : err instanceof ApiError
            ? err.message
            : t('common.error')
      patch(row.id, { state: 'failed', error: message })
    }
  }

  const start = async () => {
    setRunning(true)
    for (const row of rows.filter(sendable)) {
      await send(row)
    }
    setRunning(false)
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['documents'] }),
      queryClient.invalidateQueries({ queryKey: ['checklist'] }),
    ])
  }

  const pending = rows.some(sendable)
  const allDone = rows.length > 0 && rows.every((r) => r.state === 'done')

  return (
    <BottomSheet title={parent ? t('documents.uploadNewVersion') : t('documents.upload')} onClose={onClose}>
      <div className="space-y-4">
        {!fixedPackage && !parent && (
          <div>
            <label htmlFor="up-package" className="mb-1 block text-sm font-medium">
              {t('documents.package')}
            </label>
            <select id="up-package" className={inputClass} value={packageId} onChange={(e) => setPackageId(e.target.value)}>
              <option value="">{t('documents.projectLevel')}</option>
              {packages.data?.items.map((p) => (
                <option key={p.id} value={p.id}>
                  {t('packages.number', { n: String(p.number).padStart(2, '0') })}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <label className="inline-flex min-h-11 cursor-pointer items-center rounded-md border border-border px-4">
            {t('documents.chooseFiles')}
            <input type="file" multiple={!parent} accept={ACCEPT} hidden onChange={onPick} aria-label={t('documents.chooseFiles')} />
          </label>
          <PhotoCapture onFiles={addFiles} disabled={running} />
        </div>
        <p className="text-sm text-muted-foreground">{t('documents.dropHint')}</p>

        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.id} className="space-y-2 rounded-md border border-border p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="break-all text-sm font-medium">
                  {r.file.name} <span className="text-muted-foreground">({formatSize(r.file.size)})</span>
                </p>
                {r.state !== 'uploading' && r.state !== 'done' && (
                  <button
                    type="button"
                    aria-label={`${t('documents.removeFile')}: ${r.file.name}`}
                    className="min-h-11 min-w-11"
                    onClick={() => setRows((rs) => rs.filter((x) => x.id !== r.id))}
                  >
                    ✕
                  </button>
                )}
              </div>
              {!parent && r.state !== 'done' && (
                <div className="grid gap-2 sm:grid-cols-2">
                  <input aria-label={t('documents.docTitle')} className={inputClass} value={r.title} onChange={(e) => patch(r.id, { title: e.target.value })} />
                  <select aria-label={t('documents.docType')} className={inputClass} value={r.docType} onChange={(e) => patch(r.id, { docType: e.target.value })}>
                    {types.data?.map((d) => (
                      <option key={d.code} value={d.code}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                  <input aria-label={t('documents.docNo')} placeholder={t('documents.docNo')} className={inputClass} value={r.docNo} onChange={(e) => patch(r.id, { docNo: e.target.value })} />
                  <input aria-label={t('documents.docDate')} type="date" className={inputClass} value={r.docDate} onChange={(e) => patch(r.id, { docDate: e.target.value })} />
                </div>
              )}
              {r.state === 'uploading' && (
                <div role="progressbar" aria-valuenow={Math.round(r.progress * 100)} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-primary" style={{ width: `${r.progress * 100}%` }} />
                </div>
              )}
              <p className={`text-sm ${r.state === 'failed' ? 'text-danger' : r.state === 'done' ? 'text-success' : 'text-muted-foreground'}`} role={r.state === 'failed' ? 'alert' : undefined}>
                {r.state === 'waiting' && t('documents.waiting')}
                {r.state === 'uploading' && t('documents.uploading')}
                {r.state === 'done' && `✓ ${t('documents.done')}`}
                {r.state === 'failed' && `✕ ${r.error ?? t('documents.failed')}`}
              </p>
              {r.docDate && r.state === 'waiting' && <span className="sr-only">{formatDate(r.docDate)}</span>}
            </li>
          ))}
        </ul>

        {allDone ? (
          <button type="button" className={primaryButton} onClick={onClose}>
            {t('common.close')}
          </button>
        ) : (
          <button type="button" className={primaryButton} disabled={running || !pending || rows.length === 0} onClick={() => void start()}>
            {t('documents.startUpload')}
          </button>
        )}
      </div>
    </BottomSheet>
  )
}
