// Topic tables that live outside asylum_cases and need to be merged in.
// Keys are the boolean column names; values are the Supabase table names.

export const TOPIC_TABLES = {
  gang_opposition: 'asylum_cases_gang_opposition',
  machismo_opposition: 'asylum_cases_machismo_opposition',
}

export const TOPIC_COLS = new Set(Object.keys(TOPIC_TABLES))

// Given a page of asylum_cases rows, fetch topic data and merge it in.
// Topic table values take priority over any same-named column in asylum_cases.
export async function mergeTopicData(supabase, rows) {
  if (!rows?.length) return rows

  const links = rows.map(r => r.link)

  const fetches = Object.entries(TOPIC_TABLES).map(([concept, table]) =>
    supabase
      .from(table)
      .select(`link,${concept},${concept}_evidence`)
      .in('link', links)
      .then(({ data }) => ({ concept, map: Object.fromEntries((data || []).map(r => [r.link, r])) }))
  )

  const results = await Promise.all(fetches)

  return rows.map(row => {
    const merged = { ...row }
    for (const { concept, map } of results) {
      const topicRow = map[row.link]
      if (topicRow) {
        merged[concept] = topicRow[concept]
        merged[`${concept}_evidence`] = topicRow[`${concept}_evidence`]
      }
    }
    return merged
  })
}

// For a topic column filter, return the set of links that match.
// Returns null if no topic filter is active (caller should skip this step).
export async function fetchTopicFilterLinks(supabase, filters) {
  const topicFilters = Object.entries(filters).filter(
    ([col, val]) => TOPIC_COLS.has(col) && val !== '' && val !== null && val !== undefined
  )
  if (!topicFilters.length) return null

  const linkSets = await Promise.all(
    topicFilters.map(async ([col, val]) => {
      const table = TOPIC_TABLES[col]
      let q = supabase.from(table).select('link')
      if (val === 'true') q = q.eq(col, true)
      else if (val === 'false') q = q.eq(col, false)
      else if (val === 'null') q = q.is(col, null)
      const { data } = await q
      return new Set((data || []).map(r => r.link))
    })
  )

  // Intersection: row must match all topic filters
  return linkSets.reduce((a, b) => new Set([...a].filter(x => b.has(x))))
}
