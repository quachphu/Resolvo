function Stat({ label, value, sub, color }) {
  return (
    <div className="flex flex-col gap-0.5 p-2.5 rounded-lg bg-[#0a0a0b] border border-[#1e1e24]">
      <span className="text-[10px] font-mono text-[#6b6b7e] uppercase tracking-wider leading-none">
        {label}
      </span>
      <span
        className="text-xl font-bold font-mono leading-tight"
        style={{ color: color || '#e8e8f0' }}
      >
        {value}
      </span>
      {sub && <span className="text-[10px] text-[#6b6b7e]">{sub}</span>}
    </div>
  )
}

function formatCurrency(amount) {
  if (!amount) return '$0'
  if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}k`
  return `$${Math.round(amount)}`
}

export default function MetricsBar({ stats }) {
  const total = stats?.total_today ?? '—'
  const resolved = stats?.resolved_auto ?? '—'
  const escalated = stats?.escalated ?? '—'
  const costAvoided = stats?.cost_avoided ?? 0
  const hoursSaved = stats?.hours_saved ?? 0

  return (
    <div className="p-3 border-b border-[#1e1e24]">
      <p className="text-[10px] font-mono text-[#6b6b7e] uppercase tracking-wider mb-2">
        Today's metrics
      </p>
      <div className="grid grid-cols-2 gap-1.5">
        <Stat label="Incidents" value={total} />
        <Stat label="Auto-resolved" value={resolved} color="#22c55e" sub="no page sent" />
        <Stat label="Sleep saved" value={resolved !== '—' ? `${resolved}×` : '—'} color="#8b5cf6" sub="nights" />
        <Stat label="Cost avoided" value={formatCurrency(costAvoided)} color="#22c55e" />
      </div>
      {hoursSaved > 0 && (
        <p className="text-[10px] font-mono text-[#6b6b7e] mt-2 text-center">
          {hoursSaved.toFixed(1)}h of engineer time saved today
        </p>
      )}
    </div>
  )
}
