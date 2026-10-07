export type StepStatus = 'not_started' | 'in_progress' | 'done' | 'blocked'
export type EffectiveStatus = StepStatus | 'delayed'

export interface PlanItem {
  id: string
  line_no: number
  name: string
  details: string | null
  unit: string | null
  quantity: number | null
  assignments: { org: string; quantity: number | null }[]
  note: string | null
}

export interface PlanStep {
  id: string
  group_no: number | null
  group_title: string | null
  step_no: number
  content: string
  time_text: string | null
  start_date: string | null
  end_date: string | null
  estimated: boolean
  time_note: string | null
  participants: string[]
  status: StepStatus
  effective_status: EffectiveStatus
  days_late: number | null
  actual_start: string | null
  actual_end: string | null
  tracking_note: string | null
}

export interface Finding {
  code: string
  severity: 'warning' | 'info'
  message: string
}

export interface Plan {
  id: string
  package_id: string
  addressee: string | null
  legal_basis: string | null
  contract_text: string | null
  contract_start: string | null
  contract_end: string | null
  implement_text: string | null
  implement_start: string | null
  implement_end: string | null
  locations: { label: string; text: string }[]
  signer: string | null
  declared_total: number | null
  total_quantity: number
  source_file_name: string | null
  imported_at: string | null
  items: PlanItem[]
  steps: PlanStep[]
  progress: { done: number; total: number; pct: number }
  findings: Finding[]
}

export interface ImportPreview {
  dry_run: boolean
  replaces_existing: boolean
  addressee: string | null
  contract_start: string | null
  contract_end: string | null
  implement_start: string | null
  implement_end: string | null
  locations: number
  total_quantity: number
  items: { line_no: number; name: string; quantity: number | null }[]
  steps: {
    step_no: number
    group_no: number | null
    group_title: string | null
    summary: string
    start_date: string | null
    end_date: string | null
    estimated: boolean
    keeps_tracking: boolean
  }[]
  kept_tracking: number
  findings: Finding[]
}

export const STEP_STATUSES: StepStatus[] = ['not_started', 'in_progress', 'done', 'blocked']
