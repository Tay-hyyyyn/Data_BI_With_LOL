# 동결 계약 (병렬 작업 구간)

병렬 세션이 서로를 깨뜨리지 않도록, 아래 시그니처와 산출물은 **변경 금지**다.
변경이 정말 필요하면 작업을 멈추고 계약 소유 스트림(`docs/parallel-plan.md`)에 요청한다.

## 자동으로 강제되는 것

| 계약 | 강제 수단 |
|---|---|
| 공개 HTTP 라우트 집합 | `tests/api/test_contract.py::test_route_set_is_stable` |
| 요청·응답 스키마 전체 | `tests/api/test_contract.py::test_openapi_schema_is_stable` (스냅샷: `tests/api/openapi.snapshot.json`) |

API 스키마를 **의도적으로** 바꿀 때는 스냅샷을 재생성하되, 커밋 메시지에 변경 이유를 적고 diff가 의도한 것뿐인지 확인한다.

## 코드 시그니처

```python
# app/query  (소유: 쿼리 엔진 스트림)
materialize(dataset_id: str, columns: Sequence[str] | None = None, limit: int | None = None) -> pd.DataFrame
schema_of(dataset_id: str) -> dict[str, str]          # 컬럼 -> DuckDB 타입
run(dataset_id, plan: QueryPlan) -> pd.DataFrame       # 아직 NotImplementedError
scalar(dataset_id, plan: QueryPlan) -> float | None    # 아직 NotImplementedError

# app/services/datasets.py  (소유: 스토리지 스트림)
read_frame(dataset_id: str, limit: int | None = None) -> pd.DataFrame   # materialize에 위임
get_version(dataset_id: str) -> dict   # 최소 키: id, dataset_id, version_number, manifest_path, schema_json

# app/services/jobs.py  (소유: 잡 스트림)
job_runner.submit(job_type: str, task: Callable[[], dict]) -> JobSummary

# app/errors.py
api_errors(*rules)  # 라우터는 try/except 대신 이것을 쓴다
NotFoundError / ConflictError / DomainError(status_code=...)
```

## 데이터셋 이름 (사실상 공개 계약)

`services/lol.py`의 대시보드 생성기가 마트를 **이름으로 조회**한다.
이름을 바꾸면 생성 지점과 조회 지점을 **같은 커밋**에서 함께 바꾼다.

- `LoL contextual gold mart {patch}`
- `LoL gold and stat win-rate timeseries {patch}`
- `LoL patch stat trend`
- `LoL sample coverage`

## 공유 파일 규칙

| 파일 | 규칙 |
|---|---|
| `app/main.py`, `app/api/__init__.py` | 편집 금지. 새 라우트는 자기 라우터 파일에 추가 |
| `app/schemas/__init__.py` | 편집 금지. 모델은 도메인 모듈에 추가하고 `__all__`에 등록 |
| `pyproject.toml`, `.github/workflows/ci.yml`, `tests/conftest.py` | 편집 금지. 필요하면 요청 |
| 스트림별 테스트 픽스처 | `tests/<영역>/conftest.py` |

> 한 파일의 소유 스트림은 정확히 하나다. 두 스트림이 같은 파일을 필요로 하면 분할이 잘못된 것이다.
