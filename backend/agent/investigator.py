"""
Core agentic investigation loop.

Uses Claude with tool use to investigate incidents by reading pod logs,
checking recent commits, and correlating evidence to form a root cause
hypothesis before deciding on remediation.
"""

import json
import logging
from datetime import datetime
from typing import Callable, Awaitable, List, Optional

import anthropic

from config import settings
from models import AlertPayload, InvestigationResult
from agent.confidence import calculate_confidence, get_anthropic_client
from integrations import kubernetes_client, github as github_integration

logger = logging.getLogger(__name__)

# ── Tool definitions for Claude ──────────────────────────────────────────────

TOOLS = [
    {
        "name": "fetch_pod_logs",
        "description": "Fetch recent logs from a Kubernetes pod. Use this to read error messages and stack traces.",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pod_name": {"type": "string", "description": "Pod name or prefix"},
                "lines": {"type": "integer", "description": "Number of log lines to fetch", "default": 100},
            },
            "required": ["namespace", "pod_name"],
        },
    },
    {
        "name": "get_recent_commits",
        "description": "Fetch recent commits from the GitHub repository to correlate with the incident timing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of commits to fetch", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "get_commit_diff",
        "description": "Get the full diff of a specific commit to understand what changed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sha": {"type": "string", "description": "Full or short commit SHA"},
            },
            "required": ["sha"],
        },
    },
    {
        "name": "check_pod_status",
        "description": "Check the current status and restart count of a pod.",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pod_name": {"type": "string", "description": "Pod name"},
            },
            "required": ["namespace", "pod_name"],
        },
    },
    {
        "name": "get_deployment_history",
        "description": "Get the deployment revision history for a Deployment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "deployment_name": {"type": "string", "description": "Deployment name"},
            },
            "required": ["namespace", "deployment_name"],
        },
    },
]


async def _execute_tool(tool_name: str, tool_input: dict, alert: AlertPayload) -> str:
    """Execute a tool call and return the result as a string."""
    namespace = alert.namespace or "default"
    pod_name = alert.pod_name or alert.service
    deployment_name = alert.deployment_name or alert.service

    if tool_name == "fetch_pod_logs":
        ns = tool_input.get("namespace", namespace)
        pn = tool_input.get("pod_name", pod_name)
        lines = tool_input.get("lines", 100)
        logs = await kubernetes_client.get_pod_logs(ns, pn, lines)
        return logs

    elif tool_name == "get_recent_commits":
        limit = tool_input.get("limit", 10)
        commits = await github_integration.get_recent_commits(settings.GITHUB_REPO, limit)
        result = []
        for c in commits:
            result.append({
                "sha": c.sha[:12],
                "message": c.message[:120],
                "author": c.author,
                "timestamp": c.timestamp,
                "files_changed": c.files_changed[:5],
            })
        return json.dumps(result, indent=2)

    elif tool_name == "get_commit_diff":
        sha = tool_input.get("sha", "")
        diff = await github_integration.get_commit_diff(settings.GITHUB_REPO, sha)
        return diff

    elif tool_name == "check_pod_status":
        ns = tool_input.get("namespace", namespace)
        pn = tool_input.get("pod_name", pod_name)
        status = await kubernetes_client.get_pod_status(ns, pn)
        return json.dumps(status)

    elif tool_name == "get_deployment_history":
        ns = tool_input.get("namespace", namespace)
        dn = tool_input.get("deployment_name", deployment_name)
        history = await kubernetes_client.get_deployment_history(ns, dn)
        return json.dumps(history, indent=2)

    return f"Unknown tool: {tool_name}"


