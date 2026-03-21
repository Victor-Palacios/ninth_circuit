import { COLUMN_GROUPS, getLabel } from '@/lib/columns'

export default function TableHeader({ columns }) {
  return (
    <>
      {/* Group header row */}
      <tr>
        {COLUMN_GROUPS.map(group => {
          const visibleCols = group.columns.filter(c => columns.includes(c))
          if (visibleCols.length === 0) return null
          return (
            <th
              key={group.key}
              colSpan={visibleCols.length}
              className="bg-header-bg text-header-text px-3 py-2 text-left font-mono text-[10px] font-semibold tracking-[0.12em] uppercase border-b border-border border-r border-r-[#2e2c28] whitespace-nowrap"
            >
              {group.label}
            </th>
          )
        })}
      </tr>
      {/* Individual column labels */}
      <tr>
        {columns.map(col => (
          <th
            key={col}
            className="bg-th-bg px-3 py-2 text-left font-mono text-[10px] font-normal tracking-[0.06em] uppercase text-muted border-b border-border border-r border-r-border whitespace-nowrap"
          >
            {getLabel(col)}
          </th>
        ))}
      </tr>
    </>
  )
}
