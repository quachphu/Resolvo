import IncidentCard from './IncidentCard'

const ORDER = ['INVESTIGATING', 'REMEDIATING', 'ESCALATED', 'RESOLVED', 'FAILED']

function sortIncidents(incidents) {
  return [...incidents].sort((a, b) => {
    const ai = ORDER.indexOf(a.status)
    const bi = ORDER.indexOf(b.status)
    if (ai !== bi) return ai - bi
    return new Date(b.started_at) - new Date(a.started_at)
  })
}

export default function IncidentList({ incidents, selectedId, onSelect, loading }) {
  const sorted = sortIncidents(incidents)
  const active = sorted.filter((i) => ['INVESTIGATING', 'REMEDIATING'].includes(i.status))
  const completed = sorted.filter((i) => !['INVESTIGATING', 'REMEDIATING'].includes(i.status))

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-xs text-[#6b6b7e] font-mono animate-pulse">Loading incidents...</span>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Active incidents */}
      {active.length > 0 && (
        <div>
          <div className="px-3 pt-3 pb-1.5">
            <span className="text-[10px] font-mono text-[#6b6b7e] uppercase tracking-wider">
              Active · {active.length}
            </span>
          </div>
          <div className="space-y-0.5 px-2">
            {active.map((incident) => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                selected={incident.id === selectedId}
                onClick={() => onSelect(incident.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Completed incidents */}
      {completed.length > 0 && (
        <div>
          <div className="px-3 pt-4 pb-1.5">
            <span className="text-[10px] font-mono text-[#6b6b7e] uppercase tracking-wider">
              History · {completed.length}
            </span>
          </div>
          <div className="space-y-0.5 px-2 pb-4">
            {completed.map((incident) => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                selected={incident.id === selectedId}
                onClick={() => onSelect(incident.id)}
              />
            ))}
          </div>
        </div>
      )}

      {incidents.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <span className="text-2xl mb-2">🟢</span>
          <p className="text-xs text-[#6b6b7e]">No incidents yet.</p>
          <p className="text-xs text-[#6b6b7e]">Trigger a demo →</p>
        </div>
      )}
    </div>
  )
}
