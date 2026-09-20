"""Check a running Data BI API without reading credentials or modifying data."""
from __future__ import annotations

import argparse
import json
from urllib.request import urlopen


def check(url: str) -> dict:
    with urlopen(f"{url.rstrip('/')}/api/health", timeout=5) as response:  # nosec B310 - operator-supplied local URL
        payload = json.loads(response.read())
    if payload.get("status") != "ok" or not payload.get("storage_ready"):
        raise RuntimeError("API 상태 또는 저장소 준비 상태가 정상적이지 않습니다.")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the Data BI API health endpoint.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    print(json.dumps(check(parser.parse_args().url), ensure_ascii=False))


if __name__ == "__main__":
    main()
