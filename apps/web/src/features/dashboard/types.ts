import type { Health } from '@/features/packages/types'

export interface DashProject {
  name: string
  code: string
  investor_name: string | null
  total_investment: number | null
  funding_source: string | null
  start_year: number | null
  end_year: number | null
  package_count: number
  tvqlda_end_date: string | null
  tvqlda_days_left: number | null
}

export interface DashPackage {
  id: string
  number: number
  name: string
  package_type: string
  status: string
  contractor: string | null
  winning_price: number | null
  package_price: number | null
  current_stage: string
  progress_pct: number
  health: Health
  health_reason: string | null
}

export interface DashFinance {
  total_package_price: number
  total_winning_price: number
  total_contract_value: number
  total_advance: number
  total_paid: number
  planned_total: number
  planned_to_date: number
  disbursement_rate_pct: number | null
}

export interface Milestone {
  date: string
  days_left: number
  kind: string
  title: string
  package_id: string | null
  package_number: number | null
  entity_type: string
  entity_id: string
}

export interface Summary {
  today: string
  project: DashProject
  packages: DashPackage[]
  finance: DashFinance
  milestones: Milestone[]
}

export interface CashflowMonth {
  year: number
  month: number
  planned: number
  actual: number
}

export interface MissingDocs {
  total_missing: number
  packages: { package_id: string; number: number; name: string; required: number; missing: number }[]
}
