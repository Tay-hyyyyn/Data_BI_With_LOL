from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..storage import read_uploaded_file, save_raw_upload

ALIASES = {
    "version": "patch",
    "patch_version": "patch",
    "champion": "champion_name",
    "champ": "champion_name",
    "championid": "champion_id",
    "item": "item_name",
    "itemid": "item_id",
    "games": "sample_games",
    "game_count": "sample_games",
    "samples": "sample_games",
    "pickrate": "pick_rate",
    "winrate": "win_rate",
    "url": "source_url",
}
REQUIRED_ANY = ({"champion_id", "champion_name"}, {"item_id", "item_name", "build_order"})


def normalize_lolps_benchmark(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize an explicitly obtained LOL.PS aggregate export.

    This function intentionally accepts files only; it does not discover or call
    undocumented LOL.PS web endpoints.
    """
    if frame.empty:
        raise ValueError("LOL.PS 벤치마크 파일에 행이 없습니다.")
    normalized = frame.copy()
    normalized.columns = [ALIASES.get(str(column).strip().lower(), str(column).strip().lower()) for column in normalized.columns]
    if not all(options.intersection(normalized.columns) for options in REQUIRED_ANY):
        raise ValueError("champion_id/champion_name과 item_id/item_name/build_order 중 하나씩 필요합니다.")
    if not {"win_rate", "pick_rate", "sample_games"}.intersection(normalized.columns):
        raise ValueError("win_rate, pick_rate, sample_games 중 하나 이상의 집계 지표가 필요합니다.")

    for column in ("champion_id", "item_id", "sample_games", "win_rate", "pick_rate"):
        if column in normalized:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    for column in ("win_rate", "pick_rate"):
        if column not in normalized:
            continue
        # Accept either fractions (0.523) or percentages (52.3), store 0..1.
        values = normalized[column]
        normalized[column] = values.where(values.abs() <= 1, values / 100)
        if normalized[column].dropna().lt(0).any() or normalized[column].dropna().gt(1).any():
            raise ValueError(f"{column}은 0~1 또는 0~100 범위여야 합니다.")
    if "sample_games" in normalized and normalized["sample_games"].dropna().lt(0).any():
        raise ValueError("sample_games는 음수일 수 없습니다.")

    normalized["benchmark_source"] = "lol.ps-manual"
    normalized["usage_scope"] = "external-benchmark-only"
    preferred = [
        "patch", "region", "tier", "role", "champion_id", "champion_name",
        "item_id", "item_name", "build_order", "sample_games", "pick_rate",
        "win_rate", "source_url", "collected_at", "benchmark_source", "usage_scope",
    ]
    return normalized[[column for column in preferred if column in normalized] + [column for column in normalized if column not in preferred]]


def read_lolps_benchmark_upload(filename: str, payload: bytes, sheet_name: str | None = None) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls", ".parquet"}:
        raise ValueError("LOL.PS 벤치마크는 CSV, Excel 또는 Parquet 파일만 지원합니다.")
    raw_path = save_raw_upload(filename, payload)
    return normalize_lolps_benchmark(read_uploaded_file(raw_path, suffix, sheet_name))
