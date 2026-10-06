export type AlertSeverity = 'critical' | 'warning' | 'info'
export type AlertStatus = 'open' | 'acknowledged' | 'resolved' | 'suppressed'

export interface Alert {
  id: string
  alert_type: string
  severity: AlertSeverity
  entity_type: string
  entity_id: string
  package_id: string | null
  package_number: number | null
  title: string
  message: string
  due_date: string | null
  status: AlertStatus
  assigned_to: string | null
  first_seen_at: string
  resolved_at: string | null
  acknowledged_by: string | null
  acknowledged_at: string | null
  snoozed_until: string | null
  snooze_reason: string | null
  can_snooze: boolean
}

export interface AlertCounts {
  critical: number
  warning: number
  info: number
  total: number
}

export const SEVERITIES: AlertSeverity[] = ['critical', 'warning', 'info']
export const MAX_SNOOZE_DAYS = 7
