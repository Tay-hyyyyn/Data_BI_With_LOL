from __future__ import annotations

import json
import sqlite3
import uuid

import pandas as pd

from ..database import db
from ..schemas import AnalysisModelRun, AnalysisModelSummary, AnalysisModelWrite, ModelJoin
from .datasets import get_version, read_frame, sync_named_dataset, utcnow


def _from_row(row) -> AnalysisModelSummary:
    data = dict(row)
    return AnalysisModelSummary(
        id=data["id"], name=data["name"], base_dataset_id=data["base_dataset_id"],
        joins=[ModelJoin.model_validate(item) for item in json.loads(data["joins_json"])],
        output_dataset_id=data["output_dataset_id"], created_at=data["created_at"], updated_at=data["updated_at"],
    )


def list_models() -> list[AnalysisModelSummary]:
    with db() as connection:
        rows = connection.execute("SELECT * FROM analysis_models ORDER BY updated_at DESC").fetchall()
    return [_from_row(row) for row in rows]


def get_model(model_id: str) -> AnalysisModelSummary:
    with db() as connection:
        row = connection.execute("SELECT * FROM analysis_models WHERE id=?", (model_id,)).fetchone()
    if not row:
        raise KeyError(model_id)
    return _from_row(row)


def create_model(payload: AnalysisModelWrite) -> AnalysisModelSummary:
    get_version(payload.base_dataset_id)
    for join in payload.joins:
        get_version(join.dataset_id)
    model_id, now = uuid.uuid4().hex, utcnow()
    with db() as connection:
        try:
            connection.execute(
                "INSERT INTO analysis_models(id,name,base_dataset_id,joins_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (model_id, payload.name, payload.base_dataset_id, json.dumps([join.model_dump() for join in payload.joins]), now, now),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("같은 이름의 분석 모델이 이미 있습니다.") from error
    return get_model(model_id)


def _assert_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [name for name in columns if name not in frame.columns]
    if missing:
        raise ValueError(f"분석 모델에 없는 조인 컬럼: {', '.join(missing)}")


def build_model(model_id: str) -> dict:
    model = get_model(model_id)
    inputs: dict[str, str] = {model.base_dataset_id: get_version(model.base_dataset_id)["id"]}
    frame = read_frame(model.base_dataset_id)
    base_rows = max(len(frame), 1)
    try:
        for index, join in enumerate(model.joins, start=1):
            inputs[join.dataset_id] = get_version(join.dataset_id)["id"]
            right = read_frame(join.dataset_id)
            _assert_columns(frame, join.left_on)
            _assert_columns(right, join.right_on)
            frame = frame.merge(
                right, how=join.how, left_on=join.left_on, right_on=join.right_on,
                suffixes=("", f"_join{index}"), validate=join.cardinality, sort=False,
            )
            if len(frame) > base_rows * 10:
                raise ValueError("조인 결과가 기준 데이터의 10배를 초과했습니다. 조인 키와 카디널리티를 검토하세요.")
        dataset = sync_named_dataset(frame, f"모델 · {model.name}", "model")
        now = utcnow()
        with db() as connection:
            connection.execute("UPDATE analysis_models SET output_dataset_id=?,updated_at=? WHERE id=?", (dataset.id, now, model.id))
            connection.execute(
                "INSERT INTO analysis_model_runs(id,model_id,output_dataset_id,input_versions_json,row_count,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, model.id, dataset.id, json.dumps(inputs), len(frame), "published", now),
            )
        return {"model_id": model.id, "dataset_id": dataset.id, "row_count": len(frame), "status": "published"}
    except Exception as error:
        with db() as connection:
            connection.execute(
                "INSERT INTO analysis_model_runs(id,model_id,input_versions_json,status,message,created_at) VALUES(?,?,?,?,?,?)",
                (uuid.uuid4().hex, model.id, json.dumps(inputs), "failed", str(error), utcnow()),
            )
        raise


def list_model_runs(model_id: str, limit: int = 20) -> list[AnalysisModelRun]:
    get_model(model_id)
    with db() as connection:
        rows = connection.execute("SELECT * FROM analysis_model_runs WHERE model_id=? ORDER BY created_at DESC LIMIT ?", (model_id, min(max(limit, 1), 100))).fetchall()
    return [AnalysisModelRun(
        id=row["id"], model_id=row["model_id"], output_dataset_id=row["output_dataset_id"],
        input_versions=json.loads(row["input_versions_json"]), row_count=row["row_count"],
        status=row["status"], message=row["message"], created_at=row["created_at"],
    ) for row in rows]
