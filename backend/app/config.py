import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


# Загружаем переменные из backend/.env (override=True — .env перезаписывает уже заданные в окружении)
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)


class Settings(BaseModel):
    app_name: str = "Proxmox Lab Manager"
    debug: bool = bool(int(os.getenv("DEBUG", "1")))

    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./app.db",
    )

    secret_key: str = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    access_token_expire_minutes: int = 60 * 8
    algorithm: str = "HS256"

    proxmox_api_url: str = os.getenv("PROXMOX_API_URL", "https://proxmox.example.com:8006")
    proxmox_token_id: str = os.getenv("PROXMOX_TOKEN_ID", "user@pve!token")
    proxmox_token_secret: str = os.getenv("PROXMOX_TOKEN_SECRET", "TOKEN_SECRET")
    proxmox_default_node: str = os.getenv("PROXMOX_DEFAULT_NODE", "pve")
    proxmox_student_realm: str = os.getenv("PROXMOX_STUDENT_REALM", "pve")
    # Роль с минимальными правами (только свои ВМ). Создайте её в Proxmox — см. README.
    proxmox_student_role: str = os.getenv("PROXMOX_STUDENT_ROLE", "StudentRole")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    """Сброс кэша настроек (например после смены .env)."""
    get_settings.cache_clear()

