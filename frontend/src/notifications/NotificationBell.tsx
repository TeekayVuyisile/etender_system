import { useEffect, useRef, useState } from 'react'
import type { IconType } from 'react-icons'
import {
  LuAlarmClock,
  LuBell,
  LuCalendarDays,
  LuCircleCheck,
  LuMessageSquare,
  LuRefreshCw,
  LuSparkles,
} from 'react-icons/lu'
import { useNavigate } from 'react-router'

import { formatDateTime, readableCase, relativeTime } from '../lib/format'
import type { AppNotification } from '../lib/types'
import { useMarkRead, useNotifications } from './queries'

const ICONS: Record<string, IconType> = {
  task_assigned: LuCircleCheck,
  status_changed: LuRefreshCw,
  note_added: LuMessageSquare,
  summary_ready: LuSparkles,
  deadline_reminder: LuAlarmClock,
  briefing_reminder: LuCalendarDays,
}

function NotificationIcon({ type }: { type: string }) {
  const Icon = ICONS[type] ?? LuBell
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
      <Icon className="h-4 w-4" aria-hidden="true" />
    </span>
  )
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
        <LuBell className="h-5 w-5" aria-hidden="true" />
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
                    <NotificationIcon type={notification.type} />
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
