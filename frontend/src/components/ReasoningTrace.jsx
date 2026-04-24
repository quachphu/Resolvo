import { useState, useEffect, useRef } from 'react'
import { api } from '../lib/api'

const TERMINAL_STATUSES = ['RESOLVED', 'ESCALATED', 'FAILED']

function getStepIcon(step) {
  const s = step.toLowerCase()
  if (s.includes('reading') || s.includes('analyzing') || s.includes('waking')) return '🔍'
  if (s.includes('commit') || s.includes('github') || s.includes('diff')) return '📋'
  if (s.includes('executing') || s.includes('restarting') || s.includes('scaling') || s.includes('creating pr') || s.includes('rolling')) return '⚡'
  if (s.includes('hypothesis') || s.includes('root cause') || s.includes('assessment') || s.includes('blast radius')) return '🧠'
  if (s.includes('✅') || s.includes('resolved') || s.includes('healthy') || s.includes('success')) return '✅'
  if (s.includes('🔴') || s.includes('escalat') || s.includes('human')) return '🔴'
  if (s.includes('confidence') || s.includes('cgev') || s.includes('score')) return '📊'
  if (s.includes('slack') || s.includes('notif')) return '💬'
  if (s.includes('post-mortem') || s.includes('postmortem')) return '📄'
  if (s.includes('log') || s.includes('pod')) return '🖥️'
  return '›'
}

