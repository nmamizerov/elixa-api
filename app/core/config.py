from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.
    """

    DATABASE_URL: str

    # JWT settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    LANGSMITH_TRACING: bool
    LANGSMITH_ENDPOINT: str
    LANGSMITH_API_KEY: str
    LANGSMITH_PROJECT: str

    # OpenAI settings
    OPENAI_API_KEY: str

    # AWS S3 settings
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str
    S3_REPORTS_PREFIX: str = "reports/"
    S3_ENDPOINT_URL: str | None = None  # Кастомный endpoint для S3-совместимых хранилищ

    # Google Analytics 4 credentials
    GOOGLE_APPLICATION_CREDENTIALS: str | None = (
        None  # Путь к JSON файлу сервисного аккаунта
    )
    GOOGLE_SERVICE_ACCOUNT_JSON: str | None = "./ga_creds.json"

    model_config = SettingsConfigDict(
        env_file=".env", extra="allow", env_file_encoding="utf-8"
    )


settings = Settings()
