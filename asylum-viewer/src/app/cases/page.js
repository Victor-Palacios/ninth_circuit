'use client'

import { useState, useEffect } from 'react'
import { createClient } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

export default function CasesPage() {
  const [cases, setCases] = useState([])
  const [columnFilters, setColumnFilters] = useState({})
  const [loading, setLoading] = useState(true)
  const [columns, setColumns] = useState([])
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    const fetchCases = async () => {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) { router.push('/'); return }

      const { data, error } = await supabase.from('asylum_cases').select('*')
      if (error) { console.error(error) }
      else {
        setCases(data)
        if (data.length > 0) setColumns(Object.keys(data[0]))
      }
      setLoading(false)
    }
    fetchCases()
  }, [])

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push('/')
  }

  const handleFilterChange = (col, value) => {
    setColumnFilters(prev => ({ ...prev, [col]: value }))
  }

  const filtered = cases.filter(row =>
    Object.entries(columnFilters).every(([col, val]) => {
      if (!val) return true
      const cellVal = row[col]
      return String(cellVal ?? '').toLowerCase().includes(val.toLowerCase())
    })
  )

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

        body {
          background: var(--bg);
          color: var(--text);
          font-family: var(--font-sans);
          font-size: 14px;
          line-height: 1.5;
        }

        .header {
          background: var(--header-bg);
          color: var(--header-text);
          padding: 16px 28px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          position: sticky;
          top: 0;
          z-index: 100;
          box-shadow: var(--shadow);
        }

        .header-left {
          display: flex;
          align-items: baseline;
          gap: 12px;
        }

        .header-title {
          font-size: 18px;
          font-weight: normal;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .header-count {
          font-family: var(--font-mono);
          font-size: 12px;
          color: var(--muted);
          letter-spacing: 0.05em;
        }

        .logout-btn {
          background: transparent;
          border: 1px solid #4a4840;
          color: var(--header-text);
          padding: 6px 14px;
          font-family: var(--font-mono);
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          cursor: pointer;
          transition: all 0.15s;
        }

        .logout-btn:hover {
          border-color: var(--accent);
          color: var(--accent);
        }

        .table-wrapper {
          overflow-x: auto;
          overflow-y: auto;
          max-height: calc(100vh - 57px);
        }

        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }

        thead {
          position: sticky;
          top: 0;
          z-index: 10;
        }

        .th-label {
          background: var(--th-bg);
          padding: 10px 12px 6px;
          text-align: left;
          font-family: var(--font-mono);
          font-size: 10px;
          font-weight: normal;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--muted);
          border-bottom: 1px solid var(--border);
          white-space: nowrap;
          border-right: 1px solid var(--border);
        }

        .th-filter {
          background: var(--filter-bg);
          padding: 4px 8px 6px;
          border-bottom: 2px solid var(--border);
          border-right: 1px solid var(--border);
        }

        .th-filter input {
          width: 100%;
          min-width: 80px;
          padding: 4px 6px;
          background: var(--surface);
          border: 1px solid var(--border);
          color: var(--text);
          font-family: var(--font-mono);
          font-size: 11px;
          outline: none;
          transition: border-color 0.15s;
        }

        .th-filter input:focus {
          border-color: var(--accent);
        }

        .th-filter input::placeholder {
          color: var(--muted);
        }

        tbody tr {
          border-bottom: 1px solid var(--border);
          transition: background 0.1s;
        }

        tbody tr:hover {
          background: var(--row-hover);
        }

        td {
          padding: 8px 12px;
          border-right: 1px solid var(--border);
          max-width: 240px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          vertical-align: middle;
        }

        .no-results {
          text-align: center;
          padding: 60px;
          color: var(--muted);
          font-family: var(--font-mono);
          letter-spacing: 0.05em;
        }
      `}</style>

      <div className="header">
        <div className="header-left">
          <span className="header-title">Asylum Cases</span>
          <span className="header-count">{filtered.length} / {cases.length} records</span>
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
                <th key={col} className="th-filter">
                  <input
                    type="text"
                    placeholder="filter..."
                    value={columnFilters[col] || ''}
                    onChange={e => handleFilterChange(col, e.target.value)}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="no-results">
                  NO MATCHING RECORDS
                </td>
              </tr>
            ) : (
              filtered.map((row, i) => (
                <tr key={i}>
                  {columns.map(col => (
                    <td key={col} title={String(row[col] ?? '')}>
                      {formatCell(row[col])}
                    </td>
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