'use client'

import { createClient } from '@/lib/supabase'
import { useRouter } from 'next/navigation'

export default function AppHeader({ totalCount, filteredCount, searchValue, onSearchChange }) {
  const router = useRouter()
  const supabase = createClient()

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push('/')
  }

  const countText = filteredCount !== totalCount
    ? `${filteredCount} of ${totalCount}`
    : `${totalCount}`

  return (
    <header className="bg-header-bg text-header-text px-4 sm:px-7 py-3.5 flex items-center justify-between sticky top-0 z-50 shadow-sm">
      <div className="flex items-center gap-3 min-w-0">
        <h1 className="text-base sm:text-lg font-normal tracking-[0.08em] uppercase whitespace-nowrap">
          Asylum Cases
        </h1>
        <span className="font-mono text-xs text-muted tracking-wider whitespace-nowrap">
          {countText} records
        </span>
      </div>
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search cases..."
          value={searchValue}
          onChange={e => onSearchChange(e.target.value)}
          className="hidden sm:block w-48 lg:w-64 px-3 py-1.5 bg-transparent border border-[#4a4840] text-header-text font-mono text-xs tracking-wider outline-none transition-colors focus:border-accent placeholder:text-muted"
        />
        <button
          onClick={handleLogout}
          className="bg-transparent border border-[#4a4840] text-header-text px-3.5 py-1.5 font-mono text-[11px] tracking-[0.08em] uppercase cursor-pointer transition-colors hover:border-accent hover:text-accent"
        >
          Sign Out
        </button>
      </div>
    </header>
  )
}
