import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Alert, AlertCounts } from './types'

export interface DashAlerts {
  counts: AlertCounts
  items: Alert[]
}

/** Open alerts for the badge on the bottom bar and the dashboard block (SPEC 15.11e). */
export function useDashAlerts() {
  return useQuery({
    queryKey: ['dashboard', 'alerts'],
    queryFn: () => api.get<DashAlerts>('/dashboard/alerts'),
    refetchInterval: 60_000,
  })
}

/** Critical and warning alerts that still need a person; info alerts do not count. */
export function useAlertBadge(): number {
  const { data } = useDashAlerts()
  return data ? data.counts.critical + data.counts.warning : 0
}
