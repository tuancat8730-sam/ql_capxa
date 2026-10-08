import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Page } from '@/lib/api'
import type { Decision, DeliveryRisk, Overview, Task, Week } from './types'

// Every key starts with 'delivery' so one call refreshes whatever a change touches.
const KEY = 'delivery'

export const useOverview = () =>
  useQuery({ queryKey: [KEY, 'overview'], queryFn: () => api.get<Overview>('/delivery/overview') })

export const useTasks = () =>
  useQuery({ queryKey: [KEY, 'tasks'], queryFn: () => api.get<Task[]>('/delivery/tasks') })

export const useWeeks = () =>
  useQuery({ queryKey: [KEY, 'weeks'], queryFn: () => api.get<Week[]>('/delivery/weeks') })

export const useDecisions = () =>
  useQuery({ queryKey: [KEY, 'decisions'], queryFn: () => api.get<Decision[]>('/delivery/decisions') })

export const useDeliveryRisks = () =>
  useQuery({
    queryKey: [KEY, 'risks'],
    queryFn: async () => (await api.get<Page<DeliveryRisk>>('/risks?page_size=100')).items,
  })

/** Figures, states, weeks and the attention list all move together: refresh them as one. */
export function useRefreshDelivery(): () => Promise<void> {
  const queryClient = useQueryClient()
  return async () => {
    await queryClient.invalidateQueries({ queryKey: [KEY] })
    await queryClient.invalidateQueries({ queryKey: ['alerts'] })
  }
}
