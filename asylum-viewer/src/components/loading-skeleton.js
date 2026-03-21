export default function LoadingSkeleton() {
  return (
    <div className="flex flex-col h-screen bg-bg">
      {/* Header skeleton */}
      <div className="bg-header-bg px-7 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-5 w-32 bg-[#2e2c28] rounded animate-pulse" />
          <div className="h-4 w-20 bg-[#2e2c28] rounded animate-pulse" />
        </div>
        <div className="flex items-center gap-3">
          <div className="h-8 w-48 bg-[#2e2c28] rounded animate-pulse" />
          <div className="h-8 w-20 bg-[#2e2c28] rounded animate-pulse" />
        </div>
      </div>

      {/* Table skeleton */}
      <div className="flex-1 overflow-hidden">
        {/* Group headers */}
        <div className="flex border-b border-border">
          {[120, 160, 100, 200, 80, 220, 140, 160, 140, 100, 140].map((w, i) => (
            <div key={i} className="bg-header-bg px-3 py-2 border-r border-[#2e2c28]" style={{ minWidth: w }}>
              <div className="h-3 bg-[#2e2c28] rounded animate-pulse" style={{ width: '60%' }} />
            </div>
          ))}
        </div>

        {/* Column headers */}
        <div className="flex border-b border-border">
          {Array.from({ length: 36 }, (_, i) => (
            <div key={i} className="bg-th-bg px-3 py-2 border-r border-border" style={{ minWidth: 80 }}>
              <div className="h-3 bg-border rounded animate-pulse" style={{ width: `${50 + Math.random() * 40}%` }} />
            </div>
          ))}
        </div>

        {/* Rows */}
        {Array.from({ length: 10 }, (_, rowIdx) => (
          <div key={rowIdx} className="flex border-b border-border">
            {Array.from({ length: 36 }, (_, colIdx) => (
              <div key={colIdx} className="px-3 py-2.5 border-r border-border" style={{ minWidth: 80 }}>
                <div
                  className="h-3.5 bg-border/50 rounded animate-pulse"
                  style={{ width: `${30 + Math.random() * 50}%`, animationDelay: `${(rowIdx * 36 + colIdx) * 20}ms` }}
                />
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Pagination skeleton */}
      <div className="flex items-center justify-between px-7 py-3 bg-surface border-t border-border">
        <div className="h-4 w-24 bg-border rounded animate-pulse" />
        <div className="flex items-center gap-2">
          <div className="h-8 w-16 bg-border rounded animate-pulse" />
          <div className="h-4 w-12 bg-border rounded animate-pulse" />
          <div className="h-8 w-16 bg-border rounded animate-pulse" />
        </div>
      </div>
    </div>
  )
}
