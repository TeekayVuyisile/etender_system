import { LuArrowLeft, LuArrowRight } from 'react-icons/lu'

import { Button } from './Button'

type PaginationProps = {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  if (totalPages <= 1) {
    return null
  }

  return (
    <nav className="flex items-center justify-between gap-4" aria-label="Pagination">
      <Button variant="secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        <LuArrowLeft aria-hidden="true" /> Previous
      </Button>
      <span className="text-sm text-slate-600">
        Page {page} of {totalPages}
      </span>
      <Button
        variant="secondary"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next <LuArrowRight aria-hidden="true" />
      </Button>
    </nav>
  )
}
