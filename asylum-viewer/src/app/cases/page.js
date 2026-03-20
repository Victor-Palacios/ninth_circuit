'use client'

import { useState, useEffect, useRef } from 'react'
import { createClient } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

// Column type definitions for filter behavior
const NO_FILTER_COLS = ['link']
const BINARY_COLS = { published_status: ['Published', 'Unpublished'] }
const NUMERIC_COLS = ['char_count']
const BOOLEAN_COLS = [
  'asylum_requested', 'withholding_requested', 'CAT_requested',
  'protected_ground_race', 'protected_ground_religion',
  'protected_ground_nationality', 'protected_ground_political_opinion',
  'protected_ground_particular_social_group',
  'nexus_explicit_nexus_language', 'nexus_nexus_strength',
  'past_persecution_established', 'past_persecution_physical_violence',
  'past_persecution_detention', 'past_persecution_sexual_violence',
  'past_persecution_death_threats', 'past_persecution_harm_severity',
  'persecutor_government_actor', 'persecutor_non_state_actor',
  'persecutor_government_unable_or_unwilling',
  'future_fear_well_founded_fear', 'future_fear_internal_relocation_reasonable',
  'future_fear_changed_country_conditions',
  'credibility_credibility_finding', 'credibility_inconsistencies_central',
  'credibility_corroboration_present', 'country_conditions_cited',
  'bars_one_year_deadline_missed', 'bars_firm_resettlement',
  'bars_particularly_serious_crime',
]

// Columns hidden from the frontend (visible only in Supabase)
const HIDDEN_COLS = ['extraction_model', 'extracted_at']

// Preferred column order — link appears after char_count
const COLUMN_ORDER = [
  'published_status', 'date_filed', 'docket_no', 'char_count', 'link',
  'country_of_origin', 'country_of_origin_evidence',
  'final_disposition', 'final_disposition_evidence',
  'asylum_requested', 'asylum_requested_evidence',
  'withholding_requested', 'withholding_requested_evidence',
  'CAT_requested', 'CAT_requested_evidence',
]

function getFilterType(col) {
  if (NO_FILTER_COLS.includes(col)) return 'none'
  if (col in BINARY_COLS) return 'binary'
  if (NUMERIC_COLS.includes(col)) return 'numeric'
  if (BOOLEAN_COLS.includes(col)) return 'boolean'
  return 'text'
}

function orderColumns(rawColumns) {
  const ordered = []
  for (const col of COLUMN_ORDER) {
    if (rawColumns.includes(col)) ordered.push(col)
  }
  for (const col of rawColumns) {
    if (!ordered.includes(col)) ordered.push(col)
  }
  return ordered
}

