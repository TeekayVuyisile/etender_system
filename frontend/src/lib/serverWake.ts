// On free hosting the API sleeps after 15 minutes without requests, and the first request then
// waits up to a minute while it starts. This tracks API requests so the UI can explain the wait
// instead of looking broken.

const ASLEEP_AFTER_MS = 14 * 60 * 1000

let pending = 0
let lastResponseAt = 0
const listeners = new Set<() => void>()

function notify() {
  listeners.forEach((listener) => listener())
}

export function trackRequest(request: Promise<Response>): Promise<Response> {
  pending += 1
  notify()
  return request
    .then((response) => {
      // Any answer from the API itself (not a proxy error) means it's awake.
      if (response.status < 500) {
        lastResponseAt = Date.now()
      }
      return response
    })
    .finally(() => {
      pending -= 1
      notify()
    })
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** True while requests are waiting and the API may be asleep. */
export function isWaitingForServer(): boolean {
  return pending > 0 && Date.now() - lastResponseAt > ASLEEP_AFTER_MS
}
