# Resolvo — AI On-Call Engineer

> *"The 3am page your engineers never want to get. Resolvo gets it instead."*

Resolvo is an autonomous AI agent that investigates and resolves production incidents before any human engineer is paged. When an alert fires, Resolvo wakes up, reads the logs, checks recent commits, forms a root cause hypothesis, executes the lowest-risk fix, and sends a full resolution summary to Slack — all while the on-call engineer sleeps.

Built at **HackTech 2026 @ Caltech** for the **YC x HackTech challenge** (reimagining PagerDuty, S10).

---

## What It Does

- **Autonomous investigation** — reads pod logs, queries GitHub for recent commits, correlates error signatures with code changes using a Claude agentic loop
- **Confidence-gated remediation** — uses CGEV scoring to determine whether auto-remediation is safe; only acts when confidence ≥ threshold (default: 75/100)
- **Automatic fixes** — creates revert PRs, restarts pods, scales deployments, or rolls back — then confirms the fix worked
- **Human escalation with full briefing** — when confidence is too low, pages the engineer with root cause analysis, supporting evidence, and a ready-to-run kubectl command

---

## How It Works

1. **Alert fires** → any monitoring tool (Datadog, Sentry, Prometheus, CloudWatch) POSTs to `/api/v1/webhook/alert`
2. **Incident created** in Supabase; agent loop spins up as a background task
3. **Investigation** — Claude with tool use reads pod logs, fetches recent commits, checks deployment history
4. **CGEV scoring** — calculates confidence 0–100 based on root cause clarity, evidence strength, remediation reversibility, and blast radius
5. **Remediation** — if score ≥ threshold: creates revert PR / restarts pod / scales deployment; if below: escalates with briefing
6. **Slack notification** — posts structured resolution summary or escalation briefing with actionable context

---

## YC Company Reimagined

**PagerDuty (S10, 2010)** solved "who do we page when servers break at 3am." Their answer: wake up an engineer.

Resolvo asks a different question: *does the engineer need to be woken up at all?*

PagerDuty made alerting better. Resolvo makes the human unnecessary for the majority of incidents. In 2026, with agentic AI and tool use, an AI agent can do everything a senior engineer does in the first 45 minutes of incident triage — read the logs, trace the error through the codebase, correlate with recent deployments, form hypotheses, test them, and execute a fix.

**The market:** PagerDuty is worth $1.7B. The AIOps market is projected at $15–20B by 2028. Every engineering team is a customer.

**Monetization:** Per-incident-resolved ($X per auto-resolved incident) or per-seat ($20–40/month/engineer). The per-incident model aligns incentives perfectly — you only pay when Resolvo actually fixes something.

---

## CGEV Architecture

**CGEV (Confidence-Gated Ensemble Verification)** is Resolvo's safety mechanism for autonomous remediation.

Before executing any fix, the agent scores its own confidence 0–100 across four dimensions:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Root cause clarity | 0–30 | How specific and verifiable is the hypothesis? |
| Supporting evidence | 0–30 | How many corroborating data sources exist? |
| Remediation reversibility | 0–25 | Can we undo this fix if it's wrong? |
| Blast radius containment | 0–15 | Is the impact scope narrow and bounded? |

If `score ≥ CONFIDENCE_THRESHOLD` (default 75): auto-remediate.  
If `score < CONFIDENCE_THRESHOLD`: escalate to human with full briefing.

This ensures Resolvo is aggressive enough to handle repetitive incidents autonomously while being conservative enough to never make a bad situation worse.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn |
| AI Agent | Anthropic Claude (`claude-sonnet-4-5`) with tool use |
| Investigation Engine | Inspired by [HolmesGPT](https://github.com/HolmesGPT/holmesgpt) |
| Database | Supabase (PostgreSQL + realtime) |
| Notifications | Slack Block Kit via `slack_sdk` |
| Code access | GitHub API via `PyGithub` |
| Kubernetes | `kubernetes` Python client |
| Frontend | React 18, Vite, Tailwind CSS |
| Deploy | Railway (backend), Vercel (frontend) |

---

## Quick Start

### Prerequisites

1. [Supabase](https://supabase.com) project — run `supabase_schema.sql` in the SQL editor
2. [Anthropic API key](https://console.anthropic.com)
3. GitHub personal access token with `repo` scope
4. Slack app with `chat:write` scope and a channel to post to
5. [Minikube](https://minikube.sigs.k8s.io/docs/start/) (optional — backend falls back to mock mode)

### Setup

```bash
git clone https://github.com/your-org/resolvo
cd resolvo

# Backend
cp .env.example backend/.env
# Edit backend/.env with your API keys

cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
cp .env.example .env
# Edit .env with your Supabase URL + anon key
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### Minikube (optional, for realistic K8s demo)

```bash
cd minikube
./setup.sh
```

### Trigger a demo scenario

Via the dashboard UI — click any scenario button in the right panel.

Or via CLI:

```bash
cd minikube
./trigger_alert.sh http://localhost:8000 crashloop
./trigger_alert.sh http://localhost:8000 oom
./trigger_alert.sh http://localhost:8000 deadlock
```

---

## Demo Scenarios

### Scenario A — CrashLoop (auto-resolved)
`payment-service` enters CrashLoopBackOff. Resolvo reads pod logs, finds `NullPointerException in PaymentHandler.process()`, checks recent commits, identifies the commit that removed the null check, creates a revert PR automatically, confirms the pod stabilizes.

**Expected outcome:** PR created, Slack message: *"Incident resolved. No human required."*

### Scenario B — OOM Kill (auto-resolved)
`memory-hog-service` is OOM-killed repeatedly (exit code 137). Resolvo detects the memory leak pattern, restarts the pod, and monitors until it's healthy.

**Expected outcome:** Pod restarted, service stabilized, Slack resolution sent.

### Scenario C — DB Deadlock (escalated)
`db-service` has a database deadlock requiring manual DBA intervention. Resolvo identifies the deadlock but cannot safely auto-resolve it — confidence score comes in below threshold. It escalates with a full briefing including the exact recovery command.

**Expected outcome:** Escalation sent to Slack with briefing. Human gets all context needed to resolve immediately.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/webhook/alert` | Receive alert from any monitoring tool |
| `POST` | `/api/v1/webhook/simulate/{scenario}` | Trigger demo scenario |
| `GET` | `/api/v1/incidents` | List all incidents |
| `GET` | `/api/v1/incidents/{id}` | Get incident detail + post-mortem |
| `GET` | `/api/v1/incidents/stats` | Today's metrics |
| `GET` | `/api/v1/stream/{id}` | SSE stream for live reasoning trace |
| `GET` | `/health` | Health check |

---

*Built at HackTech 2026 @ Caltech — April 24–26, 2026*  
*YC x HackTech Challenge: Reimagining PagerDuty (S10)*
