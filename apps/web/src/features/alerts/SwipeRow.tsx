import { type PointerEvent, type ReactNode, useRef, useState } from 'react'

const THRESHOLD = 80

interface SwipeRowProps {
  children: ReactNode
  onSwipeLeft?: () => void
  onSwipeRight?: () => void
}

/**
 * Swipe left / right on touch screens (SPEC 15.11e). It is only a shortcut: every action also has
 * a visible button, so nothing depends on the gesture (SPEC 15.4).
 */
export function SwipeRow({ children, onSwipeLeft, onSwipeRight }: SwipeRowProps) {
  const [dx, setDx] = useState(0)
  const start = useRef<{ x: number; y: number } | null>(null)

  const down = (e: PointerEvent) => {
    if (e.pointerType === 'mouse') return
    start.current = { x: e.clientX, y: e.clientY }
  }
  const move = (e: PointerEvent) => {
    if (!start.current) return
    const x = e.clientX - start.current.x
    const y = e.clientY - start.current.y
    if (Math.abs(y) > Math.abs(x)) return // vertical scrolling wins
    setDx(Math.max(-120, Math.min(120, x)))
  }
  const end = () => {
    if (!start.current) return
    if (dx <= -THRESHOLD) onSwipeLeft?.()
    else if (dx >= THRESHOLD) onSwipeRight?.()
    start.current = null
    setDx(0)
  }

  return (
    <div
      data-testid="swipe-row"
      style={{ transform: `translateX(${dx}px)`, touchAction: 'pan-y' }}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
    >
      {children}
    </div>
  )
}
