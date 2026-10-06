import { useTranslation } from 'react-i18next'
import { levelOf, type Matrix } from './types'

const TONE = {
  low: 'bg-muted text-foreground',
  medium: 'border-warning text-warning',
  high: 'border-danger text-danger font-semibold',
} as const

interface RiskMatrixProps {
  matrix: Matrix
  selected: { probability: number; impact: number } | null
  onSelect: (cell: { probability: number; impact: number } | null) => void
}

/** 5x5 heat map; tap a cell to filter the list below (SPEC 4.8, 15.5g). Level is also written in text. */
export function RiskMatrix({ matrix, selected, onSelect }: RiskMatrixProps) {
  const { t } = useTranslation()
  const count = (p: number, i: number) => matrix.cells.find((c) => c.probability === p && c.impact === i)?.count ?? 0

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t('risks.matrix')}</h2>
        {selected && (
          <button type="button" className="min-h-11 rounded-md border border-border px-3 text-sm" onClick={() => onSelect(null)}>
            {t('risks.clearFilter')}
          </button>
        )}
      </div>
      <div role="grid" aria-label={t('risks.matrix')} className="grid grid-cols-[auto_repeat(5,minmax(0,1fr))] gap-1 text-center text-sm">
        <div />
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={`h${i}`} className="text-xs text-muted-foreground">
            {t('risks.impact').split(' ')[0]} {i}
          </div>
        ))}
        {[5, 4, 3, 2, 1].map((p) => (
          <div key={`r${p}`} role="row" className="contents">
            <div className="flex items-center pr-1 text-xs text-muted-foreground">XS {p}</div>
            {[1, 2, 3, 4, 5].map((i) => {
              const n = count(p, i)
              const level = levelOf(p * i)
              const active = selected?.probability === p && selected?.impact === i
              return (
                <button
                  key={`${p}-${i}`}
                  type="button"
                  role="gridcell"
                  aria-pressed={active}
                  aria-label={t('risks.matrixCell', { p, i, n })}
                  disabled={n === 0}
                  onClick={() => onSelect(active ? null : { probability: p, impact: i })}
                  className={`flex min-h-11 flex-col items-center justify-center rounded-md border ${TONE[level]} ${active ? 'ring-2 ring-primary' : 'border-border'} disabled:opacity-50`}
                >
                  <span className="text-base">{n}</span>
                  <span className="text-[10px] leading-none">{p * i}</span>
                </button>
              )
            })}
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {t('risks.level.low')} 1–5 · {t('risks.level.medium')} 6–12 · {t('risks.level.high')} 13–25
      </p>
    </div>
  )
}
