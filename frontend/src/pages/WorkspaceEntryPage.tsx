import { type ReactNode, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import { deadlineLabel, formatDateTime, readableCase } from '../lib/format'
import { NotesPanel } from '../workspace/NotesPanel'
import { useRemoveEntry, useWorkspaceEntry } from '../workspace/queries'
import { StatusPanel } from '../workspace/StatusPanel'
import { TasksPanel } from '../workspace/TasksPanel'

export function WorkspaceEntryPage() {
  const { entryId } = useParams()
  const navigate = useNavigate()
  const entryQuery = useWorkspaceEntry(Number(entryId))
  const removeEntry = useRemoveEntry()
  const [confirmRemove, setConfirmRemove] = useState(false)

  if (entryQuery.isPending) {
    return <Spinner />
  }
  if (entryQuery.isError) {
    return <ErrorAlert message={getErrorMessage(entryQuery.error)} />
  }

  const entry = entryQuery.data
  const { tender } = entry
  const deadline = deadlineLabel(tender.closing_at)

  return (
    <div className="space-y-6">
      <Link to="/workspace" className="text-sm font-medium text-emerald-700 hover:text-emerald-800">
        ← Back to workspace
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">
            {tender.tender_number}
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
            {readableCase(tender.title)}
          </h1>
          <p className="mt-1 text-slate-600">{readableCase(tender.buyer_name)}</p>
          <p className="mt-2 text-sm text-slate-600">
            Closes {formatDateTime(tender.closing_at)} ·{' '}
            <span className={deadline.urgency === 'urgent' ? 'font-semibold text-red-600' : ''}>
              {deadline.label}
            </span>
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Saved by {entry.saved_by?.full_name ?? 'a former member'}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Link
            to={`/tenders/${tender.id}`}
            className="text-sm font-semibold text-emerald-700 hover:text-emerald-800"
          >
            View full tender details →
          </Link>
          {confirmRemove ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-600">Remove from workspace?</span>
              <Button
                isLoading={removeEntry.isPending}
                onClick={() =>
                  removeEntry.mutate(entry.id, {
                    onSuccess: () => navigate('/workspace', { replace: true }),
                  })
                }
                variant="danger"
              >
                Remove
              </Button>
              <Button variant="secondary" onClick={() => setConfirmRemove(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmRemove(true)}
              className="text-sm font-medium text-slate-500 hover:text-red-600"
            >
              Remove from workspace
            </button>
          )}
          {removeEntry.isError && <ErrorAlert message={getErrorMessage(removeEntry.error)} />}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel title="Status">
            <StatusPanel entry={entry} />
          </Panel>
          <Panel title="AI summary & readiness">
            <p className="text-sm text-slate-500">
              The AI summary and match score for this tender will appear here once those features
              are available.
            </p>
          </Panel>
          <Panel title={`Notes (${entry.note_count})`}>
            <NotesPanel entryId={entry.id} notes={entry.notes} />
          </Panel>
        </div>
        <div>
          <Panel title={`Tasks (${entry.open_task_count} open)`}>
            <TasksPanel entryId={entry.id} tasks={entry.tasks} />
          </Panel>
        </div>
      </div>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-sm font-semibold text-slate-500">{title}</h2>
      {children}
    </section>
  )
}
