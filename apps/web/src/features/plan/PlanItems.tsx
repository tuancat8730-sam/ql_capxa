import { useTranslation } from 'react-i18next'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import type { PlanItem } from './types'

function Who({ item }: { item: PlanItem }) {
  if (item.assignments.length === 0) return <span className="text-muted-foreground">–</span>
  return (
    <ul className="space-y-0.5">
      {item.assignments.map((a, i) => (
        <li key={i}>
          {a.org}
          {a.quantity != null && item.assignments.length > 1 && <span className="text-muted-foreground">: {a.quantity}</span>}
        </li>
      ))}
    </ul>
  )
}

function Specs({ item }: { item: PlanItem }) {
  const { t } = useTranslation()
  if (!item.details) return null
  return (
    <details className="text-sm">
      <summary className="min-h-11 cursor-pointer py-2 text-primary">{t('plan.specs')}</summary>
      <ul className="space-y-0.5 text-muted-foreground">
        {item.details.split('\n').map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
    </details>
  )
}

export function PlanItems({ items, totalQuantity }: { items: PlanItem[]; totalQuantity: number }) {
  const { t } = useTranslation()
  return (
    <section aria-label={t('plan.equipment')} className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-lg font-semibold">{t('plan.equipment')}</h3>
        <span className="text-sm text-muted-foreground">{t('plan.equipmentTotal', { count: items.length, qty: totalQuantity })}</span>
      </div>
      <ResponsiveList
        rows={items}
        rowKey={(i) => i.id}
        caption={t('plan.equipment')}
        columns={[
          { key: 'no', header: t('plan.colNo'), cell: (i) => i.line_no },
          {
            key: 'name',
            header: t('plan.colName'),
            cell: (i) => (
              <div>
                <p className="font-medium">{i.name}</p>
                <Specs item={i} />
              </div>
            ),
          },
          { key: 'unit', header: t('plan.colUnit'), cell: (i) => i.unit ?? '–' },
          { key: 'qty', header: t('plan.colQty'), cell: (i) => (i.quantity == null ? '–' : i.quantity.toLocaleString('vi-VN')) },
          { key: 'who', header: t('plan.colWho'), cell: (i) => <Who item={i} /> },
          { key: 'note', header: t('plan.colNote'), cell: (i) => i.note ?? '', secondary: true },
        ]}
        renderCard={(i) => (
          <div className="space-y-1">
            <p className="font-medium">
              {i.line_no}. {i.name}
            </p>
            <p className="text-sm">
              {t('plan.colQty')}: <strong>{i.quantity ?? '–'}</strong> {i.unit}
            </p>
            <div className="text-sm">
              <span className="text-muted-foreground">{t('plan.colWho')}: </span>
              <Who item={i} />
            </div>
            {i.note && <p className="text-sm text-muted-foreground">{i.note}</p>}
            <Specs item={i} />
          </div>
        )}
      />
    </section>
  )
}
