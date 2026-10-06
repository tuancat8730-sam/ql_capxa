import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'
import { MoneyInput } from '@/components/ui/MoneyInput'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { api, ApiError } from '@/lib/api'
import type { Guarantee } from './types'

const TYPES = ['bid', 'performance', 'advance', 'warranty'] as const
const STORED_STATUSES = ['valid', 'pending', 'missing', 'released'] as const

const schema = z.object({
  guarantee_type: z.enum(TYPES),
  bank_name: z.string().trim().optional(),
  guarantee_no: z.string().trim().optional(),
  amount: z.number().nullable(),
  issue_date: z.string().optional(),
  expiry_date: z.string().optional(),
  status: z.enum(STORED_STATUSES),
  required: z.boolean(),
  verified: z.boolean(),
  verify_note: z.string().trim().optional(),
})
type Values = z.infer<typeof schema>

interface GuaranteeFormProps {
  contractId: string
  guarantee?: Guarantee
  onDone: () => void
}

export function GuaranteeForm({ contractId, guarantee, onDone }: GuaranteeFormProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      guarantee_type: guarantee?.guarantee_type ?? 'performance',
      bank_name: guarantee?.bank_name ?? '',
      guarantee_no: guarantee?.guarantee_no ?? '',
      amount: guarantee?.amount ?? null,
      issue_date: guarantee?.issue_date ?? '',
      expiry_date: guarantee?.expiry_date ?? '',
      status: (STORED_STATUSES as readonly string[]).includes(guarantee?.status ?? '')
        ? (guarantee?.status as Values['status'])
        : 'valid',
      required: guarantee?.required ?? true,
      verified: guarantee?.verified ?? false,
      verify_note: guarantee?.verify_note ?? '',
    },
  })

  const onSubmit = async (v: Values) => {
    setError(null)
    const payload = {
      ...v,
      bank_name: v.bank_name || null,
      guarantee_no: v.guarantee_no || null,
      issue_date: v.issue_date || null,
      expiry_date: v.expiry_date || null,
      verify_note: v.verify_note || null,
    }
    try {
      if (guarantee) await api.patch(`/guarantees/${guarantee.id}`, payload)
      else await api.post(`/contracts/${contractId}/guarantees`, payload)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['guarantees'] }),
        queryClient.invalidateQueries({ queryKey: ['contract-guarantees'] }),
        queryClient.invalidateQueries({ queryKey: ['package-overview'] }),
      ])
      onDone()
    } catch (err) {
      setError(err instanceof ApiError && err.status === 403 ? t('payments.forbidden') : t('common.error'))
    }
  }

  const label = (id: string, text: string) => (
    <label htmlFor={id} className="mb-1 block text-sm font-medium">
      {text}
    </label>
  )

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <div>
        {label('g-type', t('contract.type'))}
        <select id="g-type" className={inputClass} {...register('guarantee_type')}>
          {TYPES.map((k) => (
            <option key={k} value={k}>
              {t(`guarantees.types.${k}`)}
            </option>
          ))}
        </select>
      </div>
      <div>
        {label('g-bank', t('guarantees.bank'))}
        <input id="g-bank" className={inputClass} {...register('bank_name')} />
      </div>
      <div>
        {label('g-no', t('guarantees.guaranteeNo'))}
        <input id="g-no" className={inputClass} {...register('guarantee_no')} />
      </div>
      <div>
        {label('g-amount', t('guarantees.amount'))}
        <Controller
          control={control}
          name="amount"
          render={({ field }) => <MoneyInput id="g-amount" value={field.value} onChange={field.onChange} />}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          {label('g-issue', t('guarantees.issueDate'))}
          <input id="g-issue" type="date" className={inputClass} {...register('issue_date')} />
        </div>
        <div>
          {label('g-expiry', t('guarantees.expiryDate'))}
          <input id="g-expiry" type="date" className={inputClass} {...register('expiry_date')} />
        </div>
      </div>
      <div>
        {label('g-status', t('guarantees.storedStatus'))}
        <select id="g-status" className={inputClass} {...register('status')}>
          {STORED_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`guarantees.status.${s}`)}
            </option>
          ))}
        </select>
      </div>
      <label className="flex min-h-11 items-center gap-2">
        <input type="checkbox" className="size-5" {...register('required')} />
        {t('guarantees.required')}
      </label>
      <label className="flex min-h-11 items-center gap-2">
        <input type="checkbox" className="size-5" {...register('verified')} />
        {t('guarantees.verified')}
      </label>
      <div>
        {label('g-note', t('guarantees.verifyNote'))}
        <input id="g-note" className={inputClass} {...register('verify_note')} />
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <button type="submit" disabled={isSubmitting} className={primaryButton}>
        {t('common.save')}
      </button>
    </form>
  )
}
