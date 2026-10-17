import { Link } from 'react-router'

import { ErrorAlert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import { formatDate, isOverdue, readableCase } from '../lib/format'
import { useMyTasks } from './queries'

export function MyTasksCard() {
  const tasksQuery = useMyTasks()

  return (
    <section className="h-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-500">My open tasks</h2>
      <div className="mt-4">
        {tasksQuery.isPending && <Spinner />}
        {tasksQuery.isError && <ErrorAlert message={getErrorMessage(tasksQuery.error)} />}
        {tasksQuery.data?.length === 0 && (
          <p className="text-sm text-slate-500">Nothing assigned to you right now.</p>
        )}
        {tasksQuery.data && tasksQuery.data.length > 0 && (
          <ul className="divide-y divide-slate-100">
            {tasksQuery.data.map((task) => (
              <li key={task.id} className="py-3">
                <Link to={`/workspace/${task.entry_id}`} className="group block">
                  <p className="text-sm font-medium text-slate-900 group-hover:text-emerald-700">
                    {task.title}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-slate-500">
                    {task.due_date && (
                      <span
                        className={isOverdue(task.due_date) ? 'font-semibold text-red-600' : ''}
                      >
                        Due {formatDate(task.due_date)} ·{' '}
                      </span>
                    )}
                    {readableCase(task.tender_title)}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
