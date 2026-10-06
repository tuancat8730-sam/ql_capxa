import { type ReactNode, useEffect } from 'react'
import { useTranslation } from 'react-i18next'

interface BottomSheetProps {
  title: string
  onClose: () => void
  children: ReactNode
}

/** Bottom sheet on phones, centred dialog from `md` (SPEC 15.4). Esc and the backdrop close it. */
export function BottomSheet({ title, onClose, children }: BottomSheetProps) {
  const { t } = useTranslation()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-40 md:flex md:items-center md:justify-center"
    >
      <button
        type="button"
        aria-label={t('common.close')}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-background p-4 pb-8 md:relative md:inset-auto md:w-full md:max-w-md md:rounded-lg">
        <h2 className="mb-4 text-xl font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  )
}
