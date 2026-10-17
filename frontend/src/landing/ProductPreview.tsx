import {
  LuCalendar,
  LuCheck,
  LuCircleHelp,
  LuCircleMinus,
  LuMapPin,
  LuRefreshCw,
  LuSparkles,
} from 'react-icons/lu'

const CHECKLIST = [
  { label: 'CIDB grade 6 CE or higher', icon: LuCheck, tone: 'bg-emerald-100 text-emerald-700' },
  { label: 'Operates in Limpopo', icon: LuCheck, tone: 'bg-emerald-100 text-emerald-700' },
  { label: 'B-BBEE level 1 to 2', icon: LuCircleMinus, tone: 'bg-amber-100 text-amber-700' },
  { label: 'Compulsory site briefing', icon: LuCircleHelp, tone: 'bg-slate-200 text-slate-600' },
]

/** A static, illustrative mock-up of the app used in the landing page hero. */
export function ProductPreview() {
  return (
    <div className="relative">
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-white shadow-2xl shadow-emerald-950/40 ring-1 ring-black/5">
        <div className="flex items-center gap-2 border-b border-slate-100 bg-slate-50 px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
          <span className="ml-3 truncate rounded-md bg-white px-3 py-1 text-xs text-slate-400 ring-1 ring-slate-200">
            Tender Insight Hub · Workspace
          </span>
        </div>

        <div className="space-y-4 p-5 sm:p-6 sm:pb-14">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
                RFB 2026/041
              </p>
              <p className="mt-1 font-semibold text-slate-900">Resurfacing of municipal roads</p>
              <p className="text-sm text-slate-500">Polokwane Local Municipality</p>
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500">
                <span className="inline-flex items-center gap-1">
                  <LuMapPin aria-hidden="true" /> Limpopo
                </span>
                <span className="inline-flex items-center gap-1">
                  <LuCalendar aria-hidden="true" /> Closes in 9 days
                </span>
              </div>
            </div>
            <ScoreRing score={86} />
          </div>

          <div className="rounded-xl bg-emerald-50/70 p-4 ring-1 ring-emerald-100">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-emerald-800">
              <LuSparkles aria-hidden="true" /> AI summary
            </p>
            <p className="mt-1.5 text-sm text-slate-700">
              Rehabilitation of 4.2 km of surfaced roads, including drainage and road markings.
              Contractors need CIDB 6 CE and must attend a site briefing.
            </p>
          </div>

          <ul className="space-y-2">
            {CHECKLIST.map((item) => (
              <li key={item.label} className="flex items-center gap-2.5 text-sm text-slate-700">
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${item.tone}`}
                >
                  <item.icon className="h-3 w-3" aria-hidden="true" />
                </span>
                {item.label}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="absolute -bottom-6 -left-4 hidden w-64 items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-xl sm:flex lg:-left-10">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
          <LuRefreshCw className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900">Moved to Preparing</p>
          <p className="truncate text-xs text-slate-500">Lerato updated the bid status</p>
        </div>
      </div>
    </div>
  )
}

function ScoreRing({ score }: { score: number }) {
  const radius = 26
  const circumference = 2 * Math.PI * radius
  return (
    <div className="relative flex h-16 w-16 shrink-0 items-center justify-center">
      <svg viewBox="0 0 64 64" className="absolute inset-0 -rotate-90" aria-hidden="true">
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="6"
          className="stroke-slate-100"
        />
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score / 100)}
          className="stroke-emerald-500"
        />
      </svg>
      <span className="text-center leading-none">
        <span className="block text-lg font-bold text-slate-900">{score}</span>
        <span className="block text-[9px] font-medium text-slate-400 uppercase">match</span>
      </span>
    </div>
  )
}
