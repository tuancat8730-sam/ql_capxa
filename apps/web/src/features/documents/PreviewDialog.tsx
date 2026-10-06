import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import type { Download, DocumentItem } from './types'

interface PreviewDialogProps {
  doc: DocumentItem
  onClose: () => void
}

/** Full-screen viewer for PDFs and images (SPEC 15.5f); anything else is download-only. */
export function PreviewDialog({ doc, onClose }: PreviewDialogProps) {
  const { t } = useTranslation()
  const { data, isPending, isError } = useQuery({
    queryKey: ['download-url', doc.id, 'inline'],
    queryFn: () => api.get<Download>(`/documents/${doc.id}/download-url?inline=true`),
    staleTime: 0,
    gcTime: 0,
  })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const download = () => data && window.open(data.url, '_blank', 'noopener')

  return (
    <div role="dialog" aria-modal="true" aria-label={doc.title} className="fixed inset-0 z-50 flex flex-col bg-background">
      <header className="flex items-center justify-between gap-2 border-b border-border p-2">
        <h2 className="truncate px-2 font-semibold">{doc.title}</h2>
        <div className="flex gap-2">
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={download} disabled={!data}>
            {t('documents.download')}
          </button>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={onClose}>
            {t('common.close')}
          </button>
        </div>
      </header>
      <div className="min-h-0 flex-1">
        {isPending && <p role="status" className="p-4">{t('common.loading')}</p>}
        {isError && <p role="alert" className="p-4 text-danger">{t('common.error')}</p>}
        {data && !data.inline && <p className="p-4 text-muted-foreground">{t('documents.noPreview')}</p>}
        {data?.inline && data.mime_type === 'application/pdf' && (
          <iframe title={doc.title} src={data.url} className="h-full w-full border-0" />
        )}
        {data?.inline && data.mime_type.startsWith('image/') && (
          <img src={data.url} alt={doc.title} className="mx-auto h-full max-w-full object-contain" />
        )}
      </div>
    </div>
  )
}
