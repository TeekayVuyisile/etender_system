import type { ReactNode } from 'react'
import { LuLock } from 'react-icons/lu'
import { Link } from 'react-router'

import type { Plan, PlanFeature } from '../lib/types'
import { useHasFeature } from './queries'

const PLAN_NAMES: Record<Plan, string> = { free: 'Free', basic: 'Basic', pro: 'Pro' }

export function UpgradePrompt({
  message,
  requiredPlan,
}: {
  message: string
  requiredPlan: Plan | null
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
      <p className="flex items-center gap-2 text-sm text-emerald-900">
        <LuLock className="shrink-0" aria-hidden="true" />
        {message}
      </p>
      <Link
        to="/plan"
        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold whitespace-nowrap text-white hover:bg-emerald-700"
      >
        {requiredPlan ? `Upgrade to ${PLAN_NAMES[requiredPlan]}` : 'View plans'}
      </Link>
    </div>
  )
}

const GATE_MESSAGES: Record<PlanFeature, { message: string; plan: Plan }> = {
  ai_summaries: {
    message: 'AI summaries of tender documents are available on the Basic and Pro plans.',
    plan: 'basic',
  },
  readiness_checks: {
    message: 'Match This Tender (readiness scoring) is available on the Basic and Pro plans.',
    plan: 'basic',
  },
  exports: { message: 'Report exports are available on the Pro plan.', plan: 'pro' },
}

/** Renders its children only if the team's plan includes `feature`; otherwise an upgrade prompt. */
export function FeatureGate({ feature, children }: { feature: PlanFeature; children: ReactNode }) {
  const allowed = useHasFeature(feature)
  if (allowed === undefined) return null
  if (!allowed) {
    const gate = GATE_MESSAGES[feature]
    return <UpgradePrompt message={gate.message} requiredPlan={gate.plan} />
  }
  return <>{children}</>
}
