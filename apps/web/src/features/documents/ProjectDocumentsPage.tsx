import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { useRole } from '@/features/projects/ProjectContext'
import { api, type Page } from '@/lib/api'
import { formatDate, NO_DATA } from '@/lib/format'
import { can } from '@/lib/permissions'
import { PreviewDialog } from './PreviewDialog'
import { UploadSheet } from './UploadSheet'
import { type Download, type DocType, type DocumentItem, type FolderItem, fileIcon, formatSize } from './types'

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

/** Folders in display order, bucketed by their group ("Nhà thầu", "Giám sát", …). */
function groupFolders(folders: FolderItem[]): { group: string; items: FolderItem[] }[] {
  const groups: { group: string; items: FolderItem[] }[] = []
  for (const folder of folders) {
    const bucket = groups.find((g) => g.group === folder.group)
    if (bucket) bucket.items.push(folder)
    else groups.push({ group: folder.group, items: [folder] })
  }
  return groups
}

/** The archive of a software-delivery project: browse by folder, search, view, download, upload. No delete. */
export function ProjectDocumentsPage() {
  const { t } = useTranslation()
  const role = useRole()
  const canWrite = can(role, 'document', 'W')

  const [q, setQ] = useState('')
  const [folder, setFolder] = useState('')
  const [uploading, setUploading] = useState(false)
  const [previewing, setPreviewing] = useState<DocumentItem | null>(null)
  const search = useDebounced(q.trim(), 300)

  const folders = useQuery({ queryKey: ['document-folders'], queryFn: () => api.get<FolderItem[]>('/document-folders') })
  const types = useQuery({ queryKey: ['doc-types'], queryFn: () => api.get<DocType[]>('/doc-types'), staleTime: Infinity })
  const typeLabel = (code: string | null) => types.data?.find((d) => d.code === code)?.label ?? code ?? NO_DATA

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['documents', { search, folder, archive: true }],
    queryFn: () => {
      const p = new URLSearchParams({ page_size: '100' })
      if (search) p.set('q', search)
      if (folder) p.set('folder', folder)
      return api.get<Page<DocumentItem>>(`/documents?${p}`)
    },
  })

  const download = async (d: DocumentItem) => {
    const link = await api.get<Download>(`/documents/${d.id}/download-url`)
    window.open(link.url, '_blank', 'noopener')
  }

  const actions = (d: DocumentItem) =>
    d.restricted ? null : (
      <div className="flex flex-wrap gap-2">
        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setPreviewing(d)}>
          {t('documents.view')}
        </button>
        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => void download(d)}>
          {t('documents.download')}
        </button>
      </div>
    )

  const meta = (d: DocumentItem) =>
    [typeLabel(d.doc_type), d.doc_date ? formatDate(d.doc_date) : null, formatSize(d.size_bytes)].filter(Boolean).join(' · ')

  const folderButton = (code: string, label: string, count?: number) => (
    <button
      key={code || 'all'}
      type="button"
      aria-pressed={folder === code}
      className={`min-h-11 w-full rounded-md border px-3 py-2 text-left text-sm ${
        folder === code ? 'border-primary bg-primary/10 font-semibold' : 'border-border'
      }`}
      onClick={() => setFolder(code)}
    >
      {label}
      {count !== undefined && <span className="text-muted-foreground"> ({count})</span>}
    </button>
  )

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('documents.archiveTitle')}</h1>
        {canWrite && (
          <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setUploading(true)}>
            {t('documents.upload')}
          </button>
        )}
      </div>

      <input
        type="search"
        aria-label={t('documents.search')}
        placeholder={t('documents.search')}
        className={inputClass}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      <div className="grid gap-4 md:grid-cols-[18rem_1fr]">
        <nav aria-label={t('documents.folders')} className="space-y-3">
          {folderButton('', t('documents.allFolders'))}
          {groupFolders(folders.data ?? []).map((g) => (
            <div key={g.group} className="space-y-1">
              <p className="text-xs font-semibold uppercase text-muted-foreground">{g.group}</p>
              {g.items.map((f) => folderButton(f.code, f.label, f.count))}
            </div>
          ))}
        </nav>

        <div className="space-y-4">
          {isPending && <p role="status">{t('common.loading')}</p>}
          {isError && (
            <div role="alert" className="space-y-2">
              <p className="text-danger">{t('common.error')}</p>
              <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
                {t('common.retry')}
              </button>
            </div>
          )}
          {data && data.items.length === 0 && <p className="text-muted-foreground">{folder ? t('documents.emptyFolder') : t('documents.empty')}</p>}
          {data && data.items.length > 0 && (
            <>
              <ResponsiveList
                caption={t('documents.archiveTitle')}
                rows={data.items}
                rowKey={(d) => d.id}
                renderCard={(d) =>
                  d.restricted ? (
                    <div className="space-y-1">
                      <p className="font-semibold">🔒 {t('documents.restricted')}</p>
                      <p className="text-sm text-muted-foreground">{t('documents.restrictedHint')}</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex items-start gap-2">
                        <span aria-hidden className="text-2xl">{fileIcon(d.mime_type)}</span>
                        <div className="min-w-0">
                          <p className="break-words font-semibold">{d.title}</p>
                          <p className="text-sm text-muted-foreground">{meta(d)}</p>
                        </div>
                      </div>
                      {d.extraction_status === 'needs_ocr' && (
                        <StatusBadge tone="neutral" icon="ℹ">{t('documents.needsOcr')}</StatusBadge>
                      )}
                      {actions(d)}
                    </div>
                  )
                }
                columns={[
                  {
                    key: 'title',
                    header: t('documents.docTitle'),
                    cell: (d) => (d.restricted ? `🔒 ${t('documents.restricted')}` : <span><span aria-hidden>{fileIcon(d.mime_type)} </span>{d.title}</span>),
                  },
                  { key: 'type', header: t('documents.docType'), cell: (d) => (d.restricted ? '' : typeLabel(d.doc_type)) },
                  { key: 'date', header: t('documents.docDate'), cell: (d) => (d.doc_date ? formatDate(d.doc_date) : ''), secondary: true },
                  { key: 'size', header: '', cell: (d) => formatSize(d.size_bytes), secondary: true },
                  { key: 'actions', header: t('users.more'), cell: actions },
                ]}
              />
              <p className="text-sm text-muted-foreground">{t('documents.total', { count: data.total })}</p>
            </>
          )}
        </div>
      </div>

      {uploading && folders.data && <UploadSheet folders={folders.data} folderCode={folder || undefined} onClose={() => setUploading(false)} />}
      {previewing && <PreviewDialog doc={previewing} onClose={() => setPreviewing(null)} />}
    </section>
  )
}
