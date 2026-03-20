from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Core
    database_url: str
    db_target: str = "local"  # "local" or "neon"
    app_env: str = "development"
    log_level: str = "INFO"

    # FastAPI
    cors_origins: str = ""  # comma-separated origins

    # Neon Auth (Better Auth) — JWT verification
    neon_auth_base_url: str = ""

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_bucket: str = ""
    storage_backend: str = "local"  # "local" or "s3"

    # Resend email
    resend_api_key: str = ""
    resend_from_email: str = ""
    alert_email: str = ""

    # Fundamentals
    fundamentals_api_key: str = ""

    # Screener.in
    screener_userid: str = ""
    screener_password: str = ""


settings = Settings()
