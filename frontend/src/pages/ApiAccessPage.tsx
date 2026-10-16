import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { useAuth } from '../auth/useAuth'
import { ErrorAlert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { TextField } from '../components/ui/TextField'
import { apiRequest, getErrorMessage } from '../lib/api'
import { formatDateTime, relativeTime } from '../lib/format'
import type { ApiKeyCreated, ApiKeyInfo } from '../lib/types'

const keysKey = ['api-keys'] as const

const ENDPOINTS = [
  ['GET', '/api/enriched-releases', 'Tenders with metadata, AI summary and suitability score'],
  ['GET', '/api/analytics/spend-by-buyer', 'Tenders advertised and known values per buyer'],
  ['POST', '/api/summary/extract', 'Upload a PDF or DOCX, get a ~120-word summary'],
  ['POST', '/api/readiness/check', 'Score a tender against a company profile'],
]

export function ApiAccessPage() {
  const { user } = useAuth()
  const isOwner = user?.role === 'owner'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">API access</h1>
          <p className="mt-1 max-w-2xl text-slate-600">
            Connect other systems to Tender Insight Hub. Requests use your team's plan and company
            profile.
          </p>
        </div>
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="text-sm font-semibold text-emerald-700 hover:text-emerald-800"
        >
          Open API documentation ↗
        </a>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-500">Public endpoints</h2>
        <ul className="mt-3 divide-y divide-slate-100">
          {ENDPOINTS.map(([method, path, description]) => (
            <li key={path} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2.5 text-sm">
              <span className="w-12 font-mono text-xs font-bold text-emerald-700">{method}</span>
              <code className="font-mono text-slate-900">{path}</code>
              <span className="text-slate-500">{description}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-slate-500">
          Send your key in the <code className="font-mono">X-API-Key</code> header. Limit: 60
          requests per minute per key.
        </p>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">
          {`curl -H "X-API-Key: tih_your_key" \\
  "http://localhost:8000/api/enriched-releases?q=road+maintenance&province=Limpopo"`}
        </pre>
      </section>

      {isOwner ? (
        <ApiKeysManager />
      ) : (
        <p className="text-sm text-slate-500">Only your team owner can create API keys.</p>
      )}
    </div>
  )
}

function ApiKeysManager() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [newKey, setNewKey] = useState<ApiKeyCreated | null>(null)
  const [copied, setCopied] = useState(false)

  const keysQuery = useQuery({
    queryKey: keysKey,
    queryFn: () => apiRequest<ApiKeyInfo[]>('/team/api-keys'),
  })
  const createKey = useMutation({
    mutationFn: (keyName: string) =>
      apiRequest<ApiKeyCreated>('/team/api-keys', { method: 'POST', json: { name: keyName } }),
    onSuccess: (created) => {
      setNewKey(created)
      setCopied(false)
      setName('')
      queryClient.invalidateQueries({ queryKey: keysKey })
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (name.trim()) createKey.mutate(name.trim())
  }

  async function copyKey(key: string) {
    try {
      await navigator.clipboard.writeText(key)
      setCopied(true)
    } catch {
      setCopied(false) // clipboard blocked: the key is still visible to copy by hand
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-500">API keys</h2>

      {newKey && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-900">
            Copy your new key now: it won't be shown again.
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <code className="min-w-0 flex-1 rounded-lg bg-white px-3 py-2 font-mono text-sm break-all text-slate-900">
              {newKey.key}
            </code>
            <Button variant="secondary" onClick={() => copyKey(newKey.key)}>
              {copied ? 'Copied ✓' : 'Copy'}
            </Button>
          </div>
          <button
            type="button"
            onClick={() => setNewKey(null)}
            className="mt-2 text-xs font-medium text-amber-800 hover:text-amber-900"
          >
            I've saved it
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-4 flex flex-wrap items-end gap-3">
        <div className="min-w-[14rem] flex-1">
          <TextField
            label="Key name"
            placeholder="e.g. Municipal dashboard"
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <Button type="submit" isLoading={createKey.isPending} disabled={!name.trim()}>
          Create API key
        </Button>
      </form>
      {createKey.isError && (
        <div className="mt-3">
          <ErrorAlert message={getErrorMessage(createKey.error)} />
        </div>
      )}

      <div className="mt-6">
        {keysQuery.isPending && <Spinner />}
        {keysQuery.isError && <ErrorAlert message={getErrorMessage(keysQuery.error)} />}
        {keysQuery.data?.length === 0 && <p className="text-sm text-slate-500">No API keys yet.</p>}
        {keysQuery.data && keysQuery.data.length > 0 && (
          <ul className="divide-y divide-slate-100">
            {keysQuery.data.map((key) => (
              <ApiKeyRow key={key.id} apiKey={key} />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function ApiKeyRow({ apiKey }: { apiKey: ApiKeyInfo }) {
  const queryClient = useQueryClient()
  const [confirm, setConfirm] = useState(false)
  const revoke = useMutation({
    mutationFn: () => apiRequest<void>(`/team/api-keys/${apiKey.id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keysKey }),
  })

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="min-w-0">
        <p className="font-medium text-slate-900">{apiKey.name}</p>
        <p className="text-xs text-slate-500">
          <code className="font-mono">{apiKey.prefix}…</code> · created{' '}
          <span title={formatDateTime(apiKey.created_at)}>{relativeTime(apiKey.created_at)}</span> ·{' '}
          {apiKey.last_used_at ? `last used ${relativeTime(apiKey.last_used_at)}` : 'never used'}
        </p>
      </div>
      {confirm ? (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-600">Revoke? Apps using it will stop working.</span>
          <Button variant="danger" isLoading={revoke.isPending} onClick={() => revoke.mutate()}>
            Revoke
          </Button>
          <Button variant="secondary" onClick={() => setConfirm(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirm(true)}
          className="text-sm font-medium text-slate-500 hover:text-red-600"
        >
          Revoke
        </button>
      )}
    </li>
  )
}
