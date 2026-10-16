import { useId, useState } from 'react'

import { readableCase } from '../lib/format'
import { useBuyerSearch } from './queries'

type BuyerPickerProps = {
  selected: string[]
  onChange: (buyers: string[]) => void
}

/** Search-as-you-type picker for buyers (organs of state) with open tenders. */
export function BuyerPicker({ selected, onChange }: BuyerPickerProps) {
  const id = useId()
  const [search, setSearch] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const buyersQuery = useBuyerSearch(search.trim())
  const options = (buyersQuery.data ?? []).filter((b) => !selected.includes(b.name))

  function add(name: string) {
    onChange([...selected, name])
    setSearch('')
    setIsOpen(false)
  }

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        Buyer (organ of state)
      </label>
      {selected.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {selected.map((name) => (
            <span
              key={name}
              className="inline-flex items-center gap-1 rounded-full bg-emerald-50 py-0.5 pr-1 pl-2.5 text-xs text-emerald-800"
            >
              {readableCase(name)}
              <button
                type="button"
                onClick={() => onChange(selected.filter((s) => s !== name))}
                className="rounded-full px-1 hover:bg-emerald-100"
                aria-label={`Remove ${name}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="relative mt-2">
        <input
          id={id}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setIsOpen(true)
          }}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setTimeout(() => setIsOpen(false), 150)}
          placeholder="Search buyers…"
          autoComplete="off"
          className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 focus:outline-none"
        />
        {isOpen && options.length > 0 && (
          <ul className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            {options.map((buyer) => (
              <li key={buyer.name}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => add(buyer.name)}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
                >
                  <span className="truncate">{readableCase(buyer.name)}</span>
                  <span className="shrink-0 text-xs text-slate-400">{buyer.open_tenders}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
