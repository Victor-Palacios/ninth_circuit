'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { createClient } from '@/lib/supabase'
import { VISIBLE_COLUMNS, COLUMN_GROUPS, getColumnWidth } from '@/lib/columns'
import { applyFilters } from '@/lib/filters'
import { DEFAULT_LAYOUT, loadPreferences, savePreferences } from '@/lib/preferences'
import AppHeader from './app-header'
import TableControls from './table-controls'
import TableHeader from './table-header'
import TableFilters from './table-filters'
import TableBody from './table-body'
import TablePagination from './table-pagination'
import EvidenceDrawer from './evidence-drawer'
import CaseCard from './case-card'

const PAGE_SIZE = 50

function computeLeftOffsets(columns, frozenCols) {
  const offsets = {}
  let left = 0
  columns.slice(0, frozenCols).forEach(col => {
    offsets[col] = left
    left += getColumnWidth(col)
  })
  return offsets
}

export default function CasesTable({ initialRows, totalCount: initialTotal }) {
  const [rows, setRows] = useState(initialRows)
  const [totalCount, setTotalCount] = useState(initialTotal)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({})
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedRow, setSelectedRow] = useState(null)

  // Column management
  const [columnOrder, setColumnOrder] = useState(VISIBLE_COLUMNS)
  const [hiddenColumns, setHiddenColumns] = useState(new Set())
  const [frozenCols, setFrozenCols] = useState(0)
  const [frozenRows, setFrozenRows] = useState(0)

  const supabaseRef = useRef(createClient())
  const searchTimerRef = useRef(null)
  const saveTimerRef = useRef(null)
  const theadRef = useRef(null)
  const [theadHeight, setTheadHeight] = useState(0)
  const isMounted = useRef(false)

  // Load preferences on mount
  useEffect(() => {
    loadPreferences(supabaseRef.current).then(prefs => {
      setColumnOrder(prefs.columnOrder)
      setHiddenColumns(new Set(prefs.hiddenColumns))
      setFrozenCols(prefs.frozenCols)
      setFrozenRows(prefs.frozenRows)
    })
  }, [])

  // Save preferences (debounced) on any layout change
  useEffect(() => {
    clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      savePreferences(supabaseRef.current, {
        columnOrder,
        hiddenColumns: [...hiddenColumns],
        frozenCols,
        frozenRows,
      })
    }, 800)
  }, [columnOrder, hiddenColumns, frozenCols, frozenRows])

  const handleResetLayout = () => {
    setColumnOrder(DEFAULT_LAYOUT.columnOrder)
    setHiddenColumns(new Set(DEFAULT_LAYOUT.hiddenColumns))
    setFrozenCols(DEFAULT_LAYOUT.frozenCols)
    setFrozenRows(DEFAULT_LAYOUT.frozenRows)
  }

  const visibleColumns = columnOrder.filter(c => !hiddenColumns.has(c))
  const columnLeftOffsets = computeLeftOffsets(visibleColumns, frozenCols)
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE))

  // Measure thead height whenever columns change
  useEffect(() => {
    if (theadRef.current) setTheadHeight(theadRef.current.offsetHeight)
  })

  const fetchData = useCallback(async (currentPage, currentFilters, currentSearch) => {
    setLoading(true)
    const from = (currentPage - 1) * PAGE_SIZE
    const to = from + PAGE_SIZE - 1

    let query = supabaseRef.current
      .from('asylum_cases_full')
      .select(VISIBLE_COLUMNS.join(','), { count: 'exact' })
      .order('date_filed', { ascending: false })

    query = applyFilters(query, currentFilters)

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

  // Re-fetch when filters or page change (skip initial mount — SSR provides the first page)
  useEffect(() => {
    if (!isMounted.current) { isMounted.current = true; return }
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

  const handleToggleColumn = (col) => {
    setHiddenColumns(prev => {
      const next = new Set(prev)
      if (next.has(col)) next.delete(col)
      else next.add(col)
      return next
    })
  }

  const handleColumnReorder = (fromCol, toCol) => {
    setColumnOrder(prev => {
      const arr = [...prev]
      const fromIdx = arr.indexOf(fromCol)
      const toIdx = arr.indexOf(toCol)
      arr.splice(fromIdx, 1)
      arr.splice(toIdx, 0, fromCol)
      return arr
    })
  }

  const handleGroupReorder = (fromGroupKey, toGroupKey) => {
    setColumnOrder(prev => {
      const fromCols = new Set(COLUMN_GROUPS.find(g => g.key === fromGroupKey)?.columns ?? [])
      const toCols = new Set(COLUMN_GROUPS.find(g => g.key === toGroupKey)?.columns ?? [])
      const fromArr = prev.filter(c => fromCols.has(c))
      const rest = prev.filter(c => !fromCols.has(c))
      const firstFromIdx = prev.findIndex(c => fromCols.has(c))
      const firstToIdx = prev.findIndex(c => toCols.has(c))
      const insertIdx = rest.findIndex(c => toCols.has(c))
      if (insertIdx === -1) return prev
      const result = [...rest]
      if (firstFromIdx < firstToIdx) {
        const lastToIdx = result.reduce((acc, c, i) => toCols.has(c) ? i : acc, insertIdx)
        result.splice(lastToIdx + 1, 0, ...fromArr)
      } else {
        result.splice(insertIdx, 0, ...fromArr)
      }
      return result
    })
  }

  return (
    <div className="flex flex-col h-screen">
      <AppHeader
        totalCount={initialTotal}
        filteredCount={totalCount}
        searchValue={search}
        onSearchChange={handleSearchChange}
      />

      <TableControls
        columnOrder={columnOrder}
        hiddenColumns={hiddenColumns}
        onToggleColumn={handleToggleColumn}
        frozenCols={frozenCols}
        frozenRows={frozenRows}
        onFrozenColsChange={setFrozenCols}
        onFrozenRowsChange={setFrozenRows}
        visibleCount={visibleColumns.length}
        onResetLayout={handleResetLayout}
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
          <table className="w-full border-collapse text-sm">
            <thead ref={theadRef} className="sticky top-0 z-10">
              <TableHeader
                columns={visibleColumns}
                frozenCols={frozenCols}
                columnLeftOffsets={columnLeftOffsets}
                onColumnReorder={handleColumnReorder}
                onGroupReorder={handleGroupReorder}
              />
              <TableFilters
                columns={visibleColumns}
                filters={filters}
                onFilterChange={handleFilterChange}
                frozenCols={frozenCols}
                columnLeftOffsets={columnLeftOffsets}
              />
            </thead>
            <TableBody
              rows={rows}
              columns={visibleColumns}
              onRowClick={setSelectedRow}
              frozenCols={frozenCols}
              frozenRows={frozenRows}
              columnLeftOffsets={columnLeftOffsets}
              theadHeight={theadHeight}
            />
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
