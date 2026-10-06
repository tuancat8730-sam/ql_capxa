import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { TFunction } from 'i18next'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { MoneyInput } from '@/components/ui/MoneyInput'
import { StatusBadge, type Tone } from '@/components/ui/StatusBadge'
import { useAuth } from '@/features/auth/AuthContext'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError, type Page } from '@/lib/api'
import { formatDate, formatMoney, NO_DATA } from '@/lib/format'
import { can } from '@/lib/permissions'
import type { DisbursementItem, DisbursementPlan, PaymentRow, PaymentStatus } from './types'

const STATUS_TONE: Record<PaymentStatus, { tone: Tone; icon: string }> = {
  planned: { tone: 'neutral', icon: '○' },
  requested: { tone: 'info', icon: '→' },
  approved: { tone: 'warning', icon: '✓' },
  paid: { tone: 'success', icon: '✓✓' },
  rejected: { tone: 'danger', icon: '✕' },
}

function errorText(err: unknown, t: TFunction): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return t('payments.forbidden')
    if (err.status === 409) return t('payments.conflict')
    if (err.status === 400) return t('payments.invalidTransition')
  }
  return t('common.error')
}

const label = (r: PaymentRow, t: TFunction) =>
  `${t(`payments.types.${r.payment_type}`)}${r.payment_type === 'payment' ? ` · ${t('payments.seq', { n: r.seq })}` : ''}`

const context = (r: PaymentRow) => `Gói ${String(r.package_number).padStart(2, '0')} · HĐ ${r.contract_no}`

function MarkPaidSheet({ payment, onClose }: { payment: PaymentRow; onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [ref, setRef] = useState('')
  const [error, setError] = useState<string | null>(null)
  const pay = useMutation({
    mutationFn: () =>
      api.post(`/payments/${payment.id}/mark-paid`, { paid_date: date, treasury_ref: ref || null }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['payments'] })
      onClose()
    },
    onError: (e) => setError(errorText(e, t)),
  })
  return (
    <BottomSheet title={t('payments.markPaid')} onClose={onClose}>
      <p className="mb-3 text-sm">
        {context(payment)} · {formatMoney(payment.amount)}
      </p>
      <div className="space-y-4">
        <div>
          <label htmlFor="paid-date" className="mb-1 block text-sm font-medium">
            {t('payments.paidDate')}
          </label>
          <input id="paid-date" type="date" className={inputClass} value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div>
          <label htmlFor="paid-ref" className="mb-1 block text-sm font-medium">
            {t('payments.treasuryRef')}
          </label>
          <input id="paid-ref" className={inputClass} value={ref} onChange={(e) => setRef(e.target.value)} />
        </div>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <button type="button" className={primaryButton} disabled={pay.isPending || !date} onClick={() => pay.mutate()}>
          {t('payments.confirmPaid')}
        </button>
      </div>
    </BottomSheet>
  )
}

