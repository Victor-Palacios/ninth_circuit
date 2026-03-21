import { getFilterType } from '@/lib/columns'
import { BINARY_COLS } from '@/lib/filters'

export default function TableFilters({ columns, filters, onFilterChange }) {
  const renderFilter = (col) => {
    const filterType = getFilterType(col)
    if (filterType === 'none') return null

    const baseClass = 'w-full min-w-[70px] px-2 py-1.5 bg-surface border border-border text-text font-mono text-xs outline-none transition-colors focus:border-accent'

    if (filterType === 'binary') {
      return (
        <select
          value={filters[col] || ''}
          onChange={e => onFilterChange(col, e.target.value)}
          className={baseClass}
        >
          <option value="">All</option>
          {BINARY_COLS[col].map(opt => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      )
    }

    if (filterType === 'boolean') {
      return (
        <select
          value={filters[col] || ''}
          onChange={e => onFilterChange(col, e.target.value)}
          className={baseClass}
        >
          <option value="">All</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
          <option value="null">&mdash;</option>
        </select>
      )
    }

    if (filterType === 'numeric') {
      return (
        <input
          type="number"
          placeholder="min..."
          value={filters[col] || ''}
          onChange={e => onFilterChange(col, e.target.value)}
          className={`${baseClass} placeholder:text-muted`}
        />
      )
    }

    return (
      <input
        type="text"
        placeholder="filter..."
        value={filters[col] || ''}
        onChange={e => onFilterChange(col, e.target.value)}
        className={`${baseClass} placeholder:text-muted`}
      />
    )
  }

  return (
    <tr>
      {columns.map(col => (
        <th key={col} className="bg-filter-bg px-2 py-1.5 border-b-2 border-border border-r border-r-border">
          {renderFilter(col)}
        </th>
      ))}
    </tr>
  )
}
