import { useState } from 'react'

import { useAuth } from '../auth/useAuth'
import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import { ProfileForm } from '../profile/ProfileForm'
import { ProfileSummary } from '../profile/ProfileSummary'
import { useCompanyProfile } from '../profile/queries'

export function CompanyProfilePage() {
  const { user } = useAuth()
  const profileQuery = useCompanyProfile()
  const [isEditing, setIsEditing] = useState(false)

  if (!user || profileQuery.isPending) {
    return <Spinner />
  }
  if (profileQuery.isError) {
    return <ErrorAlert message={getErrorMessage(profileQuery.error)} />
  }

  const profile = profileQuery.data
  const isOwner = user.role === 'owner'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Company profile</h1>
          <p className="mt-1 text-slate-600">
            Used to match your company against tender requirements.
          </p>
        </div>
        {isOwner && profile && !isEditing && (
          <Button variant="secondary" onClick={() => setIsEditing(true)}>
            Edit profile
          </Button>
        )}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {isEditing ? (
          <ProfileForm
            user={user}
            profile={profile}
            submitLabel="Save changes"
            onSaved={() => setIsEditing(false)}
            onCancel={() => setIsEditing(false)}
          />
        ) : profile ? (
          <>
            <ProfileSummary profile={profile} />
            <p className="mt-4 text-xs text-slate-400">
              Last updated {new Date(profile.updated_at).toLocaleString()}
              {!isOwner && ' · Only the team owner can edit this profile.'}
            </p>
          </>
        ) : (
          <p className="text-slate-600">No company profile has been created yet.</p>
        )}
      </div>
    </div>
  )
}
