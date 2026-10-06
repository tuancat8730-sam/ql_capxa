import { describe, expect, it } from 'vitest'
import { addDays, daysBetween, fromDay, makeScale, makeTicks, resizeBar, shiftBar, toDay } from './gantt'

describe('day arithmetic', () => {
  it('round-trips ISO dates and ignores timezones and DST', () => {
    expect(fromDay(toDay('2026-10-06'))).toBe('2026-10-06')
    expect(addDays('2026-02-28', 1)).toBe('2026-03-01')
    expect(addDays('2024-02-28', 1)).toBe('2024-02-29') // leap year
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
    expect(addDays('2026-03-29', 1)).toBe('2026-03-30') // a DST change in many zones
    expect(addDays('2026-10-06', -6)).toBe('2026-09-30')
    expect(daysBetween('2026-09-14', '2026-11-12')).toBe(59) // SPEC 7.5: start + 60 - 1
  })
})

describe('scale', () => {
  const scale = makeScale('2026-09-01', '2026-09-30', 10, 5)

  it('pads the range and maps days to pixels and back', () => {
    expect(scale.start).toBe('2026-08-27')
    expect(scale.end).toBe('2026-10-05')
    expect(scale.x('2026-08-27')).toBe(0)
    expect(scale.x('2026-09-01')).toBe(50)
    expect(scale.width).toBe(40 * 10)
    expect(scale.dateAt(50)).toBe('2026-09-01')
    expect(scale.dateAt(54)).toBe('2026-09-01') // snaps to the nearest day
    expect(scale.dateAt(56)).toBe('2026-09-02')
  })
})

describe('bars', () => {
  const bar = { start: '2026-09-14', end: '2026-11-12' }

  it('moves a bar without changing its length', () => {
    const moved = shiftBar(bar, 6)
    expect(moved).toEqual({ start: '2026-09-20', end: '2026-11-18' })
    expect(daysBetween(moved.start, moved.end)).toBe(daysBetween(bar.start, bar.end))
    expect(shiftBar(bar, -14).start).toBe('2026-08-31')
  })

  it('resizes either edge but never below one day or across the other edge', () => {
    expect(resizeBar(bar, 'end', 5)).toEqual({ start: '2026-09-14', end: '2026-11-17' })
    expect(resizeBar(bar, 'start', -3)).toEqual({ start: '2026-09-11', end: '2026-11-12' })
    expect(resizeBar(bar, 'end', -1000)).toEqual({ start: '2026-09-14', end: '2026-09-14' })
    expect(resizeBar(bar, 'start', 1000)).toEqual({ start: '2026-11-12', end: '2026-11-12' })
  })
})

describe('ticks', () => {
  it('labels month starts when zoomed out', () => {
    const ticks = makeTicks(makeScale('2026-09-10', '2026-12-20', 3, 0), 'month')
    expect(ticks.map((t) => t.label)).toEqual(['10/2026', '11/2026', '12/2026'])
    expect(ticks.every((t) => t.major)).toBe(true)
  })

  it('labels Mondays when zoomed in', () => {
    const ticks = makeTicks(makeScale('2026-10-05', '2026-10-25', 12, 0), 'week')
    expect(ticks.map((t) => t.label)).toEqual(['05/10', '12/10', '19/10'])
    expect(ticks[0].major).toBe(true) // first Monday of the month
    expect(ticks[1].major).toBe(false)
  })
})
