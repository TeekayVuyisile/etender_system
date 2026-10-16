import { Outlet } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { Button } from './ui/Button'

export function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="min-w-0">
            <p className="text-sm font-semibold tracking-wide text-emerald-700 uppercase">
              Tender Insight Hub
            </p>
            <p className="truncate text-xs text-slate-500">{user?.team.name}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-slate-600 sm:inline">{user?.full_name}</span>
            <Button variant="secondary" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
