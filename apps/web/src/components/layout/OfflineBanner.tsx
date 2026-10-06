import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

/** Current connectivity; updates on the browser's online/offline events. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine))
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  return online
}

export function OfflineBanner() {
  const { t } = useTranslation()
  const online = useOnline()
  if (online) return null
  return (
    <p role="status" className="mb-3 rounded-md border border-warning bg-muted px-3 py-2 text-sm text-warning">
      ⚠ {t('offline.banner')}
    </p>
  )
}
