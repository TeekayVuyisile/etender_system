import { useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useEffect } from 'react'

import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import { formatCurrency, relativeTime } from '../lib/format'
import type { TenderSummaryContent } from '../lib/types'
import { useGenerateSummary, useTenderSummary } from './queries'

/** Shows a tender's AI summary, or lets the user generate one. */
export function SummaryPanel({ tenderId }: { tenderId: number }) {
  const summaryQuery = useTenderSummary(tenderId)
  const generate = useGenerateSummary(tenderId)
  const queryClient = useQueryClient()
  const summary = summaryQuery.data
  const status = summary?.status

  // When a summary finishes, refresh pages that show a summary-derived value (e.g. budget).
  useEffect(() => {
    if (status === 'ready') {
      queryClient.invalidateQueries({ queryKey: ['tender', tenderId] })
      queryClient.invalidateQueries({ queryKey: ['workspace'] })
    }
  }, [status, tenderId, queryClient])

  if (summaryQuery.isPending) {
    return <Spinner />
  }
  if (summaryQuery.isError) {
    return <ErrorAlert message={getErrorMessage(summaryQuery.error)} />
  }

  if (status === 'processing') {
    return (
      <div className="flex items-start gap-3 rounded-xl bg-slate-50 p-4">
        <Spinner />
        <div className="text-sm text-slate-600">
          <p className="font-medium text-slate-900">Reading the tender documents…</p>
          <p className="mt-0.5">
            Downloading documents and asking the AI for a summary. This usually takes under a
            minute. You can leave this page and come back.
          </p>
        </div>
      </div>
    )
  }

  if (status === 'ready' && summary?.content) {
    return (
      <div>
        <SummaryContent content={summary.content} />
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-xs text-slate-400">
          <p>
            {summary.source === 'details_only'
              ? 'Based on the tender details only: the documents could not be read (they may be scanned images).'
              : `Based on ${summary.documents.map((d) => d.title).join(', ')}${summary.truncated ? ' (key sections of long documents)' : ''}.`}{' '}
            AI-generated, so always check the official documents before bidding.
            {summary.updated_at && ` Generated ${relativeTime(summary.updated_at)}.`}
          </p>
          <button
            type="button"
            onClick={() => generate.mutate(true)}
            disabled={generate.isPending}
            className="font-medium text-slate-500 hover:text-slate-900"
          >
            Regenerate
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      {status === 'failed' && (
        <div className="mb-4">
          <ErrorAlert message={`The last attempt failed: ${summary?.error ?? 'unknown error'}`} />
        </div>
      )}
      <p className="text-sm text-slate-600">
        Get a plain-language summary of the tender documents: what's required, who can bid, key
        dates and requirements.
      </p>
      {generate.isError && (
        <div className="mt-3">
          <ErrorAlert message={getErrorMessage(generate.error)} />
        </div>
      )}
      <Button className="mt-4" isLoading={generate.isPending} onClick={() => generate.mutate(false)}>
        ✨ {status === 'failed' ? 'Try again' : 'Generate AI summary'}
      </Button>
    </div>
  )
}

function SummaryContent({ content }: { content: TenderSummaryContent }) {
  const { requirements } = content
  const keyFacts: [string, ReactNode][] = [
    ['Closing date', content.closing_date],
    ['Contract duration', content.contract_duration],
    ['Evaluation', content.evaluation],
    ['Estimated value', content.estimated_value ? formatCurrency(content.estimated_value) : null],
    [
      'CIDB grading',
      requirements.cidb.length
        ? requirements.cidb.map((c) => `${c.min_grade}${c.class_code} or higher`).join(', ')
        : null,
    ],
    ['Minimum B-BBEE level', requirements.bbbee_min_level ? `Level ${requirements.bbbee_min_level}` : null],
    [
      'Experience',
      requirements.min_years_experience ? `${requirements.min_years_experience}+ years` : null,
    ],
    [
      'Compulsory briefing',
      requirements.compulsory_briefing === null ? null : requirements.compulsory_briefing ? 'Yes' : 'No',
    ],
  ]

  return (
    <div className="space-y-6">
      <p className="text-sm leading-relaxed text-slate-800">{content.summary}</p>

      <dl className="grid gap-4 rounded-xl bg-slate-50 p-4 sm:grid-cols-2">
        {keyFacts
          .filter(([, value]) => value)
          .map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs font-medium text-slate-500">{label}</dt>
              <dd className="mt-0.5 text-sm text-slate-900">{value}</dd>
            </div>
          ))}
      </dl>

      <BulletList title="Objective" items={content.objective ? [content.objective] : []} />
      <BulletList title="Scope of work" items={content.scope} />
      <BulletList title="Eligibility" items={content.eligibility} />
      <BulletList title="Required certifications" items={requirements.certifications} />
      <BulletList title="Don't miss" items={content.other_highlights} />
    </div>
  )
}

function BulletList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h3 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}
