import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { primaryButton } from '@/features/auth/LoginPage'
import { GuaranteeCard } from '@/features/finance/GuaranteeCard'
import { GuaranteeForm } from '@/features/finance/GuaranteeForm'
import type { Guarantee, Payment } from '@/features/finance/types'
import { api } from '@/lib/api'
import { formatDate, formatMoney, NO_DATA } from '@/lib/format'
import { can } from '@/lib/permissions'

export function ContractGuarantees({ contractId }: { contractId: string }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [editing, setEditing] = useState<Guarantee | 'new' | null>(null)
  const canEdit = can(user?.role, 'contract', 'W')
  const { data, isPending, isError } = useQuery({
    queryKey: ['contract-guarantees', contractId],
    queryFn: () => api.get<Guarantee[]>(`/contracts/${contractId}/guarantees`),
  })

  return (
    <section className="space-y-3" aria-label={t('guarantees.forContract')}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{t('guarantees.forContract')}</h3>
        {canEdit && (
          <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setEditing('new')}>
            {t('guarantees.add')}
          </button>
        )}
      </div>
      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && <p role="alert" className="text-danger">{t('common.error')}</p>}
      {data && data.length === 0 && <p className="text-muted-foreground">{t('guarantees.none')}</p>}
      <ul className="space-y-2">
        {data?.map((g) => (
          <li key={g.id} className="rounded-md border border-border p-3">
            <GuaranteeCard g={g} onEdit={canEdit ? () => setEditing(g) : undefined} />
          </li>
        ))}
      </ul>
      {editing && (
        <BottomSheet
          title={editing === 'new' ? t('guarantees.add') : t('guarantees.edit')}
          onClose={() => setEditing(null)}
        >
          <GuaranteeForm
            contractId={contractId}
            guarantee={editing === 'new' ? undefined : editing}
            onDone={() => setEditing(null)}
          />
        </BottomSheet>
      )}
    </section>
  )
}

export function ContractPayments({ contractId }: { contractId: string }) {
  const { t } = useTranslation()
  const { data, isPending, isError } = useQuery({
    queryKey: ['contract-payments', contractId],
    queryFn: () => api.get<Payment[]>(`/contracts/${contractId}/payments`),
  })
  return (
    <section className="space-y-2">
      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && <p role="alert" className="text-danger">{t('common.error')}</p>}
      {data && data.length === 0 && <p className="text-muted-foreground">{t('payments.none')}</p>}
      <ul className="space-y-2">
        {data?.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3">
            <div>
              <p className="font-medium">
                {t(`payments.types.${p.payment_type}`)}
                {p.payment_type === 'payment' && ` · ${t('payments.seq', { n: p.seq })}`}
              </p>
              <p className="text-sm text-muted-foreground">
                {p.paid_date ? formatDate(p.paid_date) : NO_DATA}
              </p>
            </div>
            <div className="text-right">
              <p className="font-semibold">{formatMoney(p.amount)}</p>
              <StatusBadge tone={p.status === 'paid' ? 'success' : 'neutral'} icon={p.status === 'paid' ? '✓' : '○'}>
                {t(`payments.status.${p.status}`)}
              </StatusBadge>
            </div>
          </li>
        ))}
      </ul>
      <Link to="/payments" className="inline-block min-h-11 py-2 text-primary">
        {t('payments.title')} ›
      </Link>
    </section>
  )
}
