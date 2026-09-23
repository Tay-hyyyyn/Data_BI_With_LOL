# 병렬 작업 계획

Phase 0(구조 이음매)은 완료되었고 `phase0-baseline` 태그가 기준점이다.
아래 스트림은 **서로 겹치지 않는 파일**을 소유한다. 계약은 `docs/contracts.md`를 따른다.

## 세션 시작 전 (필수)

각 세션은 자기 워크트리와 **분리된 데이터 루트**를 쓴다. 한 체크아웃/한 `data/`를 공유하면
SQLite WAL과 `published/`가 공유 가변 상태가 되어 테스트가 비결정적으로 깨진다.

```bash
git worktree add ../puzzle-ws1 -b ws/1-query-engine phase0-baseline
cd ../puzzle-ws1
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[test,dev]"
echo "DATA_BI_ROOT=./data" > .env      # 워크트리 안의 data/를 사용
```

푸시 전 `make gate`(ruff + mypy + pytest)가 통과해야 한다. 브랜치는 `phase0-baseline`에서 분기하고,
push 전 `git pull --rebase`, 병합은 squash. 커밋 접두는 `feat(ws1): ...` 형식.

## 스트림

### WS-1 · 쿼리 엔진 & BI 푸시다운 (L) — ✅ 완료
- **소유**: `app/query/**`, `app/services/bi/query.py`, `app/services/bi/metrics.py`, `app/api/query.py`, `app/api/metrics.py`, `tests/query/**`
- **하지 말 것**: `services/datasets.py`, `storage.py`, `services/bi/dashboards.py`, `services/transforms/`, `lol/`, 프론트
- **할 일**
  - `run`/`scalar` 구현: `QueryPlan` → 파라미터화된 SQL (식별자는 `schema_of`로 검증, 리터럴은 컬럼 타입으로 강제변환)
  - `query_dataset`/`build_chart`/`_metric_value`를 플랜 기반으로 교체 (히스토그램·박스플롯 분위수·히트맵·표본추출)
  - `list_metrics`의 지표별 전체 스캔 제거
  - **B5**: `astype(str)` 필터 → 타입 강제변환 (널 있는 정수 컬럼의 `"1"` vs `"1.0"`)
- **계약**: `materialize` 시그니처 불변, `DatasetQueryResult`/`DatasetChartResult` 동결, `tests/query/test_bi.py`의 정렬 의미론 유지

### WS-2 · 스토리지·버전·전처리 무결성 (M) — ✅ 완료
- **소유**: `app/storage.py`, `app/services/datasets.py`, `app/database.py`, `scripts/{backup,restore,verify}_*.py`
- **한 일**
  - **B4**: `publish_new_version`을 단일 트랜잭션으로 묶고 `sqlite3.IntegrityError` 시 최대 10회 재시도 (SQLite는 `SELECT`에 쓰기 락을 잡지 않아 한 트랜잭션 안에서도 경합 가능 — 그래서 재시도가 필요). 8스레드·16동시발행 테스트로 확인
  - **B7**: `mkdir(exist_ok=True)` + 기동 시 `cleanup_staging()` 호출(`main.py` lifespan)
  - `manifest_files`가 파일당 sha256을 최초 1회 검증하고 경로별로 캐시(퍼블리시 후 파일은 불변이므로 매 쿼리마다 재해시하지 않음) — 손상 시 `ValueError`
  - `recipes` 테이블을 `GET /datasets/{id}/recipes`로 노출 (`RecipeSummary` 스키마 추가)
  - `DatasetSummary.version_number` 추가 — 프론트 B10 하드코딩 KPI 수정에 이미 사용됨
  - (추가 발견) `initialize_database()`의 연결 누수, `db()`에 `synchronous=FULL`이 적용 안 되던 문제, `backup_data.py`의 비원자적 쓰기(+실패 시 `.tmp` 잔존)도 같이 고쳤음
- **계약**: `get_version()` 최소 키 유지(변경 없음)
- **테스트**: `tests/storage/test_integrity.py`(8개) + `tests/test_backup.py`에 4개 추가

### WS-3 · 잡·파이프라인·스트림·운영 (M) — ✅ 대부분 완료 (남음: `event_schema.json` 결정, 컨테이너 비root)
- **소유**: `app/services/{jobs,pipelines}.py`, `app/api/{jobs,pipelines}.py`, `orchestration/**`, `stream/**`, `docker-compose.yml`, `infra/**`, `apps/*/Dockerfile`, `Makefile`
- **할 일**
  - **B1**: Airflow 멱등키 — f-string이 아니라 태스크 파라미터로 (`{{ data_interval_start }}`, 시간 단위)
  - **B8**: 기동 시 stale job 정리, `list_jobs` N+1 제거
  - 파이프라인 멱등성을 제출 **전** 단일 트랜잭션으로
  - `stream/consumer.py`의 batch_id를 offset 범위 기반으로, `compact.py`의 실행 간 중복 제거·열린 시간대 제외
  - `event_schema.json` 결정: `jsonschema`에 연결하거나 삭제 (지금은 죽은 코드)
  - `.dockerignore`, 헬스체크, 비root, `DATA_BI_PUUID_PEPPER` compose 연결, 포트 `127.0.0.1` 바인딩
