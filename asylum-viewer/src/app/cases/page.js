import { createServerClient } from '@/lib/supabase-server'
import { VISIBLE_COLUMNS } from '@/lib/columns'
import CasesTable from '@/components/cases-table'

export default async function CasesPage() {
  const supabase = await createServerClient()

  const { data, count } = await supabase
    .from('asylum_cases')
    .select(VISIBLE_COLUMNS.join(','), { count: 'exact' })
    .order('date_filed', { ascending: false })
    .range(0, 49)

  return <CasesTable initialRows={data || []} totalCount={count || 0} />
}
