import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, apiRequest } from '../lib/api'
import type { MatchResult } from '../lib/types'

const matchKey = (tenderId: number) => ['tender-match', tenderId] as const

/** The team's latest readiness check for a tender, or null if it hasn't been run. */
export function useTenderMatch(tenderId: number) {
  return useQuery({
    queryKey: matchKey(tenderId),
    queryFn: async () => {
      try {
        return await apiRequest<MatchResult>(`/tenders/${tenderId}/match`)
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null
        throw error
      }
    },
  })
}

export function useMatchTender(tenderId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiRequest<MatchResult>(`/tenders/${tenderId}/match`, { method: 'POST' }),
    onSuccess: (result) => {
      queryClient.setQueryData(matchKey(tenderId), result)
      queryClient.invalidateQueries({ queryKey: ['workspace'] }) // re-rank by score
    },
  })
}