- **계약**: `job_runner.submit` 시그니처, `GET /pipelines?enabled=true` 응답 형태

### WS-4 · LoL 도메인·마트·통계 (XL) — ✅ 완료
- **소유**: `app/lol/**`, `app/services/lol.py`, `app/api/lol.py`, `app/schemas/lol.py`, `scripts/collect_lol_sample.py`, `tests/lol/**`
- **한 일**
  - **B6**: `game_duration_s >= minute*60` 게이트 추가 — 경기가 끝난 뒤의 분(minute)에는 마지막 프레임을 복사하지 않고 행 자체를 버린다. 12분 스텀프에서 15·20분 행이 더 이상 생기지 않는지 테스트로 확인
  - 패치 입도를 `build_gold_win_timeseries`까지 포함해 네 마트 모두 `patch_key` 기준으로 통일(이전엔 이 마트만 전체 `game_version`으로 그룹핑해 같은 패치의 빌드 번호가 쪼개졌음)
  - `LoL patch stat trend`·`LoL sample coverage`를 진짜 누적 마트로 재정의 — 이번 요청의 프레임만이 아니라 지금까지 발행된 모든 `LoL contextual gold mart *`를 모아 다시 계산
  - `items.py`를 `items.py`(카탈로그 파싱) / `pricing.py`(Ridge·NNLS) / `marts.py`(마트 생성)로 분할
  - Ridge 입력을 표준편차로 스케일링 후 계수를 원래 단위로 환산 — crit_chance·attack_speed 같은 0~1 스케일 스탯이 L2 페널티에 눌려 0에 가깝게 수렴하던 문제. 실제 16.18.1 패치 데이터로 확인: crit_chance 계수가 3642(이전엔 사실상 0에 가까웠을 것)
  - NNLS에 절편(1로 채운 컬럼) 추가 — Ridge와 같은 추정 대상이 되도록. `nnls_intercept_gold` 컬럼으로 노출
  - 부트스트랩 신뢰구간 제거(아이템 카탈로그는 무작위 표본이 아니라 전수라 통계적으로 무효) → 5-폴드 교차검증 R²(`cv_r2`)로 교체
  - `gold_efficiency_percent`(참조가격 기준)에 더해 `model_gold_efficiency_percent`(회귀모델 기준)를 별도 컬럼으로 추가 — 이전엔 회귀 결과가 어디에도 연결되지 않았음
  - `f"{match_patch}.1"` 버전 추측 제거 → Data Dragon `versions.json`에서 실제 패치에 맞는 버전을 조회(`resolve_version_for_patch`)해 못 찾으면 명확한 404
  - 수집기: `queue` 필터(기본 420 솔로랭크), `start` 페이징, 리전 파라미터화(`RiotAccountResolveRequest`/`RiotMatchCollectRequest`에 필드 추가), `RiotClient`를 `get_riot_client()` 싱글턴으로 — 매 요청마다 새로 만들어 스로틀 상태가 리셋되던 문제 해결
  - `scripts/collect_lol_sample.py`를 `/process-grouped` 호출로 단순화(클라이언트 쪽 패치 분리·버전 추측 로직 제거), `--count` 상한 20→100, `--queue`/`--start`/`--region` 플래그 추가
  - 죽은 코드였던 `fetch_data_dragon` 제거
- **계약**: `lol/`은 FastAPI·SQLite import 금지(유지), 마트는 `pd.DataFrame` 반환(유지), 데이터셋 이름 동결(유지)
- **검증**: 새 테스트 13개(`tests/lol/`) + 회귀 테스트 3개(`test_timeline_survivorship.py`), 전체 97→106개 통과. 키 없이 되는 Data Dragon 동기화를 브라우저로 실제 실행해 16.18.1 패치 254개 아이템에 대해 스케일링 수정이 실제 데이터에서도 작동함을 확인(예: crit_chance ridge 계수 3642, 이전이라면 0에 가까웠을 값)

### WS-5 · 프론트 플랫폼 / WS-6 · 프론트 스튜디오 (M) — ✅ 완료
`docs/frontend-plan.md` 참고. router+TanStack Query+생성 타입으로 재구성, B2·B9·B10 해결,
스튜디오 재작성, 브라우저 실행 검증 완료. 남은 것: `DashboardWidget` 백엔드 스키마 부재(WS-2 소관).

## 진행 상황

WS-1~WS-6 전부 완료. 이 문서와 `docs/frontend-plan.md`가 각 스트림이 실제로 한 일과 남은 항목을 기록한다.
남은 것: WS-3의 `event_schema.json` 결정과 컨테이너 비-root 전환, WS-2 소관의 `DashboardWidget` 백엔드 스키마 부재.

Riot API 키를 확보하면(§6 로드맵) 다음이 열린다: `services/lol.py::process_matches_grouped`로 실제 경기를 수집해
누적 마트(`LoL patch stat trend`, `LoL sample coverage`)가 여러 세션에 걸쳐 실제로 쌓이는지 확인, `queue=420`
필터와 리전 파라미터가 실제 응답에서 의도대로 동작하는지 확인.