def _build_system_prompt(alert: AlertPayload) -> str:
    return f"""You are Resolvo, an AI SRE agent investigating a production incident.
Your job is to:
1. Gather evidence using available tools (pod logs, git commits, deployment history)
2. Identify the root cause with high confidence
3. Determine the safest remediation action
4. Provide a structured investigation summary

Current incident:
- Service: {alert.service}
- Severity: {alert.severity}
- Title: {alert.title}
- Description: {alert.description}
- Namespace: {alert.namespace or 'default'}
- Pod: {alert.pod_name or 'unknown'}
- Deployment: {alert.deployment_name or 'unknown'}
- Source: {alert.source}

Use tools systematically. After gathering evidence, provide your final analysis as JSON:
{{
  "root_cause": "specific description of what caused the incident",
  "root_cause_type": "bad_deployment|oom_kill|high_load|deadlock|unknown",
  "supporting_evidence": ["evidence 1", "evidence 2", ...],
  "blast_radius": "description of impact scope",
  "remediation_action": "revert_pr|pod_restart|scale_up|rollback|escalate",
  "commit_sha": "full sha if bad_deployment, otherwise null",
  "kubectl_command": "kubectl command if escalating, otherwise null",
  "escalation_reason": "why you cannot auto-fix, if escalating"
}}

Be concise but specific. If you cannot determine root cause with confidence, say so clearly."""


async def investigate_incident(
    incident_id: str,
    alert: AlertPayload,
    trace_callback: Callable[[str], Awaitable[None]],
) -> InvestigationResult:
    """
    Run the full agentic investigation loop with trace callbacks.
    Each trace_callback call updates Supabase and triggers SSE to the frontend.
    """
    await trace_callback(f"Waking up. Alert received: [{alert.severity.upper()}] {alert.title}")
    await trace_callback(f"Service: {alert.service} | Source: {alert.source} | Namespace: {alert.namespace or 'default'}")

    client = get_anthropic_client()
    messages = [
        {
            "role": "user",
            "content": f"Investigate this incident: {alert.title}\n\nDescription: {alert.description}\n\nStart by reading the pod logs, then check recent commits.",
        }
    ]

    supporting_evidence: List[str] = []
    commit_sha: Optional[str] = None
    max_iterations = 8
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=_build_system_prompt(alert),
            tools=TOOLS,
            messages=messages,
        )

        # Collect text from this response turn
        for block in response.content:
            if hasattr(block, "text") and block.text:
                text = block.text.strip()
                if text:
                    # If the model is giving its final JSON analysis, parse and break
                    if text.startswith("{") and "root_cause" in text:
                        try:
                            analysis = json.loads(text)
                            root_cause = analysis.get("root_cause", "Unknown")
                            root_cause_type = analysis.get("root_cause_type", "unknown")
                            blast_radius = analysis.get("blast_radius", "Unknown scope")
                            remediation = analysis.get("remediation_action", "escalate")
                            commit_sha = analysis.get("commit_sha")
                            kubectl_cmd = analysis.get("kubectl_command")
                            escalation_reason = analysis.get("escalation_reason")
                            supporting_evidence = analysis.get("supporting_evidence", supporting_evidence)

                            await trace_callback(f"Root cause hypothesis: {root_cause}")
                            await trace_callback(f"Blast radius: {blast_radius}")

                            confidence_result = await calculate_confidence(
                                root_cause_hypothesis=root_cause,
                                supporting_evidence=supporting_evidence,
                                remediation_action=remediation,
                                blast_radius=blast_radius,
                            )
                            score = confidence_result["score"]
                            threshold = settings.CONFIDENCE_THRESHOLD

                            if score >= threshold:
                                await trace_callback(
                                    f"CGEV confidence score: {score}/100 ✓ Above threshold ({threshold}). Safe to auto-remediate."
                                )
                            else:
                                await trace_callback(
                                    f"CGEV confidence score: {score}/100 ✗ Below threshold ({threshold}). Will escalate to human."
                                )

                            return InvestigationResult(
                                root_cause=root_cause,
                                root_cause_type=root_cause_type,
                                confidence_score=score,
                                blast_radius=blast_radius,
                                supporting_evidence=supporting_evidence,
                                remediation_action=remediation if score >= threshold else "escalate",
                                commit_sha=commit_sha,
                                kubectl_command=kubectl_cmd,
                                escalation_reason=escalation_reason or (
                                    f"Confidence {score}/100 is below threshold {threshold}/100"
                                    if score < threshold else None
                                ),
                            )
                        except json.JSONDecodeError:
                            pass
                    else:
                        # Narration from the model — stream to frontend
                        await trace_callback(text[:200])

        # Handle tool use
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            # Model stopped without giving final JSON — try to extract from text
            break

        # Add assistant message with tool calls
        messages.append({"role": "assistant", "content": response.content})

        # Execute all tool calls and collect results
        tool_results = []
        for tool_block in tool_use_blocks:
            tool_name = tool_block.name
            tool_input = tool_block.input

            # Emit trace for this tool call
            tool_trace = _tool_trace_message(tool_name, tool_input, alert)
            await trace_callback(tool_trace)

            result = await _execute_tool(tool_name, tool_input, alert)

            # Add key findings to supporting evidence
            finding = _extract_key_finding(tool_name, result, tool_input)
            if finding:
                supporting_evidence.append(finding)
                if commit_sha is None and tool_name == "get_recent_commits":
                    commits = _try_parse_json(result)
                    if commits and isinstance(commits, list) and commits:
                        commit_sha = commits[0].get("sha", "")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result[:4000],  # Truncate large outputs
            })

        messages.append({"role": "user", "content": tool_results})

        if response.stop_reason == "end_turn" and not tool_use_blocks:
            break

    # Fallback if loop exhausted without structured result
    await trace_callback("Investigation complete. Forming final assessment...")
    fallback_root_cause = f"Incident in {alert.service}: {alert.description}"
    confidence_result = await calculate_confidence(
        root_cause_hypothesis=fallback_root_cause,
        supporting_evidence=supporting_evidence,
        remediation_action="escalate",
        blast_radius=f"{alert.service} service affected",
    )
    score = confidence_result["score"]
    await trace_callback(f"CGEV confidence score: {score}/100 — escalating due to uncertainty")

    return InvestigationResult(
        root_cause=fallback_root_cause,
        root_cause_type="unknown",
        confidence_score=score,
        blast_radius=f"{alert.service} service",
        supporting_evidence=supporting_evidence,
        remediation_action="escalate",
        escalation_reason="Investigation loop concluded without high-confidence root cause",
    )


