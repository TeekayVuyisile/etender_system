import { formatDateTime, relativeTime } from '../lib/format'
import { useSyncStatus } from './queries'

/** "Tender data updated 2 hours ago · refreshes every 6 hours" */
export function DataFreshness() {
  const { data } = useSyncStatus()
  if (!data) return null

  if (!data.last_success_at) {
    return <p className="text-xs text-slate-500">No tender data has been imported yet.</p>
  }

  const hours = data.interval_hours
  const schedule = data.schedule_enabled
    ? ` · refreshes every ${hours === 1 ? 'hour' : `${hours} hours`}`
    : ''
  const lastRunFailed = data.last_run?.status === 'failed'

  return (
    <p className="text-xs text-slate-500">
      <span title={formatDateTime(data.last_success_at)}>
        Tender data from eTenders updated {relativeTime(data.last_success_at)}
      </span>
      {schedule}
      {lastRunFailed && (
        <span className="text-amber-700"> · the latest update failed and will be retried</span>
      )}
    </p>
  )
}
