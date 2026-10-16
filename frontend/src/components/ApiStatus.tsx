import { useQuery } from '@tanstack/react-query'

import { apiGet, type HealthResponse } from '../lib/api'

export function ApiStatus() {
  // useQuery calls the API, caches the result, and tracks loading/error state for us
  const { data, isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/health'),
  })

  if (isPending) {
    return <StatusBadge color="bg-slate-400" label="Checking API…" />
  }

  if (isError) {
    return <StatusBadge color="bg-red-500" label="API unreachable. Is the backend running?" />
  }

  return <StatusBadge color="bg-emerald-500" label={`API online (${data.environment})`} />
}

function StatusBadge({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-sm text-slate-700">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  )
}
