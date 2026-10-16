import { Navigate, useNavigate } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import { ProfileForm } from '../profile/ProfileForm'
import { useCompanyProfile } from '../profile/queries'

/** Shown after sign-up until the team owner has created the company profile. */
export function OnboardingPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const profileQuery = useCompanyProfile()

  if (!user || profileQuery.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Spinner />
      </div>
    )
  }
  if (profileQuery.data) {
    return <Navigate to="/" replace />
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10 sm:px-6">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold tracking-wide text-emerald-700 uppercase">
              Welcome to Tender Insight Hub
            </p>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
              Set up {user.team.name}'s company profile
            </h1>
            <p className="mt-2 max-w-2xl text-slate-600">
              We use this to score how well each tender fits your company. You can change it at
              any time.
            </p>
          </div>
          <Button variant="secondary" onClick={logout}>
            Sign out
          </Button>
        </div>

        <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          {profileQuery.isError ? (
            <ErrorAlert message={getErrorMessage(profileQuery.error)} />
          ) : user.role === 'owner' ? (
            <ProfileForm
              user={user}
              profile={null}
              submitLabel="Save and continue"
              onSaved={() => navigate('/', { replace: true })}
            />
          ) : (
            <p className="text-slate-600">
              Your team owner hasn't set up the company profile yet. Once they have, you'll have
              full access to the workspace.
            </p>
          )}
        </div>
      </div>
    </main>
  )
}