function ConfidenceBar({ step }) {
  const match = step.match(/(\d+)\/100/)
  if (!match) return null
  const score = parseInt(match[1])
  const color = score >= 75 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444'
  const label = score >= 75 ? 'Auto-remediate ✓' : score >= 50 ? 'Low confidence' : 'Escalating'
  return (
    <div className="mt-2 ml-6">
      <div className="flex items-center justify-between text-xs mb-1">
        <span style={{ color }} className="font-semibold">CGEV Score: {score}/100</span>
        <span style={{ color }} className="text-xs">{label}</span>
      </div>
      <div className="h-1.5 bg-[#1e1e24] rounded-full overflow-hidden w-48">
        <div
          className="h-full rounded-full confidence-bar"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

function TraceStep({ step, index, animate }) {
  const icon = getStepIcon(step.step || step)
  const text = step.step || step
  const ts = step.timestamp || ''
  const isConfidence = text.toLowerCase().includes('cgev') || text.toLowerCase().includes('confidence score')
  const isError = text.includes('⚠️') || text.includes('failed') || text.toLowerCase().includes('error')
  const isSuccess = text.includes('✅')
  const isEscalate = text.includes('🔴') || text.toLowerCase().includes('escalat')

  const textColor = isError
    ? 'text-red-400'
    : isSuccess
    ? 'text-green-400'
    : isEscalate
    ? 'text-red-400'
    : 'text-[#c8c8d8]'

  return (
    <div
      className={`flex gap-3 py-1.5 px-4 hover:bg-white/[0.02] group trace-step`}
      style={{ animationDelay: animate ? `${index * 30}ms` : '0ms' }}
    >
      <span className="text-[#6b6b7e] text-xs font-mono shrink-0 mt-0.5 w-16 text-right">
        {ts}
      </span>
      <span className="text-base leading-none mt-0.5 shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <span className={`font-mono text-xs leading-relaxed ${textColor}`}>{text}</span>
        {isConfidence && <ConfidenceBar step={text} />}
      </div>
    </div>
  )
}

export default function ReasoningTrace({ incident }) {
  const [liveTrace, setLiveTrace] = useState([])
  const [streamStatus, setStreamStatus] = useState(null)
  const bottomRef = useRef(null)
  const streamRef = useRef(null)
  const prevIdRef = useRef(null)

  const isTerminal = TERMINAL_STATUSES.includes(incident?.status)

  useEffect(() => {
    if (!incident?.id) return

    // Reset trace when switching incidents
    if (prevIdRef.current !== incident.id) {
      prevIdRef.current = incident.id
      setLiveTrace(incident.reasoning_trace || [])
      setStreamStatus(incident.status)

      // Close any existing stream
      if (streamRef.current) {
        streamRef.current()
        streamRef.current = null
      }

      // Don't stream if already terminal
      if (TERMINAL_STATUSES.includes(incident.status)) return

      // Open SSE stream
      let seenCount = (incident.reasoning_trace || []).length
      const stop = api.streamIncident(incident.id, (event) => {
        if (event.type === 'trace') {
          setLiveTrace((prev) => {
            const exists = prev.some(
              (s) => (s.step || s) === event.step && (s.timestamp || '') === event.timestamp,
            )
            if (exists) return prev
            return [...prev, { step: event.step, timestamp: event.timestamp }]
          })
        } else if (event.type === 'status') {
          setStreamStatus(event.status)
        } else if (event.type === 'complete') {
          setStreamStatus(event.status)
          if (streamRef.current) {
            streamRef.current()
            streamRef.current = null
          }
        }
      })
      streamRef.current = stop
    } else {
      // Same incident — merge any new trace steps from props
      setLiveTrace((prev) => {
        const incoming = incident.reasoning_trace || []
        if (incoming.length > prev.length) return incoming
        return prev
      })
      if (isTerminal) setStreamStatus(incident.status)
    }

    return () => {
      if (streamRef.current) {
        streamRef.current()
        streamRef.current = null
      }
    }
  }, [incident?.id, incident?.status, incident?.reasoning_trace?.length]) // eslint-disable-line

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [liveTrace.length])

  const displayStatus = streamStatus || incident?.status || 'INVESTIGATING'
  const statusColor = {
    INVESTIGATING: '#f59e0b',
    REMEDIATING: '#8b5cf6',
    RESOLVED: '#22c55e',
    ESCALATED: '#ef4444',
    FAILED: '#ef4444',
  }[displayStatus] || '#6b6b7e'

  const title = incident?.title || 'Untitled incident'
  const service = incident?.service || 'unknown'

  return (
    <div className="flex-1 flex flex-col overflow-hidden grid-bg">
      {/* Panel header */}
      <div className="px-4 py-3 border-b border-[#1e1e24] bg-[#0a0a0b]/80 backdrop-blur-sm shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: statusColor }}
            />
            <span className="font-mono text-xs text-[#6b6b7e]">{service}</span>
            <span className="text-[#1e1e24]">/</span>
            <span className="font-mono text-xs text-[#c8c8d8] truncate max-w-sm">{title}</span>
          </div>
          <div className="flex items-center gap-3">
            {!isTerminal && displayStatus !== 'FAILED' && (
              <span className="flex items-center gap-1.5 text-xs text-amber-400">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                Agent active
              </span>
            )}
            <span
              className="text-xs font-mono px-2 py-0.5 rounded"
              style={{ color: statusColor, backgroundColor: `${statusColor}18`, border: `1px solid ${statusColor}30` }}
            >
              {displayStatus}
            </span>
          </div>
        </div>
      </div>

      {/* Trace log */}
      <div className="flex-1 overflow-y-auto py-3">
        {liveTrace.length === 0 ? (
          <div className="flex items-center gap-3 px-4 py-2">
            <span className="text-[#6b6b7e] text-xs font-mono">
              <span className="animate-blink">▊</span>
            </span>
            <span className="text-[#6b6b7e] text-xs font-mono">Agent initializing...</span>
          </div>
        ) : (
          liveTrace.map((step, i) => (
            <TraceStep
              key={i}
              step={step}
              index={i}
              animate={i >= liveTrace.length - 5}
            />
          ))
        )}

        {/* Live cursor */}
        {!isTerminal && (
          <div className="flex gap-3 px-4 py-1.5">
            <span className="text-[#6b6b7e] text-xs font-mono w-16 text-right shrink-0" />
            <span className="font-mono text-xs text-purple-400">
              <span className="animate-blink">▊</span>
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Bottom status bar */}
      <div className="px-4 py-2 border-t border-[#1e1e24] bg-[#0a0a0b]/60 shrink-0 flex items-center justify-between">
        <span className="font-mono text-xs text-[#6b6b7e]">
          {liveTrace.length} steps
        </span>
        {incident?.confidence_score != null && (
          <span className="font-mono text-xs" style={{ color: statusColor }}>
            CGEV {incident.confidence_score}/100
          </span>
        )}
        {incident?.pr_url && (
          <a
            href={incident.pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-mono text-blue-400 hover:text-blue-300 underline"
          >
            View PR →
          </a>
        )}
      </div>
    </div>
  )
}
