import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '../lib/api'
import type { HealthResponse } from '../lib/types'

export function ApiStatus() {
  const { isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiRequest<HealthResponse>('/health'),
  })

  if (isPending) {
    return <StatusBadge color="bg-slate-400" label="Checking API…" />
  }
  if (isError) {
    return <StatusBadge color="bg-red-500" label="API unreachable" />
  }
  return <StatusBadge color="bg-emerald-500" label="API online" />
}

function StatusBadge({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-slate-500">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  )
}
