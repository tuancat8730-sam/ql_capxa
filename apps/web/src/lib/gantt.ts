/** Date maths for the Gantt chart. ISO `YYYY-MM-DD` strings in, ISO strings out (no timezone drift). */

const DAY_MS = 86_400_000

export function toDay(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  return Math.round(Date.UTC(y, m - 1, d) / DAY_MS)
}

export function fromDay(day: number): string {
  return new Date(day * DAY_MS).toISOString().slice(0, 10)
}

export function addDays(iso: string, n: number): string {
  return fromDay(toDay(iso) + n)
}

export function daysBetween(a: string, b: string): number {
  return toDay(b) - toDay(a)
}

export interface Scale {
  /** x position (px) of the start of the given day. */
  x: (iso: string) => number
  /** The day under an x position, snapped to a whole day. */
  dateAt: (px: number) => string
  pxPerDay: number
  width: number
  start: string
  end: string
}

/** Axis from `start` to `end` (inclusive) with `pad` spare days on both sides. */
export function makeScale(start: string, end: string, pxPerDay: number, pad = 7): Scale {
  const first = toDay(start) - pad
  const last = toDay(end) + pad
  return {
    x: (iso) => (toDay(iso) - first) * pxPerDay,
    dateAt: (px) => fromDay(first + Math.round(px / pxPerDay)),
    pxPerDay,
    width: (last - first + 1) * pxPerDay,
    start: fromDay(first),
    end: fromDay(last),
  }
}

export interface Bar {
  start: string
  end: string
}

/** Move a whole bar by `delta` days (dragging its body). */
export function shiftBar(bar: Bar, delta: number): Bar {
  return { start: addDays(bar.start, delta), end: addDays(bar.end, delta) }
}

/** Drag one edge; a bar is never shorter than one day and edges cannot cross. */
export function resizeBar(bar: Bar, edge: 'start' | 'end', delta: number): Bar {
  if (edge === 'start') {
    const start = addDays(bar.start, delta)
    return { start: toDay(start) > toDay(bar.end) ? bar.end : start, end: bar.end }
  }
  const end = addDays(bar.end, delta)
  return { start: bar.start, end: toDay(end) < toDay(bar.start) ? bar.start : end }
}

export interface Tick {
  iso: string
  label: string
  major: boolean
}

const pad2 = (n: number) => String(n).padStart(2, '0')

/** Axis labels: months when zoomed out, Mondays when zoomed in. */
export function makeTicks(scale: Scale, mode: 'month' | 'week'): Tick[] {
  const ticks: Tick[] = []
  for (let day = toDay(scale.start); day <= toDay(scale.end); day++) {
    const iso = fromDay(day)
    const d = new Date(day * DAY_MS)
    if (mode === 'month' && d.getUTCDate() === 1) {
      ticks.push({ iso, label: `${pad2(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`, major: true })
    } else if (mode === 'week' && d.getUTCDay() === 1) {
      ticks.push({ iso, label: `${pad2(d.getUTCDate())}/${pad2(d.getUTCMonth() + 1)}`, major: d.getUTCDate() <= 7 })
    }
  }
  return ticks
}

export const ZOOM_PX_PER_DAY = { month: 3, week: 12 } as const
