export type SearchKind = 'package' | 'contract' | 'document' | 'risk' | 'issue'

export interface SearchHit {
  kind: SearchKind
  id: string
  title: string
  snippet: string | null
  package_id: string | null
  package_number: number | null
  subtitle: string | null
}

export interface SearchGroup {
  kind: SearchKind
  total: number
  items: SearchHit[]
}

export interface SearchResult {
  query: string
  groups: SearchGroup[]
}

/** Where a hit opens (SPEC 4.16): the package for packages and contracts, the list page otherwise. */
export function hitLink(hit: Pick<SearchHit, 'kind' | 'id' | 'package_id'>): string {
  const pkg = hit.package_id ? `/packages/${hit.package_id}` : null
  switch (hit.kind) {
    case 'package':
      return `/packages/${hit.id}`
    case 'contract':
      return pkg ? `${pkg}?tab=contracts` : '/contracts'
    case 'document':
      return pkg ? `${pkg}?tab=documents` : '/documents'
    case 'risk':
      return '/risks'
    case 'issue':
      return '/issues'
  }
}
