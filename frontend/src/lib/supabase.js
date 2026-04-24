import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null

/**
 * Subscribe to realtime changes on the incidents table.
 * Calls onInsert when a new incident is created,
 * onUpdate when an existing incident is modified.
 */
export function subscribeToIncidents({ onInsert, onUpdate }) {
  if (!supabase) {
    console.warn('Supabase not configured — realtime disabled')
    return () => {}
  }

  const channel = supabase
    .channel('incidents-realtime')
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'incidents' },
      (payload) => onInsert(payload.new),
    )
    .on(
      'postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'incidents' },
      (payload) => onUpdate(payload.new),
    )
    .subscribe()

  return () => supabase.removeChannel(channel)
}
