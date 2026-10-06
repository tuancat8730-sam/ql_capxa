import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { download } from '@/lib/api'

interface ExportButtonProps {
  /** API path of the workbook, e.g. `/export/risks.xlsx`. */
  path: string
  label?: string
}

/** Downloads an .xlsx export with the current credentials (SPEC 4.13). */
export function ExportButton({ path, label }: ExportButtonProps) {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)

  const run = async () => {
    setBusy(true)
    setFailed(false)
    try {
      const { blob, filename } = await download(path)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <span className="inline-flex flex-col items-start gap-1">
      <button type="button" className="min-h-11 rounded-md border border-border px-3" disabled={busy} onClick={() => void run()}>
        {busy ? t('exportXlsx.busy') : (label ?? t('exportXlsx.button'))}
      </button>
      {failed && (
        <span role="alert" className="text-xs text-danger">
          {t('exportXlsx.failed')}
        </span>
      )}
    </span>
  )
}
