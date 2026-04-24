# Resolvo — AI On-Call Engineer

> *"The 3am page your engineers never want to get. Resolvo gets it instead."*

Resolvo is an autonomous AI agent that **investigates and resolves production incidents before any human is paged**. When an alert fires, Resolvo reads the logs, checks recent commits, forms a root cause hypothesis, executes a safe fix, and posts a full resolution summary to Slack — all automatically.

Built at **HackTech 2026 @ Caltech** · YC x HackTech Challenge · Reimagining PagerDuty (S10)

---

## What It Does

- **Alert fires** → Resolvo wakes up instantly (no human needed)
- **Investigates** → reads pod logs, checks GitHub commits, correlates errors with recent deploys
- **CGEV scores** confidence 0–100 before touching anything
- **Auto-fixes** → creates revert PRs, restarts pods, scales deployments
- **Escalates** with full briefing when confidence is too low
- **Posts to Slack** → resolution summary or escalation with ready-to-run kubectl command
- **Live dashboard** → watch the AI reason in real time

---

## Prerequisites

Make sure you have these installed:

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| npm | 9+ | comes with Node |

---

## Step 1 — Clone & Setup

```bash
git clone https://github.com/quachphu/Resolvo.git
cd Resolvo
```

---

## Step 2 — Supabase Database

