import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from models import AlertPayload, IncidentStatus
from db.supabase_client import create_incident, update_incident, append_trace_step, get_incident
from agent.investigator import investigate_incident
from agent.remediator import execute_remediation
from agent.postmortem import generate_postmortem
from integrations.slack import post_resolution, post_escalation
from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Pre-built demo scenarios ─────────────────────────────────────────────────

DEMO_SCENARIOS = {
    "crashloop": AlertPayload(
        source="sentry",
        service="payment-service",
        severity="critical",
        title="payment-service CrashLoopBackOff — 500 errors on /api/payments",
        description="payment-service pod has restarted 5 times in the last 10 minutes. "
                    "Error: NullPointerException in PaymentHandler.process() at line 47. "
                    "All payment processing is down. ~3,200 users affected.",
        namespace="default",
        pod_name="payment-service",
        deployment_name="payment-service",
    ),
    "oom": AlertPayload(
        source="datadog",
        service="memory-hog-service",
        severity="high",
        title="memory-hog-service OOMKilled — memory spike to 98%",
        description="memory-hog-service pod was OOM-killed. Container exceeded memory limit of 32Mi. "
                    "Exit code 137 (SIGKILL). Service is restarting but will OOM again without intervention. "
                    "Affecting ~800 users.",
        namespace="default",
        pod_name="memory-hog-service",
        deployment_name="memory-hog-service",
    ),
    "deadlock": AlertPayload(
        source="prometheus",
        service="db-service",
        severity="critical",
        title="db-service DEADLOCK — transaction lock contention detected",
        description="DEADLOCK detected: transaction T1 waiting for lock held by T2; "
                    "T2 waiting for lock held by T1. All connection pool slots occupied (50/50). "
                    "Database queries timing out. Manual DBA intervention may be required. "
                    "~12,000 users affected across 4 services.",
        namespace="default",
        pod_name="db-service",
        deployment_name="db-service",
    ),
}


@router.post("/alert")
async def receive_alert(alert: AlertPayload, background_tasks: BackgroundTasks):
    """Receive an alert from any monitoring tool and spin up an incident agent."""
    incident_data = {
        "status": IncidentStatus.INVESTIGATING.value,
        "source": alert.source,
        "service": alert.service,
        "severity": alert.severity,
        "title": alert.title,
        "description": alert.description,
        "namespace": alert.namespace or "default",
        "pod_name": alert.pod_name,
        "deployment_name": alert.deployment_name,
        "reasoning_trace": [],
        "started_at": datetime.utcnow().isoformat(),
    }

    incident = await create_incident(incident_data)
    incident_id = incident["id"]
    logger.info(f"Created incident {incident_id} for {alert.service}")

    background_tasks.add_task(run_incident_agent, incident_id, alert)

    return {
        "incident_id": incident_id,
        "status": "investigating",
        "message": f"Resolvo is investigating {alert.service}",
    }


@router.post("/simulate/{scenario}")
async def simulate_scenario(scenario: str, background_tasks: BackgroundTasks):
    """Trigger a pre-built demo scenario by name: crashloop | oom | deadlock"""
    if scenario not in DEMO_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario '{scenario}'. Valid: {list(DEMO_SCENARIOS.keys())}",
        )

    alert = DEMO_SCENARIOS[scenario]
    incident_data = {
        "status": IncidentStatus.INVESTIGATING.value,
        "source": alert.source,
        "service": alert.service,
        "severity": alert.severity,
        "title": alert.title,
        "description": alert.description,
        "namespace": alert.namespace or "default",
        "pod_name": alert.pod_name,
        "deployment_name": alert.deployment_name,
        "reasoning_trace": [],
        "started_at": datetime.utcnow().isoformat(),
    }

    incident = await create_incident(incident_data)
    incident_id = incident["id"]
    logger.info(f"Simulated scenario '{scenario}' as incident {incident_id}")

    background_tasks.add_task(run_incident_agent, incident_id, alert)

    return {
        "incident_id": incident_id,
        "scenario": scenario,
        "status": "investigating",
        "message": f"Demo scenario '{scenario}' started for {alert.service}",
    }


