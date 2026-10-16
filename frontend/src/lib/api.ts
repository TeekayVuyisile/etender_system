import type { Plan } from './types'

// Small wrapper around fetch for calling our FastAPI backend.
// All requests go to /api/..., which Vite proxies to the backend in development.

const TOKEN_KEY = 'tih.access_token'

export const tokenStorage = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string) {
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      // Storage unavailable (e.g. private mode): the session lasts until reload.
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      // Nothing to clear.
    }
  },
}

export class ApiError extends Error {
  status: number
  /** Machine-readable error code, e.g. "upgrade_required" when a plan limit is hit. */
  code: string | null
  requiredPlan: Plan | null

  constructor(
    status: number,
    message: string,
    code: string | null = null,
    requiredPlan: Plan | null = null,
  ) {
    super(message)
    this.status = status
    this.code = code
    this.requiredPlan = requiredPlan
  }
}

export function isUpgradeRequired(error: unknown): error is ApiError {
  return error instanceof ApiError && error.code === 'upgrade_required'
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  json?: unknown
  form?: Record<string, string>
}

export async function apiRequest<T>(
  path: string,
  { method = 'GET', json, form }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStorage.get()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  let body: BodyInit | undefined
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form) {
    body = new URLSearchParams(form)
  }

  const response = await fetch(`/api${path}`, { method, headers, body })
  if (!response.ok) {
    const { message, code, requiredPlan } = await readError(response)
    throw new ApiError(response.status, message, code, requiredPlan)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

type ValidationIssue = { loc: (string | number)[]; msg: string }

type ErrorInfo = {
  message: string
  code: string | null
  requiredPlan: Plan | null
}

// FastAPI errors look like {"detail": "message"}, validation errors (422) like
// {"detail": [{"loc": [...], "msg": "..."}]}, and plan limits like
// {"detail": {"code": "upgrade_required", "message": "...", "required_plan": "basic"}}.
async function readError(response: Response): Promise<ErrorInfo> {
  const fallback = `Request failed with status ${response.status}`
  try {
    const { detail } = await response.json()
    if (typeof detail === 'string') {
      return { message: detail, code: null, requiredPlan: null }
    }
    if (Array.isArray(detail)) {
      const message = (detail as ValidationIssue[])
        .map((issue) => `${issue.loc.at(-1)}: ${issue.msg}`)
        .join('. ')
      return { message, code: null, requiredPlan: null }
    }
    if (detail && typeof detail === 'object') {
      return {
        message: detail.message ?? fallback,
        code: detail.code ?? null,
        requiredPlan: detail.required_plan ?? null,
      }
    }
  } catch {
    // Response body wasn't JSON.
  }
  return { message: fallback, code: null, requiredPlan: null }
}

/** Download a file from the API (with the auth token) and save it in the browser. */
export async function apiDownload(path: string, fallbackName: string): Promise<void> {
  const token = tokenStorage.get()
  const response = await fetch(`/api${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    const { message, code, requiredPlan } = await readError(response)
    throw new ApiError(response.status, message, code, requiredPlan)
  }
  const disposition = response.headers.get('content-disposition') ?? ''
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName

  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
