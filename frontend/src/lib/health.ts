import { useQuery } from '@tanstack/react-query'

import { apiRequest } from './api'
import type { HealthResponse } from './types'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiRequest<HealthResponse>('/health'),
  })
}
