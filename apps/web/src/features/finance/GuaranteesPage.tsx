import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { ExportButton } from '@/components/ui/ExportButton'
import { useAuth } from '@/features/auth/AuthContext'
import { api, type Page } from '@/lib/api'
import { formatMoney, NO_DATA } from '@/lib/format'
import { can } from '@/lib/permissions'
import { Countdown, GuaranteeCard, GuaranteeStatusBadge } from './GuaranteeCard'
import { GuaranteeForm } from './GuaranteeForm'
import type { EffectiveGuaranteeStatus, GuaranteeRow } from './types'

const FILTERS: EffectiveGuaranteeStatus[] = ['expiring', 'expired', 'missing', 'valid']

const context = (g: GuaranteeRow) => `Gói ${String(g.package_number).padStart(2, '0')} · HĐ ${g.contract_no}`

export function GuaranteesPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const canEdit = can(user?.role, 'contract', 'W')
  const [status, setStatus] = useState<EffectiveGuaranteeStatus | ''>('')
  const [editing, setEditing] = useState<GuaranteeRow | null>(null)

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['guarantees', { status }],
    queryFn: () => {
      const p = new URLSearchParams({ page_size: '100' })
      if (status) p.set('status', status)
      return api.get<Page<GuaranteeRow>>(`/guarantees?${p}`)
    },
  })

  const urgent = (data?.items ?? []).flatMap((g) =>
    g.findings.filter((f) => f.severity === 'critical').map((f) => ({ g, f })),
  )

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold md:text-2xl">{t('guarantees.title')}</h1>
        {can(user?.role, 'payment', 'R') && <ExportButton path="/export/ql07.xlsx" label={t('guarantees.exportQl07')} />}
      </div>

      {data && (
        <div
          role="region"
          aria-label={t('guarantees.attention')}
          className="rounded-md border border-danger p-3"
        >
          <h2 className="mb-1 font-semibold text-danger">✕ {t('guarantees.attention')}</h2>
          {urgent.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('guarantees.nothingUrgent')}</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {urgent.map(({ g, f }) => (
                <li key={`${g.id}-${f.code}`}>
                  <span className="font-medium">{context(g)}</span>: {f.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label={t('guarantees.storedStatus')}>
        {(['', ...FILTERS] as const).map((s) => (
          <button
            key={s || 'all'}
            type="button"
            aria-pressed={status === s}
            onClick={() => setStatus(s)}
            className={`min-h-11 shrink-0 rounded-full border px-4 text-sm ${
              status === s ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
            }`}
          >
            {s ? t(`guarantees.status.${s}`) : t('guarantees.allStatus')}
          </button>
        ))}
      </div>

      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('guarantees.none')}</p>}
      {data && data.items.length > 0 && (
        <ResponsiveList
          caption={t('guarantees.title')}
          rows={data.items}
          rowKey={(g) => g.id}
          renderCard={(g) => (
            <GuaranteeCard g={g} context={context(g)} onEdit={canEdit ? () => setEditing(g) : undefined} />
          )}
          columns={[
            { key: 'ctx', header: t('contract.no'), cell: (g) => context(g) },
            { key: 'type', header: t('contract.type'), cell: (g) => t(`guarantees.types.${g.guarantee_type}`) },
            { key: 'bank', header: t('guarantees.bank'), cell: (g) => g.bank_name ?? NO_DATA, secondary: true },
            { key: 'amount', header: t('guarantees.amount'), cell: (g) => (g.amount === null ? NO_DATA : formatMoney(g.amount)) },
            { key: 'expiry', header: t('guarantees.expiryDate'), cell: (g) => (g.effective_status === 'missing' ? NO_DATA : <Countdown g={g} />) },
            { key: 'status', header: t('guarantees.storedStatus'), cell: (g) => <GuaranteeStatusBadge status={g.effective_status} /> },
            {
              key: 'actions',
              header: t('users.more'),
              cell: (g) =>
                canEdit ? (
                  <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setEditing(g)}>
                    {t('guarantees.edit')}
                  </button>
                ) : null,
            },
          ]}
        />
      )}

      {editing && (
        <BottomSheet title={t('guarantees.edit')} onClose={() => setEditing(null)}>
          <GuaranteeForm contractId={editing.contract_id} guarantee={editing} onDone={() => setEditing(null)} />
        </BottomSheet>
      )}
    </section>
  )
}
