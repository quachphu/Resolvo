import { useState, useEffect, useRef } from 'react'

const REVENUE_PER_MINUTE = 50    // $/min downtime
const ENGINEER_HOURLY_RATE = 150  // $/hr for engineer time

function formatDollar(amount) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

function calcCost(secondsElapsed) {
  const minutes = secondsElapsed / 60
  const hours = secondsElapsed / 3600
  return minutes * REVENUE_PER_MINUTE + hours * ENGINEER_HOURLY_RATE
}

export default function CostMeter({ incident }) {
  const [elapsed, setElapsed] = useState(0)
  const [frozen, setFrozen] = useState(false)
  const [finalCost, setFinalCost] = useState(null)
  const intervalRef = useRef(null)

  const isResolved = incident?.status === 'RESOLVED'
  const isEscalated = incident?.status === 'ESCALATED'
  const isTerminal = isResolved || isEscalated || incident?.status === 'FAILED'

  useEffect(() => {
    if (!incident?.started_at) return

    const start = new Date(incident.started_at).getTime()

    if (isTerminal) {
      // Freeze at actual resolution time
      const end = incident.resolved_at
        ? new Date(incident.resolved_at).getTime()
        : Date.now()
      const secs = Math.max(0, (end - start) / 1000)
      setElapsed(secs)
      setFinalCost(calcCost(secs))
      setFrozen(true)
      return
    }

    // Tick every second
    const tick = () => {
      const secs = Math.max(0, (Date.now() - start) / 1000)
      setElapsed(secs)
    }
    tick()
    intervalRef.current = setInterval(tick, 1000)
    setFrozen(false)

    return () => clearInterval(intervalRef.current)
  }, [incident?.id, incident?.started_at, isTerminal, incident?.resolved_at])

  const displayCost = frozen && finalCost != null ? finalCost : calcCost(elapsed)

  const minutes = Math.floor(elapsed / 60)
  const seconds = Math.floor(elapsed % 60)
  const elapsedLabel = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`

  return (
    <div className="space-y-2">
      <p className="text-xs text-[#6b6b7e] font-mono uppercase tracking-wider mb-2">
        Incident Cost
      </p>

      {isResolved ? (
        /* Resolved — flip to green */
        <div className="rounded-lg border border-green-500/30 bg-green-500/5 px-3 py-3 glow-green">
          <div className="text-green-400 font-mono text-xs mb-1">Resolved — saved ~</div>
          <div className="text-green-400 font-mono text-2xl font-bold">
            {formatDollar(displayCost)}
          </div>
          <div className="text-green-400/60 font-mono text-xs mt-1">
            in {elapsedLabel} • no engineer required
          </div>
        </div>
      ) : isEscalated ? (
        /* Escalated — show cost with escalation context */
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-3">
          <div className="text-red-400 font-mono text-xs mb-1">Escalated after</div>
          <div className="text-red-400 font-mono text-2xl font-bold">
            {formatDollar(displayCost)}
          </div>
          <div className="text-red-400/60 font-mono text-xs mt-1">
            {elapsedLabel} • engineer paged
          </div>
        </div>
      ) : (
        /* Active — live ticking counter */
        <div className="rounded-lg border border-[#1e1e24] bg-[#0a0a0b] px-3 py-3">
          <div className="text-[#6b6b7e] font-mono text-xs mb-1">
            Downtime cost accumulating
          </div>
          <div className="text-red-400 font-mono text-2xl font-bold cost-pulse">
            {formatDollar(displayCost)}
          </div>
          <div className="text-[#6b6b7e] font-mono text-xs mt-1">
            {elapsedLabel} elapsed
          </div>
        </div>
      )}

      {/* Breakdown */}
      <div className="space-y-1 pt-1">
        <div className="flex justify-between text-xs font-mono text-[#6b6b7e]">
          <span>Revenue loss</span>
          <span>{formatDollar((elapsed / 60) * REVENUE_PER_MINUTE)}</span>
        </div>
        <div className="flex justify-between text-xs font-mono text-[#6b6b7e]">
          <span>Eng time</span>
          <span>{formatDollar((elapsed / 3600) * ENGINEER_HOURLY_RATE)}</span>
        </div>
      </div>
    </div>
  )
}
