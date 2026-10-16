import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../lib/api'
import type { Plan, PlanFeature, TeamPlan } from '../lib/types'

export const teamPlanKey = ['team-plan'] as const

export function useTeamPlan() {
  return useQuery({
    queryKey: teamPlanKey,
    queryFn: () => apiRequest<TeamPlan>('/team/plan'),
  })
}

/** Whether the team's plan includes a feature (undefined while loading). */
export function useHasFeature(feature: PlanFeature): boolean | undefined {
  const { data } = useTeamPlan()
  return data?.current[feature]
}

export function useChangePlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (plan: Plan) =>
      apiRequest<TeamPlan>('/team/plan', { method: 'PUT', json: { plan } }),
    onSuccess: (teamPlan) => {
      queryClient.setQueryData(teamPlanKey, teamPlan)
      // The plan affects almost everything (user info, summaries, scores, limits).
      queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'team-plan' })
    },
  })
}
