type CheckboxGroupProps = {
  legend: string
  options: string[]
  selected: string[]
  onChange: (selected: string[]) => void
  showSelectAll?: boolean
}

export function CheckboxGroup({
  legend,
  options,
  selected,
  onChange,
  showSelectAll = false,
}: CheckboxGroupProps) {
  const allSelected = options.every((option) => selected.includes(option))

  function toggle(option: string) {
    onChange(
      selected.includes(option) ? selected.filter((s) => s !== option) : [...selected, option],
    )
  }

  return (
    <fieldset>
      <div className="flex items-center justify-between gap-4">
        <legend className="text-sm font-medium text-slate-700">{legend}</legend>
        {showSelectAll && (
          <button
            type="button"
            onClick={() => onChange(allSelected ? [] : options)}
            className="text-sm font-medium text-emerald-700 hover:text-emerald-800"
          >
            {allSelected ? 'Clear all' : 'Select all'}
          </button>
        )}
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {options.map((option) => (
          <label
            key={option}
            className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 has-[:checked]:border-emerald-600 has-[:checked]:bg-emerald-50"
          >
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => toggle(option)}
              className="h-4 w-4 rounded border-slate-300 accent-emerald-600"
            />
            {option}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
