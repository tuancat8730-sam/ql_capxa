import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BottomSheet } from '@/components/responsive/BottomSheet'
import { ResponsiveList } from '@/components/responsive/ResponsiveList'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { inputClass, primaryButton } from '@/features/auth/LoginPage'
import { useRole } from '@/features/projects/ProjectContext'
import { api, ApiError } from '@/lib/api'
import { can } from '@/lib/permissions'
import { dmy, LEVELS, type Level, LevelBadge, levelOf, scoreOfLevel } from './meta'
import { useDeliveryRisks, useRefreshDelivery } from './queries'
import type { DeliveryRisk } from './types'

type Status = DeliveryRisk['status']
const STATUSES: Status[] = ['open', 'mitigating', 'closed']
const blank = (v: string) => (v.trim() ? v.trim() : null)

function RiskStatus({ status }: { status: Status }) {
  const { t } = useTranslation()
  const tone = status === 'closed' ? 'success' : status === 'mitigating' ? 'info' : 'warning'
  const icon = status === 'closed' ? '✓' : status === 'mitigating' ? '●' : '!'
  return (
    <StatusBadge tone={tone} icon={icon}>
      {t(`delivery.risks.statuses.${status}`)}
    </StatusBadge>
  )
}

function RiskSheet({
  risk,
  canWrite,
  canClose,
  onClose,
}: {
  risk: DeliveryRisk | null
  canWrite: boolean
  canClose: boolean
  onClose: () => void
}) {
  const { t } = useTranslation()
  const refresh = useRefreshDelivery()
  const [title, setTitle] = useState(risk?.title ?? '')
  const [group, setGroup] = useState(risk?.group_name ?? '')
  const [level, setLevel] = useState<Level>(risk ? levelOf(risk.score) : 'medium')
  const [status, setStatus] = useState<Status>(risk?.status ?? 'open')
  const [due, setDue] = useState(risk?.due_date ?? '')
  const [owner, setOwner] = useState(risk?.owner_text ?? '')
  const [action, setAction] = useState(risk?.mitigation ?? '')
  const [note, setNote] = useState(risk?.note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true)
    setError(null)
    const common = {
      title: title.trim(),
      group_name: blank(group),
      owner_text: blank(owner),
      mitigation: blank(action),
      note: blank(note),
      due_date: due || null,
      status,
    }
    // keep the exact score of a risk whose level did not change
    const score = risk && levelOf(risk.score) === level ? {} : scoreOfLevel(level)
    try {
      if (risk) await api.patch(`/risks/${risk.id}`, { ...common, ...score })
      else await api.post('/risks', { ...common, category: 'other', ...scoreOfLevel(level) })
      await refresh()
      onClose()
    } catch (err) {
      setError(err instanceof ApiError && err.status === 403 ? t('delivery.risks.onlyDirectorCloses') : t('common.error'))
      setBusy(false)
    }
  }

  const closing = risk && (status === 'closed') !== (risk.status === 'closed')
  const locked = !canWrite || (closing && !canClose)

  return (
    <BottomSheet title={risk ? `${risk.code} · ${t('delivery.risks.risk')}` : t('delivery.risks.add')} onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (canWrite && title.trim()) void save()
        }}
      >
        <fieldset disabled={!canWrite || busy} className="space-y-4">
          <div>
            <label htmlFor="k-title" className="mb-1 block text-sm font-medium">{t('delivery.risks.risk')}</label>
            <textarea id="k-title" required rows={3} className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="k-group" className="mb-1 block text-sm font-medium">{t('delivery.risks.group')}</label>
              <input id="k-group" className={inputClass} placeholder={t('delivery.risks.groupHint')} value={group} onChange={(e) => setGroup(e.target.value)} />
            </div>
            <div>
              <label htmlFor="k-level" className="mb-1 block text-sm font-medium">{t('delivery.risks.level')}</label>
              <select id="k-level" className={inputClass} value={level} onChange={(e) => setLevel(e.target.value as Level)}>
                {LEVELS.map((l) => (
                  <option key={l} value={l}>{t(`delivery.level.${l}`)}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="k-status" className="mb-1 block text-sm font-medium">{t('delivery.risks.status')}</label>
              <select id="k-status" className={inputClass} value={status} onChange={(e) => setStatus(e.target.value as Status)}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{t(`delivery.risks.statuses.${s}`)}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="k-due" className="mb-1 block text-sm font-medium">{t('delivery.risks.due')}</label>
              <input id="k-due" type="date" className={inputClass} value={due} onChange={(e) => setDue(e.target.value)} />
            </div>
          </div>
          <div>
            <label htmlFor="k-owner" className="mb-1 block text-sm font-medium">{t('delivery.risks.owner')}</label>
            <input id="k-owner" className={inputClass} placeholder={t('delivery.risks.ownerHint')} value={owner} onChange={(e) => setOwner(e.target.value)} />
          </div>
          <div>
            <label htmlFor="k-action" className="mb-1 block text-sm font-medium">{t('delivery.risks.action')}</label>
            <textarea id="k-action" rows={3} className={inputClass} value={action} onChange={(e) => setAction(e.target.value)} />
          </div>
          <div>
            <label htmlFor="k-note" className="mb-1 block text-sm font-medium">{t('delivery.risks.note')}</label>
            <textarea id="k-note" rows={3} className={inputClass} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        </fieldset>
        {closing && !canClose && (
          <p role="alert" className="text-sm text-danger">{t('delivery.risks.onlyDirectorCloses')}</p>
        )}
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        {canWrite && (
          <button type="submit" disabled={busy || locked || !title.trim()} className={primaryButton}>
            {t('common.save')}
          </button>
        )}
      </form>
    </BottomSheet>
  )
}

export function DeliveryRisksPage() {
  const { t } = useTranslation()
  const role = useRole()
  const risks = useDeliveryRisks()
  const [openOnly, setOpenOnly] = useState(false)
  const [editing, setEditing] = useState<DeliveryRisk | 'new' | null>(null)
  const canWrite = can(role, 'risk', 'W')

  const rows = (risks.data ?? [])
    .filter((r) => (openOnly ? r.status !== 'closed' : true))
    .sort((a, b) => b.score - a.score || a.code.localeCompare(b.code))

  const open = (r: DeliveryRisk) => (
    <button type="button" className="min-h-11 rounded-md border border-border px-3" onClick={() => setEditing(r)}>
      {canWrite ? t('delivery.risks.edit') : t('delivery.decisions.view')}
    </button>
  )

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold md:text-2xl">{t('delivery.risks.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('delivery.risks.subtitle')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} />
            {t('delivery.risks.openOnly')}
          </label>
          {canWrite && (
            <button type="button" className={`${primaryButton} !w-auto`} onClick={() => setEditing('new')}>
              {t('delivery.risks.add')}
            </button>
          )}
        </div>
      </div>
      {risks.isPending && <p role="status">{t('common.loading')}</p>}
      {risks.isError && <p role="alert" className="text-danger">{t('common.error')}</p>}
      {risks.data && rows.length === 0 && <p className="text-muted-foreground">{t('delivery.risks.empty')}</p>}
      {rows.length > 0 && (
        <ResponsiveList
          rows={rows}
          rowKey={(r) => r.id}
          caption={t('delivery.risks.title')}
          columns={[
            { key: 'code', header: t('delivery.risks.code'), cell: (r) => <span className="font-mono">{r.code}</span> },
            {
              key: 'title',
              header: t('delivery.risks.risk'),
              cell: (r) => (
                <div>
                  <p className="font-medium">{r.title}</p>
                  {r.group_name && <p className="text-xs text-muted-foreground">{r.group_name}</p>}
                  {r.mitigation && <p className="text-xs text-muted-foreground">{r.mitigation}</p>}
                </div>
              ),
            },
            { key: 'level', header: t('delivery.risks.level'), cell: (r) => <LevelBadge risk={r} /> },
            { key: 'status', header: t('delivery.risks.status'), cell: (r) => <RiskStatus status={r.status} /> },
            { key: 'owner', header: t('delivery.risks.owner'), cell: (r) => r.owner_text ?? '—', secondary: true },
            { key: 'due', header: t('delivery.risks.due'), cell: (r) => dmy(r.due_date), secondary: true },
            { key: 'act', header: '', cell: open },
          ]}
          renderCard={(r) => (
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-2">
                <p className="font-medium">
                  <span className="font-mono">{r.code}</span> · {r.title}
                </p>
                <LevelBadge risk={r} />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <RiskStatus status={r.status} />
                {r.group_name && <span>{r.group_name}</span>}
                {r.owner_text && <span>{r.owner_text}</span>}
                <span>{dmy(r.due_date)}</span>
              </div>
              {open(r)}
            </div>
          )}
        />
      )}
      {editing && (
        <RiskSheet
          risk={editing === 'new' ? null : editing}
          canWrite={canWrite}
          canClose={can(role, 'risk', 'A')}
          onClose={() => setEditing(null)}
        />
      )}
    </section>
  )
}
