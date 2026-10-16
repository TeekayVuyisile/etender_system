import { Link } from 'react-router'

import { formatDate } from '../lib/format'
import { useTeamPlan } from './queries'

/** On plans with a weekly search limit, shows how many searches are left. */
export function SearchAllowance() {
  const { data } = useTeamPlan()
  const limit = data?.usage.searches_limit
  if (!data || !limit) return null

  const used = data.usage.searches_used ?? 0
  const left = Math.max(0, limit - used)
  return (
    <p className="text-sm text-slate-600">
      <span className={left === 0 ? 'font-semibold text-red-600' : 'font-semibold text-slate-900'}>
        {left} of {limit} searches left
      </span>{' '}
      this week on the {data.current.name} plan (resets Monday{' '}
      {formatDate(data.usage.searches_reset_on)}). Paging through results doesn't count.{' '}
      <Link to="/plan" className="font-medium text-emerald-700 hover:text-emerald-800">
        Get unlimited searches
      </Link>
    </p>
  )
}
