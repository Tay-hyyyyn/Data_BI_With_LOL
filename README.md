# Data BI With LoL

범용 파일 데이터 처리와 관계 추천, 대시보드 탐색을 중심으로 만든 로컬 퍼스트 BI 플랫폼입니다. League of Legends 데이터는 제품 기능을 검증하는 심화 사례로 분리합니다.

## 현재 구현 범위

- CSV·Excel·Parquet 업로드와 스키마 프로파일링
- 원본 보존, staging 작성, manifest 기반 Parquet 원자적 게시
- SQLite WAL 메타데이터와 인메모리 DuckDB 조회
- Spearman, 보정 Cramér's V, η² 기반 컬럼 관계 추천
- React·TypeScript 분석 작업공간과 ECharts 미리보기
- FastAPI와 동일 서비스를 사용하는 FastMCP 도구
- 순서형 전처리 API(선택·이름변경·형변환·결측·중복·필터·계산·집계·피벗)
- 전처리 레시피 화면과 원자적 새 버전 게시
- 전체 Parquet 대상 구조화 집계·그룹·필터 API(임의 SQL 비노출)
- KPI·막대·선·히스토그램·산점도·박스플롯·히트맵 위젯
- 공통 필터, 드래그 정렬, 저장·재편집·복제·게시 대시보드
- 단일 프로세스 비동기 JobRunner와 작업 상태 화면
- 활성 파이프라인 레지스트리·토글·멱등 실행 API와 Airflow 공통 DAG 연동
- Data Dragon 아이템 파서, 기준가격·양수 Ridge·bootstrap 분석 코어
- Data Dragon 챔피언·룬 정규화와 동일 패치 멱등 동기화
- Riot ID→PUUID 확인 및 Development Key 장기 한도 기반 요청 조절
- NNLS·양수 Ridge 계수 병렬 산출과 경기–아이템 패치 일치 검증
- Match-V5·Timeline 원본의 참가자·10/15/20분 상태·아이템 이벤트 정규화
- 인벤토리 비용·팀/라인 골드 격차·관찰 승패를 결합한 LoL 문맥 분석 마트
- 인벤토리가 제공하는 AP·AD·스킬 가속 등 시점별 스탯과 500골드 구간별 관찰 승률 시계열 마트
- 허가받은 LOL.PS CSV·Excel·Parquet 집계를 위한 수동 benchmark 입력 계약
- 웹 LoL 실험실에서 정적 동기화→계정 확인→경기 수집→마트 생성을 순서대로 실행
- 선택형 Airflow Dynamic Task Mapping 및 Redpanda JSONL→Parquet 컴팩션 실습
- Docker Compose 및 로컬 직접 실행

## 로컬 실행

Python 3.12 이상에서:

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[test,mcp]"
uvicorn app.main:app --app-dir apps/backend --reload
```

프로젝트 루트의 `.env`는 애플리케이션 시작 시 자동으로 읽으며, 이미 `.gitignore`에 포함되어 Git에 저장되지 않습니다.

다른 터미널에서:

```bash
cd apps/frontend
pnpm install
pnpm dev
```

브라우저에서 `http://localhost:5173`을 엽니다. API 문서는 `http://localhost:8000/docs`에서 확인합니다.

Riot ID의 최근 경기 표본은 `.env`의 키를 노출하지 않고 다음처럼 수집할 수 있습니다. 여러 패치가 섞이면 패치별 Data Dragon 데이터와 분석 마트로 자동 분리되며, 같은 표본의 재실행은 기존 이름의 데이터셋을 멱등 갱신합니다.

```bash
python scripts/collect_lol_sample.py "게임이름#태그" --count 20
```

LoL 실험실의 **BI 시작 대시보드**는 선택 패치의 평균 골드, 인벤토리 제공 AP·AD·스킬 가속, 골드 구간별 관찰 승률, 팀 골드 격차 산점도를 비공개 대시보드로 생성합니다. 승률은 표본 기반 관찰값이며 인과효과가 아닙니다.

여러 패치의 경기를 함께 수집해도 LoL 실험실이 패치별 아이템 카탈로그로 분리 처리하고 `LoL patch stat trend` 데이터셋을 생성합니다. 이 마트는 패치·10/15/20분별 평균 골드와 인벤토리 제공 스탯을 비교하는 용도입니다.

