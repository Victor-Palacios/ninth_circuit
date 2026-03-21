'use client'

import { useState, useEffect } from 'react'
import { createClient } from '@/lib/supabase'
import { COLUMN_GROUPS, getLabel, BOOLEAN_COLS } from '@/lib/columns'

export default function EvidenceDrawer({ row, onClose }) {
  const [fullRow, setFullRow] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchEvidence = async () => {
      setLoading(true)
      const supabase = createClient()
      const { data, error } = await supabase
        .from('asylum_cases')
        .select('*')
        .eq('link', row.link)
        .single()

      if (error) {
        console.error(error)
        setLoading(false)
        return
      }
      setFullRow(data)
      setLoading(false)
    }
    fetchEvidence()
  }, [row.link])

  // Close on Escape
  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const data = fullRow || row

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-50"
        onClick={onClose}
      />
      {/* Drawer */}
      <div className="fixed top-0 right-0 h-full w-full sm:w-[520px] bg-drawer-bg z-50 shadow-2xl overflow-y-auto border-l border-border animate-in">
        <div className="sticky top-0 bg-drawer-bg border-b border-border px-6 py-4 flex items-center justify-between z-10">
          <div>
            <p className="font-mono text-[10px] tracking-widest uppercase text-muted">Case Detail</p>
            <h2 className="text-lg font-normal text-text">{data.docket_no || 'Unknown'}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-text transition-colors text-xl leading-none px-2 py-1"
          >
            &times;
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Metadata */}
          <div className="grid grid-cols-2 gap-4 pb-5 border-b border-border">
            <MetaField label="Date Filed" value={data.date_filed} />
            <MetaField label="Status" value={data.published_status} />
            <MetaField label="Country" value={data.country_of_origin} />
            <MetaField label="Disposition" value={data.final_disposition} />
            <MetaField label="Length" value={data.char_count ? `${data.char_count.toLocaleString()} chars` : null} />
            {data.link && (
              <div>
                <p className="font-mono text-[10px] tracking-widest uppercase text-muted mb-1">PDF</p>
                <a href={data.link} target="_blank" rel="noreferrer" className="text-accent text-sm hover:underline">
                  View Document &#8599;
                </a>
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <span className="font-mono text-xs text-muted tracking-wider animate-pulse">LOADING EVIDENCE...</span>
            </div>
          ) : (
            /* Evidence sections grouped by category */
            COLUMN_GROUPS.filter(g => !['meta'].includes(g.key)).map(group => {
              const relevantCols = group.columns.filter(c => BOOLEAN_COLS.includes(c) || ['country_of_origin', 'final_disposition'].includes(c))
              if (relevantCols.length === 0) return null

              const hasAnyEvidence = relevantCols.some(col => data[`${col}_evidence`])
              const hasAnyValue = relevantCols.some(col => data[col] !== null && data[col] !== undefined)
              if (!hasAnyValue && !hasAnyEvidence) return null

              return (
                <div key={group.key} className="space-y-3">
                  <h3 className="font-mono text-[10px] tracking-[0.12em] uppercase text-muted font-semibold">
                    {group.label}
                  </h3>
                  {relevantCols.map(col => {
                    const val = data[col]
                    const evidence = data[`${col}_evidence`]
                    if (val === null && !evidence) return null

                    return (
                      <div key={col} className="pl-3 border-l-2 border-border">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium text-text">{getLabel(col)}</span>
                          {typeof val === 'boolean' && (
                            <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                              val ? 'bg-yes-bg text-yes-text' : 'bg-no-bg text-no-text'
                            }`}>
                              {val ? 'YES' : 'NO'}
                            </span>
                          )}
                          {typeof val === 'string' && (
                            <span className="text-sm text-muted">{val}</span>
                          )}
                        </div>
                        {evidence && (
                          <p className="text-[13px] leading-relaxed text-muted mt-1">
                            {evidence}
                          </p>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })
          )}
        </div>
      </div>
    </>
  )
}

function MetaField({ label, value }) {
  return (
    <div>
      <p className="font-mono text-[10px] tracking-widest uppercase text-muted mb-1">{label}</p>
      <p className="text-sm text-text">{value ?? <span className="text-muted">&mdash;</span>}</p>
    </div>
  )
}
