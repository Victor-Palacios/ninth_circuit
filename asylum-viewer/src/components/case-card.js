export default function CaseCard({ row, onClick }) {
  return (
    <div
      onClick={onClick}
      className="bg-surface border border-border p-4 cursor-pointer transition-colors hover:border-accent active:bg-row-hover"
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="font-mono text-xs text-muted">{row.date_filed}</p>
          <p className="text-sm font-medium text-text">{row.docket_no}</p>
        </div>
        <span className={`font-mono text-[10px] tracking-wider px-2 py-0.5 ${
          row.published_status === 'Published'
            ? 'text-yes-text bg-yes-bg'
            : 'text-muted bg-th-bg'
        }`}>
          {row.published_status}
        </span>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm text-text">{row.country_of_origin || <span className="text-muted">&mdash;</span>}</span>
        <span className="text-muted">&middot;</span>
        <span className="text-sm text-muted">{row.final_disposition || 'Unknown'}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {row.asylum_requested && <ClaimChip label="Asylum" />}
        {row.withholding_requested && <ClaimChip label="Withholding" />}
        {row.CAT_requested && <ClaimChip label="CAT" />}
      </div>
    </div>
  )
}

function ClaimChip({ label }) {
  return (
    <span className="inline-block px-2 py-0.5 bg-accent/10 text-accent font-mono text-[10px] tracking-wider uppercase">
      {label}
    </span>
  )
}
