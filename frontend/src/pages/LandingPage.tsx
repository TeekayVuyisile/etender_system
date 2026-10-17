import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import type { IconType } from 'react-icons'
import {
  LuArrowRight,
  LuBellRing,
  LuBuilding2,
  LuCheck,
  LuChevronDown,
  LuCode,
  LuFolderKanban,
  LuMenu,
  LuPlay,
  LuSearch,
  LuSparkles,
  LuTarget,
  LuX,
} from 'react-icons/lu'
import { Link } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { Logo } from '../components/Logo'
import { getErrorMessage } from '../lib/api'
import { useHealth } from '../lib/health'
import { ProductPreview } from '../landing/ProductPreview'

const NAV_LINKS = [
  { href: '#features', label: 'Features' },
  { href: '#how-it-works', label: 'How it works' },
  { href: '#pricing', label: 'Pricing' },
  { href: '#developers', label: 'Developers' },
]

const FEATURES: { icon: IconType; title: string; description: string }[] = [
  {
    icon: LuSearch,
    title: 'Search every open tender',
    description:
      'Tenders are synced from the National Treasury eTenders portal, with full-text search and filters for province, buyer, category and closing date.',
  },
  {
    icon: LuSparkles,
    title: 'AI document summaries',
    description:
      'Turn a 60-page bid document into a one-minute read: scope, key dates, CIDB grades, B-BBEE and compliance requirements.',
  },
  {
    icon: LuTarget,
    title: 'Match This Tender',
    description:
      'A 0 to 100 readiness score with a checklist that compares the requirements against your company profile, so you only bid where you can win.',
  },
  {
    icon: LuFolderKanban,
    title: 'Shared team workspace',
    description:
      'Save tenders, move them from Interested to Submitted, and keep notes and assigned tasks in one place your whole team can see.',
  },
  {
    icon: LuBellRing,
    title: 'Deadline reminders',
    description:
      'In-app notifications for closing dates, compulsory briefings, task assignments and status changes, so nothing slips.',
  },
  {
    icon: LuCode,
    title: 'Public REST API',
    description:
      'Pull enriched tender data, spend analytics and readiness checks into your own tools with an API key.',
  },
]

const STEPS = [
  {
    title: 'Create your company profile',
    description:
      'Tell us your industry, provinces, CIDB grades and B-BBEE level. It takes two minutes.',
  },
  {
    title: 'Find relevant tenders',
    description: 'Search the latest public tenders and save the promising ones to your workspace.',
  },
  {
    title: 'Assess, plan and bid',
    description:
      'Read the AI summary, check your match score, then split the work across your team.',
  },
]

const PLANS = [
  {
    name: 'Free',
    price: 'R0',
    period: 'forever',
    description: 'For trying things out on your own.',
    features: ['1 team member', '3 tender searches per week', 'Team workspace, notes and tasks'],
    highlighted: false,
  },
  {
    name: 'Basic',
    price: 'R499',
    period: 'per month',
    description: 'For small teams bidding regularly.',
    features: [
      'Up to 3 team members',
      'Unlimited tender searches',
      'AI summaries of tender documents',
      'Match This Tender readiness scoring',
    ],
    highlighted: true,
  },
  {
    name: 'Pro',
    price: 'R1,499',
    period: 'per month',
    description: 'For established bid teams.',
    features: ['Unlimited team members', 'Everything in Basic', 'CSV and PDF workspace reports'],
    highlighted: false,
  },
]

const FAQS = [
  {
    question: 'Where does the tender data come from?',
    answer:
      'From the National Treasury eTenders portal through its public Open Contracting (OCDS) API. New tenders are synced automatically throughout the day.',
  },
  {
    question: 'How accurate are the AI summaries?',
    answer:
      'Summaries are generated from the official tender documents and are a fast way to decide whether a tender is worth your time. Always confirm the details in the original documents before you submit a bid.',
  },
  {
    question: 'How is the match score calculated?',
    answer:
      'It is rule-based, not a black box. Each requirement (CIDB grade, province, B-BBEE level, briefing and more) is checked against your company profile and weighted, and you can see every point in the checklist.',
  },
  {
    question: 'Can I try it without signing up?',
    answer:
      'Yes. The live demo gives you a private, pre-filled workspace with real tenders, AI summaries and match scores. It resets after 24 hours.',
  },
]

