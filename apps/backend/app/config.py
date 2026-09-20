from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    root: Path
    environment: str
    max_upload_bytes: int
    cors_origins: tuple[str, ...]
    riot_enable_public_data: bool
    auth_required: bool
    auth_secret: str
    admin_email: str | None
    admin_password: str | None
    auth_cookie_secure: bool

    @classmethod
    def from_env(cls) -> "Settings":
        raw_root = Path(os.getenv("DATA_BI_ROOT", PROJECT_ROOT / "data"))
        root = raw_root if raw_root.is_absolute() else PROJECT_ROOT / raw_root
        origins = tuple(
            value.strip()
            for value in os.getenv("DATA_BI_CORS_ORIGINS", "http://localhost:5173").split(",")
            if value.strip()
        )
        return cls(
            root=root.resolve(),
            environment=os.getenv("DATA_BI_ENV", "local"),
            max_upload_bytes=int(os.getenv("DATA_BI_MAX_UPLOAD_MB", "100")) * 1024 * 1024,
            cors_origins=origins,
            riot_enable_public_data=os.getenv("RIOT_ENABLE_PUBLIC_DATA", "false").lower() == "true",
            auth_required=os.getenv("DATA_BI_AUTH_REQUIRED", "false").lower() == "true",
            auth_secret=os.getenv("DATA_BI_AUTH_SECRET", ""),
            admin_email=os.getenv("DATA_BI_ADMIN_EMAIL") or None,
            admin_password=os.getenv("DATA_BI_ADMIN_PASSWORD") or None,
            auth_cookie_secure=os.getenv("DATA_BI_AUTH_COOKIE_SECURE", "false").lower() == "true",
        )


settings = Settings.from_env()
