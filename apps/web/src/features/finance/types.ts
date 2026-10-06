export type GuaranteeType = 'bid' | 'performance' | 'advance' | 'warranty'
export type EffectiveGuaranteeStatus =
  | 'pending'
  | 'valid'
  | 'expiring'
  | 'expired'
  | 'released'
  | 'missing'

export interface Finding {
  code: string
  severity: 'warning' | 'critical'
  message: string
  guarantee_id: string | null
  due_date: string | null
}

export interface Guarantee {
  id: string
  contract_id: string
  guarantee_type: GuaranteeType
  bank_name: string | null
  guarantee_no: string | null
  amount: number | null
  issue_date: string | null
  expiry_date: string | null
  validity_text: string | null
  status: string
  effective_status: EffectiveGuaranteeStatus
  days_left: number | null
  required: boolean
  verified: boolean
  verify_note: string | null
  findings: Finding[]
}

export interface GuaranteeRow extends Guarantee {
  contract_no: string
  package_id: string
  package_number: number
  package_name: string
}

export type PaymentStatus = 'planned' | 'requested' | 'approved' | 'paid' | 'rejected'

export interface Payment {
  id: string
  contract_id: string
  payment_type: 'advance' | 'payment' | 'recovery' | 'penalty'
  seq: number
  amount: number
  requested_date: string | null
  paid_date: string | null
  status: PaymentStatus
  invoice_no: string | null
  treasury_ref: string | null
  notes: string | null
}

export interface PaymentRow extends Payment {
  contract_no: string
  package_id: string
  package_number: number
  package_name: string
}

export interface DisbursementItem {
  package_id: string | null
  year: number
  month: number
  planned_amount: number
  actual_amount: number | null
}

export interface DisbursementPlan {
  items: DisbursementItem[]
  planned_total: number
  actual_total: number
}
