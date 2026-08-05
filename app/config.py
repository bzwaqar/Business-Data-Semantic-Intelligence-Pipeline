import os

# Set environment variables before any ML/OpenMP libraries are imported
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    MAX_UPLOAD_ROWS: int = 150000
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    UMAP_N_COMPONENTS: int = 50
    KMEANS_MIN_K: int = 2
    KMEANS_MAX_K: int = 70
    KMEANS_STEP_K: int = 1
    JOB_STORAGE_PATH: str = "./jobs"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
