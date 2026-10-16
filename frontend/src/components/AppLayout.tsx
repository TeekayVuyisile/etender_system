import { Link, NavLink, Outlet } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { Button } from './ui/Button'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/tenders', label: 'Tenders' },
  { to: '/workspace', label: 'Workspace' },
  { to: '/company-profile', label: 'Company profile' },
  { to: '/plan', label: 'Plan' },
]

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
            {user && (
              <Link
                to="/plan"
                className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 capitalize hover:bg-emerald-100"
                title="View plan and usage"
              >
                {user.team.plan} plan
              </Link>
            )}
            <span className="hidden text-sm text-slate-600 sm:inline">{user?.full_name}</span>
            <Button variant="secondary" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-4 sm:px-6">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `border-b-2 px-3 py-2.5 text-sm font-medium whitespace-nowrap ${
                  isActive
                    ? 'border-emerald-600 text-emerald-700'
                    : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900'
                }`
              }
            >
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
