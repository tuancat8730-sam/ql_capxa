import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { useRole } from '@/features/projects/ProjectContext'
import { api } from '@/lib/api'
import { can } from '@/lib/permissions'
import { DecisionBadge, dmy } from './meta'
import { useDecisions, useRefreshDelivery } from './queries'
import type { Decision, DecisionInput, DecisionStatus } from './types'

const STATUSES: DecisionStatus[] = ['pending', 'decided', 'not_applicable']
const blank = (v: string) => (v.trim() ? v.trim() : null)

function DecisionSheet({ item, canWrite, onClose }: { item: Decision | null; canWrite: boolean; onClose: () => void }) {
  const { t } = useTranslation()
  const refresh = useRefreshDelivery()
  const [title, setTitle] = useState(item?.title ?? '')
  const [reason, setReason] = useState(item?.reason ?? '')
  const [status, setStatus] = useState<DecisionStatus>(item?.status ?? 'pending')
  const [due, setDue] = useState(item?.due_date ?? '')
  const [decision, setDecision] = useState(item?.decision ?? '')
  const [decidedOn, setDecidedOn] = useState(item?.decided_on ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (call: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await call()
      await refresh()
      onClose()
    } catch {
      setError(t('common.error'))
      setBusy(false)
    }
  }

  const save = () => {
    const body: DecisionInput = {
      title: title.trim(),
      reason: blank(reason),
      status,
      due_date: due || null,
      decision: blank(decision),
      decided_on: decidedOn || null,
    }
    return run(() => (item ? api.patch(`/delivery/decisions/${item.id}`, body) : api.post('/delivery/decisions', body)))
  }

  return (
    <BottomSheet title={item ? t('delivery.decisions.edit', { no: item.no }) : t('delivery.decisions.add')} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (canWrite && title.trim()) void save()
        }}
      >
        <fieldset disabled={!canWrite || busy} className="space-y-4">
          <div>
            <label htmlFor="d-title" className="mb-1 block text-sm font-medium">{t('delivery.decisions.matter')}</label>
            <textarea id="d-title" required rows={3} className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label htmlFor="d-reason" className="mb-1 block text-sm font-medium">{t('delivery.decisions.reason')}</label>
            <textarea id="d-reason" rows={3} className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="d-status" className="mb-1 block text-sm font-medium">{t('delivery.decisions.status')}</label>
              <select id="d-status" className={inputClass} value={status} onChange={(e) => setStatus(e.target.value as DecisionStatus)}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{t(`delivery.decision.${s}`)}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="d-due" className="mb-1 block text-sm font-medium">{t('delivery.decisions.due')}</label>
              <input id="d-due" type="date" className={inputClass} value={due} onChange={(e) => setDue(e.target.value)} />
            </div>
          </div>
          <div>
            <label htmlFor="d-decision" className="mb-1 block text-sm font-medium">{t('delivery.decisions.decision')}</label>
            <textarea
              id="d-decision"
              rows={3}
              className={inputClass}
              placeholder={t('delivery.decisions.decisionHint')}
              value={decision}
              onChange={(e) => setDecision(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="d-on" className="mb-1 block text-sm font-medium">{t('delivery.decisions.decidedOn')}</label>
            <input id="d-on" type="date" className={inputClass} value={decidedOn} onChange={(e) => setDecidedOn(e.target.value)} />
          </div>
        </fieldset>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        {canWrite && (
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="submit" disabled={busy || !title.trim()} className={primaryButton}>
              {t('common.save')}
            </button>
            {item && (
              <button
                type="button"
                disabled={busy}
                className="min-h-11 rounded-md border border-border px-4"
                onClick={() =>
                  window.confirm(t('delivery.decisions.confirmDelete')) &&
                  void run(() => api.delete(`/delivery/decisions/${item.id}`))
                }
              >
                {t('delivery.decisions.delete')}
              </button>
            )}
          </div>
        )}
      </form>
    </BottomSheet>
  )
}

export function DecisionsPage() {
  const { t } = useTranslation()
  const role = useRole()
  const canWrite = can(role, 'decision', 'W')
  const decisions = useDecisions()
  const [editing, setEditing] = useState<Decision | 'new' | null>(null)

  const edit = (d: Decision) => (
    <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setEditing(d)}>
      {canWrite ? t('delivery.decisions.editShort') : t('delivery.decisions.view')}
    </button>
  )

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold md:text-2xl">{t('delivery.decisions.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('delivery.decisions.subtitle')}</p>
        </div>
        {canWrite && (
          <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setEditing('new')}>
            {t('delivery.decisions.add')}
          </button>
        )}
      </div>
      {decisions.isPending && <p role="status">{t('common.loading')}</p>}
      {decisions.isError && <p role="alert" className="text-danger">{t('common.error')}</p>}
      {decisions.data?.length === 0 && <p className="text-muted-foreground">{t('delivery.decisions.empty')}</p>}
      {decisions.data && decisions.data.length > 0 && (
        <ResponsiveList
          rows={decisions.data}
          rowKey={(d) => d.id}
          caption={t('delivery.decisions.title')}
          columns={[
            { key: 'no', header: '#', cell: (d) => d.no },
            {
              key: 'title',
              header: t('delivery.decisions.matter'),
              cell: (d) => (
                <div>
                  <p className="font-medium">{d.title}</p>
                  {d.reason && <p className="text-xs text-muted-foreground">{d.reason}</p>}
                </div>
              ),
            },
            { key: 'status', header: t('delivery.decisions.status'), cell: (d) => <DecisionBadge status={d.status} /> },
            {
              key: 'due',
              header: t('delivery.decisions.due'),
              cell: (d) => <span className={d.overdue ? 'text-danger' : undefined}>{dmy(d.due_date)}</span>,
            },
            { key: 'decision', header: t('delivery.decisions.decision'), cell: (d) => d.decision ?? t('delivery.decisions.none'), secondary: true },
            { key: 'act', header: '', cell: edit },
          ]}
          renderCard={(d) => (
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-2">
                <p className="font-medium">
                  #{d.no} · {d.title}
                </p>
                <DecisionBadge status={d.status} />
              </div>
              {d.reason && <p className="text-sm text-muted-foreground">{d.reason}</p>}
              <p className={`text-sm ${d.overdue ? 'text-danger' : 'text-muted-foreground'}`}>
                {t('delivery.decisions.due')}: {dmy(d.due_date)}
              </p>
              {d.decision && <p className="text-sm">{d.decision}</p>}
              {edit(d)}
            </div>
          )}
        />
      )}
      {editing && (
        <DecisionSheet item={editing === 'new' ? null : editing} canWrite={canWrite} onClose={() => setEditing(null)} />
      )}
    </section>
  )
}
