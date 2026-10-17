import { useQuery } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import type { ConstructionLog, LogHistoryItem, LogWeek } from './logTypes'

// Under the 'delivery' key so `useRefreshDelivery` refreshes them with everything else.
const KEY = 'delivery'

export const useLogWeeks = () =>
  useQuery({ queryKey: [KEY, 'log-weeks'], queryFn: () => api.get<LogWeek[]>('/delivery/logs') })

/** The log of one week; `null` when the week has none yet (the API answers 404). */
export const useLog = (weekStart: string) =>
  useQuery({
    queryKey: [KEY, 'log', weekStart],
    queryFn: async () => {
      try {
        return await api.get<ConstructionLog>(`/delivery/logs/${weekStart}`)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null
        throw err
      }
    },
  })

export const useTaskLogHistory = (taskCode: string) =>
  useQuery({
    queryKey: [KEY, 'log-history', taskCode],
    queryFn: () => api.get<LogHistoryItem[]>(`/delivery/tasks/${encodeURIComponent(taskCode)}/log-history`),
  })
