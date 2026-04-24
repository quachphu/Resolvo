from fastapi import APIRouter, HTTPException
from db.supabase_client import get_incident, get_all_incidents, get_incident_stats

router = APIRouter()


@router.get("/stats")
async def get_stats():
    """Aggregated stats for today's incidents (for MetricsBar)."""
    return await get_incident_stats()


@router.get("")
async def list_incidents(limit: int = 50):
    """List all incidents ordered by most recent first."""
    incidents = await get_all_incidents(limit=limit)
    return {"incidents": incidents, "total": len(incidents)}


@router.get("/{incident_id}")
async def get_incident_detail(incident_id: str):
    """Get full incident detail including reasoning trace and post-mortem."""
    incident = await get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incident
