import type { IconType } from 'react-icons'
import {
  LuArrowRight,
  LuBuilding2,
  LuCode,
  LuCreditCard,
  LuFolderKanban,
  LuLayoutDashboard,
  LuLogOut,
  LuSearch,
} from 'react-icons/lu'
import { Link, NavLink, Outlet } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { NotificationBell } from '../notifications/NotificationBell'
import { Logo } from './Logo'

const navItems: { to: string; label: string; icon: IconType }[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LuLayoutDashboard },
  { to: '/tenders', label: 'Tenders', icon: LuSearch },
  { to: '/workspace', label: 'Workspace', icon: LuFolderKanban },
  { to: '/company-profile', label: 'Company profile', icon: LuBuilding2 },
  { to: '/plan', label: 'Plan', icon: LuCreditCard },
  { to: '/developers', label: 'API', icon: LuCode },
]

export function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-slate-50">
      {user?.team.is_demo && (
        <div className="bg-slate-900 px-4 py-2 text-center text-sm text-slate-100">
          You&apos;re exploring a demo workspace with sample data from real tenders. It&apos;s
          private to you and resets after 24 hours.{' '}
          <button
            type="button"
            onClick={() => {
              logout()
              // A full page load: an in-app navigation would be overridden by the
              // protected-route redirect to /login, and this also clears all demo state.
              window.location.assign('/register')
            }}
            className="inline-flex items-center gap-1 font-semibold text-emerald-300 underline-offset-2 hover:underline"
          >
            Create your own account <LuArrowRight aria-hidden="true" />
          </button>
        </div>
      )}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link to="/dashboard" className="flex min-w-0 items-center gap-3">
            <Logo nameClassName="hidden sm:inline" />
            <span className="hidden h-5 w-px bg-slate-200 sm:block" aria-hidden="true" />
            <span className="truncate text-sm text-slate-500">{user?.team.name}</span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            {user && (
              <Link
                to="/plan"
                className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 capitalize ring-1 ring-emerald-100 hover:bg-emerald-100"
                title="View plan and usage"
              >
                {user.team.plan} plan
              </Link>
            )}
            <NotificationBell />
            <span className="hidden text-sm text-slate-600 md:inline">{user?.full_name}</span>
            <button
              type="button"
              onClick={logout}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <LuLogOut aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 sm:px-6">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap ${
                  isActive
                    ? 'border-emerald-600 text-emerald-700'
                    : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900'
                }`
              }
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
