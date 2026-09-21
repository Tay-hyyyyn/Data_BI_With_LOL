# Architecture

```mermaid
flowchart LR
  U[CSV / Excel / Parquet] --> API[FastAPI service layer]
  DD[Data Dragon] --> LOL[LoL adapter] --> API
  RIOT[Match-V5 / Timeline] --> LOL
  API --> RAW[Immutable raw]
  API --> STG[Staging Parquet]
  STG -->|manifest + atomic rename| PUB[Published Parquet]
  API --> META[SQLite WAL metadata]
  PUB --> DDB[In-memory DuckDB]
  DDB -->|"materialize (SELECT *)"| REL[Relationship Analyzer]
  DDB -->|"QueryPlan -> SQL pushdown"| QUERY[Structured aggregate / group / filter]
  API --> JOB[Single-process JobRunner]
  JOB --> REL
  REL --> WEB[React + ECharts]
  API --> MCP[FastMCP tools]
  RP[Redpanda optional] --> JSONL[JSONL bronze] --> CMP[64MiB / hourly compaction] --> PUB
  AF[Airflow optional] --> API
```

## 불변 조건

1. 게시 데이터는 manifest가 확정된 버전만 읽는다.
2. DuckDB는 인메모리 연결에서 Parquet를 직접 조회하여 파일 락을 공유하지 않는다.
3. SQLite는 상태·설정만 짧게 쓰며 WAL과 5초 busy timeout을 사용한다.
4. 웹과 FastMCP는 동일한 서비스/API 계약을 사용한다.
5. 스트리밍은 at-least-once 전달과 `event_id` 멱등 반영을 목표로 한다.
6. Riot 개발 키와 파생 데이터는 production 공개 환경에서 사용할 수 없다.
7. Match 참가자 식별자는 원문 대신 HMAC-SHA256 값만 Silver 이후에 게시한다.
8. 대시보드와 MCP 집계는 미리보기 행이 아니라 동일한 게시 버전 전체를 조회한다.

## 현재 구현과 목표의 차이

BI 집계·차트·지표는 DuckDB로 푸시다운된다(2M행 기준 82ms, 이전 방식 1.66s). 아직 남은 차이:

| 항목 | 현재 | 목표 |
|---|---|---|
| 관계 분석·전처리·LoL 마트 | `query.materialize`로 전체를 pandas에 올려 처리 (정당한 pandas 작업이지만 큰 데이터에서는 메모리 부담) | 필요한 컬럼만 `columns=`로 투영 |

각 항목은 `docs/parallel-plan.md`의 담당 스트림이 해결하며, 해결되면 이 표에서 삭제한다.

## 모듈 구조

```
app/main.py          앱 팩토리 (라우터 등록·미들웨어·lifespan만)
app/api/*            HTTP 라우터. 파싱 → 서비스 호출 → 반환
app/errors.py        api_errors() 컨텍스트 매니저, DomainError 계열
app/schemas/*        도메인별 Pydantic 모델 (app.schemas에서 재노출)
app/services/*       비즈니스 로직 (bi/, transforms/, lol.py, datasets.py ...)
app/query/*          DuckDB 경계: QueryPlan, materialize, schema_of
app/lol/*            순수 LoL 도메인 (FastAPI·SQLite 의존 금지)
```
