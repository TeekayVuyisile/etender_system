import { Link } from 'react-router'

import { getErrorMessage } from '../lib/api'
import { useSavedTenders, useSaveTender } from './queries'
import { STATUS_LABELS } from './statuses'

type SaveTenderButtonProps = {
  tenderId: number
  size?: 'sm' | 'md'
}

/** "Save to workspace", or a link to the workspace entry if the team already saved it. */
export function SaveTenderButton({ tenderId, size = 'md' }: SaveTenderButtonProps) {
  const savedQuery = useSavedTenders()
  const saveTender = useSaveTender()
  const saved = savedQuery.data?.get(tenderId)

  const sizing = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-4 py-2 text-sm'
  // relative z-10 keeps the button clickable above a card's full-size link.
  const base = `relative z-10 inline-flex items-center gap-1.5 rounded-lg font-semibold ${sizing}`

  if (saved) {
    return (
      <Link
        to={`/workspace/${saved.entry_id}`}
        className={`${base} bg-emerald-50 text-emerald-700 hover:bg-emerald-100`}
        title="Open in workspace"
      >
        ✓ Saved · {STATUS_LABELS[saved.status]}
      </Link>
    )
  }

  return (
    <span className="relative z-10 inline-flex flex-col items-end">
      <button
        type="button"
        onClick={() => saveTender.mutate(tenderId)}
        disabled={saveTender.isPending || savedQuery.isPending}
        className={`${base} border border-slate-300 bg-white text-slate-700 hover:border-emerald-600 hover:text-emerald-700 disabled:opacity-60`}
      >
        {saveTender.isPending ? 'Saving…' : '☆ Save to workspace'}
      </button>
      {saveTender.isError && (
        <span className="mt-1 text-xs text-red-600">{getErrorMessage(saveTender.error)}</span>
      )}
    </span>
  )
}