async def run_incident_agent(incident_id: str, alert: AlertPayload):
    """
    Full end-to-end agent pipeline:
    1. Investigate (agentic loop with trace callbacks)
    2. Remediate (based on investigation result)
    3. Generate post-mortem
    4. Notify Slack
    5. Update Supabase with final state
    """
    logger.info(f"Starting agent for incident {incident_id}")

    async def trace_callback(step: str):
        """Append a step to the reasoning trace in Supabase."""
        trace_entry = {
            "step": step,
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
        }
        try:
            await append_trace_step(incident_id, trace_entry)
        except Exception as e:
            logger.error(f"Failed to append trace step: {e}")

    try:
        # ── Phase 1: Investigation ─────────────────────────────────────────
        investigation = await investigate_incident(incident_id, alert, trace_callback)

        # Update Supabase with investigation results
        await update_incident(incident_id, {
            "status": IncidentStatus.REMEDIATING.value,
            "root_cause": investigation.root_cause,
            "root_cause_type": investigation.root_cause_type,
            "confidence_score": investigation.confidence_score,
            "blast_radius": investigation.blast_radius,
        })

        # ── Phase 2: Remediation ───────────────────────────────────────────
        remediation = await execute_remediation(
            incident_id=incident_id,
            alert=alert,
            investigation=investigation,
            trace_callback=trace_callback,
        )

        # Calculate cost estimate
        incident_record = await get_incident(incident_id)
        started_at = datetime.fromisoformat(
            (incident_record.get("started_at") or datetime.utcnow().isoformat()).replace("Z", "+00:00")
        )
        duration_minutes = (datetime.utcnow() - started_at.replace(tzinfo=None)).total_seconds() / 60
        cost_estimate = (duration_minutes * settings.REVENUE_PER_MINUTE) + (
            (duration_minutes / 60) * settings.ENGINEER_HOURLY_RATE
        )

        # Determine final status
        is_resolved = remediation.action != "escalate"
        final_status = IncidentStatus.RESOLVED if is_resolved else IncidentStatus.ESCALATED
        resolved_at = datetime.utcnow().isoformat() if is_resolved else None

        kubectl_cmd = investigation.kubectl_command or (
            f"kubectl rollout undo deployment/{alert.deployment_name or alert.service} -n {alert.namespace or 'default'}"
            if not is_resolved else None
        )

        # ── Phase 3: Update Supabase ────────────────────────────────────────
        updates: dict = {
            "status": final_status.value,
            "remediation_action": remediation.action,
            "remediation_result": remediation.message or "",
            "cost_estimate": round(cost_estimate, 2),
            "kubectl_command": kubectl_cmd,
        }
        if resolved_at:
            updates["resolved_at"] = resolved_at
        if remediation.pr_url:
            updates["pr_url"] = remediation.pr_url
        if investigation.escalation_reason:
            updates["remediation_result"] = investigation.escalation_reason

        await update_incident(incident_id, updates)

        # ── Phase 4: Post-mortem ────────────────────────────────────────────
        full_incident = await get_incident(incident_id)
        try:
            postmortem = await generate_postmortem(full_incident)
            await update_incident(incident_id, {"postmortem": postmortem})
        except Exception as pm_err:
            logger.error(f"Post-mortem generation failed: {pm_err}")

        # ── Phase 5: Slack notification ─────────────────────────────────────
        slack_sent = False
        try:
            full_incident = await get_incident(incident_id)
            if is_resolved:
                await trace_callback(f"✅ Incident resolved. Notifying Slack...")
                slack_sent = await post_resolution(full_incident)
            else:
                await trace_callback(f"🔴 Escalating to human. Notifying Slack...")
                slack_sent = await post_escalation(full_incident)
        except Exception as slack_err:
            logger.error(f"Slack notification failed: {slack_err}")

        await update_incident(incident_id, {"slack_message_sent": slack_sent})

        # ── Final trace step ────────────────────────────────────────────────
        if is_resolved:
            await trace_callback(
                f"✅ Incident resolved in {int(duration_minutes)}m. "
                f"Post-mortem generated. Slack notified. No human required."
            )
        else:
            await trace_callback(
                f"🔴 Escalated to on-call engineer. Full briefing sent to Slack. "
                f"CGEV score: {investigation.confidence_score}/100."
            )

        logger.info(f"Incident {incident_id} completed with status {final_status.value}")

    except Exception as e:
        logger.error(f"Agent failed for incident {incident_id}: {e}", exc_info=True)
        await trace_callback(f"⚠️  Agent encountered an error: {str(e)[:200]}")
        try:
            await update_incident(incident_id, {"status": IncidentStatus.FAILED.value})
        except Exception:
            pass
