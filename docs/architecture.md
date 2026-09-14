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
  DDB --> REL[Relationship Analyzer]
  DDB --> QUERY[Typed aggregate / group / filter]
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
