'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

export default function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const router = useRouter()
  const supabase = createClient()

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setError(error.message)
      setLoading(false)
    } else {
      router.push('/cases')
    }
  }

  return (
    <form onSubmit={handleLogin} className="space-y-5">
      <div>
        <label className="block font-mono text-[10px] tracking-widest uppercase text-muted mb-1.5">
          Email
        </label>
        <input
          type="email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
          autoComplete="email"
          className="w-full px-3 py-2.5 bg-surface border border-border text-text font-sans text-sm outline-none transition-colors focus:border-accent"
        />
      </div>
      <div>
        <label className="block font-mono text-[10px] tracking-widest uppercase text-muted mb-1.5">
          Password
        </label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
          autoComplete="current-password"
          className="w-full px-3 py-2.5 bg-surface border border-border text-text font-sans text-sm outline-none transition-colors focus:border-accent"
        />
      </div>
      {error && (
        <div className="font-mono text-[11px] text-no-text bg-no-bg px-3 py-2 border-l-2 border-no-text">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 bg-text text-bg border-none font-mono text-[11px] tracking-[0.12em] uppercase cursor-pointer transition-colors hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed mt-2"
      >
        {loading ? 'Authenticating...' : 'Sign In \u2192'}
      </button>
    </form>
  )
}
