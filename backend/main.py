import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes.webhook import router as webhook_router
from routes.incidents import router as incidents_router
from routes.stream import router as stream_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup checks: verify all integrations are reachable."""
    logger.info("Resolvo starting up...")

    # Verify Supabase
    try:
        from db.supabase_client import get_supabase
        get_supabase()
        logger.info("✅ Supabase connected")
    except Exception as e:
        logger.warning(f"⚠️  Supabase connection issue: {e}")

    # Verify Kubernetes
    try:
        from integrations.kubernetes_client import _k8s_available
        if _k8s_available:
            logger.info("✅ Kubernetes connected (Minikube)")
        else:
            logger.info("⚠️  Kubernetes not connected — running in mock mode")
    except Exception:
        pass

    # Verify Slack
    slack_ok = False
    try:
        from slack_sdk import WebClient
        slack_client = WebClient(token=settings.SLACK_BOT_TOKEN)
        resp = slack_client.auth_test()
        if resp["ok"]:
            logger.info(f"✅ Slack connected (workspace: {resp.get('team')})")
            slack_ok = True
    except Exception as e:
        logger.warning(f"⚠️  Slack connection issue: {e}")

    app.state.slack_ok = slack_ok
    logger.info("Resolvo ready. The on-call engineer is now AI.")

    yield

    logger.info("Resolvo shutting down.")


app = FastAPI(
    title="Resolvo",
    description="AI On-Call Engineer — automated incident investigation and remediation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(webhook_router, prefix="/api/v1/webhook", tags=["Webhooks"])
app.include_router(incidents_router, prefix="/api/v1/incidents", tags=["Incidents"])
app.include_router(stream_router, prefix="/api/v1/stream", tags=["Streaming"])


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    from integrations.kubernetes_client import _k8s_available
    return {
        "status": "ok",
        "service": "resolvo",
        "k8s": _k8s_available,
        "slack": getattr(app.state, "slack_ok", False),
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "Resolvo",
        "tagline": "The 3am page your engineers never want to get. Resolvo gets it instead.",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
