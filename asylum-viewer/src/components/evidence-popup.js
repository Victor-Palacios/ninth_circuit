'use client'

import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { createClient } from '@/lib/supabase'
import { getLabel } from '@/lib/columns'

export default function EvidencePopup({ col, link, value, onClose }) {
  const [evidence, setEvidence] = useState(null)
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  const dialogRef = useRef(null)

  useEffect(() => {
    const fetch = async () => {
      const supabase = createClient()
      const { data } = await supabase
        .from('asylum_cases')
        .select(`${col}_evidence`)
        .eq('link', link)
        .single()
      setEvidence(data?.[`${col}_evidence`] ?? null)
      setLoading(false)
    }
    fetch()
  }, [col, link])

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const handleCopy = () => {
    if (!evidence) return
    navigator.clipboard.writeText(evidence)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const isBool = typeof value === 'boolean'

  return createPortal(
    <>
      <div className="fixed inset-0 z-[60]" onClick={onClose} />
      <div
        ref={dialogRef}
        className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[61] w-full max-w-lg bg-drawer-bg border border-border shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-filter-bg">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs tracking-wider uppercase text-text font-semibold">
              {getLabel(col)}
            </span>
            {isBool && (
              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                value ? 'bg-yes-bg text-yes-text' : 'bg-no-bg text-no-text'
              }`}>
                {value ? 'YES' : 'NO'}
              </span>
            )}
            {!isBool && value && (
              <span className="text-xs text-muted font-mono">{value}</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-text transition-colors text-xl leading-none px-1"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 min-h-[80px]">
          {loading ? (
            <p className="text-xs text-muted font-mono tracking-wider animate-pulse">LOADING...</p>
          ) : evidence ? (
            <p className="text-sm leading-relaxed text-text select-text">{evidence}</p>
          ) : (
            <p className="text-sm text-muted italic">No evidence recorded.</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-border bg-filter-bg">
          <button
            onClick={handleCopy}
            disabled={!evidence || loading}
            className="px-3 py-1.5 text-xs font-mono tracking-wider uppercase border border-border text-text hover:border-accent hover:text-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-mono tracking-wider uppercase border border-border text-text hover:border-accent hover:text-accent transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </>,
    document.body
  )
}
