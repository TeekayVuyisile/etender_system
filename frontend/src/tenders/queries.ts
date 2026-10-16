import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../lib/api'
import { teamPlanKey } from '../plans/queries'
import type { BuyerOption, TenderDetail, TenderSearchResponse } from '../lib/types'
import { PAGE_SIZE, type TenderQuery, toSearchParams } from './searchParams'

export function useTenderSearch(query: TenderQuery, enabled: boolean) {
  const queryClient = useQueryClient()
  const params = toSearchParams(query, { page_size: String(PAGE_SIZE) })
  return useQuery({
    queryKey: ['tenders', params.toString()],
    queryFn: async () => {
      const result = await apiRequest<TenderSearchResponse>(`/tenders?${params}`)
      // Searches can count towards the plan's weekly limit, so refresh the usage numbers.
      queryClient.invalidateQueries({ queryKey: teamPlanKey })
      return result
    },
    enabled,
    placeholderData: keepPreviousData, // keep showing old results while the next page loads
  })
}

export function useTender(id: number) {
  return useQuery({
    queryKey: ['tender', id],
    queryFn: () => apiRequest<TenderDetail>(`/tenders/${id}`),
    enabled: Number.isFinite(id),
  })
}

export function useBuyerSearch(q: string) {
  return useQuery({
    queryKey: ['tender-buyers', q],
    queryFn: () => apiRequest<BuyerOption[]>(`/tenders/buyers?${new URLSearchParams({ q })}`),
    staleTime: 5 * 60 * 1000,
  })
}
