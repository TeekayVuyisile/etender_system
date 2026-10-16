// Tender search state lives in the URL (?q=road&province=Gauteng...), so searches can be
// bookmarked and shared, and the browser's back button works.

export type TenderSort = 'relevance' | 'closing_soon' | 'newest'

export type TenderQuery = {
  q: string
  provinces: string[]
  buyers: string[]
  closingFrom: string
  closingTo: string
  minValue: string
  maxValue: string
  sort: TenderSort
  page: number
}

export const PAGE_SIZE = 20

export function readTenderQuery(params: URLSearchParams): TenderQuery {
  const sort = params.get('sort')
  return {
    q: params.get('q') ?? '',
    provinces: params.getAll('province'),
    buyers: params.getAll('buyer'),
    closingFrom: params.get('closing_from') ?? '',
    closingTo: params.get('closing_to') ?? '',
    minValue: params.get('min_value') ?? '',
    maxValue: params.get('max_value') ?? '',
    sort: sort === 'closing_soon' || sort === 'newest' ? sort : 'relevance',
    page: Math.max(1, Number(params.get('page')) || 1),
  }
}

export function toSearchParams(query: TenderQuery, extra: Record<string, string> = {}) {
  const params = new URLSearchParams()
  if (query.q) params.set('q', query.q)
  query.provinces.forEach((p) => params.append('province', p))
  query.buyers.forEach((b) => params.append('buyer', b))
  if (query.closingFrom) params.set('closing_from', query.closingFrom)
  if (query.closingTo) params.set('closing_to', query.closingTo)
  if (query.minValue) params.set('min_value', query.minValue)
  if (query.maxValue) params.set('max_value', query.maxValue)
  if (query.sort !== 'relevance') params.set('sort', query.sort)
  if (query.page > 1) params.set('page', String(query.page))
  Object.entries(extra).forEach(([key, value]) => params.set(key, value))
  return params
}

export function countActiveFilters(query: TenderQuery): number {
  return (
    query.provinces.length +
    query.buyers.length +
    (query.closingFrom || query.closingTo ? 1 : 0) +
    (query.minValue || query.maxValue ? 1 : 0)
  )
}
