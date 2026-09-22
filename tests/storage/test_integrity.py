"""Storage-layer integrity: concurrent version publishing, corruption detection, crash recovery."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest
from app import storage
from app.database import db
from app.services.datasets import create_dataset_from_frame, list_recipes, publish_new_version, read_frame


def test_concurrent_publishes_all_succeed_with_unique_sequential_versions(client):
    """Regression (B4): MAX(version_number)+1 was read in one connection and inserted in a
    second one, so concurrent writers could compute the same 'next' number and one would fail
    with an uncaught IntegrityError, leaving its Parquet orphaned."""
    dataset = create_dataset_from_frame(pd.DataFrame({"x": [1, 2, 3]}), "concurrent", "test")

    def publish(i: int) -> dict:
        return publish_new_version(dataset.id, pd.DataFrame({"x": [i]}), f"write-{i}", [])

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(publish, range(16)))

    version_numbers = sorted(result["version_number"] for result in results)
    assert version_numbers == list(range(2, 18))  # dataset started at version 1

    with db() as connection:
        count = connection.execute("SELECT COUNT(*) FROM dataset_versions WHERE dataset_id=?", (dataset.id,)).fetchone()[0]
    assert count == 17


def test_manifest_files_rejects_a_corrupted_body(client):
    dataset = create_dataset_from_frame(pd.DataFrame({"x": [1, 2]}), "corrupt-me", "test")
    with db() as connection:
        manifest_path = connection.execute(
            "SELECT manifest_path FROM dataset_versions WHERE dataset_id=?", (dataset.id,)
        ).fetchone()[0]
    body_path = next(iter(storage.manifest_files(manifest_path)))  # first read: verifies and caches
    storage._verified_files.clear()  # force re-verification for this test
    body_path.write_bytes(b"corrupted")

    with pytest.raises(ValueError, match="무결성"):
        storage.manifest_files(manifest_path)


def test_manifest_files_only_hashes_each_path_once(client, monkeypatch):
    dataset = create_dataset_from_frame(pd.DataFrame({"x": [1, 2]}), "hash-once", "test")
    with db() as connection:
        manifest_path = connection.execute(
            "SELECT manifest_path FROM dataset_versions WHERE dataset_id=?", (dataset.id,)
        ).fetchone()[0]
    storage._verified_files.clear()
    calls = []
    original = storage.sha256_file
    monkeypatch.setattr(storage, "sha256_file", lambda path: calls.append(path) or original(path))

    storage.manifest_files(manifest_path)
    storage.manifest_files(manifest_path)

    assert len(calls) == 1


def test_publish_tolerates_a_leftover_staging_directory_from_a_crash(data_root):
    """Regression (B7): a crashed publish could leave `staging/<version_id>/` behind; retrying
    with the same version_id used to fail with FileExistsError instead of overwriting it."""
    frame = pd.DataFrame({"x": [1, 2, 3]})
    stale = data_root / "staging" / "reused-id"
    stale.mkdir(parents=True)
    (stale / "leftover.txt").write_text("from a crashed run", encoding="utf-8")

    result = storage.publish_dataframe("dataset-1", "reused-id", frame)

    assert (data_root / "published" / "dataset-1" / "reused-id" / "manifest.json").is_file()
    assert result["row_count"] == 3


def test_cleanup_staging_removes_orphaned_directories_but_leaves_published_alone(data_root):
    orphan = data_root / "staging" / "orphan-version"
    orphan.mkdir(parents=True)
    (orphan / "part-00000.parquet").write_bytes(b"partial")
    published = data_root / "published" / "dataset-1" / "v1"
    published.mkdir(parents=True)
    (published / "manifest.json").write_text("{}", encoding="utf-8")

    storage.cleanup_staging()

    assert not orphan.exists()
    assert published.is_file() is False and published.is_dir()  # untouched


def test_recipe_lineage_is_recorded_and_listable(client, dataset):
    from app.schemas import TransformRequest, TransformStep
    from app.services.transforms import run_recipe

    run_recipe(
        dataset["id"],
        TransformRequest(name="첫 정리", steps=[TransformStep(operation="drop_duplicates", config={"columns": ["channel"]})]),
    )

    recipes = list_recipes(dataset["id"])

    assert len(recipes) == 1
    assert recipes[0].name == "첫 정리"
    assert recipes[0].steps[0]["operation"] == "drop_duplicates"


def test_list_recipes_rejects_unknown_dataset(client):
    with pytest.raises(KeyError):
        list_recipes("does-not-exist")


def test_a_corrupted_old_version_does_not_block_reading_a_freshly_published_one(client):
    """The verification cache is keyed by path, so a version-1 file corrupted after the fact does
    not poison reads of version 2, which lives at its own fresh path."""
    dataset = create_dataset_from_frame(pd.DataFrame({"x": [1]}), "recover", "test")
    with db() as connection:
        old_manifest_path = connection.execute(
            "SELECT manifest_path FROM dataset_versions WHERE dataset_id=?", (dataset.id,)
        ).fetchone()[0]
    old_body = next(iter(storage.manifest_files(old_manifest_path)))
    old_body.write_bytes(b"corrupted after the fact")

    publish_new_version(dataset.id, pd.DataFrame({"x": [1, 2]}), "fix", [])

    assert len(read_frame(dataset.id)) == 2
