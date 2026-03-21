export default function TablePagination({ page, totalPages, totalCount, pageSize, onPageChange }) {
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, totalCount)

  return (
    <div className="flex items-center justify-between px-4 sm:px-7 py-3 bg-surface border-t border-border">
      <span className="font-mono text-xs text-muted tracking-wider">
        {totalCount > 0 ? `${from}\u2013${to} of ${totalCount}` : 'No results'}
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="px-3 py-1.5 font-mono text-[11px] tracking-wider uppercase border border-border text-text bg-transparent cursor-pointer transition-colors hover:border-accent hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:border-border disabled:hover:text-text"
        >
          &larr; Prev
        </button>
        <span className="font-mono text-xs text-muted px-2">
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="px-3 py-1.5 font-mono text-[11px] tracking-wider uppercase border border-border text-text bg-transparent cursor-pointer transition-colors hover:border-accent hover:text-accent disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:border-border disabled:hover:text-text"
        >
          Next &rarr;
        </button>
      </div>
    </div>
  )
}
