export type RiskLevel = 'low' | 'medium' | 'high'
export type RiskStatus = 'open' | 'mitigating' | 'occurred' | 'closed'
export type RiskCategory = 'schedule' | 'cost' | 'quality' | 'legal' | 'contract' | 'supply' | 'safety' | 'other'

export interface Risk {
  id: string
  code: string
  package_id: string | null
  title: string
  description: string | null
  category: RiskCategory
  probability: number
  impact: number
  score: number
  level: RiskLevel
  mitigation: string | null
  contingency: string | null
  status: RiskStatus
  due_date: string | null
  last_reviewed_at: string | null
  needs_review: boolean
}

export interface MatrixCell {
  probability: number
  impact: number
  count: number
  risk_ids: string[]
}

export interface Matrix {
  cells: MatrixCell[]
  total: number
}

export const RISK_CATEGORIES: RiskCategory[] = ['schedule', 'cost', 'quality', 'legal', 'contract', 'supply', 'safety', 'other']
export const RISK_STATUSES: RiskStatus[] = ['open', 'mitigating', 'occurred', 'closed']

/** Same bands as the API (SPEC 4.8): 1-5 low, 6-12 medium, 13-25 high. */
export function levelOf(score: number): RiskLevel {
  return score <= 5 ? 'low' : score <= 12 ? 'medium' : 'high'
}
