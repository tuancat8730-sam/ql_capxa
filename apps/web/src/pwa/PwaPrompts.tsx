import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRegisterSW } from 'virtual:pwa-register/react'

const DISMISS_KEY = 'pwa-install-dismissed'

interface InstallEvent extends Event {
  prompt: () => Promise<void>
}

function dismissed(): boolean {
  try {
    return localStorage.getItem(DISMISS_KEY) === '1'
  } catch {
    return false
  }
}

/** "Install app" (once, dismissible) and "new version" toast (SPEC 15.6). Loaded lazily. */
export default function PwaPrompts() {
  const { t } = useTranslation()
  const [installEvent, setInstallEvent] = useState<InstallEvent | null>(null)
  const {
    needRefresh: [needRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW()

  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault()
      if (!dismissed()) setInstallEvent(e as InstallEvent)
    }
    window.addEventListener('beforeinstallprompt', onPrompt)
    return () => window.removeEventListener('beforeinstallprompt', onPrompt)
  }, [])

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, '1')
    } catch {
      /* private mode: just hide it for this session */
    }
    setInstallEvent(null)
  }

  const bar = 'fixed inset-x-3 bottom-20 z-50 flex items-center justify-between gap-2 rounded-md border border-border bg-background p-3 shadow-lg md:bottom-4 md:left-auto md:max-w-sm'

  if (needRefresh) {
    return (
      <div role="status" className={bar}>
        <span>{t('pwa.updateReady')}</span>
        <button type="button" className="min-h-11 rounded-md bg-primary px-3 text-primary-foreground" onClick={() => void updateServiceWorker(true)}>
          {t('pwa.reload')}
        </button>
      </div>
    )
  }
  if (installEvent) {
    return (
      <div role="status" className={bar}>
        <span>{t('pwa.install')}</span>
        <span className="flex gap-2">
          <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={dismiss}>
            {t('pwa.dismiss')}
          </button>
          <button
            type="button"
            className="min-h-11 rounded-md bg-primary px-3 text-primary-foreground"
            onClick={async () => {
              await installEvent.prompt()
              dismiss()
            }}
          >
            {t('pwa.installAction')}
          </button>
        </span>
      </div>
    )
  }
  if (offlineReady) {
    return (
      <div role="status" className={bar}>
        <span>{t('pwa.offlineReady')}</span>
        <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setOfflineReady(false)}>
          {t('common.close')}
        </button>
      </div>
    )
  }
  return null
}