같은 처리 흐름은 `LoL sample coverage`도 생성합니다. 이 마트는 패치·시점·포지션별 경기/참가자/챔피언 표본 수와 빈 인벤토리 비율을 보여 주므로, 적은 표본이나 특정 포지션 편향을 분석 결과와 함께 확인할 수 있습니다.

`LoL 패치 비교·표본 품질 대시보드`는 위 두 마트를 이용해 패치별 10/15/20분 골드·인벤토리 AD/AP/스킬 가속과 표본 수·결측 비율을 다중 계열 선 차트로 비교합니다. 이 다중 계열 기능은 LoL에 한정되지 않아, 일반 데이터셋에서도 시간/숫자 축과 범주형 계열을 선택해 같은 방식으로 사용할 수 있습니다.

LoL 타임라인처럼 한 참가자가 여러 시점에 반복되는 데이터의 관계 분석은 `match_participant_key`, `minute`, `latest`를 함께 지정합니다. FastMCP의 `analyze_column_relationships` 도구도 동일한 `entity_key`, `time_column`, `analysis_grain` 인자를 지원합니다.

합성 마케팅 데이터는 다음 명령으로 만듭니다.

```bash
python scripts/generate_marketing_sample.py
```

## Docker

```bash
docker compose up --build
```

웹은 `http://localhost:8080`, API는 `http://localhost:8000`에서 실행됩니다. `data/`는 호스트 볼륨에 유지됩니다.

Airflow는 `/api/v1/pipelines?enabled=true`에서 활성 정의만 읽으며 동일 `idempotency_key` 재실행은 기존 작업을 반환합니다. 기본 BI는 Airflow가 없어도 로컬 `JobRunner`로 동일 작업을 수행합니다.

## 백업 및 검증

실행 중인 SQLite WAL 데이터베이스와 게시된 Parquet를 일관된 ZIP으로 백업합니다. 기본 백업에는 원본 업로드와 Riot Bronze 데이터가 포함되지 않으며, 필요한 경우에만 명시적으로 포함합니다. `.env`와 API 키는 어떤 경우에도 백업하지 않습니다.

```bash
python scripts/backup_data.py
python scripts/verify_backup.py backups/data-bi-YYYYMMDD-HHMMSS.zip
python scripts/backup_data.py --include-raw
python scripts/restore_data.py backups/data-bi-YYYYMMDD-HHMMSS.zip --data-root data-restored
```

복원은 비어 있는 대상 디렉터리에서만 허용됩니다. 기존 `data/`를 덮어쓰지 않으므로, 복원 결과를 점검한 뒤 필요하면 앱을 중지하고 `DATA_BI_ROOT=data-restored`로 실행해 확인할 수 있습니다.

## FastMCP

API를 먼저 실행한 뒤 다음 서버를 stdio MCP로 등록합니다.

```bash
python apps/backend/app/mcp_server.py
```

`.mcp.json.example`을 `.mcp.json`으로 복사해 호환 클라이언트에 연결할 수 있습니다. 제공 도구는 `list_datasets`, `describe_dataset`, `preview_dataset`, `query_dataset`, `analyze_column_relationships`, `generate_chart_spec`, `get_job_status`이며 임의 SQL·파일 경로·JavaScript 실행은 노출하지 않습니다.

상세 구조와 불변 조건은 [docs/architecture.md](docs/architecture.md)를 참고하세요.

## 안전 경계

- 모든 업로드 데이터와 Riot 개발 키 기반 결과는 기본적으로 `private`입니다.
- Riot 데이터가 연결된 대시보드는 `RIOT_ENABLE_PUBLIC_DATA=true`의 명시적 승인 없이는 게시가 거부됩니다.
- `DATA_BI_ENV=production`에서 개발 키 사용을 차단하는 LoL 수집 계층을 추가합니다.
- `reference_data_analysis_process/`는 참고 자료이며 애플리케이션이 수정하거나 런타임 입력으로 사용하지 않습니다.
- LOL.PS 연동은 공식 허가·문서가 확인되기 전까지 파일 업로드 방식만 제공하며 비공개 엔드포인트를 호출하지 않습니다.

LOL.PS 등에서 정식으로 제공받은 집계 파일은 `samples/lolps_benchmark_template.csv` 계약에 맞춰 LoL 실험실의 선택 입력란에 등록할 수 있습니다. 템플릿 값은 형식 설명용 예시이며 실제 LOL.PS 통계가 아닙니다.
