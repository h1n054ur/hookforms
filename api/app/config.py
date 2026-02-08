import sys

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://hookforms:hookforms@localhost:5432/hookforms"
    redis_url: str = "redis://localhost:6379"
    admin_api_key: str = ""

    app_name: str = "HookForms"
    debug: bool = False

    # CORS — comma-separated allowed origins (empty = allow all for dev)
    cors_origins: str = ""

    # Gmail API
    gmail_credentials_path: str = "/app/config/gmail/credentials.json"
    gmail_token_path: str = "/app/config/gmail/token.json"
    gmail_sender_email: str = ""

    # Event retention (days)
    event_retention_days: int = 30

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

if not settings.admin_api_key:
    print(
        "FATAL: ADMIN_API_KEY environment variable is not set. Refusing to start.",
        file=sys.stderr,
    )
    sys.exit(1)
