import type { Alert } from './types'

/** Where an alert's source lives, so a tap opens the entity that raised it (SPEC 4.10). */
export function alertLink(a: Pick<Alert, 'alert_type' | 'entity_type' | 'package_id'>): string {
  const pkg = a.package_id ? `/packages/${a.package_id}` : null
  switch (a.alert_type) {
    case 'GUARANTEE_EXPIRING':
    case 'ADVANCE_GUARANTEE_SHORT':
    case 'GUARANTEE_MISSING':
    case 'CONTRACT_ENDING':
      return pkg ? `${pkg}?tab=contracts` : '/contracts'
    case 'PAYMENT_DUE':
      return pkg ? `${pkg}?tab=payments` : '/payments'
    case 'STAGE_DELAYED':
    case 'PROGRESS_BEHIND':
      return pkg ? `${pkg}?tab=progress` : '/progress'
    case 'PLAN_STEP_OVERDUE':
      return pkg ? `${pkg}?tab=plan` : '/progress'
    case 'DOC_MISSING':
      return pkg ? `${pkg}?tab=documents` : '/documents'
    case 'ISSUE_SLA':
      return '/issues'
    case 'DAILY_LOG_MISSING':
      return '/daily-log'
    case 'REPORT_DUE':
      return '/progress'
    default:
      return pkg ?? '/alerts'
  }
}
