import { ExternalLink } from 'lucide-react'

const ACTION_LABELS = {
  revert_pr: 'Revert PR created',
  pod_restart: 'Pod restarted',
  scale_up: 'Deployment scaled up',
  rollback: 'Deployment rolled back',
  escalate: 'Escalated to human',
}

function formatCost(amount) {
  if (!amount) return '$0'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount)
}

function resolveDuration(startStr, endStr) {
  if (!startStr) return '?'
  const end = endStr ? new Date(endStr) : new Date()
  const secs = Math.floor((end - new Date(startStr)) / 1000)
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function SlackPreview({ incident }) {
  if (!incident) return null

  const isResolved = incident.status === 'RESOLVED'
  const isEscalated = incident.status === 'ESCALATED'
  const duration = resolveDuration(incident.started_at, incident.resolved_at)
  const actionLabel = ACTION_LABELS[incident.remediation_action] || incident.remediation_action

  return (
    <div>
      <p className="text-[10px] font-mono text-[#6b6b7e] uppercase tracking-wider mb-2">
        Slack notification sent
      </p>

      {/* Slack-styled message block */}
      <div className="rounded-lg border border-[#1e1e24] bg-[#1a1a21] overflow-hidden">
        {/* Slack top bar */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[#1e1e24] bg-[#0f0f14]">
          <div className="w-5 h-5 rounded-md bg-purple-600 flex items-center justify-center text-white text-xs font-bold">
            R
          </div>
          <span className="text-xs font-semibold text-[#e8e8f0]">Resolvo</span>
          <span className="text-[10px] text-[#6b6b7e] ml-auto font-mono">
            #{incident.service?.replace(/\s/g, '-').toLowerCase()}
          </span>
        </div>

        {/* Message body */}
        <div className="px-3 py-3 space-y-2.5">
          {/* Header */}
          <div
            className="flex items-center gap-2 text-sm font-semibold"
            style={{ color: isResolved ? '#22c55e' : '#ef4444' }}
          >
            <span>{isResolved ? '🟢' : '🔴'}</span>
            <span>
              {isResolved
                ? 'INCIDENT RESOLVED — No human required'
                : 'INCIDENT ESCALATED — Human review required'}
            </span>
          </div>

          {/* Fields */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
            <SlackField label="Service" value={incident.service} mono />
            <SlackField
              label="Confidence"
              value={`${incident.confidence_score ?? '?'}/100`}
              mono
              color={isResolved ? '#22c55e' : '#ef4444'}
            />
            {isResolved ? (
              <>
                <SlackField label="Fix applied" value={actionLabel} />
                <SlackField label="Time to resolve" value={duration} mono />
                <SlackField
                  label="Cost avoided"
                  value={`~${formatCost(incident.cost_estimate)}`}
                  color="#22c55e"
                />
              </>
            ) : (
              <>
                <SlackField label="Status" value="Awaiting human" />
                <SlackField label="Duration" value={duration} mono />
              </>
            )}
          </div>

          {/* Root cause */}
          {incident.root_cause && (
            <div>
              <p className="text-[10px] text-[#6b6b7e] mb-0.5">Root cause</p>
              <p className="text-xs text-[#c8c8d8] leading-relaxed">{incident.root_cause}</p>
            </div>
          )}

          {/* Escalation reason */}
          {isEscalated && incident.remediation_result && (
            <div>
              <p className="text-[10px] text-[#6b6b7e] mb-0.5">Why I didn't auto-fix</p>
              <p className="text-xs text-[#c8c8d8]">{incident.remediation_result}</p>
            </div>
          )}

          {/* kubectl command */}
          {isEscalated && incident.kubectl_command && (
            <div>
              <p className="text-[10px] text-[#6b6b7e] mb-0.5">Command to run</p>
              <code className="block text-xs font-mono bg-[#0a0a0b] border border-[#1e1e24] rounded px-2 py-1.5 text-amber-400 break-all">
                {incident.kubectl_command}
              </code>
            </div>
          )}

          {/* CTA buttons */}
          <div className="flex gap-2 pt-1">
            {incident.pr_url && (
              <a
                href={incident.pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs px-2.5 py-1 rounded border border-blue-500/40 text-blue-400 hover:bg-blue-500/10 transition-colors font-mono"
              >
                Review PR <ExternalLink size={10} />
              </a>
            )}
            <button className="flex items-center gap-1 text-xs px-2.5 py-1 rounded border border-[#1e1e24] text-[#6b6b7e] hover:bg-white/[0.04] transition-colors font-mono">
              View trace →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SlackField({ label, value, mono, color }) {
  return (
    <div>
      <p className="text-[10px] text-[#6b6b7e]">{label}</p>
      <p
        className={`text-xs ${mono ? 'font-mono' : ''} text-[#e8e8f0]`}
        style={color ? { color } : {}}
      >
        {value}
      </p>
    </div>
  )
}
