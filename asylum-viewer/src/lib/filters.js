import { getFilterType, BINARY_COLS } from './columns'

export function applyFilters(query, filters) {
  for (const [col, val] of Object.entries(filters)) {
    if (!val && val !== 0) continue
    const filterType = getFilterType(col)
    if (filterType === 'binary') {
      query = query.eq(col, val)
    } else if (filterType === 'date') {
      // Support year (2024), year-month (2024-03), or full date (2024-03-15)
      const v = String(val).trim()
      if (/^\d{4}$/.test(v)) {
        // Year only: filter to entire year
        query = query.gte(col, `${v}-01-01`).lte(col, `${v}-12-31`)
      } else if (/^\d{4}-\d{2}$/.test(v)) {
        // Year-month: filter to entire month
        const [year, month] = v.split('-')
        const lastDay = new Date(Number(year), Number(month), 0).getDate()
        query = query.gte(col, `${v}-01`).lte(col, `${v}-${lastDay}`)
      } else if (/^\d{4}-\d{2}-\d{2}$/.test(v)) {
        // Exact date
        query = query.eq(col, v)
      }
      // Otherwise ignore invalid input silently
    } else if (filterType === 'numeric') {
      const num = Number(val)
      if (!isNaN(num)) query = query.gte(col, num)
    } else if (filterType === 'boolean') {
      if (val === 'true') query = query.eq(col, true)
      else if (val === 'false') query = query.eq(col, false)
      else if (val === 'null') query = query.is(col, null)
    } else if (filterType === 'text') {
      query = query.ilike(col, `%${val}%`)
    }
  }
  return query
}

export { BINARY_COLS }
