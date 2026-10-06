/**
 * Client-side mirror of the SPEC section 8 matrix (apps/api/app/core/rbac.py).
 * It only decides which buttons to show; the API remains the source of truth and returns 403.
 */
export type Level = 'R' | 'W' | 'A'

const ROLES = ['admin', 'director', 'procurement', 'technical', 'cost', 'onsite', 'clerk', 'viewer'] as const

//                                  adm  dir  proc tech cost onst clrk view
const row = (s: string): Record<string, string> =>
  Object.fromEntries(ROLES.map((r, i) => [r, s[i]]).filter(([, l]) => l !== '-'))

const MATRIX: Record<string, Record<string, string>> = {
  project: row('WRRRR--R'),
  package: row('WWWRRRRR'),
  contract: row('WAWRWRRR'),
  payment: row('WARRW--R'),
  progress: row('WWRWRW-R'),
  risk: row('WAWWWW-R'),
  document: row('WWWWWWWR'),
  meeting: row('WAWWRRRR'),
  doc_number: row('WRRRR-WR'),
  audit_log: row('RR------'),
}

const RANK: Record<string, number> = { R: 1, W: 2, A: 3 }

export function can(role: string | undefined, resource: string, level: Level): boolean {
  const grant = role ? MATRIX[resource]?.[role] : undefined
  return grant !== undefined && RANK[grant] >= RANK[level]
}
