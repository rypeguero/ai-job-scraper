from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# Convert a text environment variable into an integer setting.
def _as_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)

# Turn a relative path like data/jobs.db into a full project path.
def _as_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return BASE_DIR / path

# Store all app settings in one place so the rest of the project stays clean.
@dataclass(frozen=True)
class Settings:
    database_path: Path
    ollama_model: str
    request_delay_seconds: int
    max_jobs: int
    default_source: str

# Build the settings object by reading environment variables and defaults.
def get_settings() -> Settings:
    return Settings(
        database_path=_as_path(os.getenv("DATABASE_PATH", "data/jobs.db")),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        request_delay_seconds=_as_int("REQUEST_DELAY_SECONDS", 2),
        max_jobs=_as_int("MAX_JOBS", 25),
        default_source=os.getenv("DEFAULT_SOURCE", "greenhouse"),
    )


settings = get_settings()