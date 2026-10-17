import { LuArrowRight } from 'react-icons/lu'
import { Link } from 'react-router'

import { Spinner } from '../components/ui/Spinner'
import { useWorkspace } from './queries'
import { STATUS_LABELS, STATUS_ORDER } from './statuses'

export function WorkspaceSummaryCard() {
  const workspaceQuery = useWorkspace(null)
  const counts = workspaceQuery.data?.status_counts

  return (
    <section className="h-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-500">Workspace</h2>
      {!counts ? (
        <div className="mt-4">
          <Spinner />
        </div>
      ) : (
        <dl className="mt-4 space-y-2 text-sm">
          {STATUS_ORDER.map((status) => (
            <div key={status} className="flex justify-between gap-4">
              <dt className="text-slate-500">{STATUS_LABELS[status]}</dt>
              <dd className="font-semibold text-slate-900">{counts[status]}</dd>
            </div>
          ))}
        </dl>
      )}
      <Link
        to="/workspace"
        className="mt-6 inline-flex items-center gap-1 text-sm font-semibold text-emerald-700 hover:text-emerald-800"
      >
        Open workspace <LuArrowRight aria-hidden="true" />
      </Link>
    </section>
  )
}
