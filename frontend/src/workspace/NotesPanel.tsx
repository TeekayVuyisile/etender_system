import { type FormEvent, useState } from 'react'

import { useAuth } from '../auth/useAuth'
import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { getErrorMessage } from '../lib/api'
import { formatDateTime, relativeTime } from '../lib/format'
import type { WorkspaceNote } from '../lib/types'
import { useAddNote, useDeleteNote, useEditNote } from './queries'

const textareaClass =
  'block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 focus:outline-none'

export function NotesPanel({ entryId, notes }: { entryId: number; notes: WorkspaceNote[] }) {
  const addNote = useAddNote(entryId)
  const [draft, setDraft] = useState('')

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft.trim()) return
    addNote.mutate(draft, { onSuccess: () => setDraft('') })
  }

  return (
    <div>
      {notes.length === 0 ? (
        <p className="text-sm text-slate-500">No notes yet. Start the conversation below.</p>
      ) : (
        <ul className="space-y-4">
          {notes.map((note) => (
            <NoteItem key={note.id} entryId={entryId} note={note} />
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="mt-5 space-y-2">
        <label htmlFor="new-note" className="sr-only">
          Add a note
        </label>
        <textarea
          id="new-note"
          rows={3}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add an internal note for your team…"
          maxLength={5000}
          className={textareaClass}
        />
        {addNote.isError && <ErrorAlert message={getErrorMessage(addNote.error)} />}
        <Button type="submit" isLoading={addNote.isPending} disabled={!draft.trim()}>
          Add note
        </Button>
      </form>
    </div>
  )
}

function NoteItem({ entryId, note }: { entryId: number; note: WorkspaceNote }) {
  const { user } = useAuth()
  const editNote = useEditNote(entryId)
  const deleteNote = useDeleteNote(entryId)
  const [isEditing, setIsEditing] = useState(false)
  const [body, setBody] = useState(note.body)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const isAuthor = note.author?.id === user?.id
  const canDelete = isAuthor || user?.role === 'owner'
  const wasEdited = new Date(note.updated_at).getTime() - new Date(note.created_at).getTime() > 1000

  return (
    <li className="rounded-xl bg-slate-50 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-slate-900">
          {note.author?.full_name ?? 'A former member'}
        </p>
        <p className="text-xs text-slate-400" title={formatDateTime(note.created_at)}>
          {relativeTime(note.created_at)}
          {wasEdited && ' · edited'}
        </p>
      </div>

      {isEditing ? (
        <div className="mt-2 space-y-2">
          <textarea
            rows={3}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={5000}
            className={textareaClass}
            aria-label="Edit note"
          />
          {editNote.isError && <ErrorAlert message={getErrorMessage(editNote.error)} />}
          <div className="flex gap-2">
            <Button
              isLoading={editNote.isPending}
              disabled={!body.trim()}
              onClick={() =>
                editNote.mutate({ noteId: note.id, body }, { onSuccess: () => setIsEditing(false) })
              }
            >
              Save
            </Button>
            <Button variant="secondary" onClick={() => setIsEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-1 text-sm whitespace-pre-line text-slate-700">{note.body}</p>
      )}

      {!isEditing && (isAuthor || canDelete) && (
        <div className="mt-2 flex gap-3 text-xs">
          {isAuthor && (
            <button
              type="button"
              onClick={() => {
                setBody(note.body)
                setIsEditing(true)
              }}
              className="font-medium text-slate-500 hover:text-slate-900"
            >
              Edit
            </button>
          )}
          {canDelete &&
            (confirmDelete ? (
              <span className="flex gap-2">
                <span className="text-slate-500">Delete this note?</span>
                <button
                  type="button"
                  onClick={() => deleteNote.mutate(note.id)}
                  className="font-semibold text-red-600 hover:text-red-700"
                >
                  Yes, delete
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  className="font-medium text-slate-500"
                >
                  No
                </button>
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="font-medium text-slate-500 hover:text-red-600"
              >
                Delete
              </button>
            ))}
        </div>
      )}
    </li>
  )
}
