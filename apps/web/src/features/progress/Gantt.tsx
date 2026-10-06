import { type KeyboardEvent, type PointerEvent, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDate } from '@/lib/format'
import { type Bar, makeScale, makeTicks, resizeBar, shiftBar, ZOOM_PX_PER_DAY } from '@/lib/gantt'
import type { StageStatus, Timeline } from './types'

const LABEL_W = 168
const HEAD_H = 26
const PKG_H = 26
const ROW_H = 24
const BAR_H = 12

const STATUS_FILL: Record<StageStatus, string> = {
  not_started: 'var(--neutral)',
  in_progress: 'var(--info)',
  done: 'var(--success)',
  delayed: 'var(--danger)',
  blocked: 'var(--warning)',
}

interface Drag {
  stageId: string
  mode: 'move' | 'start' | 'end'
  originX: number
  delta: number
}

export interface GanttProps {
  timeline: Timeline
  zoom: 'month' | 'week'
  /** Dragging is for large screens and users who may edit progress (SPEC 15.4). */
  editable: boolean
  onChangeStage: (stageId: string, dates: { planned_start: string; planned_end: string }) => void
}

export function Gantt({ timeline, zoom, editable, onChangeStage }: GanttProps) {
  const { t } = useTranslation()
  const [drag, setDrag] = useState<Drag | null>(null)
  const dragRef = useRef<Drag | null>(null)

  const start = timeline.range_start ?? timeline.today
  const end = timeline.range_end ?? timeline.today
  const pxPerDay = ZOOM_PX_PER_DAY[zoom]
  const scale = makeScale(
    start < timeline.today ? start : timeline.today,
    end > timeline.today ? end : timeline.today,
    pxPerDay,
  )
  const ticks = makeTicks(scale, zoom)

  // vertical layout: one header row per package, then one row per stage
  let y = HEAD_H
  const layout = timeline.packages.map((p) => {
    const top = y
    y += PKG_H + p.stages.length * ROW_H
    return { p, top }
  })
  const height = y + 6

  const barFor = (stage: { id: string; planned_start: string | null; planned_end: string | null }): Bar | null => {
    if (!stage.planned_start || !stage.planned_end) return null
    let bar: Bar = { start: stage.planned_start, end: stage.planned_end }
    if (drag && drag.stageId === stage.id) {
      bar =
        drag.mode === 'move' ? shiftBar(bar, drag.delta) : resizeBar(bar, drag.mode, drag.delta)
    }
    return bar
  }

  const begin = (e: PointerEvent, stageId: string, mode: Drag['mode']) => {
    if (!editable) return
    e.preventDefault()
    ;(e.currentTarget as Element).setPointerCapture?.(e.pointerId)
    const next = { stageId, mode, originX: e.clientX, delta: 0 }
    dragRef.current = next
    setDrag(next)
  }
  const move = (e: PointerEvent) => {
    const d = dragRef.current
    if (!d) return
    const delta = Math.round((e.clientX - d.originX) / pxPerDay)
    if (delta !== d.delta) {
      dragRef.current = { ...d, delta }
      setDrag(dragRef.current)
    }
  }
  const finish = (stage: { planned_start: string | null; planned_end: string | null }) => {
    const d = dragRef.current
    dragRef.current = null
    setDrag(null)
    if (!d || d.delta === 0 || !stage.planned_start || !stage.planned_end) return
    const base: Bar = { start: stage.planned_start, end: stage.planned_end }
    const next = d.mode === 'move' ? shiftBar(base, d.delta) : resizeBar(base, d.mode, d.delta)
    onChangeStage(d.stageId, { planned_start: next.start, planned_end: next.end })
  }

  const onKey = (e: KeyboardEvent, stage: { id: string; planned_start: string | null; planned_end: string | null }) => {
    if (!editable || !stage.planned_start || !stage.planned_end) return
    const dir = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!dir) return
    e.preventDefault()
    const base: Bar = { start: stage.planned_start, end: stage.planned_end }
    const next = e.shiftKey ? resizeBar(base, 'end', dir) : shiftBar(base, dir)
    onChangeStage(stage.id, { planned_start: next.start, planned_end: next.end })
  }

  return (
    <div className="flex rounded-md border border-border">
      <div className="shrink-0 border-r border-border" style={{ width: LABEL_W }} aria-hidden>
        <div style={{ height: HEAD_H }} />
        {layout.map(({ p }) => (
          <div key={p.id}>
            <div className="truncate px-2 text-sm font-semibold" style={{ height: PKG_H, lineHeight: `${PKG_H}px` }}>
              {t('packages.number', { n: String(p.number).padStart(2, '0') })}
            </div>
            {p.stages.map((s) => (
              <div key={s.id} className="truncate px-2 text-xs text-muted-foreground" style={{ height: ROW_H, lineHeight: `${ROW_H}px` }}>
                {s.name}
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="min-w-0 flex-1 overflow-x-auto">
        <svg width={scale.width} height={height} role="img" aria-label={t('progress.ganttTitle')} className="block select-none">
          {ticks.map((tick) => (
            <g key={tick.iso}>
              <line x1={scale.x(tick.iso)} x2={scale.x(tick.iso)} y1={HEAD_H - 6} y2={height} style={{ stroke: 'var(--border)' }} />
              <text x={scale.x(tick.iso) + 3} y={HEAD_H - 10} fontSize="10" style={{ fill: 'var(--muted-foreground)' }}>
                {tick.label}
              </text>
            </g>
          ))}

          {layout.map(({ p, top }) => (
            <g key={p.id}>
              {p.contract?.start && (p.contract.end ?? p.contract.extended_end_date) && (
                <rect
                  x={scale.x(p.contract.start)}
                  y={top + PKG_H / 2 - 2}
                  width={Math.max(2, scale.x((p.contract.extended_end_date ?? p.contract.end)!) - scale.x(p.contract.start))}
                  height={4}
                  rx={2}
                  style={{ fill: 'var(--muted-foreground)', opacity: 0.5 }}
                >
                  <title>{`HĐ ${p.contract.contract_no}`}</title>
                </rect>
              )}
              {p.contract?.end && (
                <line
                  x1={scale.x(p.contract.end) + pxPerDay}
                  x2={scale.x(p.contract.end) + pxPerDay}
                  y1={top}
                  y2={top + PKG_H + p.stages.length * ROW_H}
                  strokeDasharray="4 3"
                  style={{ stroke: 'var(--danger)' }}
                >
                  <title>{`${t('progress.contractEnd')}: ${formatDate(p.contract.end)}`}</title>
                </line>
              )}
              {p.stages.map((s, i) => {
                const bar = barFor(s)
                const rowY = top + PKG_H + i * ROW_H
                if (!bar) return null
                const x = scale.x(bar.start)
                const w = Math.max(pxPerDay, scale.x(bar.end) - x + pxPerDay)
                const label = t('progress.barLabel', {
                  package: t('packages.number', { n: String(p.number).padStart(2, '0') }),
                  stage: s.name,
                  start: formatDate(bar.start),
                  end: formatDate(bar.end),
                })
                return (
                  <g key={s.id}>
                    <g
                      tabIndex={editable ? 0 : -1}
                      role="group"
                      aria-label={label}
                      data-testid={`bar-${s.id}`}
                      onKeyDown={(e) => onKey(e, s)}
                      onPointerDown={(e) => begin(e, s.id, 'move')}
                      onPointerMove={move}
                      onPointerUp={() => finish(s)}
                      style={{ cursor: editable ? 'grab' : 'default' }}
                    >
                      <rect x={x} y={rowY + (ROW_H - BAR_H) / 2} width={w} height={BAR_H} rx={3} style={{ fill: STATUS_FILL[s.effective_status], opacity: 0.35 }} />
                      <rect x={x} y={rowY + (ROW_H - BAR_H) / 2} width={(w * s.progress_pct) / 100} height={BAR_H} rx={3} style={{ fill: STATUS_FILL[s.effective_status] }} />
                      <title>{label}</title>
                    </g>
                    {editable && (
                      <>
                        <rect
                          x={x - 3}
                          y={rowY + 3}
                          width={7}
                          height={ROW_H - 6}
                          data-testid={`handle-start-${s.id}`}
                          style={{ fill: 'transparent', cursor: 'ew-resize' }}
                          onPointerDown={(e) => begin(e, s.id, 'start')}
                          onPointerMove={move}
                          onPointerUp={() => finish(s)}
                        />
                        <rect
                          x={x + w - 4}
                          y={rowY + 3}
                          width={7}
                          height={ROW_H - 6}
                          data-testid={`handle-end-${s.id}`}
                          style={{ fill: 'transparent', cursor: 'ew-resize' }}
                          onPointerDown={(e) => begin(e, s.id, 'end')}
                          onPointerMove={move}
                          onPointerUp={() => finish(s)}
                        />
                      </>
                    )}
                    {s.actual_start && (
                      <rect
                        x={scale.x(s.actual_start)}
                        y={rowY + ROW_H - 5}
                        width={Math.max(pxPerDay, scale.x(s.actual_end ?? timeline.today) - scale.x(s.actual_start) + pxPerDay)}
                        height={3}
                        style={{ fill: 'var(--foreground)' }}
                      />
                    )}
                  </g>
                )
              })}
            </g>
          ))}

          <line x1={scale.x(timeline.today)} x2={scale.x(timeline.today)} y1={HEAD_H - 6} y2={height} strokeWidth={2} style={{ stroke: 'var(--primary)' }}>
            <title>{`${t('progress.today')}: ${formatDate(timeline.today)}`}</title>
          </line>
        </svg>
      </div>
    </div>
  )
}
