from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SLACK_BOT_TOKEN: str
    SLACK_CHANNEL_ID: str
    GITHUB_TOKEN: str
    GITHUB_REPO: str  # format: "owner/repo"
    KUBECONFIG_PATH: str = "~/.kube/config"
    CONFIDENCE_THRESHOLD: int = 75
    ENGINEER_HOURLY_RATE: int = 150
    REVENUE_PER_MINUTE: int = 50
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
