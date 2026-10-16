import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../lib/api'
import type { NotificationList } from '../lib/types'

const notificationsKey = ['notifications'] as const

/** The user's latest notifications, re-checked every minute (and when the tab regains focus). */
export function useNotifications() {
  return useQuery({
    queryKey: notificationsKey,
    queryFn: () => apiRequest<NotificationList>('/notifications?limit=15'),
    refetchInterval: 60_000,
  })
}

export function useMarkRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiRequest(id === 'all' ? '/notifications/read-all' : `/notifications/${id}/read`, {
        method: 'POST',
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: notificationsKey }),
  })
}
