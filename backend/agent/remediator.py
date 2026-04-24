"""
Remediation executor.

Receives an InvestigationResult and executes the appropriate fix:
  - bad_deployment  → create revert PR on GitHub
  - oom_kill        → restart the pod
  - high_load       → scale up the deployment
  - deadlock/unknown → escalate to human with full briefing
"""

import logging
from typing import Callable, Awaitable

from config import settings
from models import AlertPayload, InvestigationResult, RemediationResult
from integrations import kubernetes_client, github as github_integration

logger = logging.getLogger(__name__)


async def execute_remediation(
    incident_id: str,
    alert: AlertPayload,
    investigation: InvestigationResult,
    trace_callback: Callable[[str], Awaitable[None]],
) -> RemediationResult:
    """
    Decide on and execute the appropriate remediation based on the investigation result.
    Returns a RemediationResult describing what was done.
    """
    namespace = alert.namespace or "default"
    pod_name = alert.pod_name or alert.service
    deployment_name = alert.deployment_name or alert.service
    root_cause_type = investigation.root_cause_type
    confidence = investigation.confidence_score
    threshold = settings.CONFIDENCE_THRESHOLD

    # ── Guard: confidence gating ──────────────────────────────────────────
    if confidence < threshold or root_cause_type == "unknown":
        escalation_reason = investigation.escalation_reason or (
            f"Confidence score {confidence}/100 is below auto-remediation threshold ({threshold}/100)"
        )
        await trace_callback(f"Confidence {confidence}/100 < threshold {threshold}/100 — escalating to human")
        await trace_callback(f"Escalation reason: {escalation_reason}")
        kubectl_cmd = _suggest_kubectl_command(root_cause_type, namespace, pod_name, deployment_name)
        return RemediationResult(
            action="escalate",
            success=False,
            escalation_reason=escalation_reason,
            message=f"Escalated with CGEV score {confidence}/100. {escalation_reason}",
        )

    # ── bad_deployment → revert PR ────────────────────────────────────────
    if root_cause_type == "bad_deployment" and investigation.commit_sha:
        sha = investigation.commit_sha
        short_sha = sha[:7]
        await trace_callback(f"Creating revert PR for commit {short_sha}...")
        pr_url = await github_integration.create_revert_pr(
            repo_name=settings.GITHUB_REPO,
            commit_sha=sha,
            incident_id=incident_id,
            reason=investigation.root_cause,
            confidence=confidence,
        )
        if pr_url:
            await trace_callback(f"✅ Revert PR created: {pr_url}")
            await trace_callback(f"Verifying {alert.service} pod is stabilizing...")
            healthy = await kubernetes_client.wait_for_pod_healthy(namespace, pod_name, timeout=30)
            if healthy:
                await trace_callback(f"✅ {alert.service} pod is Running and healthy.")
            else:
                await trace_callback(f"⚠️  Pod still starting — revert PR is the fix, merge when ready.")
            return RemediationResult(
                action="revert_pr",
                success=True,
                pr_url=pr_url,
                message=f"Revert PR created for commit {short_sha}. Service stabilizing.",
            )
        else:
            await trace_callback("⚠️  PR creation failed — escalating")
            return RemediationResult(
                action="escalate",
                success=False,
                escalation_reason="PR creation failed — manual revert required",
                message="Failed to create revert PR. Manual intervention needed.",
            )

    # ── bad_deployment without commit SHA → rollback deployment ──────────
    if root_cause_type == "bad_deployment":
        await trace_callback(f"No specific commit identified — rolling back deployment {deployment_name}...")
        success = await kubernetes_client.rollback_deployment(namespace, deployment_name)
        if success:
            await trace_callback(f"✅ Deployment {deployment_name} rolled back to previous revision.")
            await trace_callback(f"Monitoring pod health for 30s...")
            healthy = await kubernetes_client.wait_for_pod_healthy(namespace, pod_name, timeout=30)
            status = "healthy" if healthy else "still starting"
            await trace_callback(f"{'✅' if healthy else '⚠️ '} Pod is {status}.")
        else:
            await trace_callback(f"⚠️  Rollback failed — please run: kubectl rollout undo deployment/{deployment_name}")
        return RemediationResult(
            action="rollback",
            success=success,
            message=f"Deployment {deployment_name} {'rolled back' if success else 'rollback failed'}.",
        )

    # ── oom_kill → restart pod ────────────────────────────────────────────
    if root_cause_type == "oom_kill":
        await trace_callback(f"Restarting pod {pod_name} (OOM kill recovery)...")
        success = await kubernetes_client.restart_pod(namespace, pod_name)
        if success:
            await trace_callback(f"Pod {pod_name} deleted — Deployment will recreate it. Monitoring for 30s...")
            healthy = await kubernetes_client.wait_for_pod_healthy(namespace, pod_name, timeout=30)
            if healthy:
                await trace_callback(f"✅ {pod_name} is Running and healthy.")
            else:
                await trace_callback(f"⚠️  Pod still starting — check: kubectl get pods -n {namespace}")
            return RemediationResult(
                action="pod_restart",
                success=healthy,
                message=f"Pod {pod_name} restarted. {'Healthy.' if healthy else 'Monitor manually.'}",
            )
        else:
            await trace_callback(f"⚠️  Pod restart failed — escalating")
            return RemediationResult(
                action="escalate",
                success=False,
                escalation_reason="Pod restart failed — K8s API error",
                message="Pod restart failed. Manual intervention needed.",
            )

    # ── high_load → scale up deployment ──────────────────────────────────
    if root_cause_type == "high_load":
        target_replicas = 3
        await trace_callback(f"Scaling deployment {deployment_name} to {target_replicas} replicas to handle load...")
        success = await kubernetes_client.scale_deployment(namespace, deployment_name, target_replicas)
        if success:
            await trace_callback(f"✅ {deployment_name} scaled to {target_replicas} replicas.")
            await trace_callback(f"Load should distribute across new pods within ~60s.")
        else:
            await trace_callback(f"⚠️  Scale operation failed — try: kubectl scale deployment/{deployment_name} --replicas={target_replicas}")
        return RemediationResult(
            action="scale_up",
            success=success,
            message=f"Deployment {deployment_name} scaled to {target_replicas} replicas.",
        )

    # ── deadlock / fallthrough ────────────────────────────────────────────
    kubectl_cmd = _suggest_kubectl_command(root_cause_type, namespace, pod_name, deployment_name)
    escalation_reason = investigation.escalation_reason or f"Root cause type '{root_cause_type}' requires manual intervention"
    await trace_callback(f"Auto-remediation not available for {root_cause_type} — escalating to human")
    await trace_callback(f"Suggested command: {kubectl_cmd}")
    return RemediationResult(
        action="escalate",
        success=False,
        escalation_reason=escalation_reason,
        message=f"Escalated. Suggested: {kubectl_cmd}",
    )


def _suggest_kubectl_command(
    root_cause_type: str,
    namespace: str,
    pod_name: str,
    deployment_name: str,
) -> str:
    if root_cause_type == "deadlock":
        return f"kubectl exec -n {namespace} {pod_name} -- kill -9 1"
    elif root_cause_type == "oom_kill":
        return f"kubectl delete pod {pod_name} -n {namespace}"
    elif root_cause_type == "bad_deployment":
        return f"kubectl rollout undo deployment/{deployment_name} -n {namespace}"
    elif root_cause_type == "high_load":
        return f"kubectl scale deployment/{deployment_name} --replicas=5 -n {namespace}"
    return f"kubectl describe pod {pod_name} -n {namespace}"
