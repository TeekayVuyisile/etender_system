import { type FormEvent, useState } from 'react'

import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { getErrorMessage } from '../lib/api'
import { formatDate, isOverdue } from '../lib/format'
import type { User, WorkspaceTask } from '../lib/types'
import { useTeamMembers } from '../team/queries'
import { useAddTask, useDeleteTask, useUpdateTask } from './queries'

const inputClass =
  'rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 focus:outline-none'

export function TasksPanel({ entryId, tasks }: { entryId: number; tasks: WorkspaceTask[] }) {
  const membersQuery = useTeamMembers()
  const members = membersQuery.data ?? []
  const open = tasks.filter((t) => !t.is_done)
  const done = tasks.filter((t) => t.is_done)

  return (
    <div>
      {tasks.length === 0 && <p className="text-sm text-slate-500">No tasks yet.</p>}
      <ul className="divide-y divide-slate-100">
        {[...open, ...done].map((task) => (
          <TaskItem key={task.id} entryId={entryId} task={task} members={members} />
        ))}
      </ul>
      <AddTaskForm entryId={entryId} members={members} />
    </div>
  )
}

function TaskItem({
  entryId,
  task,
  members,
}: {
  entryId: number
  task: WorkspaceTask
  members: User[]
}) {
  const updateTask = useUpdateTask(entryId)
  const deleteTask = useDeleteTask(entryId)
  const overdue = !task.is_done && isOverdue(task.due_date)

  return (
    <li className="py-3">
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={task.is_done}
          onChange={(e) =>
            updateTask.mutate({ taskId: task.id, changes: { is_done: e.target.checked } })
          }
          className="mt-1 h-4 w-4 rounded border-slate-300 accent-emerald-600"
          aria-label={`Mark "${task.title}" as ${task.is_done ? 'not done' : 'done'}`}
        />
        <div className="min-w-0 flex-1">
          <p className={`text-sm ${task.is_done ? 'text-slate-400 line-through' : 'text-slate-900'}`}>
            {task.title}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <select
              value={task.assignee?.id ?? ''}
              onChange={(e) =>
                updateTask.mutate({
                  taskId: task.id,
                  changes: { assignee_id: e.target.value ? Number(e.target.value) : null },
                })
              }
              className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-xs"
              aria-label="Assignee"
            >
              <option value="">Unassigned</option>
              {members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.full_name}
                </option>
              ))}
            </select>
            {task.due_date && (
              <span className={overdue ? 'font-semibold text-red-600' : ''}>
                Due {formatDate(task.due_date)}
                {overdue && ' · overdue'}
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => deleteTask.mutate(task.id)}
          className="text-xs font-medium text-slate-400 hover:text-red-600"
          aria-label={`Delete task "${task.title}"`}
        >
          ✕
        </button>
      </div>
      {(updateTask.isError || deleteTask.isError) && (
        <div className="mt-2">
          <ErrorAlert message={getErrorMessage(updateTask.error ?? deleteTask.error)} />
        </div>
      )}
    </li>
  )
}

function AddTaskForm({ entryId, members }: { entryId: number; members: User[] }) {
  const addTask = useAddTask(entryId)
  const [title, setTitle] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [dueDate, setDueDate] = useState('')

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!title.trim()) return
    addTask.mutate(
      {
        title,
        assignee_id: assigneeId ? Number(assigneeId) : null,
        due_date: dueDate || null,
      },
      {
        onSuccess: () => {
          setTitle('')
          setAssigneeId('')
          setDueDate('')
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-2 border-t border-slate-100 pt-4">
      <label htmlFor="new-task" className="text-sm font-medium text-slate-700">
        Add a task
      </label>
      <input
        id="new-task"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="e.g. Get a tax compliance pin"
        maxLength={300}
        className={`${inputClass} w-full`}
      />
      <div className="flex flex-wrap gap-2">
        <select
          value={assigneeId}
          onChange={(e) => setAssigneeId(e.target.value)}
          className={`${inputClass} flex-1`}
          aria-label="Assign to"
        >
          <option value="">Unassigned</option>
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.full_name}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
          className={inputClass}
          aria-label="Due date"
        />
      </div>
      {addTask.isError && <ErrorAlert message={getErrorMessage(addTask.error)} />}
      <Button type="submit" isLoading={addTask.isPending} disabled={!title.trim()}>
        Add task
      </Button>
    </form>
  )
}
