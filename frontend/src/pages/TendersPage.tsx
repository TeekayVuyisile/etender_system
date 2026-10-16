import { type FormEvent, useState } from 'react'
import { useSearchParams } from 'react-router'

import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Pagination } from '../components/ui/Pagination'
import { Spinner } from '../components/ui/Spinner'
import { getErrorMessage, isUpgradeRequired } from '../lib/api'
import { SearchAllowance } from '../plans/SearchAllowance'
import { UpgradePrompt } from '../plans/UpgradePrompt'
import { FilterPanel } from '../tenders/FilterPanel'
import { useTenderSearch } from '../tenders/queries'
import {
  countActiveFilters,
  PAGE_SIZE,
  readTenderQuery,
  type TenderQuery,
  type TenderSort,
  toSearchParams,
} from '../tenders/searchParams'
import { TenderCard } from '../tenders/TenderCard'

const SORT_OPTIONS: { value: TenderSort; label: string }[] = [
  { value: 'relevance', label: 'Best match' },
  { value: 'closing_soon', label: 'Closing soonest' },
  { value: 'newest', label: 'Newest' },
]

export function TendersPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const query = readTenderQuery(searchParams)
  // Results (and the filter panel) only appear once the user has run a search.
  const hasSearched = searchParams.size > 0
  const searchQuery = useTenderSearch(query, hasSearched)
  const [keywords, setKeywords] = useState(query.q)

  function updateQuery(changes: Partial<TenderQuery>) {
    setSearchParams(toSearchParams({ ...query, page: 1, ...changes }))
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    updateQuery({ q: keywords.trim() })
  }

  const activeFilters = countActiveFilters(query)
  const data = searchQuery.data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Find tenders</h1>
        <p className="mt-1 text-slate-600">
          Search open government tenders from the eTenders portal.
        </p>
      </div>

      <SearchAllowance />

      <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="tender-search" className="sr-only">
          Search tenders
        </label>
        <input
          id="tender-search"
          type="search"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder='Try "road construction" or "security services"'
          className="block w-full flex-1 rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 focus:outline-none"
        />
        <Button type="submit" className="px-6 py-3">
          Search
        </Button>
      </form>

      {!hasSearched ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="text-slate-600">Enter keywords above to search open tenders.</p>
          <button
            type="button"
            onClick={() => updateQuery({ sort: 'closing_soon' })}
            className="mt-3 text-sm font-semibold text-emerald-700 hover:text-emerald-800"
          >
            Or browse all open tenders →
          </button>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-4">
          <aside className="lg:col-span-1">
            <details
              className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:open:block"
              open
            >
              <summary className="flex cursor-pointer list-none items-center justify-between font-semibold text-slate-900">
                Filters{activeFilters > 0 && ` (${activeFilters})`}
                <span className="text-slate-400 group-open:rotate-180 lg:hidden">⌄</span>
              </summary>
              <div className="mt-4">
                {/* Re-create the panel when the URL changes so its draft matches. */}
                <FilterPanel
                  key={searchParams.toString()}
                  query={query}
                  provinceCounts={data?.province_counts ?? {}}
                  onApply={(filters) => updateQuery(filters)}
                />
              </div>
            </details>
          </aside>

          <section className="space-y-4 lg:col-span-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-slate-600" aria-live="polite">
                {data ? (
                  <>
                    <span className="font-semibold text-slate-900">
                      {data.total.toLocaleString()}
                    </span>{' '}
                    open tender{data.total === 1 ? '' : 's'}
                    {query.q && (
                      <>
                        {' '}
                        matching “<span className="font-medium">{query.q}</span>”
                      </>
                    )}
                  </>
                ) : searchQuery.isError ? null : (
                  'Searching…'
                )}
              </p>
              <label className="flex items-center gap-2 text-sm text-slate-600">
                Sort by
                <select
                  value={query.sort}
                  onChange={(e) => updateQuery({ sort: e.target.value as TenderSort })}
                  className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900"
                >
                  {SORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {searchQuery.isError &&
              (isUpgradeRequired(searchQuery.error) ? (
                <UpgradePrompt
                  message={searchQuery.error.message}
                  requiredPlan={searchQuery.error.requiredPlan}
                />
              ) : (
                <ErrorAlert message={getErrorMessage(searchQuery.error)} />
              ))}
            {searchQuery.isPending && <Spinner />}

            {data && data.items.length === 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-600">
                No open tenders match your search. Try fewer keywords or clear some filters.
              </div>
            )}

            <div className={`space-y-3 ${searchQuery.isPlaceholderData ? 'opacity-60' : ''}`}>
              {data?.items.map((tender) => (
                <TenderCard key={tender.id} tender={tender} />
              ))}
            </div>

            {data && (
              <Pagination
                page={query.page}
                pageSize={PAGE_SIZE}
                total={data.total}
                onPageChange={(page) => {
                  setSearchParams(toSearchParams({ ...query, page }))
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              />
            )}
          </section>
        </div>
      )}
    </div>
  )
}
