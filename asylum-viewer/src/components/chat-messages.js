'use client'

import { useEffect, useRef } from 'react'
import CitationCard from './citation-card'

function MessageBubble({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] bg-accent/10 border border-accent/30 text-text px-3 py-2 text-sm">
          {msg.content}
        </div>
      </div>
    )
  }
  if (msg.role === 'assistant') {
    const hasAnswer = typeof msg.answer === 'string' && msg.answer.trim().length > 0
    const hasCitations = msg.citations && msg.citations.length > 0
    const label = hasAnswer ? 'Answer' : 'Top matches'
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono tracking-wider text-muted uppercase">
            {label}
          </span>
          <span className="text-[9px] font-mono tracking-wider px-1.5 py-0.5 bg-no-bg text-no-text uppercase">
            experimental
          </span>
          {msg.latency_ms != null && (
            <span className="text-[10px] font-mono text-muted">{msg.latency_ms} ms</span>
          )}
        </div>

        {/* Conversational answer (chat mode) */}
        {hasAnswer && (
          <div className="text-sm text-text leading-relaxed whitespace-pre-wrap">
            {msg.answer}
          </div>
        )}

        {msg.refused || (!hasAnswer && !hasCitations) ? (
          <div className="text-xs text-muted italic">
            No matching cases in the corpus for that query.
          </div>
        ) : hasCitations ? (
          <div className="space-y-2">
            {hasAnswer && (
              <div className="text-[10px] font-mono tracking-wider text-muted uppercase pt-1">
                Sources
              </div>
            )}
            {msg.citations.map((c, i) => (
              <div key={c.chunk_id} id={`cite-${i + 1}`}>
                <CitationCard citation={c} index={i + 1} />
              </div>
            ))}
          </div>
        ) : null}
      </div>
    )
  }
  if (msg.role === 'error') {
    return (
      <div className="border border-no-bg bg-no-bg/30 text-no-text text-xs p-3">
        {msg.content}
      </div>
    )
  }
  return null
}

export default function ChatMessages({ messages, loading, mode = 'chat' }) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  if (messages.length === 0 && !loading) {
    return mode === 'chat' ? (
      <div className="flex-1 flex items-center justify-center text-muted text-xs font-mono tracking-wider px-6 text-center">
        ASK ABOUT THE CASE CORPUS.
        <br />
        EXAMPLES: &quot;What does the court require to show past persecution?&quot;,
        <br />
        &quot;How is a particular social group defined?&quot;.
      </div>
    ) : (
      <div className="flex-1 flex items-center justify-center text-muted text-xs font-mono tracking-wider px-6 text-center">
        SEARCH FOR SIMILAR CASES.
        <br />
        EXAMPLES: &quot;gang persecution El Salvador&quot;,
        <br />
        &quot;one-year filing bar&quot;, &quot;credibility findings&quot;.
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-6">
      {messages.map((m, i) => (
        <MessageBubble key={i} msg={m} />
      ))}
      {loading && (
        <div className="flex items-center gap-2 text-muted text-xs font-mono tracking-wider animate-pulse">
          <span>{mode === 'chat' ? 'THINKING' : 'SEARCHING'}</span>
          <span className="inline-block w-1 h-1 bg-muted rounded-full" />
          <span className="inline-block w-1 h-1 bg-muted rounded-full" />
          <span className="inline-block w-1 h-1 bg-muted rounded-full" />
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}
