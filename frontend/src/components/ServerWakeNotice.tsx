import { useEffect, useState, useSyncExternalStore } from 'react'
import { LuLoaderCircle } from 'react-icons/lu'

import { isWaitingForServer, subscribe } from '../lib/serverWake'

// Most requests finish well within this, so the notice only appears for a real cold start.
const SHOW_AFTER_MS = 3000

export function ServerWakeNotice() {
  const waiting = useSyncExternalStore(subscribe, isWaitingForServer)
  const [delayPassed, setDelayPassed] = useState(false)

  useEffect(() => {
    if (!waiting) return
    const timer = setTimeout(() => setDelayPassed(true), SHOW_AFTER_MS)
    return () => {
      clearTimeout(timer)
      setDelayPassed(false)
    }
  }, [waiting])

  if (!waiting || !delayPassed) return null

  return (
    <div role="status" className="fixed inset-x-0 bottom-4 z-50 flex justify-center px-4">
      <div className="flex max-w-md items-start gap-3 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 text-sm shadow-lg backdrop-blur">
        <LuLoaderCircle className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-emerald-600" />
        <p>
          <span className="font-medium text-slate-900">Waking up the server…</span>{' '}
          <span className="text-slate-600">
            The free hosting sleeps when idle, so the first request can take up to a minute.
          </span>
        </p>
      </div>
    </div>
  )
}
