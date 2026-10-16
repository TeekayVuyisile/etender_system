import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router'

import { apiDownload, getErrorMessage } from '../lib/api'
import { useHasFeature } from '../plans/queries'

type Format = 'csv' | 'pdf'

/** Workspace report downloads (Pro plan); a locked link to the plans page otherwise. */
export function ExportButtons() {
  const canExport = useHasFeature('exports')
  const download = useMutation({
    mutationFn: (format: Format) =>
      apiDownload(`/workspace/export?format=${format}`, `workspace.${format}`),
  })

  if (canExport === undefined) return null
  if (!canExport) {
    return (
      <Link
        to="/plan"
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-400 hover:text-slate-600"
        title="Report exports are available on the Pro plan"
      >
        🔒 Export (Pro)
      </Link>
    )
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="inline-flex gap-2">
        {(['csv', 'pdf'] as Format[]).map((format) => (
          <button
            key={format}
            type="button"
            disabled={download.isPending}
            onClick={() => download.mutate(format)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-emerald-600 hover:text-emerald-700 disabled:opacity-60"
          >
            {download.isPending && download.variables === format
              ? 'Preparing…'
              : `⬇ ${format === 'csv' ? 'CSV' : 'PDF report'}`}
          </button>
        ))}
      </div>
      {download.isError && (
        <p className="text-xs text-red-600">{getErrorMessage(download.error)}</p>
      )}
    </div>
  )
}
