import { type FormEvent, useState } from 'react'

import { Button } from '../components/ui/Button'
import { TextField } from '../components/ui/TextField'
import { isoDate } from '../lib/format'
import { BuyerPicker } from './BuyerPicker'
import type { TenderQuery } from './searchParams'

const PROVINCE_OPTIONS = [
  'Eastern Cape',
  'Free State',
  'Gauteng',
  'KwaZulu-Natal',
  'Limpopo',
  'Mpumalanga',
  'Northern Cape',
  'North West',
  'Western Cape',
  'National',
]

const DEADLINE_WINDOWS = [
  { days: 7, label: 'Next 7 days' },
  { days: 14, label: 'Next 14 days' },
  { days: 30, label: 'Next 30 days' },
]

type Filters = Pick<
  TenderQuery,
  'provinces' | 'buyers' | 'closingFrom' | 'closingTo' | 'minValue' | 'maxValue'
>

type FilterPanelProps = {
  query: TenderQuery
  provinceCounts: Record<string, number>
  onApply: (filters: Filters) => void
}

/** Closing-date range from today to `days` days ahead. */
function deadlineRange(days: number): Pick<Filters, 'closingFrom' | 'closingTo'> {
  const today = new Date()
  const end = new Date(today)
  end.setDate(today.getDate() + days)
  return { closingFrom: isoDate(today), closingTo: isoDate(end) }
}

const noFilters: Filters = {
  provinces: [],
  buyers: [],
  closingFrom: '',
  closingTo: '',
  minValue: '',
  maxValue: '',
}

/**
 * Filters are edited as a draft and only take effect when the user clicks "Apply",
 * so the result list doesn't jump around while choosing several options.
 */
export function FilterPanel({ query, provinceCounts, onApply }: FilterPanelProps) {
  const [draft, setDraft] = useState<Filters>(() => ({
    provinces: query.provinces,
    buyers: query.buyers,
    closingFrom: query.closingFrom,
    closingTo: query.closingTo,
    minValue: query.minValue,
    maxValue: query.maxValue,
  }))

  function update<K extends keyof Filters>(field: K, value: Filters[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  function toggleProvince(province: string) {
    update(
      'provinces',
      draft.provinces.includes(province)
        ? draft.provinces.filter((p) => p !== province)
        : [...draft.provinces, province],
    )
  }

  function setDeadlineWindow(days: number) {
    setDraft((current) => ({ ...current, ...deadlineRange(days) }))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onApply(draft)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Province</legend>
        <div className="mt-2 space-y-1">
          {PROVINCE_OPTIONS.map((province) => (
            <label
              key={province}
              className="flex cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-1 text-sm text-slate-700 hover:bg-slate-50"
            >
              <span className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={draft.provinces.includes(province)}
                  onChange={() => toggleProvince(province)}
                  className="h-4 w-4 rounded border-slate-300 accent-emerald-600"
                />
                {province}
              </span>
              <span className="text-xs text-slate-400">{provinceCounts[province] ?? 0}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Submission deadline</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {DEADLINE_WINDOWS.map((window) => (
            <button
              key={window.days}
              type="button"
              onClick={() => setDeadlineWindow(window.days)}
              className="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:border-emerald-600 hover:text-emerald-700"
            >
              {window.label}
            </button>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <TextField
            label="From"
            type="date"
            value={draft.closingFrom}
            onChange={(e) => update('closingFrom', e.target.value)}
          />
          <TextField
            label="To"
            type="date"
            min={draft.closingFrom || undefined}
            value={draft.closingTo}
            onChange={(e) => update('closingTo', e.target.value)}
          />
        </div>
      </fieldset>

      <BuyerPicker selected={draft.buyers} onChange={(buyers) => update('buyers', buyers)} />

      <fieldset>
        <legend className="text-sm font-medium text-slate-700">Budget range (ZAR)</legend>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <TextField
            label="Min"
            type="number"
            min={0}
            step={1000}
            value={draft.minValue}
            onChange={(e) => update('minValue', e.target.value)}
          />
          <TextField
            label="Max"
            type="number"
            min={0}
            step={1000}
            value={draft.maxValue}
            onChange={(e) => update('maxValue', e.target.value)}
          />
        </div>
        <p className="mt-1 text-xs text-slate-500">
          Most government tenders don't publish a budget, so this only matches tenders with a known
          value.
        </p>
      </fieldset>

      <div className="flex gap-2">
        <Button type="submit" className="flex-1">
          Apply filters
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            setDraft(noFilters)
            onApply(noFilters)
          }}
        >
          Clear
        </Button>
      </div>
    </form>
  )
}
