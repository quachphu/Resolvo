import StatusBadge from './StatusBadge'

const SEVERITY_COLORS = {
  critical: '#ef4444',
  high: '#f59e0b',
  medium: '#3b82f6',
  low: '#6b6b7e',
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function resolveDuration(startStr, endStr) {
  if (!startStr || !endStr) return null
  const secs = Math.floor((new Date(endStr) - new Date(startStr)) / 1000)
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function IncidentCard({ incident, onClick, selected, expanded }) {
  const severityColor = SEVERITY_COLORS[incident.severity] || '#6b6b7e'
  const duration = resolveDuration(incident.started_at, incident.resolved_at)
  const isTerminal = ['RESOLVED', 'ESCALATED', 'FAILED'].includes(incident.status)

  return (
    <div
      onClick={onClick}
      className={`
        w-full text-left transition-colors rounded-lg border
        ${onClick ? 'cursor-pointer hover:bg-white/[0.03]' : ''}
        ${selected ? 'bg-purple-600/10 border-purple-600/30' : 'bg-transparent border-transparent'}
        ${!expanded ? 'p-3' : 'p-0 border-none'}
      `}
    >
      {/* Severity dot + service */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: severityColor }}
          />
          <span className="text-xs font-mono text-[#6b6b7e] truncate">{incident.service}</span>
        </div>
        <StatusBadge status={incident.status} size="xs" />
      </div>

      {/* Title */}
      <p className={`text-sm text-[#e8e8f0] font-medium leading-snug ${!expanded ? 'line-clamp-1' : ''}`}>
        {incident.title}
      </p>

      {/* Metadata row */}
      <div className="flex items-center gap-3 mt-1.5 text-[10px] font-mono text-[#6b6b7e]">
        <span>{timeAgo(incident.started_at)}</span>
        {duration && isTerminal && (
          <span>resolved in {duration}</span>
        )}
        {incident.confidence_score != null && (
          <span className="ml-auto">
            CGEV {incident.confidence_score}/100
          </span>
        )}
      </div>

      {/* Expanded details */}
      {expanded && incident.root_cause && (
        <div className="mt-3 space-y-2">
          <div>
            <p className="text-[10px] text-[#6b6b7e] font-mono uppercase tracking-wider mb-1">Root Cause</p>
            <p className="text-xs text-[#c8c8d8] leading-relaxed">{incident.root_cause}</p>
          </div>
          {incident.remediation_action && (
            <div>
              <p className="text-[10px] text-[#6b6b7e] font-mono uppercase tracking-wider mb-1">Remediation</p>
              <p className="text-xs font-mono text-purple-400">
                {incident.remediation_action.replace(/_/g, ' ')}
              </p>
            </div>
          )}
          {incident.blast_radius && (
            <div>
              <p className="text-[10px] text-[#6b6b7e] font-mono uppercase tracking-wider mb-1">Blast Radius</p>
              <p className="text-xs text-[#c8c8d8]">{incident.blast_radius}</p>
            </div>
          )}
          {incident.kubectl_command && incident.status === 'ESCALATED' && (
            <div>
              <p className="text-[10px] text-[#6b6b7e] font-mono uppercase tracking-wider mb-1">Suggested Fix</p>
              <code className="block text-xs font-mono bg-[#0a0a0b] border border-[#1e1e24] rounded px-2 py-1.5 text-amber-400 break-all">
                {incident.kubectl_command}
              </code>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
