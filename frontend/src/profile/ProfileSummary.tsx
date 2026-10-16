import type { ReactNode } from 'react'

import type { CompanyProfile } from '../lib/types'

export function ProfileSummary({ profile }: { profile: CompanyProfile }) {
  return (
    <dl className="divide-y divide-slate-100">
      <Row label="Industry sector">{profile.industry_sector}</Row>
      <Row label="Services">
        <Tags values={profile.services} />
      </Row>
      <Row label="Years of experience">{profile.years_of_experience}</Row>
      <Row label="CIDB gradings">
        {profile.cidb_gradings.length > 0 ? (
          <Tags values={profile.cidb_gradings.map((g) => `${g.grade}${g.class_code}`)} />
        ) : (
          <Muted>Not CIDB registered</Muted>
        )}
      </Row>
      <Row label="B-BBEE level">
        {profile.bbbee_level ? `Level ${profile.bbbee_level}` : <Muted>Not rated</Muted>}
      </Row>
      <Row label="Certifications">
        {profile.certifications.length > 0 ? (
          <Tags values={profile.certifications} />
        ) : (
          <Muted>None listed</Muted>
        )}
      </Row>
      <Row label="Provinces">
        {profile.provinces.length === 9 ? 'National (all provinces)' : <Tags values={profile.provinces} />}
      </Row>
      <Row label="Contact">
        <div className="space-y-0.5">
          <p>{profile.contact_name}</p>
          <p className="text-slate-500">
            {profile.contact_email} · {profile.contact_phone}
          </p>
          {profile.website && (
            <a
              href={profile.website}
              target="_blank"
              rel="noreferrer"
              className="text-emerald-700 hover:text-emerald-800"
            >
              {profile.website}
            </a>
          )}
          {profile.physical_address && <p className="text-slate-500">{profile.physical_address}</p>}
        </div>
      </Row>
    </dl>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 py-4 text-sm sm:grid-cols-3 sm:gap-4">
      <dt className="font-medium text-slate-500">{label}</dt>
      <dd className="text-slate-900 sm:col-span-2">{children}</dd>
    </div>
  )
}

function Tags({ values }: { values: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {values.map((value) => (
        <span key={value} className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700">
          {value}
        </span>
      ))}
    </div>
  )
}

function Muted({ children }: { children: ReactNode }) {
  return <span className="text-slate-400">{children}</span>
}