const API_SNIPPET = `curl -G "$TIH_URL/api/enriched-releases" \\
  -d province=Gauteng -d q=security \\
  -H "X-API-Key: tih_..."`

export function LandingPage() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      <SiteHeader />
      <main>
        <Hero />
        <Features />
        <HowItWorks />
        <Pricing />
        <Developers />
        <Faq />
        <FinalCta />
      </main>
      <SiteFooter />
    </div>
  )
}

function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/90 backdrop-blur-lg">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-4 py-3.5 sm:px-6">
        <Link to="/" aria-label="Tender Insight Hub home">
          <Logo tone="light" />
        </Link>
        <nav className="hidden items-center gap-8 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-slate-300 transition-colors hover:text-white"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <div className="hidden items-center gap-3 md:flex">
          <Link to="/login" className="text-sm font-semibold text-slate-200 hover:text-white">
            Sign in
          </Link>
          <Link
            to="/register"
            className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-sm transition-colors hover:bg-emerald-400"
          >
            Get started
          </Link>
        </div>
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          className="rounded-lg p-2 text-slate-200 hover:bg-white/10 md:hidden"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
        >
          {menuOpen ? <LuX className="h-5 w-5" /> : <LuMenu className="h-5 w-5" />}
        </button>
      </div>
      {menuOpen && (
        <nav className="border-t border-white/10 px-4 pt-2 pb-4 md:hidden">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className="block rounded-lg px-3 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/5"
            >
              {link.label}
            </a>
          ))}
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Link
              to="/login"
              className="rounded-lg border border-white/15 px-4 py-2.5 text-center text-sm font-semibold text-white"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              className="rounded-lg bg-emerald-500 px-4 py-2.5 text-center text-sm font-semibold text-slate-950"
            >
              Get started
            </Link>
          </div>
        </nav>
      )}
    </header>
  )
}

function Hero() {
  return (
    <section className="relative isolate overflow-hidden bg-slate-950 pb-24 sm:pb-32">
      <div
        className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,rgba(16,185,129,0.25),transparent_60%)]"
        aria-hidden="true"
      />
      <div
        className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.04)_1px,transparent_1px)] mask-[radial-gradient(ellipse_at_center,black_30%,transparent_75%)] bg-size-[48px_48px]"
        aria-hidden="true"
      />

      <div className="mx-auto grid max-w-6xl items-center gap-16 px-4 pt-16 sm:px-6 sm:pt-24 lg:grid-cols-2 lg:gap-12">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Live data from the National Treasury eTenders portal
          </p>
          <h1 className="mt-6 text-4xl font-bold tracking-tight text-balance text-white sm:text-5xl lg:text-6xl">
            Win more public tenders with{' '}
            <span className="bg-linear-to-r from-emerald-300 to-teal-300 bg-clip-text text-transparent">
              less paperwork
            </span>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-pretty text-slate-300">
            Tender Insight Hub finds the government tenders that fit your business, summarises the
            bid documents with AI and scores how ready you are to win, so your team spends its time
            on bids worth making.
          </p>
          <HeroActions />
          <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-400">
            {['Free plan available', 'No credit card needed', 'Built for South African SMEs'].map(
              (item) => (
                <li key={item} className="inline-flex items-center gap-1.5">
                  <LuCheck className="text-emerald-400" aria-hidden="true" />
                  {item}
                </li>
              ),
            )}
          </ul>
        </div>
        <ProductPreview />
      </div>
    </section>
  )
}

