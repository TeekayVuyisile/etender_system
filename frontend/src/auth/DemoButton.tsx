import { useMutation } from '@tanstack/react-query'
import { LuPlay } from 'react-icons/lu'

import { ErrorAlert } from '../components/ui/Alert'
import { getErrorMessage } from '../lib/api'
import { useHealth } from '../lib/health'
import { useAuth } from './useAuth'

/** "Try the demo": shown only when the server has demo mode turned on. */
export function DemoButton() {
  const { startDemo } = useAuth()
  const health = useHealth()
  const demo = useMutation({ mutationFn: startDemo })

  if (!health.data?.demo_mode) return null

  return (
    <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
      <p className="text-sm text-emerald-900">
        Just looking around? Explore a ready-made workspace with real tenders, AI summaries and
        match scores. No sign-up needed.
      </p>
      <button
        type="button"
        onClick={() => demo.mutate()}
        disabled={demo.isPending}
        className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-60"
      >
        {demo.isPending ? (
          'Setting up your demo workspace…'
        ) : (
          <>
            <LuPlay aria-hidden="true" /> Try the demo
          </>
        )}
      </button>
      {demo.isError && (
        <div className="mt-3 text-left">
          <ErrorAlert message={getErrorMessage(demo.error)} />
        </div>
      )}
    </div>
  )
}
