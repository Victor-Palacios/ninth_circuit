'use client'

import { useState } from 'react'

export default function ChatInput({ onSubmit, disabled, mode = 'chat' }) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-border p-3 space-y-2">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKey}
        placeholder={
          mode === 'chat'
            ? 'Ask about the cases…  (⌘/Ctrl + Enter)'
            : 'Search the corpus…  (⌘/Ctrl + Enter)'
        }
        rows={2}
        disabled={disabled}
        className="w-full bg-filter-bg border border-border text-text text-sm p-2 resize-none focus:outline-none focus:border-accent font-mono"
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="w-full px-3 py-1.5 text-xs font-mono tracking-wider uppercase border border-border text-text hover:border-accent hover:text-accent disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {disabled ? 'Sending…' : 'Send'}
      </button>
    </div>
  )
}
