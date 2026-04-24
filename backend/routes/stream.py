"""
Server-Sent Events (SSE) stream for real-time reasoning trace updates.

GET /stream/{incident_id} — streams trace steps as they are appended to Supabase.
The frontend connects via EventSource and animates each incoming step.
"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from db.supabase_client import get_incident

router = APIRouter()
logger = logging.getLogger(__name__)

POLL_INTERVAL = 0.8  # seconds between Supabase polls
MAX_STREAM_DURATION = 600  # 10 minutes max per stream


async def _event_generator(incident_id: str):
    """
    Poll Supabase for new trace steps and stream them as SSE events.
    Terminates when the incident reaches a terminal state.
    """
    last_trace_count = 0
    start_time = asyncio.get_event_loop().time()
    terminal_states = {"RESOLVED", "ESCALATED", "FAILED"}

    # Send a heartbeat immediately so the browser knows the connection is open
    yield f"data: {json.dumps({'type': 'connected', 'incident_id': incident_id})}\n\n"

    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > MAX_STREAM_DURATION:
            yield f"data: {json.dumps({'type': 'timeout', 'message': 'Stream timeout'})}\n\n"
            break

        try:
            incident = await get_incident(incident_id)
            if not incident:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Incident not found'})}\n\n"
                break

            trace = incident.get("reasoning_trace") or []
            status = incident.get("status", "INVESTIGATING")

            # Stream any new trace steps since last poll
            if len(trace) > last_trace_count:
                new_steps = trace[last_trace_count:]
                for step in new_steps:
                    if isinstance(step, dict):
                        event_data = {
                            "type": "trace",
                            "step": step.get("step", ""),
                            "timestamp": step.get("timestamp", datetime.utcnow().strftime("%H:%M:%S")),
                        }
                    else:
                        event_data = {
                            "type": "trace",
                            "step": str(step),
                            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                        }
                    yield f"data: {json.dumps(event_data)}\n\n"
                last_trace_count = len(trace)

            # Send status update on every poll so frontend stays in sync
            status_event = {
                "type": "status",
                "status": status,
                "confidence_score": incident.get("confidence_score"),
                "root_cause": incident.get("root_cause"),
                "pr_url": incident.get("pr_url"),
                "resolved_at": incident.get("resolved_at"),
            }
            yield f"data: {json.dumps(status_event)}\n\n"

            # Terminal state reached — send final event and close
            if status in terminal_states:
                final_event = {
                    "type": "complete",
                    "status": status,
                    "incident": {
                        "id": incident.get("id"),
                        "status": status,
                        "root_cause": incident.get("root_cause"),
                        "remediation_action": incident.get("remediation_action"),
                        "confidence_score": incident.get("confidence_score"),
                        "pr_url": incident.get("pr_url"),
                        "cost_estimate": incident.get("cost_estimate"),
                        "resolved_at": incident.get("resolved_at"),
                    },
                }
                yield f"data: {json.dumps(final_event)}\n\n"
                break

        except Exception as e:
            logger.error(f"SSE stream error for {incident_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"

        await asyncio.sleep(POLL_INTERVAL)


@router.get("/{incident_id}")
async def stream_incident(incident_id: str):
    """SSE endpoint — connect with EventSource in the browser."""
    return StreamingResponse(
        _event_generator(incident_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
