import { Link } from 'react-router'

import { deadlineLabel, formatDate, readableCase, type Urgency } from '../lib/format'
import type { TenderListItem } from '../lib/types'
import { SaveTenderButton } from '../workspace/SaveTenderButton'

const urgencyStyles: Record<Urgency, string> = {
  closed: 'bg-slate-100 text-slate-500',
  urgent: 'bg-red-50 text-red-700',
  soon: 'bg-amber-50 text-amber-700',
  normal: 'bg-emerald-50 text-emerald-700',
}

export function TenderCard({ tender }: { tender: TenderListItem }) {
  const deadline = deadlineLabel(tender.closing_at)

  return (
    <article className="relative rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-emerald-300 hover:shadow">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">
          {tender.tender_number}
        </p>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${urgencyStyles[deadline.urgency]}`}
        >
          {deadline.label}
        </span>
      </div>

      <h2 className="mt-2 text-base font-semibold text-slate-900">
        <Link
          to={`/tenders/${tender.id}`}
          className="after:absolute after:inset-0 hover:text-emerald-700 focus:outline-none"
        >
          {readableCase(tender.title)}
        </Link>
      </h2>
      <p className="mt-1 text-sm text-slate-600">{readableCase(tender.buyer_name)}</p>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
        <div className="flex min-w-0 flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>📍 {tender.province ?? 'Province not specified'}</span>
        <span>🗓 Closes {formatDate(tender.closing_at)}</span>
        {tender.category && <span className="max-w-xs truncate">🏷 {tender.category}</span>}
        {tender.document_count > 0 && (
          <span>
            📄 {tender.document_count} document{tender.document_count === 1 ? '' : 's'}
          </span>
        )}
        {tender.briefing_compulsory && (
          <span className="font-medium text-amber-700">Compulsory briefing</span>
        )}
        </div>
        <SaveTenderButton tenderId={tender.id} size="sm" />
      </div>
    </article>
  )
}
