import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../lib/api'
import type { TenderSummary } from '../lib/types'

const summaryKey = (tenderId: number) => ['tender-summary', tenderId] as const

/** The tender's AI summary. While it's being generated, re-checks every 3 seconds. */
export function useTenderSummary(tenderId: number) {
  return useQuery({
    queryKey: summaryKey(tenderId),
    queryFn: () => apiRequest<TenderSummary>(`/tenders/${tenderId}/summary`),
    refetchInterval: (query) => (query.state.data?.status === 'processing' ? 3000 : false),
  })
}

export function useGenerateSummary(tenderId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (refresh: boolean) =>
      apiRequest<TenderSummary>(`/tenders/${tenderId}/summary${refresh ? '?refresh=true' : ''}`, {
        method: 'POST',
      }),
    onSuccess: (summary) => {
      queryClient.setQueryData(summaryKey(tenderId), summary)
      // Workspace cards show the summary text too.
      queryClient.invalidateQueries({ queryKey: ['workspace'] })
    },
  })
}
