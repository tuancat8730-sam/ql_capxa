import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, type Page } from '@/lib/api'
import { formatDate, NO_DATA } from '@/lib/format'
import { can } from '@/lib/permissions'
import { PreviewDialog } from './PreviewDialog'
import { UploadSheet } from './UploadSheet'
import { DOC_CATEGORIES, type Download, type DocType, type DocumentItem, fileIcon, formatSize } from './types'

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

export function DocumentsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const canWrite = can(user?.role, 'document', 'W')

  const [q, setQ] = useState('')
  const [packageId, setPackageId] = useState(params.get('package') ?? '')
  const [category, setCategory] = useState('')
  const [uploading, setUploading] = useState<{ parent?: DocumentItem } | null>(null)
  const [previewing, setPreviewing] = useState<DocumentItem | null>(null)
  const search = useDebounced(q.trim(), 300)

  const packages = useQuery({
    queryKey: ['packages', 'options'],
    queryFn: () => api.get<Page<{ id: string; number: number }>>('/packages?page_size=100'),
  })
  const types = useQuery({ queryKey: ['doc-types'], queryFn: () => api.get<DocType[]>('/doc-types'), staleTime: Infinity })
  const typeLabel = (code: string | null) => types.data?.find((d) => d.code === code)?.label ?? code ?? NO_DATA
  const packageLabel = (id: string | null) => {
    const p = packages.data?.items.find((x) => x.id === id)
    return p ? t('packages.number', { n: String(p.number).padStart(2, '0') }) : t('documents.projectLevel')
  }

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['documents', { search, packageId, category }],
    queryFn: () => {
      const p = new URLSearchParams({ page_size: '100' })
      if (search) p.set('q', search)
      if (packageId) p.set('package_id', packageId)
      if (category) p.set('category', category)
      return api.get<Page<DocumentItem>>(`/documents?${p}`)
    },
  })

  const remove = useMutation({
    mutationFn: (d: DocumentItem) => api.request('DELETE', `/documents/${d.id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
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
        {canWrite && (
          <>
            <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setUploading({ parent: d })}>
              {t('documents.uploadNewVersion')}
            </button>
            <button
              type="button"
              className="min-h-11 rounded-md border border-border px-3"
              onClick={() => window.confirm(t('documents.confirmDelete')) && remove.mutate(d)}
            >
              {t('documents.delete')}
            </button>
          </>
        )}
      </div>
    )

  const meta = (d: DocumentItem) =>
    [packageLabel(d.package_id), typeLabel(d.doc_type), d.doc_date ? formatDate(d.doc_date) : null, formatSize(d.size_bytes)]
      .filter(Boolean)
      .join(' · ')

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('documents.title')}</h1>
        {canWrite && (
          <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setUploading({})}>
            {t('documents.upload')}
          </button>
        )}
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        <input
          type="search"
          aria-label={t('documents.search')}
          placeholder={t('documents.search')}
          className={inputClass}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select aria-label={t('documents.package')} className={inputClass} value={packageId} onChange={(e) => setPackageId(e.target.value)}>
          <option value="">{t('documents.allPackages')}</option>
          {packages.data?.items.map((p) => (
            <option key={p.id} value={p.id}>
              {t('packages.number', { n: String(p.number).padStart(2, '0') })}
            </option>
          ))}
        </select>
        <select aria-label={t('documents.allCategories')} className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">{t('documents.allCategories')}</option>
          {DOC_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`documents.categories.${c}`)}
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
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('documents.empty')}</p>}
      {data && data.items.length > 0 && (
        <>
          <ResponsiveList
            caption={t('documents.title')}
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
                  <div className="flex flex-wrap gap-2 text-sm">
                    {(d.version ?? 1) > 1 && <StatusBadge tone="info" icon="v">{t('documents.version', { n: d.version })}</StatusBadge>}
                    {d.confidentiality === 'sensitive' && <StatusBadge tone="warning" icon="🔒">{t('documents.sensitive')}</StatusBadge>}
                    {d.extraction_status === 'needs_ocr' && <StatusBadge tone="neutral" icon="ℹ">{t('documents.needsOcr')}</StatusBadge>}
                  </div>
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
              { key: 'pkg', header: t('documents.package'), cell: (d) => packageLabel(d.package_id) },
              { key: 'date', header: t('documents.docDate'), cell: (d) => (d.doc_date ? formatDate(d.doc_date) : ''), secondary: true },
              { key: 'size', header: '', cell: (d) => formatSize(d.size_bytes), secondary: true },
              { key: 'actions', header: t('users.more'), cell: actions },
            ]}
          />
          <p className="text-sm text-muted-foreground">{t('documents.total', { count: data.total })}</p>
        </>
      )}

      {uploading && <UploadSheet parent={uploading.parent} packageId={packageId || undefined} onClose={() => setUploading(null)} />}
      {previewing && <PreviewDialog doc={previewing} onClose={() => setPreviewing(null)} />}

      {canWrite && (
        <button
          type="button"
          aria-label={t('documents.upload')}
          onClick={() => setUploading({})}
          className="fixed bottom-20 right-4 z-20 size-14 rounded-full bg-primary text-2xl text-primary-foreground shadow-lg md:hidden"
        >
          +
        </button>
      )}
    </section>
  )
}
