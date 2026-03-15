'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
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
    if (error) { setError(error.message); setLoading(false) }
    else { router.push('/cases') }
  }

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
          --font-sans: 'Georgia', 'Times New Roman', serif;
          --font-mono: 'Courier New', monospace;
        }

        @media (prefers-color-scheme: dark) {
          :root {
            --bg: #111010;
            --surface: #1a1916;
            --border: #2e2c28;
            --text: #e8e5de;
            --muted: #6b6860;
            --accent: #e07848;
          }
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
          background: var(--bg);
          color: var(--text);
          font-family: var(--font-sans);
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .container {
          width: 100%;
          max-width: 380px;
          padding: 24px;
        }

        .eyebrow {
          font-family: var(--font-mono);
          font-size: 10px;
          letter-spacing: 0.15em;
          text-transform: uppercase;
          color: var(--muted);
          margin-bottom: 8px;
        }

        h1 {
          font-size: 28px;
          font-weight: normal;
          letter-spacing: -0.01em;
          margin-bottom: 32px;
          line-height: 1.2;
          border-bottom: 1px solid var(--border);
          padding-bottom: 24px;
        }

        .field {
          margin-bottom: 20px;
        }

        label {
          display: block;
          font-family: var(--font-mono);
          font-size: 10px;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--muted);
          margin-bottom: 6px;
        }

        input {
          width: 100%;
          padding: 10px 12px;
          background: var(--surface);
          border: 1px solid var(--border);
          color: var(--text);
          font-family: var(--font-sans);
          font-size: 14px;
          outline: none;
          transition: border-color 0.15s;
        }

        input:focus {
          border-color: var(--accent);
        }

        .error {
          font-family: var(--font-mono);
          font-size: 11px;
          color: #bf6a6a;
          margin-bottom: 16px;
          padding: 8px 10px;
          background: #2e1a1a;
          border-left: 2px solid #bf6a6a;
        }

        button {
          width: 100%;
          padding: 12px;
          background: var(--text);
          color: var(--bg);
          border: none;
          font-family: var(--font-mono);
          font-size: 11px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          cursor: pointer;
          transition: background 0.15s;
          margin-top: 8px;
        }

        button:hover:not(:disabled) {
          background: var(--accent);
        }

        button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>

      <div className="container">
        <p className="eyebrow">Ninth Circuit Research</p>
        <h1>Asylum Cases Database</h1>
        <form onSubmit={handleLogin}>
          <div className="field">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? 'Authenticating...' : 'Sign In →'}
          </button>
        </form>
      </div>
    </>
  )
}