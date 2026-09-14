from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    environment: str
    max_upload_bytes: int
    cors_origins: tuple[str, ...]
    riot_enable_public_data: bool

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = Path(__file__).resolve().parents[3]
        raw_root = Path(os.getenv("DATA_BI_ROOT", project_root / "data"))
        root = raw_root if raw_root.is_absolute() else project_root / raw_root
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
        )


settings = Settings.from_env()
