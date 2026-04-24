import { useState, useEffect, useCallback } from 'react'
import { api } from './lib/api'
import { subscribeToIncidents } from './lib/supabase'
import MetricsBar from './components/MetricsBar'
import IncidentList from './components/IncidentList'
import ReasoningTrace from './components/ReasoningTrace'
import IncidentCard from './components/IncidentCard'
import CostMeter from './components/CostMeter'
import SlackPreview from './components/SlackPreview'
import TriggerDemo from './components/TriggerDemo'

const ACTIVE_STATUSES = ['INVESTIGATING', 'REMEDIATING']

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const selectedIncident = incidents.find((i) => i.id === selectedId) || null

  // ── Load initial data ──────────────────────────────────────────────────────
  const loadIncidents = useCallback(async () => {
    try {
      const { incidents: data } = await api.getIncidents()
      setIncidents(data)
      // Auto-select the most recent active incident, or just the newest
      if (!selectedId && data.length > 0) {
        const active = data.find((i) => ACTIVE_STATUSES.includes(i.status))
        setSelectedId(active?.id || data[0].id)
      }
    } catch (e) {
      console.error('Failed to load incidents:', e)
    } finally {
      setLoading(false)
    }
  }, [selectedId])

  const loadStats = useCallback(async () => {
    try {
      const data = await api.getStats()
      setStats(data)
    } catch (e) {
      console.error('Failed to load stats:', e)
    }
  }, [])

  useEffect(() => {
    loadIncidents()
    loadStats()

    // Poll for updates every 5s as a fallback if Supabase realtime isn't configured
    const poll = setInterval(() => {
      loadIncidents()
      loadStats()
    }, 5000)

    return () => clearInterval(poll)
  }, []) // eslint-disable-line

  // ── Supabase realtime subscription ────────────────────────────────────────
  useEffect(() => {
    const unsubscribe = subscribeToIncidents({
      onInsert: (newIncident) => {
        setIncidents((prev) => {
          const exists = prev.find((i) => i.id === newIncident.id)
          if (exists) return prev
          return [newIncident, ...prev]
        })
        setSelectedId(newIncident.id)
        loadStats()
      },
      onUpdate: (updatedIncident) => {
        setIncidents((prev) =>
          prev.map((i) => (i.id === updatedIncident.id ? updatedIncident : i)),
        )
        loadStats()
      },
    })
    return unsubscribe
  }, [loadStats])

  const hasActiveIncident = incidents.some((i) => ACTIVE_STATUSES.includes(i.status))

  const handleIncidentTriggered = (newIncident) => {
    setIncidents((prev) => {
      const exists = prev.find((i) => i.id === newIncident.incident_id)
      if (exists) return prev
      // Optimistic insert — will be replaced by realtime/poll
      return [
        {
          id: newIncident.incident_id,
          status: 'INVESTIGATING',
          service: newIncident.message?.split(' ')[2] || 'unknown',
          title: 'Incident triggered...',
          severity: 'critical',
          started_at: new Date().toISOString(),
          reasoning_trace: [],
        },
        ...prev,
      ]
    })
    setSelectedId(newIncident.incident_id)
  }

  return (
    <div className="h-screen flex flex-col bg-[#0a0a0b] text-[#e8e8f0] overflow-hidden">
      {/* ── Top header bar ──────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-5 py-3 border-b border-[#1e1e24] bg-[#111114] shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-purple-600 flex items-center justify-center font-bold text-white text-sm">
            R
          </div>
          <span className="font-semibold text-[#e8e8f0] tracking-tight">Resolvo</span>
          <span className="text-[#6b6b7e] text-xs font-mono">AI On-Call Engineer</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-[#6b6b7e]">
          {hasActiveIncident && (
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
              Investigation active
            </span>
          )}
          <span>Built at HackTech 2026 @ Caltech</span>
        </div>
      </header>

      {/* ── Main 3-column layout ─────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: incident list */}
        <aside className="w-72 flex flex-col border-r border-[#1e1e24] bg-[#111114] shrink-0 overflow-hidden">
          <MetricsBar stats={stats} />
          <IncidentList
            incidents={incidents}
            selectedId={selectedId}
            onSelect={setSelectedId}
            loading={loading}
          />
        </aside>

        {/* Center: reasoning trace */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {selectedIncident ? (
            <ReasoningTrace incident={selectedIncident} />
          ) : (
            <EmptyState />
          )}
        </main>

        {/* Right: details panel */}
        <aside className="w-80 flex flex-col border-l border-[#1e1e24] bg-[#111114] shrink-0 overflow-y-auto">
          <div className="p-4 border-b border-[#1e1e24]">
            <TriggerDemo
              onTriggered={handleIncidentTriggered}
              disabled={hasActiveIncident}
            />
          </div>

          {selectedIncident && (
            <>
              <div className="p-4 border-b border-[#1e1e24]">
                <IncidentCard incident={selectedIncident} expanded />
              </div>
              {ACTIVE_STATUSES.includes(selectedIncident.status) && (
                <div className="p-4 border-b border-[#1e1e24]">
                  <CostMeter incident={selectedIncident} />
                </div>
              )}
              {['RESOLVED', 'ESCALATED'].includes(selectedIncident.status) && (
                <div className="p-4">
                  <SlackPreview incident={selectedIncident} />
                </div>
              )}
            </>
          )}
        </aside>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center grid-bg">
      <div className="text-center">
        <div className="w-16 h-16 rounded-2xl bg-purple-600/10 border border-purple-600/20 flex items-center justify-center mx-auto mb-4">
          <span className="text-3xl">🤖</span>
        </div>
        <p className="text-[#6b6b7e] text-sm">Trigger a demo scenario to see</p>
        <p className="text-[#6b6b7e] text-sm">the agent reasoning in real time</p>
      </div>
    </div>
  )
}
