export type Health = 'green' | 'amber' | 'red' | 'grey'

export interface PackageItem {
  id: string
  number: number
  name: string
  scope_summary: string | null
  package_type: 'goods' | 'consulting'
  package_price: number | null
  winning_price: number | null
  winning_org_text: string | null
  current_stage: string
  status: string
  progress_pct: number
  health: Health
  health_reason: string | null
  is_sensitive: boolean
  notes: string | null
  etbmt_no: string | null
  approved_duration_days: number | null
  contract_no?: string | null
  contract_value?: number | null
  contract_end_date?: string | null
  needs_review?: boolean
  checklist_pct?: number | null
}

export interface Issue {
  code: string
  severity: 'warning' | 'info'
  message: string
  expected: string | null
  actual: string | null
}

export interface Party {
  id: string
  organization_name: string | null
  role: 'lead' | 'member' | 'sole'
  share_pct: number | null
  share_amount: number | null
}

export interface ContractDetail {
  id: string
  contract_no: string
  signed_date: string | null
  effective_date: string | null
  duration_days: number | null
  planned_end_date: string | null
  extended_end_date: string | null
  end_date_override: boolean
  contract_type: 'lump_sum' | 'unit_price' | null
  price_adjustment: boolean
  value: number | null
  advance_pct: number | null
  advance_amount: number | null
  performance_bond_pct: number | null
  performance_bond_amount: number | null
  warranty_bond_pct: number | null
  warranty_bond_amount: number | null
  penalty_rate_pct: number | null
  penalty_unit: 'day' | 'week' | null
  penalty_cap_pct: number | null
  investor_account: string | null
  status: string
  data_quality_note: string | null
  consistency: Issue[]
  needs_review: boolean
  parties: Party[]
}

export interface PackageOverview {
  package: PackageItem
  project: { name: string; treasury_account: string | null }
  contracts: ContractDetail[]
  needs_review: boolean
}
