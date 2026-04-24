from supabase import create_client, Client
from config import settings
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _client


async def create_incident(incident_data: dict) -> dict:
    client = get_supabase()
    result = client.table("incidents").insert(incident_data).execute()
    if result.data:
        return result.data[0]
    raise Exception("Failed to create incident")


async def update_incident(incident_id: str, updates: dict) -> dict:
    client = get_supabase()
    result = client.table("incidents").update(updates).eq("id", incident_id).execute()
    if result.data:
        return result.data[0]
    raise Exception(f"Failed to update incident {incident_id}")


async def get_incident(incident_id: str) -> Optional[dict]:
    client = get_supabase()
    result = client.table("incidents").select("*").eq("id", incident_id).execute()
    if result.data:
        return result.data[0]
    return None


async def get_all_incidents(limit: int = 50) -> List[dict]:
    client = get_supabase()
    result = (
        client.table("incidents")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


async def append_trace_step(incident_id: str, step: dict) -> None:
    """Append a single trace step to the reasoning_trace JSONB array."""
    client = get_supabase()
    # Fetch current trace
    current = client.table("incidents").select("reasoning_trace").eq("id", incident_id).execute()
    if not current.data:
        logger.error(f"Incident {incident_id} not found for trace update")
        return

    trace = current.data[0].get("reasoning_trace") or []
    trace.append(step)

    client.table("incidents").update({"reasoning_trace": trace}).eq("id", incident_id).execute()


async def get_incident_stats() -> dict:
    """Get aggregated stats for today's incidents."""
    from datetime import date
    client = get_supabase()
    today = date.today().isoformat()

    result = (
        client.table("incidents")
        .select("status, cost_estimate, started_at, resolved_at")
        .gte("started_at", f"{today}T00:00:00")
        .execute()
    )
    incidents = result.data or []

    total_today = len(incidents)
    resolved_auto = sum(1 for i in incidents if i["status"] == "RESOLVED")
    escalated = sum(1 for i in incidents if i["status"] == "ESCALATED")
    cost_avoided = sum(
        (i.get("cost_estimate") or 0.0)
        for i in incidents
        if i["status"] == "RESOLVED"
    )

    # Hours saved = 45 min per resolved incident (average manual triage time)
    hours_saved = resolved_auto * 0.75

    return {
        "total_today": total_today,
        "resolved_auto": resolved_auto,
        "escalated": escalated,
        "cost_avoided": round(cost_avoided, 2),
        "hours_saved": round(hours_saved, 2),
    }
