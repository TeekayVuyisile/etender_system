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

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
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
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

type ValidationIssue ={ loc: (string | number)[]; msg: string }

// FastAPI errors look like {"detail": "message"}, or for validation errors (422)
// {"detail": [{"loc": ["body", "password"], "msg": "..."}]}.
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') {
      return data.detail
    }
    if (Array.isArray(data.detail)) {
      return (data.detail as ValidationIssue[])
        .map((issue) => `${issue.loc.at(-1)}: ${issue.msg}`)
        .join('. ')
    }
  } catch {
    // Response body wasn't JSON.
  }
  return `Request failed with status ${response.status}`
}
