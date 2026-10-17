import { LuRadar } from 'react-icons/lu'

type LogoProps = {
  tone?: 'dark' | 'light'
  className?: string
  nameClassName?: string
}

export function Logo({ tone = 'dark', className = '', nameClassName = '' }: LogoProps) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-2.5 ${className}`}>
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-linear-to-br from-emerald-500 to-teal-600 text-white shadow-sm shadow-emerald-600/30">
        <LuRadar className="h-4.5 w-4.5" aria-hidden="true" />
      </span>
      <span
        className={`font-semibold tracking-tight whitespace-nowrap ${
          tone === 'light' ? 'text-white' : 'text-slate-900'
        } ${nameClassName}`}
      >
        Tender Insight Hub
      </span>
    </span>
  )
}
