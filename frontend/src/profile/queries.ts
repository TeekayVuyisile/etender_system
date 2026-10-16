import { useQuery } from '@tanstack/react-query'

import { ApiError, apiRequest } from '../lib/api'
import type { CompanyProfile, ProfileOptions } from '../lib/types'

export const companyProfileKey = ['company-profile'] as const

/** The team's profile, or null if it hasn't been created yet. */
export function useCompanyProfile() {
  return useQuery({
    queryKey: companyProfileKey,
    queryFn: async () => {
      try {
        return await apiRequest<CompanyProfile>('/company-profile')
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null
        }
        throw error
      }
    },
  })
}

export function useProfileOptions() {
  return useQuery({
    queryKey: ['company-profile-options'],
    queryFn: () => apiRequest<ProfileOptions>('/company-profile/options'),
    staleTime: Infinity,
  })
}
