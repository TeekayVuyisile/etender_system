// Small wrapper around fetch for calling our FastAPI backend.
// All requests go to /api/..., which Vite proxies to the backend in development.

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`)
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

// --- Response types (these mirror the backend's responses) ---

export type HealthResponse = {
  status: string
  app: string
  environment: string
}
