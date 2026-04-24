const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = {
  async getIncidents() {
    const res = await fetch(`${BASE_URL}/api/v1/incidents`)
    if (!res.ok) throw new Error('Failed to fetch incidents')
    return res.json()
  },

  async getIncident(id) {
    const res = await fetch(`${BASE_URL}/api/v1/incidents/${id}`)
    if (!res.ok) throw new Error(`Failed to fetch incident ${id}`)
    return res.json()
  },

  async getStats() {
    const res = await fetch(`${BASE_URL}/api/v1/incidents/stats`)
    if (!res.ok) throw new Error('Failed to fetch stats')
    return res.json()
  },

  async triggerScenario(scenario) {
    const res = await fetch(`${BASE_URL}/api/v1/webhook/simulate/${scenario}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to trigger ${scenario}`)
    }
    return res.json()
  },

  streamIncident(incidentId, onEvent) {
    const url = `${BASE_URL}/api/v1/stream/${incidentId}`
    const es = new EventSource(url)

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onEvent(data)
      } catch (e) {
        console.error('SSE parse error:', e)
      }
    }

    es.onerror = (err) => {
      console.error('SSE error:', err)
      es.close()
    }

    return () => es.close()
  },
}
