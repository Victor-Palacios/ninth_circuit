'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import { VISIBLE_COLUMNS } from '@/lib/columns'
import { applyFilters } from '@/lib/filters'
import AppHeader from './app-header'
import TableHeader from './table-header'
import TableFilters from './table-filters'
import TableBody from './table-body'
import TablePagination from './table-pagination'
import EvidenceDrawer from './evidence-drawer'
import CaseCard from './case-card'

const PAGE_SIZE = 50

export default function CasesTable({ initialRows, totalCount: initialTotal }) {
  const [rows, setRows] = useState(initialRows)
  const [totalCount, setTotalCount] = useState(initialTotal)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({})
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedRow, setSelectedRow] = useState(null)
  const supabaseRef = useRef(createClient())
  const searchTimerRef = useRef(null)

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE))

  const fetchData = useCallback(async (currentPage, currentFilters, currentSearch) => {
    setLoading(true)
    const from = (currentPage - 1) * PAGE_SIZE
    const to = from + PAGE_SIZE - 1

    let query = supabaseRef.current
      .from('asylum_cases')
      .select(VISIBLE_COLUMNS.join(','), { count: 'exact' })
      .order('date_filed', { ascending: false })

    query = applyFilters(query, currentFilters)

    // Global search across key text columns
    if (currentSearch.trim()) {
      const term = `%${currentSearch.trim()}%`
      query = query.or(
        `docket_no.ilike.${term},country_of_origin.ilike.${term},final_disposition.ilike.${term}`
      )
    }

    query = query.range(from, to)

    const { data, count, error } = await query
    if (error) {
      console.error(error)
      setLoading(false)
      return
    }
    setRows(data || [])
    setTotalCount(count || 0)
    setLoading(false)
  }, [])

  // Re-fetch when filters or page change
  useEffect(() => {
    // Skip initial load — we already have server-fetched data for page 1 with no filters
    if (page === 1 && Object.keys(filters).length === 0 && !search.trim()) return
    fetchData(page, filters, search)
  }, [page, filters, search, fetchData])

  const handleFilterChange = (col, value) => {
    setFilters(prev => ({ ...prev, [col]: value }))
    setPage(1)
  }

  const handleSearchChange = (value) => {
    clearTimeout(searchTimerRef.current)
    searchTimerRef.current = setTimeout(() => {
      setSearch(value)
      setPage(1)
    }, 300)
  }

  const handlePageChange = (newPage) => {
    if (newPage < 1 || newPage > totalPages) return
    setPage(newPage)
  }

  return (
    <div className="flex flex-col h-screen">
      <AppHeader
        totalCount={initialTotal}
        filteredCount={totalCount}
        searchValue={search}
        onSearchChange={handleSearchChange}
      />

      {/* Mobile card view */}
      <div className="block sm:hidden flex-1 overflow-y-auto p-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <span className="font-mono text-xs text-muted tracking-wider animate-pulse">LOADING...</span>
          </div>
        ) : rows.length === 0 ? (
          <div className="text-center py-16 text-muted font-mono tracking-wider">NO MATCHING RECORDS</div>
        ) : (
          rows.map((row, i) => (
            <CaseCard key={row.link || i} row={row} onClick={() => setSelectedRow(row)} />
          ))
        )}
      </div>

      {/* Desktop table view */}
      <div className="hidden sm:block flex-1 overflow-auto relative">
        <div className={`transition-opacity ${loading ? 'opacity-50' : 'opacity-100'}`}>
          <table className="w-full border-collapse text-[13px]">
            <thead className="sticky top-0 z-10">
              <TableHeader columns={VISIBLE_COLUMNS} />
              <TableFilters columns={VISIBLE_COLUMNS} filters={filters} onFilterChange={handleFilterChange} />
            </thead>
            <TableBody rows={rows} columns={VISIBLE_COLUMNS} onRowClick={setSelectedRow} />
          </table>
        </div>
      </div>

      <TablePagination
        page={page}
        totalPages={totalPages}
        totalCount={totalCount}
        pageSize={PAGE_SIZE}
        onPageChange={handlePageChange}
      />

      {selectedRow && (
        <EvidenceDrawer
          row={selectedRow}
          onClose={() => setSelectedRow(null)}
        />
      )}
    </div>
  )
}
