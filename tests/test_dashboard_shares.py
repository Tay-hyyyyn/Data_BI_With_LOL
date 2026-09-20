from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import database
from app.schemas import DashboardWrite
from app.services import bi


def test_authenticated_dashboard_share_can_be_revoked(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(database, "settings", SimpleNamespace(root=tmp_path))
    database.initialize_database()
    dashboard = bi.save_dashboard(DashboardWrite(name="Shared", widgets=[], filters=[]))
    share = bi.create_dashboard_share(dashboard.id)

    assert bi.get_shared_dashboard(share["token"]).id == dashboard.id
    bi.revoke_dashboard_share(share["token"])
    with pytest.raises(KeyError):
        bi.get_shared_dashboard(share["token"])
