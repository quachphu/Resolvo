const STATUS_CONFIG = {
  INVESTIGATING: { label: 'Investigating', color: '#f59e0b', bg: '#f59e0b18', dot: 'animate-pulse' },
  REMEDIATING:   { label: 'Remediating',   color: '#8b5cf6', bg: '#8b5cf618', dot: 'animate-pulse' },
  RESOLVED:      { label: 'Resolved',      color: '#22c55e', bg: '#22c55e18', dot: '' },
  ESCALATED:     { label: 'Escalated',     color: '#ef4444', bg: '#ef444418', dot: '' },
  FAILED:        { label: 'Failed',        color: '#ef4444', bg: '#ef444418', dot: '' },
}

export default function StatusBadge({ status, size = 'sm' }) {
  const cfg = STATUS_CONFIG[status] || { label: status, color: '#6b6b7e', bg: '#6b6b7e18', dot: '' }
  const textSize = size === 'xs' ? 'text-[10px]' : 'text-xs'

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-mono ${textSize} font-medium`}
      style={{ color: cfg.color, backgroundColor: cfg.bg, border: `1px solid ${cfg.color}28` }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`}
        style={{ backgroundColor: cfg.color }}
      />
      {cfg.label}
    </span>
  )
}
