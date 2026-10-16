import { Navigate, Outlet } from 'react-router'

import { Spinner } from '../components/ui/Spinner'
import { useAuth } from './useAuth'

/** Only renders its child routes for logged-in users; everyone else goes to /login. */
export function RequireAuth() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <FullPageSpinner />
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}

/** Login/register pages: logged-in users are sent straight to the dashboard. */
export function GuestOnly() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <FullPageSpinner />
  }
  if (user) {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}

function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <Spinner />
    </div>
  )
}
