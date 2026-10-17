import type { ReactNode } from 'react'
import { LuBellRing, LuSparkles, LuTarget } from 'react-icons/lu'
import { Link } from 'react-router'

import { ApiStatus } from './ApiStatus'
import { Logo } from './Logo'

type AuthLayoutProps = {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
}

const HIGHLIGHTS = [
  { icon: LuSparkles, text: 'AI summaries of every bid document' },
  { icon: LuTarget, text: 'A readiness score for each tender' },
  { icon: LuBellRing, text: 'Reminders before deadlines and briefings' },
]

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <main className="flex flex-col bg-white px-4 py-8 sm:px-6">
        <Link to="/" className="self-start" aria-label="Tender Insight Hub home">
          <Logo />
        </Link>

        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-12">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{title}</h1>
          <p className="mt-2 text-slate-600">{subtitle}</p>

          <div className="mt-8">{children}</div>

          <p className="mt-8 text-sm text-slate-600">{footer}</p>
        </div>

        <div className="flex justify-center">
          <ApiStatus />
        </div>
      </main>

      <aside className="relative isolate hidden overflow-hidden bg-slate-950 lg:flex lg:flex-col lg:justify-center lg:px-16">
        <div
          className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top_right,rgba(16,185,129,0.3),transparent_60%)]"
          aria-hidden="true"
        />
        <div className="max-w-md">
          <p className="text-3xl font-bold tracking-tight text-balance text-white">
            Spend your time on the bids you can win.
          </p>
          <p className="mt-4 text-slate-300">
            Public tenders from the eTenders portal, filtered for your business and assessed by your
            whole team in one shared workspace.
          </p>
          <ul className="mt-10 space-y-4">
            {HIGHLIGHTS.map((item) => (
              <li key={item.text} className="flex items-center gap-3 text-slate-200">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-300 ring-1 ring-emerald-400/20">
                  <item.icon className="h-4.5 w-4.5" aria-hidden="true" />
                </span>
                {item.text}
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  )
}
