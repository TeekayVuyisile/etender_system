import { useAuth } from '../auth/useAuth'
import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import { formatDate } from '../lib/format'
import type { PlanDetails } from '../lib/types'
import { useChangePlan, useTeamPlan } from '../plans/queries'

function featureList(plan: PlanDetails): { label: string; included: boolean }[] {
  return [
    {
      label:
        plan.seats === null
          ? 'Unlimited team members'
          : `Up to ${plan.seats} team member${plan.seats === 1 ? '' : 's'}`,
      included: true,
    },
    {
      label:
        plan.weekly_searches === null
          ? 'Unlimited tender searches'
          : `${plan.weekly_searches} tender searches per week`,
      included: true,
    },
    { label: 'Team workspace, notes and tasks', included: true },
    { label: 'AI summaries of tender documents', included: plan.ai_summaries },
    {
      label: 'Match This Tender (readiness scoring)',
      included: plan.readiness_checks,
    },
    { label: 'Export workspace reports (CSV, PDF)', included: plan.exports },
  ]
}

export function PlanPage() {
  const { user } = useAuth()
  const planQuery = useTeamPlan()
  const changePlan = useChangePlan()

  if (planQuery.isPending) return <Spinner />
  if (planQuery.isError) return <ErrorAlert message={getErrorMessage(planQuery.error)} />

  const { current, usage, available } = planQuery.data
  const isOwner = user?.role === 'owner'

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Plan &amp; usage</h1>
        <p className="mt-1 text-slate-600">
          Your team is on the <strong>{current.name}</strong> plan.
        </p>
      </div>

      <section className="grid gap-4 sm:grid-cols-2">
        <UsageMeter label="Team members" used={usage.seats_used} limit={usage.seats_limit} />
        <UsageMeter
          label="Searches this week"
          used={usage.searches_used}
          limit={usage.searches_limit}
          note={
            usage.searches_limit
              ? `Resets on Monday ${formatDate(usage.searches_reset_on)}`
              : undefined
          }
        />
      </section>

      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
        Demo mode: switching plans takes effect immediately and no payment is taken.
      </div>
      {changePlan.isError && <ErrorAlert message={getErrorMessage(changePlan.error)} />}

      <section className="grid gap-6 lg:grid-cols-3">
        {available.map((plan) => {
          const isCurrent = plan.plan === current.plan
          return (
            <div
              key={plan.plan}
              className={`flex flex-col rounded-2xl border bg-white p-6 shadow-sm ${
                isCurrent ? 'border-emerald-500 ring-2 ring-emerald-500/20' : 'border-slate-200'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-lg font-semibold text-slate-900">{plan.name}</h2>
                {isCurrent && (
                  <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
                    Current plan
                  </span>
                )}
              </div>
              <p className="mt-2 text-2xl font-bold text-slate-900">{plan.price_label}</p>
              <ul className="mt-6 flex-1 space-y-2 text-sm">
                {featureList(plan).map((feature) => (
                  <li
                    key={feature.label}
                    className={feature.included ? 'text-slate-700' : 'text-slate-400 line-through'}
                  >
                    <span className="mr-2">{feature.included ? '✓' : '✕'}</span>
                    {feature.label}
                  </li>
                ))}
              </ul>
              {isOwner && !isCurrent && (
                <Button
                  className="mt-6 w-full"
                  variant={plan.plan === 'free' ? 'secondary' : 'primary'}
                  isLoading={changePlan.isPending && changePlan.variables === plan.plan}
                  disabled={changePlan.isPending}
                  onClick={() => changePlan.mutate(plan.plan)}
                >
                  Switch to {plan.name}
                </Button>
              )}
            </div>
          )
        })}
      </section>
      {!isOwner && (
        <p className="text-sm text-slate-500">Only your team owner can change the plan.</p>
      )}
    </div>
  )
}

function UsageMeter({
  label,
  used,
  limit,
  note,
}: {
  label: string
  used: number | null
  limit: number | null
  note?: string
}) {
  const percent = limit && used !== null ? Math.min(100, (used / limit) * 100) : 0
  const full = limit !== null && used !== null && used >= limit
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <p className="text-sm font-semibold text-slate-900">
          {limit === null ? 'Unlimited' : `${used ?? 0} of ${limit}`}
        </p>
      </div>
      {limit !== null && (
        <div className="mt-3 h-2 rounded-full bg-slate-100">
          <div
            className={`h-2 rounded-full ${full ? 'bg-red-500' : 'bg-emerald-500'}`}
            style={{ width: `${percent}%` }}
          />
        </div>
      )}
      {note && <p className="mt-2 text-xs text-slate-500">{note}</p>}
    </div>
  )
}
