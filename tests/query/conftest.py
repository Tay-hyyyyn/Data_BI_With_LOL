from __future__ import annotations

import pytest
from app.services.datasets import create_dataset_from_frame


@pytest.fixture
def publish(client):
    """Publish a DataFrame through the real path and return its dataset id."""
    counter = iter(range(1_000))

    def _publish(frame, name: str | None = None) -> str:
        return create_dataset_from_frame(frame, name or f"test-{next(counter)}", "test").id

    return _publish
