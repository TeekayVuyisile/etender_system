import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'

import { formatDateTime, readableCase, relativeTime } from '../lib/format'
import type { AppNotification } from '../lib/types'
import { useMarkRead, useNotifications } from './queries'

const ICONS: Record<string, string> = {
  task_assigned: '✅',
  status_changed: '🔄',
  note_added: '💬',
  summary_ready: '✨',
  deadline_reminder: '⏰',
  briefing_reminder: '📅',
}

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const { data } = useNotifications()
  const markRead = useMarkRead()
  const unread = data?.unread_count ?? 0

  // Close when clicking outside the panel or pressing Escape.
  useEffect(() => {
    if (!open) return
    function onClick(event: MouseEvent) {
      if (!panelRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function openNotification(notification: AppNotification) {
    if (!notification.read_at) markRead.mutate(notification.id)
    setOpen(false)
    if (notification.link) navigate(notification.link)
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="relative rounded-full p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        aria-label={unread ? `Notifications (${unread} unread)` : 'Notifications'}
        aria-expanded={open}
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.8}
          className="h-5 w-5"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0"
          />
        </svg>
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <p className="font-semibold text-slate-900">Notifications</p>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markRead.mutate('all')}
                className="text-xs font-medium text-emerald-700 hover:text-emerald-800"
              >
                Mark all as read
              </button>
            )}
          </div>
          {!data || data.items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-slate-500">
              You&apos;re all caught up. Task assignments, status changes and deadline reminders
              will appear here.
            </p>
          ) : (
            <ul className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
              {data.items.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => openNotification(notification)}
                    className={`flex w-full gap-3 px-4 py-3 text-left hover:bg-slate-50 ${
                      notification.read_at ? '' : 'bg-emerald-50/50'
                    }`}
                  >
                    <span className="mt-0.5 text-base" aria-hidden="true">
                      {ICONS[notification.type] ?? '🔔'}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span
                        className={`block text-sm ${
                          notification.read_at ? 'text-slate-700' : 'font-semibold text-slate-900'
                        }`}
                      >
                        {notification.title}
                      </span>
                      {notification.body && (
                        <span className="mt-0.5 block truncate text-xs text-slate-500">
                          {readableCase(notification.body)}
                        </span>
                      )}
                      <span
                        className="mt-1 block text-[11px] text-slate-400"
                        title={formatDateTime(notification.created_at)}
                      >
                        {relativeTime(notification.created_at)}
                      </span>
                    </span>
                    {!notification.read_at && (
                      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-emerald-600" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
