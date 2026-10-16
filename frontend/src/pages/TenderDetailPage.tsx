import type { ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ErrorAlert } from '../components/ui/Alert'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage } from '../lib/api'
import {
  deadlineLabel,
  formatCurrency,
  formatDate,
  formatDateTime,
  readableCase,
} from '../lib/format'
import { SummaryPanel } from '../summaries/SummaryPanel'
import { useTender } from '../tenders/queries'
import { SaveTenderButton } from '../workspace/SaveTenderButton'

export function TenderDetailPage() {
  const { tenderId } = useParams()
  const navigate = useNavigate()
  const tenderQuery = useTender(Number(tenderId))

  if (tenderQuery.isPending) {
    return <Spinner />
  }
  if (tenderQuery.isError) {
    return <ErrorAlert message={getErrorMessage(tenderQuery.error)} />
  }

  const tender = tenderQuery.data
  const deadline = deadlineLabel(tender.closing_at)

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/tenders'))}
        className="text-sm font-medium text-emerald-700 hover:text-emerald-800"
      >
        ← Back to results
      </button>

      <div>
        <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">
          {tender.tender_number}
        </p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
          {readableCase(tender.title)}
        </h1>
        <p className="mt-1 text-slate-600">{readableCase(tender.buyer_name)}</p>
        <div className="mt-4">
          <SaveTenderButton tenderId={tender.id} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Section title="Key details">
            <dl className="grid gap-4 sm:grid-cols-2">
              <Detail label="Closing date">
                {formatDateTime(tender.closing_at)}
                <span className="block text-xs text-slate-500">{deadline.label}</span>
              </Detail>
              <Detail label="Published">{formatDate(tender.published_at)}</Detail>
              <Detail label="Province">
                {tender.province ?? 'Not specified'}
                {tender.province_source === 'inferred' && (
                  <span className="block text-xs text-slate-500">Estimated from the description</span>
                )}
              </Detail>
              <Detail label="Estimated value">{formatCurrency(tender.estimated_value)}</Detail>
              <Detail label="Category">{tender.category ?? '—'}</Detail>
              <Detail label="Type">
                {tender.procurement_method ?? '—'}
                {tender.procurement_category && (
                  <span className="block text-xs text-slate-500 capitalize">
                    {tender.procurement_category}
                  </span>
                )}
              </Detail>
              {tender.delivery_location && (
                <Detail label="Delivery location">{tender.delivery_location}</Detail>
              )}
            </dl>
          </Section>

          {tender.briefing_session && (
            <Section title="Briefing session">
              <p className="text-sm text-slate-900">
                {tender.briefing_compulsory ? (
                  <span className="font-semibold text-amber-700">Compulsory. </span>
                ) : (
                  'Optional. '
                )}
                {formatDateTime(tender.briefing_at)}
              </p>
              {tender.briefing_venue && (
                <p className="mt-1 text-sm text-slate-600">{tender.briefing_venue}</p>
              )}
            </Section>
          )}

          {tender.special_conditions && (
            <Section title="Special conditions">
              <p className="text-sm whitespace-pre-line text-slate-700">
                {tender.special_conditions}
              </p>
            </Section>
          )}

          <Section title="AI summary">
            <SummaryPanel tenderId={tender.id} />
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Documents">
            {tender.documents.length === 0 ? (
              <p className="text-sm text-slate-500">No documents attached.</p>
            ) : (
              <ul className="space-y-2">
                {tender.documents.map((doc) => (
                  <li key={doc.url}>
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-start gap-2 text-sm text-emerald-700 hover:text-emerald-800"
                    >
                      <span className="mt-0.5 rounded bg-slate-100 px-1.5 text-xs font-semibold text-slate-600 uppercase">
                        {doc.format ?? 'file'}
                      </span>
                      <span className="break-all">{doc.title}</span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Contact">
            {tender.contact_person || tender.contact_email || tender.contact_phone ? (
              <div className="space-y-1 text-sm">
                {tender.contact_person && <p className="text-slate-900">{tender.contact_person}</p>}
                {tender.contact_email && (
                  <a
                    href={`mailto:${tender.contact_email}`}
                    className="block text-emerald-700 hover:text-emerald-800"
                  >
                    {tender.contact_email}
                  </a>
                )}
                {tender.contact_phone && <p className="text-slate-600">{tender.contact_phone}</p>}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No contact details published.</p>
            )}
          </Section>

          <a
            href="https://www.etenders.gov.za/Home/opportunities"
            target="_blank"
            rel="noreferrer"
            className="block text-sm font-medium text-slate-600 hover:text-slate-900"
          >
            Find on the eTenders portal ↗
            <span className="block text-xs font-normal text-slate-500">
              Search for reference {tender.tender_number}
            </span>
          </a>
          <Link to="/tenders" className="block text-sm font-medium text-slate-600 hover:text-slate-900">
            New search
          </Link>
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-sm font-semibold text-slate-500">{title}</h2>
      {children}
    </section>
  )
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-900">{children}</dd>
    </div>
  )
}
