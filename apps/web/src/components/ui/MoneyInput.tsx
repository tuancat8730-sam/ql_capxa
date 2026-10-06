import type { InputHTMLAttributes } from 'react'

const group = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 })

/** `1234567` -> `1.234.567`; empty for null. */
export function formatDigits(value: number | null): string {
  return value === null ? '' : group.format(value)
}

/** Keep only digits; empty input means "no value". */
export function parseDigits(text: string): number | null {
  const digits = text.replace(/\D/g, '')
  return digits === '' ? null : Number(digits)
}

interface MoneyInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange' | 'type' | 'inputMode'> {
  value: number | null
  onChange: (value: number | null) => void
}

/** VND input that groups thousands while typing (SPEC 15.4); numeric keypad on phones. */
export function MoneyInput({ value, onChange, className = '', ...rest }: MoneyInputProps) {
  return (
    <input
      {...rest}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      className={`min-h-11 w-full rounded-md border border-border bg-background px-3 text-base focus:outline-2 focus:outline-primary ${className}`}
      value={formatDigits(value)}
      onChange={(e) => onChange(parseDigits(e.target.value))}
    />
  )
}
