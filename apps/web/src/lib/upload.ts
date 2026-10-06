/**
 * Direct-to-storage upload (SPEC section 9, 15.7): ask the API for a presigned URL, PUT the file
 * straight to S3 with progress, retry network/5xx failures up to 5 times with growing delays.
 * The API then confirms the object and computes its SHA-256 itself, so the browser never has to
 * hash a 100 MB file.
 */
import { api } from './api'

export interface UploadTarget {
  url: string
  method: string
  headers: Record<string, string>
}

export interface UploadUrlResponse {
  document_id: string
  file_key: string
  version: number
  upload: UploadTarget
  expires_in: number
  max_bytes: number
}

export interface UploadedFile {
  document_id: string
  file_key: string
  file_name: string
  mime_type: string
  size_bytes: number
}

export class UploadError extends Error {
  status: number

  constructor(status: number) {
    super(`upload failed with status ${status}`)
    this.status = status
  }
}

export const RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 16_000]
export const MAX_IMAGE_EDGE = 1600

const MIME_BY_EXTENSION: Record<string, string> = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  doc: 'application/msword',
  xls: 'application/vnd.ms-excel',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  zip: 'application/zip',
}

/** Browsers often leave `file.type` empty for Office files: fall back to the extension. */
export function guessMime(file: Pick<File, 'name' | 'type'>): string {
  if (file.type) return file.type
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  return MIME_BY_EXTENSION[ext] ?? 'application/octet-stream'
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

/** Only transient failures are worth retrying; a 403 means the signed URL expired. */
export function isRetryable(err: unknown): boolean {
  return err instanceof UploadError && (err.status === 0 || err.status >= 500)
}

function putOnce(file: Blob, target: UploadTarget, onProgress?: (fraction: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open(target.method, target.url)
    for (const [name, value] of Object.entries(target.headers)) xhr.setRequestHeader(name, value)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total)
    }
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new UploadError(xhr.status)))
    xhr.onerror = () => reject(new UploadError(0))
    xhr.send(file)
  })
}

export async function putWithRetry(
  file: Blob,
  target: UploadTarget,
  opts: { onProgress?: (fraction: number) => void; wait?: (ms: number) => Promise<void> } = {},
): Promise<void> {
  const wait = opts.wait ?? sleep
  for (let attempt = 0; ; attempt++) {
    try {
      return await putOnce(file, target, opts.onProgress)
    } catch (err) {
      if (!isRetryable(err) || attempt >= RETRY_DELAYS_MS.length) throw err
      await wait(RETRY_DELAYS_MS[attempt])
    }
  }
}

export interface UploadOptions {
  packageId?: string | null
  /** Set when uploading a new version of an existing document. */
  parentDocumentId?: string | null
  onProgress?: (fraction: number) => void
  wait?: (ms: number) => Promise<void>
}

export async function uploadFile(file: File, opts: UploadOptions = {}): Promise<UploadedFile> {
  const mime = guessMime(file)
  const target = await api.post<UploadUrlResponse>('/documents/upload-url', {
    file_name: file.name,
    mime_type: mime,
    size_bytes: file.size,
    package_id: opts.packageId ?? null,
    parent_document_id: opts.parentDocumentId ?? null,
  })
  // The signature binds Content-Type, so send exactly what the API signed.
  await putWithRetry(file, target.upload, { onProgress: opts.onProgress, wait: opts.wait })
  return {
    document_id: target.document_id,
    file_key: target.file_key,
    file_name: file.name,
    mime_type: mime,
    size_bytes: file.size,
  }
}

/** Scale (w, h) down so the long edge is at most `max`; never scales up. */
export function fitWithin(width: number, height: number, max = MAX_IMAGE_EDGE): { width: number; height: number } {
  const longest = Math.max(width, height)
  if (longest <= max) return { width, height }
  const scale = max / longest
  return { width: Math.round(width * scale), height: Math.round(height * scale) }
}

/** Shrink phone photos before upload (SPEC 15.5d); returns the original when it can't decode. */
export async function compressImage(file: File, max = MAX_IMAGE_EDGE): Promise<File> {
  if (!file.type.startsWith('image/') || typeof createImageBitmap === 'undefined') return file
  try {
    const bitmap = await createImageBitmap(file)
    const { width, height } = fitWithin(bitmap.width, bitmap.height, max)
    if (width === bitmap.width && file.size < 1_500_000) return file
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    canvas.getContext('2d')?.drawImage(bitmap, 0, 0, width, height)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85))
    if (!blob || blob.size >= file.size) return file
    return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' })
  } catch {
    return file
  }
}