function HeroActions() {
  const { startDemo } = useAuth()
  const health = useHealth()
  const demo = useMutation({ mutationFn: startDemo })

  return (
    <div className="mt-10">
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          to="/register"
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-6 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-emerald-500/20 transition-colors hover:bg-emerald-400"
        >
          Get started free <LuArrowRight aria-hidden="true" />
        </Link>
        {health.data?.demo_mode ? (
          <button
            type="button"
            onClick={() => demo.mutate()}
            disabled={demo.isPending}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/15 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10 disabled:opacity-60"
          >
            <LuPlay aria-hidden="true" />
            {demo.isPending ? 'Setting up your demo…' : 'Try the live demo'}
          </button>
        ) : (
          <Link
            to="/login"
            className="inline-flex items-center justify-center rounded-lg border border-white/15 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/10"
          >
            Sign in
          </Link>
        )}
      </div>
      {demo.isError && <p className="mt-3 text-sm text-red-300">{getErrorMessage(demo.error)}</p>}
    </div>
  )
}

function SectionHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-sm font-semibold text-emerald-600">{eyebrow}</p>
      <h2 className="mt-2 text-3xl font-bold tracking-tight text-balance text-slate-900 sm:text-4xl">
        {title}
      </h2>
      <p className="mt-4 text-lg text-pretty text-slate-600">{description}</p>
    </div>
  )
}

function Features() {
  return (
    <section id="features" className="scroll-mt-20 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="Everything in one place"
          title="From the tender notice to the submitted bid"
          description="Stop refreshing the eTenders portal and reading every document front to back. Focus on the tenders you can actually win."
        />
        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="group rounded-2xl border border-slate-200 bg-white p-6 transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-lg hover:shadow-emerald-900/5"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 ring-1 ring-emerald-100 transition-colors group-hover:bg-emerald-600 group-hover:text-white">
                <feature.icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-5 font-semibold text-slate-900">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 bg-slate-50 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="How it works"
          title="Up and running in minutes"
          description="No setup, no spreadsheets. Your company profile does the filtering for you."
        />
        <ol className="mt-16 grid gap-8 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="relative">
              {index < STEPS.length - 1 && (
                <span
                  className="absolute top-6 left-14 hidden h-px w-[calc(100%-3.5rem)] bg-linear-to-r from-emerald-300 to-transparent md:block"
                  aria-hidden="true"
                />
              )}
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600 text-lg font-bold text-white shadow-lg shadow-emerald-600/20">
                {index + 1}
              </span>
              <h3 className="mt-6 text-lg font-semibold text-slate-900">{step.title}</h3>
              <p className="mt-2 text-slate-600">{step.description}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

function Pricing() {
  return (
    <section id="pricing" className="scroll-mt-20 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="Pricing"
          title="Simple plans that grow with your team"
          description="Start for free and upgrade when you need AI summaries, readiness scoring and reports."
        />
        <div className="mt-16 grid gap-6 lg:grid-cols-3">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`relative flex flex-col rounded-2xl p-8 ${
                plan.highlighted
                  ? 'bg-slate-950 text-white shadow-2xl shadow-emerald-900/20 ring-2 ring-emerald-500'
                  : 'border border-slate-200 bg-white'
              }`}
            >
              {plan.highlighted && (
                <span className="absolute -top-3 left-8 rounded-full bg-emerald-500 px-3 py-1 text-xs font-semibold text-slate-950">
                  Most popular
                </span>
              )}
              <h3 className="text-lg font-semibold">{plan.name}</h3>
              <p
                className={`mt-1 text-sm ${plan.highlighted ? 'text-slate-400' : 'text-slate-500'}`}
              >
                {plan.description}
              </p>
              <p className="mt-6 flex items-baseline gap-1.5">
                <span className="text-4xl font-bold tracking-tight">{plan.price}</span>
                <span className={plan.highlighted ? 'text-slate-400' : 'text-slate-500'}>
                  {plan.period}
                </span>
              </p>
              <ul className="mt-8 flex-1 space-y-3 text-sm">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2.5">
                    <LuCheck
                      className={`mt-0.5 shrink-0 ${plan.highlighted ? 'text-emerald-400' : 'text-emerald-600'}`}
                      aria-hidden="true"
                    />
                    <span className={plan.highlighted ? 'text-slate-200' : 'text-slate-700'}>
                      {feature}
                    </span>
                  </li>
                ))}
              </ul>
              <Link
                to="/register"
                className={`mt-8 rounded-lg px-4 py-2.5 text-center text-sm font-semibold transition-colors ${
                  plan.highlighted
                    ? 'bg-emerald-500 text-slate-950 hover:bg-emerald-400'
                    : 'border border-slate-300 text-slate-900 hover:bg-slate-50'
                }`}
              >
                {plan.name === 'Free' ? 'Start for free' : `Choose ${plan.name}`}
              </Link>
            </div>
          ))}
        </div>
        <p className="mt-8 text-center text-sm text-slate-500">
          Every account starts on Free. This is a portfolio project, so billing is simulated and no
          payment is taken.
        </p>
      </div>
    </section>
  )
}

