'use client'

import { useEffect, useState } from 'react'
import { chat as chatApi, search as searchApi } from '@/lib/rag-client'
import ChatInput from './chat-input'
import ChatMessages from './chat-messages'

const STORAGE_KEY = 'asylum-chat-open'
const MODE_KEY = 'asylum-chat-mode'

export default function ChatPanel() {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('chat') // 'chat' (conversational) | 'search' (citations only)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)

  // Restore open/closed + mode state from localStorage
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY)
      if (saved === '1') setOpen(true)
      const savedMode = window.localStorage.getItem(MODE_KEY)
      if (savedMode === 'search' || savedMode === 'chat') setMode(savedMode)
    } catch {}
  }, [])

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, open ? '1' : '0')
    } catch {}
  }, [open])

  useEffect(() => {
    try {
      window.localStorage.setItem(MODE_KEY, mode)
    } catch {}
  }, [mode])

  const handleSubmit = async (query) => {
    setMessages((m) => [...m, { role: 'user', content: query }])
    setLoading(true)
    try {
      if (mode === 'chat') {
        const resp = await chatApi(query, 5)
        setMessages((m) => [
          ...m,
          {
            role: 'assistant',
            answer: resp.answer,
            citations: resp.citations || [],
            latency_ms: resp.latency_ms,
            refused: resp.refused,
          },
        ])
      } else {
        const resp = await searchApi(query, 5)
        setMessages((m) => [
          ...m,
          {
            role: 'assistant',
            citations: resp.hits || [],
            latency_ms: resp.latency_ms,
            refused: resp.refused,
          },
        ])
      }
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: 'error',
          content: `Request failed: ${err.message}. The backend may be cold-starting — try again in ~30s.`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    // Collapsed: thin vertical tab at the right edge of the viewport
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hidden sm:flex fixed top-1/2 right-0 -translate-y-1/2 z-30 flex-col items-center gap-2 bg-drawer-bg border border-r-0 border-border px-2 py-3 text-text hover:border-accent hover:text-accent transition-colors"
        title="Open case assistant"
        aria-label="Open case assistant"
      >
        <span className="text-base">💬</span>
        <span className="text-[10px] font-mono tracking-wider uppercase [writing-mode:vertical-rl]">
          Ask
        </span>
      </button>
    )
  }

  return (
    <aside className="hidden sm:flex flex-col w-[400px] shrink-0 border-l border-border bg-drawer-bg">
      {/* Testing-mode banner — always visible while panel is open */}
      <div className="bg-yes-bg text-yes-text border-b border-border px-3 py-2 text-[11px] font-mono tracking-wider leading-snug">
        🧪 TESTING MODE — answers may be incorrect and retrieval may miss relevant cases; always verify against the cited PDFs.
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs tracking-wider uppercase text-text font-semibold">
            Case Assistant
          </span>
          <span className="text-[9px] font-mono tracking-wider px-1.5 py-0.5 bg-no-bg text-no-text uppercase">
            beta
          </span>
        </div>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={() => setMessages([])}
              className="px-2 py-1 text-[10px] font-mono tracking-wider uppercase text-muted hover:text-text transition-colors"
              title="Clear conversation"
            >
              Clear
            </button>
          )}
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="text-muted hover:text-text transition-colors text-lg leading-none px-1"
            title="Close panel"
            aria-label="Close panel"
          >
            ×
          </button>
        </div>
      </div>

      {/* Mode toggle: conversational answer vs. citations-only search */}
      <div className="flex border-b border-border text-[10px] font-mono tracking-wider uppercase">
        {[
          ['chat', 'Ask', 'Conversational answer with citations'],
          ['search', 'Search', 'Ranked matching cases only'],
        ].map(([value, label, title]) => (
          <button
            key={value}
            type="button"
            onClick={() => setMode(value)}
            title={title}
            className={
              'flex-1 px-3 py-1.5 transition-colors ' +
              (mode === value
                ? 'bg-accent/10 text-accent border-b-2 border-accent'
                : 'text-muted hover:text-text border-b-2 border-transparent')
            }
          >
            {label}
          </button>
        ))}
      </div>

      <ChatMessages messages={messages} loading={loading} mode={mode} />
      <ChatInput onSubmit={handleSubmit} disabled={loading} mode={mode} />
    </aside>
  )
}