function applyFilters(query, filters) {
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

export default function CasesPage() {
  const [rows, setRows] = useState([])
  const [columns, setColumns] = useState([])
  const [loading, setLoading] = useState(true)
  const [columnFilters, setColumnFilters] = useState({})
  const supabaseRef = useRef(createClient())
  const router = useRouter()

  useEffect(() => {
    const load = async () => {
      const { data: { session } } = await supabaseRef.current.auth.getSession()
      if (!session) { router.push('/'); return }

      setLoading(true)
      const { data, error } = await applyFilters(
        supabaseRef.current.from('asylum_cases').select('*').order('date_filed', { ascending: false }),
        columnFilters
      )
      if (error) { console.error(error); setLoading(false); return }
      setRows(data)
      if (data.length > 0 && columns.length === 0) {
        setColumns(orderColumns(Object.keys(data[0]).filter(c => !HIDDEN_COLS.includes(c))))
      }
      setLoading(false)
    }
    load()
  }, [columnFilters])

  const handleLogout = async () => {
    await supabaseRef.current.auth.signOut()
    router.push('/')
  }

  const handleFilterChange = (col, value) => {
    setColumnFilters(prev => ({ ...prev, [col]: value }))
  }

  const formatCell = (val) => {
    if (val === null || val === undefined) return <span style={{ color: 'var(--muted)' }}>—</span>
    if (typeof val === 'boolean') return (
      <span style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.05em',
        background: val ? 'var(--yes-bg)' : 'var(--no-bg)',
        color: val ? 'var(--yes-text)' : 'var(--no-text)',
      }}>{val ? 'YES' : 'NO'}</span>
    )
    if (String(val).startsWith('http')) return (
      <a href={val} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 500 }}>
        View PDF ↗
      </a>
    )
    return String(val)
  }

  const renderFilter = (col) => {
    const filterType = getFilterType(col)
    if (filterType === 'none') return null

    if (filterType === 'binary') {
      return (
        <select value={columnFilters[col] || ''} onChange={e => handleFilterChange(col, e.target.value)}>
          <option value="">All</option>
          {BINARY_COLS[col].map(opt => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      )
    }

    if (filterType === 'boolean') {
      return (
        <select value={columnFilters[col] || ''} onChange={e => handleFilterChange(col, e.target.value)}>
          <option value="">All</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
          <option value="null">—</option>
        </select>
      )
    }

    if (filterType === 'numeric') {
      return (
        <input
          type="number"
          placeholder="min..."
          value={columnFilters[col] || ''}
          onChange={e => handleFilterChange(col, e.target.value)}
        />
      )
    }

    return (
      <input
        type="text"
        placeholder="filter..."
        value={columnFilters[col] || ''}
        onChange={e => handleFilterChange(col, e.target.value)}
      />
    )
  }

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg)' }}>
      <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--muted)', letterSpacing: '0.1em' }}>LOADING CASES...</div>
    </div>
  )

  return (
    <>
      <style>{`
        :root {
          --bg: #f7f6f2;
          --surface: #ffffff;
          --border: #e2e0d8;
          --text: #1a1916;
          --muted: #9b9689;
          --accent: #c4622d;
          --accent-hover: #a84e22;
          --header-bg: #1a1916;
          --header-text: #f7f6f2;
          --th-bg: #f0ede6;
          --filter-bg: #faf9f6;
          --yes-bg: #e8f4e8;
          --yes-text: #2d6e2d;
          --no-bg: #fce8e8;
          --no-text: #8b2020;
          --font-sans: 'Georgia', 'Times New Roman', serif;
          --font-mono: 'Courier New', monospace;
          --row-hover: #f0ede6;
          --shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        @media (prefers-color-scheme: dark) {
          :root {
            --bg: #111010;
            --surface: #1a1916;
            --border: #2e2c28;
            --text: #e8e5de;
            --muted: #6b6860;
            --accent: #e07848;
            --accent-hover: #c4622d;
            --header-bg: #0a0a09;
            --header-text: #e8e5de;
            --th-bg: #211f1c;
            --filter-bg: #161512;
            --yes-bg: #1a2e1a;
            --yes-text: #6abf6a;
            --no-bg: #2e1a1a;
            --no-text: #bf6a6a;
            --row-hover: #211f1c;
            --shadow: 0 1px 3px rgba(0,0,0,0.3);
          }
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: var(--bg); color: var(--text); font-family: var(--font-sans); font-size: 14px; line-height: 1.5; }

        .header {
          background: var(--header-bg); color: var(--header-text);
          padding: 16px 28px; display: flex; align-items: center;
          justify-content: space-between; position: sticky; top: 0; z-index: 100;
          box-shadow: var(--shadow);
        }
        .header-left { display: flex; align-items: baseline; gap: 12px; }
        .header-title { font-size: 18px; font-weight: normal; letter-spacing: 0.08em; text-transform: uppercase; }
        .header-count { font-family: var(--font-mono); font-size: 12px; color: var(--muted); letter-spacing: 0.05em; }

        .logout-btn {
          background: transparent; border: 1px solid #4a4840; color: var(--header-text);
          padding: 6px 14px; font-family: var(--font-mono); font-size: 11px;
          letter-spacing: 0.08em; text-transform: uppercase; cursor: pointer; transition: all 0.15s;
        }
        .logout-btn:hover { border-color: var(--accent); color: var(--accent); }

        .table-wrapper { overflow-x: auto; overflow-y: auto; max-height: calc(100vh - 57px); }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        thead { position: sticky; top: 0; z-index: 10; }

        .th-label {
          background: var(--th-bg); padding: 10px 12px 6px; text-align: left;
          font-family: var(--font-mono); font-size: 10px; font-weight: normal;
          letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted);
          border-bottom: 1px solid var(--border); white-space: nowrap; border-right: 1px solid var(--border);
        }
        .th-filter {
          background: var(--filter-bg); padding: 4px 8px 6px;
          border-bottom: 2px solid var(--border); border-right: 1px solid var(--border);
        }
        .th-filter input, .th-filter select {
          width: 100%; min-width: 80px; padding: 4px 6px; background: var(--surface);
          border: 1px solid var(--border); color: var(--text); font-family: var(--font-mono);
          font-size: 11px; outline: none; transition: border-color 0.15s;
        }
        .th-filter input:focus, .th-filter select:focus { border-color: var(--accent); }
        .th-filter input::placeholder { color: var(--muted); }

        tbody tr { border-bottom: 1px solid var(--border); transition: background 0.1s; }
        tbody tr:hover { background: var(--row-hover); }
        td {
          padding: 8px 12px; border-right: 1px solid var(--border);
          max-width: 240px; overflow: hidden; text-overflow: ellipsis;
          white-space: nowrap; vertical-align: middle;
        }
        .no-results { text-align: center; padding: 60px; color: var(--muted); font-family: var(--font-mono); letter-spacing: 0.05em; }
      `}</style>

      <div className="header">
        <div className="header-left">
          <span className="header-title">Asylum Cases</span>
          <span className="header-count">{rows.length} records</span>
        </div>
        <button className="logout-btn" onClick={handleLogout}>Sign Out</button>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col} className="th-label">{col.replace(/_/g, ' ')}</th>
              ))}
            </tr>
            <tr>
              {columns.map(col => (
                <th key={col} className="th-filter">{renderFilter(col)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="no-results">NO MATCHING RECORDS</td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr key={i}>
                  {columns.map(col => (
                    <td key={col} title={String(row[col] ?? '')}>{formatCell(row[col])}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
