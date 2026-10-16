import { type KeyboardEvent, useId, useState } from 'react'

type TagInputProps = {
  label: string
  values: string[]
  onChange: (values: string[]) => void
  placeholder?: string
  hint?: string
}

/** Text input that turns each entry into a removable tag (press Enter or comma to add). */
export function TagInput({ label, values, onChange, placeholder, hint }: TagInputProps) {
  const id = useId()
  const [draft, setDraft] = useState('')

  function addDraft() {
    const value = draft.trim()
    const exists = values.some((v) => v.toLowerCase() === value.toLowerCase())
    if (value.length >= 2 && !exists) {
      onChange([...values, value])
    }
    setDraft('')
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      addDraft()
    } else if (event.key === 'Backspace' && draft === '' && values.length > 0) {
      onChange(values.slice(0, -1))
    }
  }

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="mt-1 flex flex-wrap gap-2 rounded-lg border border-slate-300 bg-white p-2 shadow-sm focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20">
        {values.map((value) => (
          <span
            key={value}
            className="inline-flex items-center gap-1 rounded-full bg-emerald-50 py-1 pr-1.5 pl-3 text-sm text-emerald-800"
          >
            {value}
            <button
              type="button"
              onClick={() => onChange(values.filter((v) => v !== value))}
              className="rounded-full px-1 text-emerald-600 hover:bg-emerald-100 hover:text-emerald-900"
              aria-label={`Remove ${value}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          id={id}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={addDraft}
          placeholder={values.length === 0 ? placeholder : ''}
          className="min-w-[10rem] flex-1 border-0 px-1 py-1 text-slate-900 placeholder:text-slate-400 focus:ring-0 focus:outline-none"
        />
      </div>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}
