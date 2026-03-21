import { getFilterType, BINARY_COLS } from './columns'

export function applyFilters(query, filters) {
  for (const [col, val] of Object.entries(filters)) {
    if (!val && val !== 0) continue
    const filterType = getFilterType(col)
    if (filterType === 'binary') {
      query = query.eq(col, val)
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
