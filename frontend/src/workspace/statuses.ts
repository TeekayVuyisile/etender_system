import type { WorkspaceStatus } from '../lib/types'

export const STATUS_ORDER: WorkspaceStatus[] = [
  'pending',
  'interested',
  'preparing',
  'submitted',
  'not_eligible',
]

export const STATUS_LABELS: Record<WorkspaceStatus, string> = {
  pending: 'Pending',
  interested: 'Interested',
  preparing: 'Preparing bid',
  submitted: 'Submitted',
  not_eligible: 'Not eligible',
}

export const STATUS_STYLES: Record<WorkspaceStatus, string> = {
  pending: 'bg-slate-100 text-slate-700',
  interested: 'bg-sky-50 text-sky-700',
  preparing: 'bg-amber-50 text-amber-700',
  submitted: 'bg-emerald-50 text-emerald-700',
  not_eligible: 'bg-red-50 text-red-700',
}
