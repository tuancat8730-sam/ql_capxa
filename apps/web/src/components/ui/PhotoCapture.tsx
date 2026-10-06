import { Camera } from 'lucide-react'
import { type ChangeEvent, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { compressImage } from '@/lib/upload'

interface PhotoCaptureProps {
  /** Receives compressed photos (long edge <= 1600 px). */
  onFiles: (files: File[]) => void
  disabled?: boolean
}

/** "Take photo" button: opens the rear camera on phones, a file picker on desktops. */
export function PhotoCapture({ onFiles, disabled }: PhotoCaptureProps) {
  const { t } = useTranslation()
  const input = useRef<HTMLInputElement>(null)

  const onChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? [])
    e.target.value = '' // allow taking the same photo twice
    if (picked.length) onFiles(await Promise.all(picked.map((f) => compressImage(f))))
  }

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => input.current?.click()}
        className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border px-4 disabled:opacity-60"
      >
        <Camera size={20} aria-hidden />
        {t('documents.takePhoto')}
      </button>
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        hidden
        data-testid="photo-input"
        onChange={onChange}
      />
    </>
  )
}
