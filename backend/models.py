from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class IncidentStatus(str, Enum):
    INVESTIGATING = "INVESTIGATING"
    REMEDIATING = "REMEDIATING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class AlertPayload(BaseModel):
    source: str = "manual"  # e.g. "datadog", "sentry", "prometheus", "manual"
    service: str
    severity: str  # "critical", "high", "medium", "low"
    title: str
    description: str
    namespace: Optional[str] = "default"
    pod_name: Optional[str] = None
    deployment_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: IncidentStatus = IncidentStatus.INVESTIGATING
    alert: AlertPayload
    reasoning_trace: List[dict] = Field(default_factory=list)
    root_cause: Optional[str] = None
    root_cause_type: Optional[str] = None
    confidence_score: Optional[int] = None
    blast_radius: Optional[str] = None
    remediation_action: Optional[str] = None
    remediation_result: Optional[str] = None
    kubectl_command: Optional[str] = None
    slack_message_sent: bool = False
    pr_url: Optional[str] = None
    postmortem: Optional[str] = None
    cost_estimate: Optional[float] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class InvestigationResult(BaseModel):
    root_cause: str
    root_cause_type: str  # "bad_deployment", "oom_kill", "high_load", "deadlock", "unknown"
    confidence_score: int
    blast_radius: str
    supporting_evidence: List[str]
    remediation_action: str
    commit_sha: Optional[str] = None
    kubectl_command: Optional[str] = None
    escalation_reason: Optional[str] = None


class RemediationResult(BaseModel):
    action: str
    success: bool
    pr_url: Optional[str] = None
    escalation_reason: Optional[str] = None
    message: Optional[str] = None


class TraceStep(BaseModel):
    step: str
    timestamp: str
    icon: Optional[str] = None


class IncidentStats(BaseModel):
    total_today: int
    resolved_auto: int
    escalated: int
    cost_avoided: float
    hours_saved: float
