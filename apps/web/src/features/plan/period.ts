import { formatDate } from '@/lib/format'

/** "05/11/2026" or "05/11/2026 – 13/11/2026"; null when the document gave no date. */
export function periodText(start: string | null, end: string | null): string | null {
  if (!start && !end) return null
  if (start && end && start !== end) return `${formatDate(start)} – ${formatDate(end)}`
  return formatDate(start ?? end)
}
