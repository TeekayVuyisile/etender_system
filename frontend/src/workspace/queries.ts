import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../lib/api'
import type {
  MyTask,
  SavedTenderRef,
  TaskInput,
  WorkspaceEntryDetail,
  WorkspaceListResponse,
  WorkspaceNote,
  WorkspaceStatus,
  WorkspaceTask,
} from '../lib/types'

const keys = {
  all: ['workspace'] as const,
  list: (status: WorkspaceStatus | null) => ['workspace', 'list', status] as const,
  entry: (id: number) => ['workspace', 'entry', id] as const,
  saved: ['workspace', 'saved'] as const,
  myTasks: ['workspace', 'my-tasks'] as const,
}

// --- Queries ------------------------------------------------------------------

export function useWorkspace(status: WorkspaceStatus | null) {
  const params = status ? `?status=${status}` : ''
  return useQuery({
    queryKey: keys.list(status),
    queryFn: () => apiRequest<WorkspaceListResponse>(`/workspace${params}`),
  })
}

export function useWorkspaceEntry(id: number) {
  return useQuery({
    queryKey: keys.entry(id),
    queryFn: () => apiRequest<WorkspaceEntryDetail>(`/workspace/${id}`),
    enabled: Number.isFinite(id),
  })
}

/** Map of tender ID -> saved workspace entry, for showing "Saved" on tender cards. */
export function useSavedTenders() {
  return useQuery({
    queryKey: keys.saved,
    queryFn: () => apiRequest<SavedTenderRef[]>('/workspace/saved'),
    select: (refs) => new Map(refs.map((ref) => [ref.tender_id, ref])),
  })
}

export function useMyTasks() {
  return useQuery({
    queryKey: keys.myTasks,
    queryFn: () => apiRequest<MyTask[]>('/workspace/my-tasks'),
  })
}

// --- Mutations ----------------------------------------------------------------
// After any change, everything under ['workspace'] is refetched so lists, counts and
// the entry page all stay in sync.

function useWorkspaceMutation<TVariables, TResult>(
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  })
}

export function useSaveTender() {
  return useWorkspaceMutation((tenderId: number) =>
    apiRequest<WorkspaceEntryDetail>('/workspace', { method: 'POST', json: { tender_id: tenderId } }),
  )
}

export function useUpdateStatus(entryId: number) {
  return useWorkspaceMutation((status: WorkspaceStatus) =>
    apiRequest<WorkspaceEntryDetail>(`/workspace/${entryId}`, { method: 'PATCH', json: { status } }),
  )
}

export function useRemoveEntry() {
  return useWorkspaceMutation((entryId: number) =>
    apiRequest<void>(`/workspace/${entryId}`, { method: 'DELETE' }),
  )
}

export function useAddNote(entryId: number) {
  return useWorkspaceMutation((body: string) =>
    apiRequest<WorkspaceNote>(`/workspace/${entryId}/notes`, { method: 'POST', json: { body } }),
  )
}

export function useEditNote(entryId: number) {
  return useWorkspaceMutation(({ noteId, body }: { noteId: number; body: string }) =>
    apiRequest<WorkspaceNote>(`/workspace/${entryId}/notes/${noteId}`, {
      method: 'PATCH',
      json: { body },
    }),
  )
}

export function useDeleteNote(entryId: number) {
  return useWorkspaceMutation((noteId: number) =>
    apiRequest<void>(`/workspace/${entryId}/notes/${noteId}`, { method: 'DELETE' }),
  )
}

export function useAddTask(entryId: number) {
  return useWorkspaceMutation((task: TaskInput) =>
    apiRequest<WorkspaceTask>(`/workspace/${entryId}/tasks`, { method: 'POST', json: task }),
  )
}

export function useUpdateTask(entryId: number) {
  return useWorkspaceMutation(({ taskId, changes }: { taskId: number; changes: TaskInput }) =>
    apiRequest<WorkspaceTask>(`/workspace/${entryId}/tasks/${taskId}`, {
      method: 'PATCH',
      json: changes,
    }),
  )
}

export function useDeleteTask(entryId: number) {
  return useWorkspaceMutation((taskId: number) =>
    apiRequest<void>(`/workspace/${entryId}/tasks/${taskId}`, { method: 'DELETE' }),
  )
}
