export type TaskStatus = 'not_started' | 'in_progress' | 'done' | 'on_hold'
export type TaskState = 'done' | 'paused' | 'late' | 'stale' | 'todo' | 'behind' | 'progress'
export type WeekState = 'received' | 'needs_more' | 'missing' | 'current' | 'future'
export type DecisionStatus = 'pending' | 'decided' | 'not_applicable'

export interface Task {
  id: string
  code: string
  phase_code: string
  phase_name: string
  name: string
  is_milestone: boolean
  plan_start: string
  plan_end: string
  plan_days: number
  tracked: boolean
  status: TaskStatus
  pct: number
  actual_start: string | null
  actual_end: string | null
  note: string | null
  updated_at: string
  state: TaskState
  late_days: number
}

export interface TaskPatch {
  status?: TaskStatus
  pct?: number
  actual_start?: string | null
  actual_end?: string | null
  note?: string | null
}

export interface Report {
  id: string
  week_start: string
  report_no: string | null
  status: 'received' | 'needs_more'
  submitted_on: string | null
  link: string | null
  planned_pct: number | null
  actual_pct: number | null
  done: string | null
  issues: string | null
  recommendations: string | null
  next_plan: string | null
  risk_ids: string[]
  updated_at: string
}

export interface ReportInput {
  report_no: string | null
  status: 'received' | 'needs_more'
  submitted_on: string | null
  link: string | null
  planned_pct: number | null
  actual_pct: number | null
  done: string | null
  issues: string | null
  recommendations: string | null
  next_plan: string | null
  risk_ids: string[]
}

export interface Week {
  no: number
  start: string
  end: string
  state: WeekState
  report: Report | null
  suggested_planned_pct: number
  suggested_actual_pct: number
}

export interface Decision {
  id: string
  no: number
  title: string
  reason: string | null
  status: DecisionStatus
  due_date: string | null
  decision: string | null
  decided_on: string | null
  updated_at: string
  overdue: boolean
}

export interface DecisionInput {
  title: string
  reason: string | null
  status: DecisionStatus
  due_date: string | null
  decision: string | null
  decided_on: string | null
}

export interface Attention {
  rank: number
  chip: 'good' | 'warn' | 'bad' | 'accent' | 'stale' | 'muted'
  label: string
  title: string
  sub: string
  target: 'task' | 'week' | 'risks'
  ref: string
}

export interface PhaseSummary {
  code: string
  name: string
  start: string
  end: string
  actual_pct: number
  plan_pct: number
  state: TaskState
}

export interface CurvePoint {
  date: string
  pct: number
}

export interface Overview {
  today: string
  project_start: string | null
  project_end: string | null
  has_progress: boolean
  actual_pct: number
  plan_pct: number
  diff: number
  next_milestone: { id: string; code: string; name: string; date: string; days_left: number } | null
  late_count: number
  stale_count: number
  weeks_ended: number
  weeks_received: number
  pending_decisions: number
  attention: Attention[]
  phases: PhaseSummary[]
  plan_curve: CurvePoint[]
  report_points: CurvePoint[]
}

/** A risk of a software-delivery project as the shared risks API returns it. */
export interface DeliveryRisk {
  id: string
  code: string
  title: string
  group_name: string | null
  owner_text: string | null
  mitigation: string | null
  note: string | null
  status: 'open' | 'mitigating' | 'occurred' | 'closed'
  due_date: string | null
  probability: number
  impact: number
  score: number
}