def _tool_trace_message(tool_name: str, tool_input: dict, alert: AlertPayload) -> str:
    if tool_name == "fetch_pod_logs":
        pod = tool_input.get("pod_name", alert.pod_name or alert.service)
        return f"Reading pod logs from {pod}..."
    elif tool_name == "get_recent_commits":
        return f"Checking recent commits on {settings.GITHUB_REPO}..."
    elif tool_name == "get_commit_diff":
        sha = tool_input.get("sha", "")[:7]
        return f"Reading diff for commit {sha}..."
    elif tool_name == "check_pod_status":
        pod = tool_input.get("pod_name", alert.pod_name or alert.service)
        return f"Checking pod status for {pod}..."
    elif tool_name == "get_deployment_history":
        dep = tool_input.get("deployment_name", alert.deployment_name or alert.service)
        return f"Fetching deployment history for {dep}..."
    return f"Executing {tool_name}..."


def _extract_key_finding(tool_name: str, result: str, tool_input: dict) -> Optional[str]:
    if tool_name == "fetch_pod_logs":
        if "CrashLoopBackOff" in result:
            return "Pod is in CrashLoopBackOff state — repeated crash detected"
        if "OOMKilled" in result or "exit code 137" in result:
            return "Pod was OOM-killed — memory limit exceeded"
        if "NullPointerException" in result or "NullReferenceException" in result:
            return "NullPointerException found in pod logs"
        if "DEADLOCK" in result.upper():
            return "Database deadlock detected in pod logs"
        if "Error" in result or "error" in result:
            return f"Errors found in pod logs"
        return None
    elif tool_name == "get_recent_commits":
        commits = _try_parse_json(result)
        if commits and isinstance(commits, list) and commits:
            latest = commits[0]
            return f"Most recent commit: {latest.get('sha', '')[:7]} by @{latest.get('author', '?')} — \"{latest.get('message', '')[:80]}\""
        return None
    elif tool_name == "get_commit_diff":
        if "-        if " in result or "null check" in result.lower():
            return "Commit removed a null/safety check — likely introduced the bug"
        if len(result) > 100:
            return f"Commit diff shows changes to {result.count('---')} file(s)"
        return None
    elif tool_name == "check_pod_status":
        status = _try_parse_json(result)
        if status:
            return f"Pod status: {status.get('phase')} ({status.get('reason')}) — {status.get('restart_count', 0)} restarts"
        return None
    return None


def _try_parse_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None
