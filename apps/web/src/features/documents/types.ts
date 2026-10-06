export type DocCategory = 'legal' | 'selection' | 'contract' | 'execution' | 'acceptance' | 'payment' | 'other'

export interface DocumentItem {
  id: string
  package_id: string | null
  restricted: boolean
  title: string
  confidentiality: 'normal' | 'sensitive'
  category: DocCategory | null
  doc_type: string | null
  doc_no: string | null
  doc_date: string | null
  file_name: string | null
  mime_type: string | null
  size_bytes: number | null
  version: number | null
  is_current: boolean | null
  extraction_status: 'pending' | 'done' | 'needs_ocr' | 'unsupported' | 'failed' | null
  tags: string[]
  notes: string | null
}

export interface DocType {
  code: string
  label: string
  category: DocCategory
}

export interface Download {
  url: string
  expires_in: number
  file_name: string
  mime_type: string
  inline: boolean
}

export interface ChecklistItem {
  id: string
  package_id: string
  stage_code: string
  doc_type: string
  title: string
  required: boolean
  status: 'missing' | 'received' | 'not_applicable'
  document_id: string | null
  document_title: string | null
  document_restricted: boolean
  due_date: string | null
  overdue: boolean
  note: string | null
}

export interface Checklist {
  items: ChecklistItem[]
  required_total: number
  required_done: number
  completion_pct: number
}

export const DOC_CATEGORIES: DocCategory[] = [
  'legal',
  'selection',
  'contract',
  'execution',
  'acceptance',
  'payment',
  'other',
]

/** Human size: 1536 -> "1,5 KB". */
export function formatSize(bytes: number | null): string {
  if (bytes === null) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i++
  }
  return `${i === 0 ? value : value.toFixed(1).replace('.', ',')} ${units[i]}`
}

export function fileIcon(mime: string | null): string {
  if (!mime) return '📄'
  if (mime.startsWith('image/')) return '🖼'
  if (mime.includes('pdf')) return '📕'
  if (mime.includes('spreadsheet') || mime.includes('excel')) return '📊'
  if (mime.includes('word')) return '📝'
  if (mime.includes('zip')) return '🗜'
  return '📄'
}
