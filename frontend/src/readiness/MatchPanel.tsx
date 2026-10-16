import { Link } from 'react-router'

import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import { relativeTime } from '../lib/format'
import type { CheckStatus, MatchResult } from '../lib/types'
import { useTenderSummary } from '../summaries/queries'
import { useMatchTender, useTenderMatch } from './queries'

const VERDICT_STYLES: Record<MatchResult['verdict'], { label: string; className: string }> = {
  suitable: { label: 'Suitable', className: 'bg-emerald-50 text-emerald-700' },
  possibly_suitable: { label: 'Possibly suitable', className: 'bg-amber-50 text-amber-700' },
  not_suitable: { label: 'Not suitable', className: 'bg-red-50 text-red-700' },
}

const STATUS_ICONS: Record<CheckStatus, { icon: string; label: string; className: string }> = {
  met: { icon: '✓', label: 'Yes', className: 'bg-emerald-100 text-emerald-700' },
  partial: { icon: '◐', label: 'Partly', className: 'bg-amber-100 text-amber-700' },
  unknown: { icon: '?', label: 'Confirm', className: 'bg-slate-200 text-slate-600' },
  not_met: { icon: '✕', label: 'No', className: 'bg-red-100 text-red-700' },
}

/** "Match This Tender": readiness score, checklist and recommendation for the team. */
export function MatchPanel({ tenderId }: { tenderId: number }) {
  const summaryQuery = useTenderSummary(tenderId)
  const matchQuery = useTenderMatch(tenderId)
  const matchTender = useMatchTender(tenderId)

  if (matchQuery.isPending || summaryQuery.isPending) {
    return <Spinner />
  }
  if (matchQuery.isError) {
    return <ErrorAlert message={getErrorMessage(matchQuery.error)} />
  }

  const summaryReady = summaryQuery.data?.status === 'ready'
  const result = matchQuery.data

  if (!result) {
    return (
      <div>
        <p className="text-sm text-slate-600">
          Check how well this tender fits your{' '}
          <Link to="/company-profile" className="font-medium text-emerald-700 hover:text-emerald-800">
            company profile
          </Link>
          : CIDB grading, provinces, B-BBEE, experience, certifications and services.
        </p>
        {!summaryReady && (
          <p className="mt-2 text-sm text-slate-500">
            Generate the AI summary first: matching uses the requirements it extracts.
          </p>
        )}
        {matchTender.isError && (
          <div className="mt-3">
            <ErrorAlert message={getErrorMessage(matchTender.error)} />
          </div>
        )}
        <Button
          className="mt-4"
          disabled={!summaryReady}
          isLoading={matchTender.isPending}
          onClick={() => matchTender.mutate()}
        >
          🎯 Match This Tender
        </Button>
      </div>
    )
  }

  const verdict = VERDICT_STYLES[result.verdict]

  return (
    <div className="space-y-5">
      {result.outdated && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Your company profile or the AI summary changed since this check.
          <Button
            variant="secondary"
            isLoading={matchTender.isPending}
            onClick={() => matchTender.mutate()}
          >
            Re-check
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-5">
        <ScoreRing score={result.score} />
        <div className="min-w-0 flex-1">
          <span
            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${verdict.className}`}
          >
            {verdict.label}
          </span>
          <p className="mt-2 text-sm font-medium text-slate-900">{result.recommendation}</p>
          <p className="mt-1 text-xs text-slate-500">
            Estimated competition: {result.competition}. Based on the tender's requirements, not
            on who else is bidding.
          </p>
        </div>
      </div>

      <ul className="divide-y divide-slate-100 rounded-xl border border-slate-100">
        {result.checklist.map((item) => {
          const status = STATUS_ICONS[item.status]
          return (
            <li key={item.key} className="flex items-start gap-3 px-4 py-3">
              <span
                className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${status.className}`}
                aria-label={status.label}
                title={status.label}
              >
                {status.icon}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-900">{item.label}</p>
                <p className="text-sm text-slate-600">{item.detail}</p>
              </div>
              <span className="shrink-0 text-xs text-slate-400">
                {Math.round(item.points)}/{item.weight}
              </span>
            </li>
          )
        })}
      </ul>

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
        <p>
          Checked {relativeTime(result.checked_at)}
          {result.checked_by && ` by ${result.checked_by}`}. Requirements come from the AI
          summary, so confirm them in the official documents.
        </p>
        {!result.outdated && (
          <button
            type="button"
            onClick={() => matchTender.mutate()}
            disabled={matchTender.isPending}
            className="font-medium text-slate-500 hover:text-slate-900"
          >
            Re-check
          </button>
        )}
      </div>
      {matchTender.isError && <ErrorAlert message={getErrorMessage(matchTender.error)} />}
    </div>
  )
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 75 ? '#059669' : score >= 50 ? '#d97706' : '#dc2626'
  const circumference = 2 * Math.PI * 34
  return (
    <div className="relative h-24 w-24 shrink-0" role="img" aria-label={`Score ${score} out of 100`}>
      <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90">
        <circle cx="40" cy="40" r="34" fill="none" stroke="#e2e8f0" strokeWidth="8" />
        <circle
          cx="40"
          cy="40"
          r="34"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score / 100)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-slate-900">{score}</span>
        <span className="text-[10px] text-slate-500">/ 100</span>
      </div>
    </div>
  )
}
