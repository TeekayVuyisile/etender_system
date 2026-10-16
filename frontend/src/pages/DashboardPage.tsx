import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { Link } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { TextField } from '../components/ui/TextField'
import { apiRequest, getErrorMessage } from '../lib/api'
import type { CurrentUser, MemberCreateData, Plan, User } from '../lib/types'
import { teamPlanKey, useTeamPlan } from '../plans/queries'
import { UpgradePrompt } from '../plans/UpgradePrompt'
import { useCompanyProfile } from '../profile/queries'
import { teamMembersKey, useTeamMembers } from '../team/queries'
import { MyTasksCard } from '../workspace/MyTasksCard'
import { WorkspaceSummaryCard } from '../workspace/WorkspaceSummaryCard'

const planLabels: Record<Plan, string> = {
  free: 'Free',
  basic: 'Basic',
  pro: 'Pro',
}

export function DashboardPage() {
  const { user } = useAuth()
  if (!user) {
    return null
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Welcome, {user.full_name.split(' ')[0]}
        </h1>
        <p className="mt-1 text-slate-600">Here's what's happening in your team's workspace.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <MyTasksCard />
        </div>
        <WorkspaceSummaryCard />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <TeamCard user={user} />
        <div className="lg:col-span-2">
          <MembersCard user={user} />
        </div>
      </div>
    </div>
  )
}

function TeamCard({ user }: { user: CurrentUser }) {
  const { data: profile } = useCompanyProfile()

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-500">Your team</h2>
      <p className="mt-2 text-lg font-semibold text-slate-900">{user.team.name}</p>
      <dl className="mt-4 space-y-3 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">Plan</dt>
          <dd>
            <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
              {planLabels[user.team.plan]}
            </span>
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">Your role</dt>
          <dd className="font-medium text-slate-900 capitalize">{user.role}</dd>
        </div>
        {profile && (
          <>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Sector</dt>
              <dd className="text-right font-medium text-slate-900">{profile.industry_sector}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Coverage</dt>
              <dd className="font-medium text-slate-900">
                {profile.provinces.length === 9
                  ? 'National'
                  : `${profile.provinces.length} province${profile.provinces.length === 1 ? '' : 's'}`}
              </dd>
            </div>
          </>
        )}
      </dl>
      <Link
        to="/company-profile"
        className="mt-6 inline-block text-sm font-semibold text-emerald-700 hover:text-emerald-800"
      >
        View company profile →
      </Link>
    </section>
  )
}

function MembersCard({ user }: { user: CurrentUser }) {
  const membersQuery = useTeamMembers()
  const { data: teamPlan } = useTeamPlan()
  const seatLimit = teamPlan?.usage.seats_limit
  const seatsFull =
    seatLimit !== undefined && seatLimit !== null && (teamPlan?.usage.seats_used ?? 0) >= seatLimit

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-500">
        Team members
        {seatLimit !== undefined && (
          <span className="ml-2 font-normal text-slate-400">
            {seatLimit === null
              ? `${teamPlan?.usage.seats_used} member${teamPlan?.usage.seats_used === 1 ? '' : 's'} · unlimited seats`
              : `${teamPlan?.usage.seats_used} of ${seatLimit} seats used`}
          </span>
        )}
      </h2>

      {membersQuery.isPending && (
        <div className="mt-4">
          <Spinner />
        </div>
      )}
      {membersQuery.isError && (
        <div className="mt-4">
          <ErrorAlert message={getErrorMessage(membersQuery.error)} />
        </div>
      )}
      {membersQuery.data && (
        <ul className="mt-4 divide-y divide-slate-100">
          {membersQuery.data.map((member) => (
            <li key={member.id} className="flex items-center justify-between gap-4 py-3">
              <div className="min-w-0">
                <p className="truncate font-medium text-slate-900">
                  {member.full_name}
                  {member.id === user.id && <span className="text-slate-400"> (you)</span>}
                </p>
                <p className="truncate text-sm text-slate-500">{member.email}</p>
              </div>
              <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 capitalize">
                {member.role}
              </span>
            </li>
          ))}
        </ul>
      )}

      {user.role === 'owner' &&
        (seatsFull ? (
          <div className="mt-6 border-t border-slate-100 pt-6">
            <UpgradePrompt
              message={`Your ${teamPlan?.current.name} plan allows ${seatLimit} team member${seatLimit === 1 ? '' : 's'}.`}
              requiredPlan={teamPlan?.current.plan === 'free' ? 'basic' : 'pro'}
            />
          </div>
        ) : (
          <AddMemberForm />
        ))}
    </section>
  )
}

const emptyMember: MemberCreateData = {
  full_name: '',
  email: '',
  password: '',
}

function AddMemberForm() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<MemberCreateData>(emptyMember)

  const addMember = useMutation({
    mutationFn: (data: MemberCreateData) =>
      apiRequest<User>('/team/members', { method: 'POST', json: data }),
    onSuccess: () => {
      setForm(emptyMember)
      queryClient.invalidateQueries({ queryKey: teamMembersKey })
      queryClient.invalidateQueries({ queryKey: teamPlanKey })
    },
  })

  function updateField(field: keyof MemberCreateData, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    addMember.mutate(form)
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-4 border-t border-slate-100 pt-6">
      <h3 className="font-semibold text-slate-900">Add a team member</h3>
      {addMember.isError && <ErrorAlert message={getErrorMessage(addMember.error)} />}
      <div className="grid gap-4 sm:grid-cols-3">
        <TextField
          label="Full name"
          required
          minLength={2}
          value={form.full_name}
          onChange={(e) => updateField('full_name', e.target.value)}
        />
        <TextField
          label="Email"
          type="email"
          required
          value={form.email}
          onChange={(e) => updateField('email', e.target.value)}
        />
        <TextField
          label="Temporary password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={form.password}
          onChange={(e) => updateField('password', e.target.value)}
        />
      </div>
      <Button type="submit" isLoading={addMember.isPending}>
        Add member
      </Button>
    </form>
  )
}