function Developers() {
  return (
    <section id="developers" className="scroll-mt-20 bg-slate-950 py-24 sm:py-32">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 sm:px-6 lg:grid-cols-2">
        <div>
          <p className="text-sm font-semibold text-emerald-400">For developers</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Tender data, enriched and ready to use
          </h2>
          <p className="mt-4 text-lg text-slate-300">
            The same data that powers the app is available through a documented REST API, with AI
            summaries, readiness checks and spend analytics by buyer.
          </p>
          <ul className="mt-8 space-y-3 text-slate-300">
            {[
              'API keys managed by your team, sent as an X-API-Key header',
              'OpenAPI documentation you can try in the browser',
              'Rate limited to 60 requests per minute per key',
            ].map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <LuCheck className="mt-1 shrink-0 text-emerald-400" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900 shadow-2xl">
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
            <LuCode className="text-emerald-400" aria-hidden="true" />
            <span className="text-xs font-medium text-slate-400">Request</span>
          </div>
          <pre className="overflow-x-auto p-5 text-sm leading-relaxed text-emerald-200">
            <code>{API_SNIPPET}</code>
          </pre>
        </div>
      </div>
    </section>
  )
}

function Faq() {
  return (
    <section className="py-24 sm:py-32">
      <div className="mx-auto max-w-3xl px-4 sm:px-6">
        <SectionHeading
          eyebrow="FAQ"
          title="Questions, answered"
          description="Everything you need to know before you start."
        />
        <div className="mt-12 divide-y divide-slate-200 rounded-2xl border border-slate-200">
          {FAQS.map((faq) => (
            <details key={faq.question} className="group px-6 py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-slate-900">
                {faq.question}
                <LuChevronDown
                  className="shrink-0 text-slate-400 transition-transform group-open:rotate-180"
                  aria-hidden="true"
                />
              </summary>
              <p className="mt-3 leading-relaxed text-slate-600">{faq.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}

function FinalCta() {
  return (
    <section className="px-4 pb-24 sm:px-6 sm:pb-32">
      <div className="relative isolate mx-auto max-w-6xl overflow-hidden rounded-3xl bg-linear-to-br from-emerald-600 to-teal-700 px-6 py-16 text-center sm:px-12">
        <div
          className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.18),transparent_50%)]"
          aria-hidden="true"
        />
        <LuBuilding2 className="mx-auto h-10 w-10 text-emerald-100" aria-hidden="true" />
        <h2 className="mt-6 text-3xl font-bold tracking-tight text-balance text-white sm:text-4xl">
          Your next contract is already out there
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-emerald-50">
          Create a free account and see which open tenders match your business today.
        </p>
        <Link
          to="/register"
          className="mt-10 inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3 text-sm font-semibold text-emerald-700 shadow-lg transition-colors hover:bg-emerald-50"
        >
          Get started free <LuArrowRight aria-hidden="true" />
        </Link>
      </div>
    </section>
  )
}

function SiteFooter() {
  return (
    <footer className="border-t border-slate-200">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <Logo />
          <p className="mt-3 text-sm text-slate-500">
            Tender data from the National Treasury eTenders portal (OCDS).
          </p>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="hover:text-slate-900">
              {link.label}
            </a>
          ))}
          <Link to="/login" className="hover:text-slate-900">
            Sign in
          </Link>
        </nav>
      </div>
    </footer>
  )
}
