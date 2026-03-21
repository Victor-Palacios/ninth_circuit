export default function TableBody({ rows, columns, onRowClick }) {
  const formatCell = (val, col) => {
    if (val === null || val === undefined) {
      return <span className="text-muted">&mdash;</span>
    }
    if (typeof val === 'boolean') {
      return (
        <span className={`inline-block px-2.5 py-1 rounded text-xs font-semibold tracking-wider ${
          val
            ? 'bg-yes-bg text-yes-text'
            : 'bg-no-bg text-no-text'
        }`}>
          {val ? 'YES' : 'NO'}
        </span>
      )
    }
    if (col === 'link' && String(val).startsWith('http')) {
      return (
        <a
          href={val}
          target="_blank"
          rel="noreferrer"
          onClick={e => e.stopPropagation()}
          className="text-accent no-underline font-medium hover:underline"
        >
          PDF &#8599;
        </a>
      )
    }
    return String(val)
  }

  if (rows.length === 0) {
    return (
      <tbody>
        <tr>
          <td colSpan={columns.length} className="text-center py-16 text-muted font-mono tracking-wider">
            NO MATCHING RECORDS
          </td>
        </tr>
      </tbody>
    )
  }

  return (
    <tbody>
      {rows.map((row, i) => (
        <tr
          key={row.link || i}
          onClick={() => onRowClick(row)}
          className="border-b border-border transition-colors hover:bg-row-hover cursor-pointer"
        >
          {columns.map(col => (
            <td
              key={col}
              title={String(row[col] ?? '')}
              className="px-4 py-2.5 border-r border-border max-w-[260px] overflow-hidden text-ellipsis whitespace-nowrap align-middle text-sm"
            >
              {formatCell(row[col], col)}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  )
}