function DisbursementSection({ canEdit }: { canEdit: boolean }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['disbursement-plan'],
    queryFn: () => api.get<DisbursementPlan>('/project/disbursement-plan'),
  })
  const [year, setYear] = useState(() => new Date().getFullYear())
  const [month, setMonth] = useState(() => new Date().getMonth() + 1)
  const [planned, setPlanned] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: (items: DisbursementItem[]) => api.put<DisbursementPlan>('/project/disbursement-plan', { items }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['disbursement-plan'] }),
    onError: (e) => setError(errorText(e, t)),
  })

  const items = data?.items ?? []
  const add = () => {
    if (planned === null) return
    setError(null)
    save.mutate([...items, { package_id: null, year, month, planned_amount: planned, actual_amount: null }])
    setPlanned(null)
  }

  return (
    <section className="space-y-3" aria-label={t('payments.disbursement')}>
      <h2 className="text-lg font-semibold">{t('payments.disbursement')}</h2>
      {items.length === 0 ? (
        <p className="text-muted-foreground">{t('payments.noPlan')}</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="px-2 py-2 font-medium">{t('payments.period')}</th>
              <th className="px-2 py-2 text-right font-medium">{t('payments.planned')}</th>
              <th className="px-2 py-2 text-right font-medium">{t('payments.actual')}</th>
              {canEdit && <th className="px-2 py-2" />}
            </tr>
          </thead>
          <tbody>
            {items.map((i, idx) => (
              <tr key={`${i.package_id}-${i.year}-${i.month}`} className="border-b border-border">
                <td className="px-2 py-2">
                  {String(i.month).padStart(2, '0')}/{i.year}
                </td>
                <td className="px-2 py-2 text-right">{formatMoney(i.planned_amount)}</td>
                <td className="px-2 py-2 text-right">{i.actual_amount === null ? NO_DATA : formatMoney(i.actual_amount)}</td>
                {canEdit && (
                  <td className="px-2 py-1 text-right">
                    <button
                      type="button"
                      aria-label={`${t('payments.removePeriod')} ${i.month}/${i.year}`}
                      className="min-h-11 min-w-11"
                      onClick={() => save.mutate(items.filter((_, n) => n !== idx))}
                    >
                      ✕
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="font-semibold">
              <td className="px-2 py-2">Σ</td>
              <td className="px-2 py-2 text-right">{formatMoney(data?.planned_total ?? 0)}</td>
              <td className="px-2 py-2 text-right">{formatMoney(data?.actual_total ?? 0)}</td>
              {canEdit && <td />}
            </tr>
          </tfoot>
        </table>
      )}
      {canEdit && (
        <div className="grid gap-2 sm:grid-cols-[6rem_6rem_1fr_auto] sm:items-end">
          <div>
            <label htmlFor="d-month" className="mb-1 block text-sm font-medium">
              {t('payments.month')}
            </label>
            <input id="d-month" type="number" min={1} max={12} className={inputClass} value={month} onChange={(e) => setMonth(Number(e.target.value))} />
          </div>
          <div>
            <label htmlFor="d-year" className="mb-1 block text-sm font-medium">
              {t('payments.year')}
            </label>
            <input id="d-year" type="number" min={2000} max={2100} className={inputClass} value={year} onChange={(e) => setYear(Number(e.target.value))} />
          </div>
          <div>
            <label htmlFor="d-amount" className="mb-1 block text-sm font-medium">
              {t('payments.planned')}
            </label>
            <MoneyInput id="d-amount" value={planned} onChange={setPlanned} />
          </div>
          <button type="button" className={`${primaryButton} !w-auto`} disabled={planned === null || save.isPending} onClick={add}>
            {t('payments.addPeriod')}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </section>
  )
}

export function PaymentsPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = can(user?.role, 'payment', 'W')
  const canApprove = can(user?.role, 'payment', 'A')
  const [paying, setPaying] = useState<PaymentRow | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ['payments'],
    queryFn: () => api.get<Page<PaymentRow>>('/payments?page_size=100'),
  })

  const move = useMutation({
    mutationFn: ({ id, status }: { id: string; status: PaymentStatus }) => api.patch(`/payments/${id}`, { status }),
    onSuccess: () => {
      setError(null)
      return queryClient.invalidateQueries({ queryKey: ['payments'] })
    },
    onError: (e) => setError(errorText(e, t)),
  })

  const paidTotal = (data?.items ?? []).filter((p) => p.status === 'paid').reduce((s, p) => s + p.amount, 0)
  const plannedTotal = (data?.items ?? []).reduce((s, p) => s + p.amount, 0)

  const actions = (p: PaymentRow) => {
    const btn = 'min-h-11 rounded-md border border-border px-3'
    return (
      <div className="flex flex-wrap gap-2">
        {canWrite && p.status === 'planned' && (
          <button type="button" className={btn} onClick={() => move.mutate({ id: p.id, status: 'requested' })}>
            {t('payments.request')}
          </button>
        )}
        {canApprove && p.status === 'requested' && (
          <>
            <button type="button" className={btn} onClick={() => move.mutate({ id: p.id, status: 'approved' })}>
              {t('payments.approve')}
            </button>
            <button type="button" className={btn} onClick={() => move.mutate({ id: p.id, status: 'rejected' })}>
              {t('payments.reject')}
            </button>
          </>
        )}
        {canWrite && p.status === 'approved' && (
          <button type="button" className={btn} onClick={() => setPaying(p)}>
            {t('payments.markPaid')}
          </button>
        )}
        {canWrite && p.status === 'rejected' && (
          <button type="button" className={btn} onClick={() => move.mutate({ id: p.id, status: 'planned' })}>
            {t('payments.reopen')}
          </button>
        )}
      </div>
    )
  }

  const badge = (p: PaymentRow) => (
    <StatusBadge tone={STATUS_TONE[p.status].tone} icon={STATUS_TONE[p.status].icon}>
      {t(`payments.status.${p.status}`)}
    </StatusBadge>
  )

  return (
    <section className="space-y-6">
      <h1 className="text-xl font-semibold md:text-2xl">{t('payments.title')}</h1>

      {data && (
        <dl className="grid grid-cols-2 gap-2">
          <div className="rounded-md border border-border p-3">
            <dt className="text-sm text-muted-foreground">{t('payments.totalPlanned')}</dt>
            <dd className="text-lg font-semibold">{formatMoney(plannedTotal)}</dd>
          </div>
          <div className="rounded-md border border-border p-3">
            <dt className="text-sm text-muted-foreground">{t('payments.totalPaid')}</dt>
            <dd className="text-lg font-semibold">{formatMoney(paidTotal)}</dd>
          </div>
        </dl>
      )}

      {isPending && <p role="status">{t('common.loading')}</p>}
      {isError && (
        <div role="alert" className="space-y-2">
          <p className="text-danger">{t('common.error')}</p>
          <button type="button" className="min-h-11 rounded-md border border-border px-4" onClick={() => void refetch()}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      {data && data.items.length === 0 && <p className="text-muted-foreground">{t('payments.none')}</p>}
      {data && data.items.length > 0 && (
        <ResponsiveList
          caption={t('payments.title')}
          rows={data.items}
          rowKey={(p) => p.id}
          renderCard={(p) => (
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm text-muted-foreground">{context(p)}</p>
                  <p className="font-semibold">{label(p, t)}</p>
                </div>
                {badge(p)}
              </div>
              <p className="text-lg font-semibold">{formatMoney(p.amount)}</p>
              {p.paid_date && (
                <p className="text-sm text-muted-foreground">
                  {t('payments.paidDate')}: {formatDate(p.paid_date)}
                </p>
              )}
              {actions(p)}
            </div>
          )}
          columns={[
            { key: 'ctx', header: t('contract.no'), cell: context },
            { key: 'type', header: t('contract.type'), cell: (p) => label(p, t) },
            { key: 'amount', header: t('guarantees.amount'), cell: (p) => formatMoney(p.amount) },
            { key: 'status', header: t('contract.status'), cell: badge },
            { key: 'paid', header: t('payments.paidDate'), cell: (p) => (p.paid_date ? formatDate(p.paid_date) : NO_DATA), secondary: true },
            { key: 'actions', header: t('users.more'), cell: actions },
          ]}
        />
      )}

      <DisbursementSection canEdit={canWrite} />

      {paying && <MarkPaidSheet payment={paying} onClose={() => setPaying(null)} />}
    </section>
  )
}
