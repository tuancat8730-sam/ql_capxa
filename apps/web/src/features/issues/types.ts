export type IssueType = 'operational' | 'contract' | 'schedule' | 'investor_request' | 'other'
export type IssueStatus = 'open' | 'in_progress' | 'escalated' | 'resolved' | 'closed'

export interface Issue {
  id: string
  code: string
  package_id: string | null
  issue_type: IssueType
  level: number
  title: string
  description: string | null
  due_at: string | null
  status: IssueStatus
  resolution: string | null
  decided_by: string | null
  resolved_at: string | null
  overdue: boolean
  overdue_days: number
}

export interface IssueEvent {
  id: string
  ts: string
  event: string
  from_level: number | null
  to_level: number | null
  note: string | null
}

export interface IssueDetail extends Issue {
  events: IssueEvent[]
}

export const ISSUE_TYPES: IssueType[] = ['operational', 'contract', 'schedule', 'investor_request', 'other']
export const BOARD_STATUSES: IssueStatus[] = ['open', 'in_progress', 'escalated', 'resolved']
export const FINISHED: IssueStatus[] = ['resolved', 'closed']

/** Days until the deadline in whole calendar days of the viewer (negative once past). */
export function daysUntilDue(dueIso: string, now = new Date()): number {
  const due = new Date(dueIso)
  const a = Date.UTC(due.getFullYear(), due.getMonth(), due.getDate())
  const b = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((a - b) / 86_400_000)
}
