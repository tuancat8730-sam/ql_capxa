import dayjs from 'dayjs'

export const NO_DATA = 'Chưa có dữ liệu'

type Maybe<T> = T | null | undefined

function groupThousands(n: number): string {
  return Math.round(n)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '.')
}

function decimalComma(n: number): string {
  return n.toFixed(2).replace('.', ',')
}

export function formatMoney(value: Maybe<number>): string {
  if (value == null) return NO_DATA
  return `${groupThousands(value)} đ`
}

export function formatMoneyShort(value: Maybe<number>): string {
  if (value == null) return NO_DATA
  const abs = Math.abs(value)
  if (abs >= 1e9) return `${decimalComma(value / 1e9)} tỷ`
  if (abs >= 1e6) return `${decimalComma(value / 1e6)} triệu`
  return formatMoney(value)
}

export function formatDate(value: Maybe<string>): string {
  if (!value) return NO_DATA
  const d = dayjs(value)
  return d.isValid() ? d.format('DD/MM/YYYY') : NO_DATA
}
