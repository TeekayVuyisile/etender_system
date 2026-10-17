import { LuCircleCheck, LuMessageSquare } from 'react-icons/lu'
import { Link } from 'react-router'

import { deadlineLabel, readableCase, relativeTime } from '../lib/format'
import type { WorkspaceEntry } from '../lib/types'
import { StatusBadge } from './StatusBadge'

export function WorkspaceEntryCard({ entry }: { entry: WorkspaceEntry }) {
  const deadline = deadlineLabel(entry.tender.closing_at)

  return (
    <article className="relative rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-emerald-300 hover:shadow">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={entry.status} />
          <span
            className={`text-xs font-medium ${deadline.urgency === 'urgent' ? 'text-red-600' : 'text-slate-500'}`}
          >
            {deadline.label}
          </span>
        </div>
        <MatchScore score={entry.match_score} />
      </div>

      <h3 className="mt-2 font-semibold text-slate-900">
        <Link
          to={`/workspace/${entry.id}`}
          className="after:absolute after:inset-0 hover:text-emerald-700 focus:outline-none"
        >
          {readableCase(entry.tender.title)}
        </Link>
      </h3>
      <p className="mt-0.5 text-sm text-slate-600">
        {readableCase(entry.tender.buyer_name)} · {entry.tender.tender_number}
      </p>

      <p className="mt-3 line-clamp-2 text-sm text-slate-500 italic">
        {entry.ai_summary ?? 'AI summary not generated yet.'}
      </p>

      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1">
          <LuMessageSquare aria-hidden="true" />
          {entry.note_count} note{entry.note_count === 1 ? '' : 's'}
        </span>
        <span className="inline-flex items-center gap-1">
          <LuCircleCheck aria-hidden="true" />
          {entry.open_task_count} open task{entry.open_task_count === 1 ? '' : 's'}
        </span>
        {entry.status_changed_by && (
          <span>
            Status set by {entry.status_changed_by.full_name}{' '}
            {relativeTime(entry.status_changed_at)}
          </span>
        )}
      </div>
    </article>
  )
}

function MatchScore({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <span className="rounded-full bg-slate-50 px-2.5 py-0.5 text-xs text-slate-400">
        Match score: not checked
      </span>
    )
  }
  const color = score >= 70 ? 'bg-emerald-600' : score >= 40 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold text-white ${color}`}>
      {Math.round(score)}/100
    </span>
  )
}
