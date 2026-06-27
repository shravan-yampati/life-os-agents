from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    # Cloud Dynamic Configuration
    CLOUD_PROVIDER: str = Field(default="gcp")  # Options: "gcp", "aws", or "local"

    # Vector store backend: "pgvector" (requires Postgres) or "local" (numpy, on-disk)
    VECTOR_BACKEND: str = Field(default="local")
    LOCAL_VECTOR_PATH: str = Field(default=".raglab/vector_store.json")

    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql://fund_manager:CHANGE_ME_LOCAL_DEV@localhost:5432/rag_lab"
    )

    # GCP Configuration
    GCP_PROJECT_ID: str = Field(default="your-gcp-project-id")
    GCP_LOCATION: str = Field(default="us-central1")
    GCS_BUCKET_NAME: str = Field(default="your-gcs-bucket-name")
    # AI Studio API key — used by the google-genai SDK (Generative Language API).
    GOOGLE_API_KEY: str | None = Field(default=None)
    # Cheap Gemini flash model for testing first; swap to a stronger model
    # (or Claude) later by changing these — no code change needed.
    GCP_LLM_MODEL: str = Field(default="gemini-2.5-flash")
    GCP_EMBED_MODEL: str = Field(default="gemini-embedding-2")

    # AWS Configuration
    AWS_ACCESS_KEY_ID: str | None = Field(default=None)
    AWS_SECRET_ACCESS_KEY: str | None = Field(default=None)
    AWS_REGION: str = Field(default="us-east-1")
    S3_BUCKET_NAME: str = Field(default="your-s3-bucket-name")

    # Optional APIs
    COHERE_API_KEY: str | None = Field(default=None)
    OPENAI_API_KEY: str | None = Field(default=None)

settings = Settings()
