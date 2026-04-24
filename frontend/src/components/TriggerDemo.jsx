import { useState } from 'react'
import { api } from '../lib/api'

const SCENARIOS = [
  {
    id: 'crashloop',
    label: 'CrashLoop Crash',
    description: 'NullPointerException from bad commit',
    emoji: '🔴',
    color: '#ef4444',
    borderColor: 'border-red-500/30',
    hoverBg: 'hover:bg-red-500/10',
  },
  {
    id: 'oom',
    label: 'Memory OOM Kill',
    description: 'Container exceeded memory limit',
    emoji: '🟡',
    color: '#f59e0b',
    borderColor: 'border-amber-500/30',
    hoverBg: 'hover:bg-amber-500/10',
  },
  {
    id: 'deadlock',
    label: 'DB Deadlock',
    description: 'Lock contention — escalates to human',
    emoji: '🔵',
    color: '#3b82f6',
    borderColor: 'border-blue-500/30',
    hoverBg: 'hover:bg-blue-500/10',
  },
]

export default function TriggerDemo({ onTriggered, disabled }) {
  const [loading, setLoading] = useState(null)
  const [error, setError] = useState(null)

  const handleTrigger = async (scenarioId) => {
    if (disabled || loading) return
    setLoading(scenarioId)
    setError(null)
    try {
      const result = await api.triggerScenario(scenarioId)
      onTriggered?.(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(null)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] font-mono text-[#6b6b7e] uppercase tracking-wider">
          Demo scenarios
        </p>
        <span className="text-[10px] text-[#6b6b7e] font-mono">Minikube</span>
      </div>

      <div className="space-y-1.5">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            onClick={() => handleTrigger(s.id)}
            disabled={!!disabled || !!loading}
            className={`
              w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg border text-left
              transition-all duration-150
              ${s.borderColor} ${s.hoverBg}
              ${disabled || loading ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
              bg-[#0a0a0b]
            `}
          >
            <span className="text-base shrink-0">
              {loading === s.id ? (
                <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" style={{ color: s.color }} />
              ) : (
                s.emoji
              )}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-[#e8e8f0] leading-none mb-0.5">
                {s.label}
              </p>
              <p className="text-[10px] text-[#6b6b7e] font-mono leading-none">{s.description}</p>
            </div>
          </button>
        ))}
      </div>

      {disabled && (
        <p className="text-[10px] text-[#6b6b7e] font-mono mt-2 text-center">
          ← Agent is active. Wait for resolution.
        </p>
      )}

      {error && (
        <p className="text-[10px] text-red-400 font-mono mt-2 text-center">{error}</p>
      )}
    </div>
  )
}
