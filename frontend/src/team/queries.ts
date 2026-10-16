import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '../lib/api'
import type { User } from '../lib/types'

export const teamMembersKey = ['team-members'] as const

export function useTeamMembers() {
  return useQuery({
    queryKey: teamMembersKey,
    queryFn: () => apiRequest<User[]>('/team/members'),
  })
}
