export type EntryState = 'not_started' | 'in_progress' | 'done' | 'blocked'

export const ENTRY_STATES: EntryState[] = ['not_started', 'in_progress', 'done', 'blocked']

/** One reporting week in the list: whether a log (and a weekly report) exists for it. */
export interface LogWeek {
  no: number
  week_start: string
  week_end: string
  has_log: boolean
  has_report: boolean
  report_date: string | null
  entry_count: number
  max_delay_days: number
}

export interface LogEntry {
  entry_date: string
  phase_code: string
  task_code: string | null
  content: string
  personnel: string[]
  note: string | null
  state: EntryState | null
  delay_days: number | null
}

export interface LogCarryover {
  phase_code: string
  task_code: string | null
  title: string
  result_to_date: string | null
  next_week: string | null
  note: string | null
}

export interface LogMemberWork {
  member_name: string
  item: string
  plan_ref: string | null
  personnel: string[]
  result: string | null
  next_plan: string | null
  issues_actions: string | null
}

export interface LogHeader {
  report_date: string | null
  recipients: string | null
  reporter_org: string | null
  contract_ref: string | null
  coordinator: string | null
  environment_note: string | null
  overall_status: string | null
  key_results: string | null
  issues: string | null
  coordination_requests: string | null
  related_report: string | null
}

export interface ConstructionLog extends LogHeader {
  id: string
  week_start: string
  week_end: string
  entries: (LogEntry & { id: string })[]
  carryovers: (LogCarryover & { id: string })[]
  member_work: (LogMemberWork & { id: string })[]
  updated_at: string
}

/** The body of PUT /delivery/logs/{week_start}: the whole log, lines in display order. */
export interface ConstructionLogInput extends LogHeader {
  entries: LogEntry[]
  carryovers: LogCarryover[]
  member_work: LogMemberWork[]
  expected_updated_at: string | null
}

export interface LogHistoryItem {
  week_start: string
  entry_date: string
  content: string
  note: string | null
  state: EntryState | null
  delay_days: number | null
  personnel: string[]
}
