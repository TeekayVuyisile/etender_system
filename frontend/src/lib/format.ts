const SMALL_WORDS = new Set([
  'a', 'an', 'and', 'as', 'at', 'by', 'for', 'from', 'in', 'of', 'on', 'or', 'the', 'to', 'with',
])

// Acronyms common in South African tenders that should stay upper case.
const ACRONYMS = new Set([
  'ATNS', 'BBBEE', 'CCMA', 'CIDB', 'CSD', 'DBSA', 'ECDOE', 'ERP', 'ESKOM', 'HR', 'HVAC', 'ICT',
  'IT', 'KZN', 'LED', 'NDPWI', 'NHBRC', 'PPE', 'PRASA', 'PSIRA', 'RFQ', 'RFP', 'RSA', 'SA',
  'SABC', 'SANRAL', 'SAPS', 'SASSA', 'SITA', 'SMME', 'SOC', 'TB', 'UPS', 'VAT',
])

function titleCaseWord(word: string): string {
  return word
    .toLowerCase()
    .replace(/(^|[(-])([a-z])/g, (_, sep, char) => sep + char.toUpperCase())
    .replace(/\/([a-z])(?=[a-z])/g, (_, char) => `/${char.toUpperCase()}`) // Goods/Services, not Provider/S
}

/**
 * Many tender descriptions are written in ALL CAPS. Convert those to title case for
 * readability, keeping known acronyms (ICT, KZN), letter-only abbreviations without
 * vowels (CCTV) and codes with digits (TN051/2026) as they are.
 */
export function readableCase(text: string): string {
  const letters = text.replace(/[^a-zA-Z]/g, '')
  const upper = letters.replace(/[^A-Z]/g, '')
  if (letters.length < 8 || upper.length / letters.length < 0.7) {
    return text
  }
  return text
    .split(' ')
    .map((word, index) => {
      const bare = word.replace(/[^a-zA-Z]/g, '')
      const lower = word.toLowerCase()
      if (index > 0 && SMALL_WORDS.has(lower)) return lower
      if (/\d/.test(word) || ACRONYMS.has(bare.toUpperCase())) return word
      if (bare.length > 1 && !/[AEIOU]/i.test(bare)) return word.toUpperCase()
      return titleCaseWord(word)
    })
    .join(' ')
}

const dateFormatter = new Intl.DateTimeFormat('en-ZA', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})
const dateTimeFormatter = new Intl.DateTimeFormat('en-ZA', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const currencyFormatter = new Intl.NumberFormat('en-ZA', {
  style: 'currency',
  currency: 'ZAR',
  maximumFractionDigits: 0,
})

export function formatDate(value: string | null): string {
  return value ? dateFormatter.format(new Date(value)) : '—'
}

export function formatDateTime(value: string | null): string {
  return value ? dateTimeFormatter.format(new Date(value)) : '—'
}

export function formatCurrency(value: number | null): string {
  return value === null ? 'Not published' : currencyFormatter.format(value)
}

export type Urgency = 'closed' | 'urgent' | 'soon' | 'normal'

/** Human-friendly time left until a deadline, e.g. "Closes in 3 days". */
export function deadlineLabel(closingAt: string | null): { label: string; urgency: Urgency } {
  if (!closingAt) {
    return { label: 'No closing date', urgency: 'normal' }
  }
  const msLeft = new Date(closingAt).getTime() - Date.now()
  if (msLeft < 0) {
    return { label: 'Closed', urgency: 'closed' }
  }
  const hours = msLeft / 3_600_000
  if (hours < 24) {
    return { label: `Closes in ${Math.max(1, Math.round(hours))}h`, urgency: 'urgent' }
  }
  const days = Math.round(hours / 24)
  return {
    label: `Closes in ${days} day${days === 1 ? '' : 's'}`,
    urgency: days <= 3 ? 'urgent' : days <= 7 ? 'soon' : 'normal',
  }
}

/** Today's date as YYYY-MM-DD in the user's local time zone. */
export function isoDate(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 10)
}

const relativeFormatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** "just now", "5 minutes ago", "yesterday", "3 days ago"... */
export function relativeTime(value: string): string {
  const seconds = (new Date(value).getTime() - Date.now()) / 1000
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['week', 604_800],
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) {
      return relativeFormatter.format(Math.round(seconds / size), unit)
    }
  }
  return 'just now'
}

/** True if a YYYY-MM-DD due date has fully passed (it counts as due until the end of the day). */
export function isOverdue(dueDate: string | null): boolean {
  return dueDate !== null && new Date(`${dueDate}T23:59:59`).getTime() < Date.now()
}