1. Go to [supabase.com](https://supabase.com) → create a free project
2. Open **SQL Editor** in the left sidebar
3. Copy and paste the entire contents of `supabase_schema.sql` and click **Run**
4. You should see: `Success. No rows returned`

From your Supabase project settings, collect:
- **Project URL** → `https://xxxx.supabase.co`
- **Service Role key** (under API keys) → starts with `sb_secret_...`
- **Anon/Public key** → starts with `sb_publishable_...`

---

## Step 3 — Get API Keys

You need 4 services. All have free tiers:

### Anthropic (Claude AI)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create API key → copy it (`sk-ant-...`)

### Slack
1. Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From Scratch
2. **OAuth & Permissions** → Add Bot Token Scopes: `chat:write`, `chat:write.public`
3. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
4. Open Slack → go to your incidents channel → click channel name → copy **Channel ID** (`C0XXXXXX`)
5. In that channel type `/invite @your-app-name`

### GitHub
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → Fine-grained tokens → Generate
2. Select your repo → Permissions: **Contents** (read/write), **Pull requests** (read/write)
3. Copy the token (`github_pat_...`)

---

## Step 4 — Configure Environment

```bash
# Backend config
cp .env.example backend/.env
```

Open `backend/.env` and fill in all values:

```bash
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_...
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C0XXXXXXX
GITHUB_TOKEN=github_pat_...
GITHUB_REPO=your-username/your-repo
```

```bash
# Frontend config
cp frontend/.env.example frontend/.env
```

Open `frontend/.env` and fill in:

```bash
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=sb_publishable_...
```

---

## Step 5 — Install Dependencies

### Backend

```bash
cd backend
pip install -r requirements.txt
```

> **Note:** If you see `supabase==2.7.0` errors, run: `pip install "supabase>=2.10.0" --upgrade`

### Frontend

```bash
cd frontend
npm install
```

---

## Step 6 — Run the Project

You need **two terminals open at the same time**:

### Terminal 1 — Backend

```bash
cd /path/to/Resolvo/backend
uvicorn main:app --reload --port 8000
```

You should see:
```
✅ Supabase connected
✅ Slack connected (workspace: Your Workspace)
Resolvo ready. The on-call engineer is now AI.
```

### Terminal 2 — Frontend

```bash
cd /path/to/Resolvo/frontend
npm run dev
```

You should see:
```
VITE v5.x  ready in Xms
➜  Local:   http://localhost:5173/
```

---

## Step 7 — Open the Dashboard

Go to **[http://localhost:5173](http://localhost:5173)**

You'll see the Resolvo dashboard with 3 demo scenario buttons in the top right.

---

## Demo Scenarios

Click any button to watch the AI agent work in real time:

### 🔴 CrashLoop Crash ← *Start here for the demo*
`payment-service` enters CrashLoopBackOff from a null check removed in a recent commit.

**What happens:** Resolvo reads pod logs → finds the NullPointerException → checks recent GitHub commits → identifies the bad commit → creates a revert PR automatically → posts to Slack: *"Incident resolved. No human required."*

---

### 🟡 Memory OOM Kill
`memory-hog-service` gets OOM-killed (exit code 137, memory limit exceeded).

**What happens:** Resolvo detects the OOM pattern → restarts the pod → monitors until healthy → Slack notification sent.

---

### 🔵 DB Deadlock ← *escalation demo*
`db-service` hits a database deadlock requiring manual DBA intervention.

**What happens:** Resolvo identifies the deadlock but confidence score is too low to auto-fix → escalates to human with full briefing + ready-to-run kubectl command in Slack.

---

## How to Trigger via API (alternative to UI)

```bash
# CrashLoop scenario
curl -X POST http://localhost:8000/api/v1/webhook/simulate/crashloop

# OOM scenario
curl -X POST http://localhost:8000/api/v1/webhook/simulate/oom

# Deadlock scenario
curl -X POST http://localhost:8000/api/v1/webhook/simulate/deadlock
```

---

## Project Structure

```
Resolvo/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Environment variables
│   ├── models.py                  # Pydantic data models
│   ├── agent/
│   │   ├── investigator.py        # Claude agentic loop (core AI)
│   │   ├── remediator.py          # Auto-fix executor
│   │   ├── confidence.py          # CGEV scoring logic
│   │   └── postmortem.py          # Post-mortem generator
│   ├── integrations/
│   │   ├── kubernetes_client.py   # K8s operations (mock-safe)
│   │   ├── github.py              # Commit lookup + PR creation
│   │   └── slack.py               # Slack Block Kit notifications
│   ├── routes/
│   │   ├── webhook.py             # Alert ingestion + demo triggers
│   │   ├── incidents.py           # Incident CRUD endpoints
│   │   └── stream.py              # SSE real-time trace streaming
│   ├── db/
│   │   └── supabase_client.py     # Database helpers
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx                # 3-column dashboard layout
│       └── components/
│           ├── ReasoningTrace.jsx # Live agent thought stream
│           ├── CostMeter.jsx      # Live ticking cost counter
│           ├── TriggerDemo.jsx    # Demo scenario buttons
│           ├── SlackPreview.jsx   # Slack message preview
│           ├── IncidentList.jsx   # Incident sidebar
│           ├── MetricsBar.jsx     # Today's stats
│           └── IncidentCard.jsx   # Single incident card
├── minikube/                      # Optional: real K8s demo
│   ├── setup.sh
│   └── scenarios/                 # CrashLoop, OOM, Deadlock YAMLs
├── supabase_schema.sql            # Run this in Supabase first
├── .env.example                   # Backend env template
└── README.md
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Check backend + integrations status |
| `POST` | `/api/v1/webhook/alert` | Receive alert from any monitoring tool |
| `POST` | `/api/v1/webhook/simulate/{scenario}` | Trigger demo scenario |
| `GET` | `/api/v1/incidents` | List all incidents |
| `GET` | `/api/v1/incidents/{id}` | Get full incident + post-mortem |
| `GET` | `/api/v1/incidents/stats` | Today's metrics |
| `GET` | `/api/v1/stream/{id}` | SSE stream (live reasoning trace) |

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Invalid API key` (Supabase) | Run `pip install "supabase>=2.10.0" --upgrade` |
| `Failed to fetch` in browser | Make sure backend is running on port 8000 |
| `localhost:5173` not loading | Make sure `npm run dev` is running in `frontend/` |
| Slack not posting | Check `SLACK_BOT_TOKEN` and run `/invite @your-bot` in the channel |
| GitHub PR not created | Check token has `Contents` + `Pull requests` write permissions |
| K8s errors | Ignored — runs in mock mode automatically without Minikube |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Agent | Anthropic Claude (`claude-sonnet-4-5`) with tool use |
| Backend | Python 3.11, FastAPI, uvicorn |
| Database | Supabase (PostgreSQL + realtime) |
| Notifications | Slack Block Kit |
| Code Access | GitHub API (PyGithub) |
| Kubernetes | Python kubernetes client (mock-safe) |
| Frontend | React 18, Vite, Tailwind CSS |
| Streaming | Server-Sent Events (SSE) |

---

## The Big Idea

**PagerDuty (YC S10, 2010)** solved *"who do we page when servers break at 3am?"* Their answer: wake up an engineer.

**Resolvo asks a different question:** does the engineer need to be woken up at all?

With Claude's agentic reasoning + tool use, an AI can do everything a senior engineer does in the first 45 minutes of triage — read logs, trace errors through code, correlate with deployments, form hypotheses, and execute a fix. The on-call engineer's job changes from **detective to decision-maker**.

---

*Built at HackTech 2026 @ Caltech — April 24–26, 2026*
*YC x HackTech Challenge: Reimagining PagerDuty (S10)*
