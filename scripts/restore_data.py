"""Restore a verified Data BI backup into an empty data directory.

The script intentionally refuses a non-empty target. Point ``DATA_BI_ROOT`` to
the restored directory after stopping the application, or swap directories with
an operating-system level backup procedure after inspecting the result.
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = Path(__file__).with_name("verify_backup.py")


def verifier():
    spec = importlib.util.spec_from_file_location("data_bi_verify_backup", VERIFY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_backup


def restore_backup(archive_path: Path, target: Path) -> Path:
    manifest = verifier()(archive_path)
    target = target.resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"복원 대상은 비어 있어야 합니다: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="data-bi-restore-", dir=target.parent) as temporary:
        staged = Path(temporary) / "data"
        staged.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            for item in manifest["files"]:
                relative = Path(item["path"])
                destination = staged / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(relative.as_posix()) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
        if target.exists():
            target.rmdir()
        shutil.move(str(staged), str(target))
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a verified Data BI backup into an empty directory.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT / "data-restored")
    args = parser.parse_args()
    print(restore_backup(args.archive, args.data_root))


if __name__ == "__main__":
    main()
