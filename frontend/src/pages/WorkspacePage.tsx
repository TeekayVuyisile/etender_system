import { Link, useSearchParams } from 'react-router'

import { ErrorAlert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import type { WorkspaceEntry, WorkspaceStatus } from '../lib/types'
import { useWorkspace } from '../workspace/queries'
import { STATUS_LABELS, STATUS_ORDER } from '../workspace/statuses'
import { WorkspaceEntryCard } from '../workspace/WorkspaceEntryCard'

type View = 'ranked' | 'grouped'

export function WorkspacePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const statusParam = searchParams.get('status')
  const status = STATUS_ORDER.includes(statusParam as WorkspaceStatus)
    ? (statusParam as WorkspaceStatus)
    : null
  const view: View = searchParams.get('view') === 'grouped' ? 'grouped' : 'ranked'
  const workspaceQuery = useWorkspace(status)

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next)
  }

  const data = workspaceQuery.data
  const total = data ? Object.values(data.status_counts).reduce((sum, n) => sum + n, 0) : 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Team workspace</h1>
          <p className="mt-1 text-slate-600">
            Tenders your team has saved, with the best matches first.
          </p>
        </div>
        <div className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5 text-sm">
          {(['ranked', 'grouped'] as View[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setParam('view', option === 'grouped' ? 'grouped' : null)}
              className={`rounded-md px-3 py-1.5 font-medium ${
                view === option ? 'bg-emerald-600 text-white' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {option === 'ranked' ? 'Ranked list' : 'Group by status'}
            </button>
          ))}
        </div>
      </div>

      <nav className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-slate-200" aria-label="Status">
        <StatusTab label="All" count={total} active={status === null} onClick={() => setParam('status', null)} />
        {STATUS_ORDER.map((s) => (
          <StatusTab
            key={s}
            label={STATUS_LABELS[s]}
            count={data?.status_counts[s] ?? 0}
            active={status === s}
            onClick={() => setParam('status', s)}
          />
        ))}
      </nav>

      {workspaceQuery.isPending && <Spinner />}
      {workspaceQuery.isError && <ErrorAlert message={getErrorMessage(workspaceQuery.error)} />}

      {data && data.items.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="text-slate-600">
            {status
              ? `No tenders with status "${STATUS_LABELS[status]}".`
              : 'Your team hasn’t saved any tenders yet.'}
          </p>
          <Link
            to="/tenders"
            className="mt-3 inline-block text-sm font-semibold text-emerald-700 hover:text-emerald-800"
          >
            Find tenders to save →
          </Link>
        </div>
      )}

      {data && data.items.length > 0 &&
        (view === 'grouped' ? (
          <GroupedEntries entries={data.items} />
        ) : (
          <div className="space-y-3">
            {data.items.map((entry) => (
              <WorkspaceEntryCard key={entry.id} entry={entry} />
            ))}
          </div>
        ))}
    </div>
  )
}

function StatusTab({
  label,
  count,
  active,
  onClick,
}: {
  label: string
  count: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`-mb-px flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap ${
        active
          ? 'border-emerald-600 text-emerald-700'
          : 'border-transparent text-slate-600 hover:text-slate-900'
      }`}
    >
      {label}
      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{count}</span>
    </button>
  )
}

function GroupedEntries({ entries }: { entries: WorkspaceEntry[] }) {
  return (
    <div className="space-y-8">
      {STATUS_ORDER.map((status) => {
        const group = entries.filter((entry) => entry.status === status)
        if (group.length === 0) return null
        return (
          <section key={status}>
            <h2 className="mb-3 text-sm font-semibold text-slate-500">
              {STATUS_LABELS[status]} ({group.length})
            </h2>
            <div className="space-y-3">
              {group.map((entry) => (
                <WorkspaceEntryCard key={entry.id} entry={entry} />
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
