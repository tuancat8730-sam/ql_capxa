import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatMoney, formatMoneyShort } from './format'

describe('formatMoney', () => {
  it('groups thousands with dots and appends đ', () => {
    expect(formatMoney(1234567)).toBe('1.234.567 đ')
    expect(formatMoney(51505400000)).toBe('51.505.400.000 đ')
  })
  it('shows placeholder for null/undefined', () => {
    expect(formatMoney(null)).toBe('Chưa có dữ liệu')
    expect(formatMoney(undefined)).toBe('Chưa có dữ liệu')
  })
  it('handles zero', () => {
    expect(formatMoney(0)).toBe('0 đ')
  })
})

describe('formatMoneyShort', () => {
  it('abbreviates billions with comma decimal', () => {
    expect(formatMoneyShort(1726920000)).toBe('1,73 tỷ')
  })
  it('abbreviates millions', () => {
    expect(formatMoneyShort(237382337)).toBe('237,38 triệu')
  })
  it('falls back to full format below 1 million', () => {
    expect(formatMoneyShort(500000)).toBe('500.000 đ')
  })
  it('placeholder for null', () => {
    expect(formatMoneyShort(null)).toBe('Chưa có dữ liệu')
  })
})

describe('formatDate', () => {
  it('formats ISO date as dd/MM/yyyy', () => {
    expect(formatDate('2026-09-24')).toBe('24/09/2026')
  })
  it('placeholder for empty', () => {
    expect(formatDate(null)).toBe('Chưa có dữ liệu')
  })
})

describe('formatDateTime', () => {
  it('always shows Vietnam time (UTC+7)', () => {
    expect(formatDateTime('2026-11-05T03:00:00Z')).toBe('05/11/2026 10:00:00')
    expect(formatDateTime('2026-11-05T20:30:15Z')).toBe('06/11/2026 03:30:15') // next day in Vietnam
  })
  it('placeholder for empty or invalid input', () => {
    expect(formatDateTime(null)).toBe('Chưa có dữ liệu')
    expect(formatDateTime('nope')).toBe('Chưa có dữ liệu')
  })
})
