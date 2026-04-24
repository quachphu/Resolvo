import logging
from typing import Optional
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)


def _get_slack_client():
    try:
        from slack_sdk import WebClient
        return WebClient(token=settings.SLACK_BOT_TOKEN)
    except Exception as e:
        logger.error(f"Failed to init Slack client: {e}")
        return None


def _format_duration(started_at: datetime, resolved_at: Optional[datetime] = None) -> str:
    end = resolved_at or datetime.utcnow()
    delta = end - started_at
    total_seconds = int(delta.total_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


async def post_resolution(incident: dict) -> bool:
    """Post a resolution message to Slack using Block Kit."""
    client = _get_slack_client()
    if not client:
        logger.warning("Slack client unavailable — skipping notification")
        return False

    service = incident.get("service", "unknown")
    root_cause = incident.get("root_cause", "Unknown root cause")
    remediation_action = incident.get("remediation_action", "unknown")
    confidence_score = incident.get("confidence_score", 0)
    pr_url = incident.get("pr_url")
    cost_estimate = incident.get("cost_estimate", 0) or 0
    started_at = _parse_dt(incident.get("started_at"))
    resolved_at = _parse_dt(incident.get("resolved_at"))
    duration = _format_duration(started_at, resolved_at) if started_at else "?"
    incident_id = incident.get("id", "")
    dashboard_url = f"{settings.FRONTEND_URL}?incident={incident_id}"

    action_label = {
        "revert_pr": "Revert PR created",
        "pod_restart": "Pod restarted",
        "scale_up": "Deployment scaled up",
        "rollback": "Deployment rolled back",
    }.get(remediation_action, remediation_action.replace("_", " ").title())

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🟢 INCIDENT RESOLVED — No human required",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Service:*\n`{service}`"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence_score}/100 ✓"},
                {"type": "mrkdwn", "text": f"*Fix applied:*\n{action_label}"},
                {"type": "mrkdwn", "text": f"*Time to resolve:*\n{duration}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Root cause:*\n{root_cause}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Cost avoided:*\n~${cost_estimate:,.2f}"},
            ],
        },
        {"type": "divider"},
    ]

    actions_elements = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "View full trace →"},
            "url": dashboard_url,
            "style": "primary",
        }
    ]
    if pr_url:
        actions_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Review PR →"},
            "url": pr_url,
        })

    blocks.append({"type": "actions", "elements": actions_elements})

    try:
        response = client.chat_postMessage(
            channel=settings.SLACK_CHANNEL_ID,
            blocks=blocks,
            text=f"🟢 Incident resolved for {service} — {action_label}",
        )
        logger.info(f"Slack resolution posted: {response['ts']}")
        return True
    except Exception as e:
        logger.error(f"Failed to post Slack resolution: {e}")
        return False


async def post_escalation(incident: dict) -> bool:
    """Post an escalation briefing to Slack."""
    client = _get_slack_client()
    if not client:
        logger.warning("Slack client unavailable — skipping notification")
        return False

    service = incident.get("service", "unknown")
    root_cause = incident.get("root_cause", "Could not determine root cause")
    confidence_score = incident.get("confidence_score", 0) or 0
    escalation_reason = incident.get("remediation_result", "Confidence below threshold")
    kubectl_command = incident.get("kubectl_command", "")
    incident_id = incident.get("id", "")
    dashboard_url = f"{settings.FRONTEND_URL}?incident={incident_id}"
    threshold = settings.CONFIDENCE_THRESHOLD

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🔴 INCIDENT ESCALATED — Human review required",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Service:*\n`{service}`"},
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence score:*\n{confidence_score}/100 (threshold: {threshold}/100)",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*What I found:*\n{root_cause}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Why I didn't auto-fix:*\n{escalation_reason}",
            },
        },
    ]

    if kubectl_command:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Command to run:*\n```{kubectl_command}```",
            },
        })

    blocks += [
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View full investigation →"},
                    "url": dashboard_url,
                    "style": "danger",
                }
            ],
        },
    ]

    try:
        response = client.chat_postMessage(
            channel=settings.SLACK_CHANNEL_ID,
            blocks=blocks,
            text=f"🔴 Incident escalated for {service} — human review required",
        )
        logger.info(f"Slack escalation posted: {response['ts']}")
        return True
    except Exception as e:
        logger.error(f"Failed to post Slack escalation: {e}")
        return False


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return datetime.utcnow()
