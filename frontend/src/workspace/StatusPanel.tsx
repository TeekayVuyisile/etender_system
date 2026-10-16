import { ErrorAlert } from '../components/ui/Alert'
import { getErrorMessage } from '../lib/api'
import { formatDateTime, relativeTime } from '../lib/format'
import type { WorkspaceEntryDetail } from '../lib/types'
import { useUpdateStatus } from './queries'
import { STATUS_LABELS, STATUS_ORDER, STATUS_STYLES } from './statuses'

export function StatusPanel({ entry }: { entry: WorkspaceEntryDetail }) {
  const updateStatus = useUpdateStatus(entry.id)

  return (
    <div>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Change status">
        {STATUS_ORDER.map((status) => {
          const isCurrent = entry.status === status
          return (
            <button
              key={status}
              type="button"
              aria-pressed={isCurrent}
              disabled={updateStatus.isPending}
              onClick={() => !isCurrent && updateStatus.mutate(status)}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                isCurrent
                  ? `${STATUS_STYLES[status]} ring-2 ring-current`
                  : 'border border-slate-200 text-slate-600 hover:border-slate-400'
              } disabled:opacity-60`}
            >
              {STATUS_LABELS[status]}
            </button>
          )
        })}
      </div>
      {updateStatus.isError && (
        <div className="mt-3">
          <ErrorAlert message={getErrorMessage(updateStatus.error)} />
        </div>
      )}

      <h3 className="mt-6 text-xs font-semibold tracking-wide text-slate-500 uppercase">
        Status history
      </h3>
      <ol className="mt-3 space-y-3 border-l-2 border-slate-100 pl-4">
        {entry.status_changes.map((change) => (
          <li key={change.id} className="relative text-sm">
            <span className="absolute top-1.5 -left-[1.4rem] h-2.5 w-2.5 rounded-full bg-slate-300" />
            <p className="text-slate-700">
              <span className="font-medium text-slate-900">
                {change.changed_by?.full_name ?? 'A former member'}
              </span>{' '}
              {change.from_status ? (
                <>
                  changed status from <strong>{STATUS_LABELS[change.from_status]}</strong> to{' '}
                  <strong>{STATUS_LABELS[change.to_status]}</strong>
                </>
              ) : (
                'saved this tender to the workspace'
              )}
            </p>
            <p className="text-xs text-slate-400" title={formatDateTime(change.created_at)}>
              {relativeTime(change.created_at)}
            </p>
          </li>
        ))}
      </ol>
    </div>
  )
}
