import type { ReactNode } from 'react'

import { ApiStatus } from './ApiStatus'

type AuthLayoutProps = {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        <p className="text-center text-sm font-semibold tracking-wide text-emerald-700 uppercase">
          Tender Insight Hub
        </p>
        <h1 className="mt-2 text-center text-2xl font-bold tracking-tight text-slate-900">
          {title}
        </h1>
        <p className="mt-2 text-center text-sm text-slate-600">{subtitle}</p>

        <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          {children}
        </div>

        <p className="mt-6 text-center text-sm text-slate-600">{footer}</p>
        <div className="mt-8 flex justify-center">
          <ApiStatus />
        </div>
      </div>
    </main>
  )
}
