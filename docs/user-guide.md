# 사용 가이드

내 PC에서 프로그램을 직접 실행하고 화면으로 써보는 방법입니다. 모든 데이터는 이 PC 안(`data/` 폴더)에만 저장됩니다.

## 1. 준비물

| 도구 | 버전 | 확인 |
|---|---|---|
| Python | 3.12 이상 | `python --version` |
| Node.js | 22 | `node --version` |
| pnpm | 11.19 | `pnpm --version` |

Node/pnpm 설치 방법(Windows): `winget install OpenJS.NodeJS.22` 후 `npm install -g pnpm@11.19.0`

## 2. 처음 한 번만: 설치

프로젝트 폴더에서:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[test,dev]"
cd apps/frontend
pnpm install
```

## 3. 실행 (터미널 2개)

**터미널 1 — 백엔드**

```bash
.venv/Scripts/python -m uvicorn app.main:app --app-dir apps/backend --reload
```

**터미널 2 — 프론트엔드**

```bash
cd apps/frontend
pnpm dev
```

브라우저에서 <http://localhost:5173> 을 엽니다.
API 문서(직접 호출해볼 수 있음)는 <http://localhost:8000/docs> 입니다.

종료는 각 터미널에서 `Ctrl+C`.

> `make api` / `make web`으로도 실행할 수 있습니다(`make`가 설치된 경우).

## 4. 첫 실행 따라 해보기 (약 3분)

1. 왼쪽 아래 **파일 가져오기**(또는 위쪽 **업로드**)를 눌러 `samples/marketing_campaigns.csv`를 올립니다.
   CSV·Excel(.xlsx)·Parquet를 지원하고 기본 최대 크기는 100MB입니다.
2. **데이터 허브**에 행 수(2,000)·컬럼 수(9)·데이터 완성도가 표시됩니다.
3. 기준 컬럼(예: `channel`)을 고르고 **관계 찾기**를 누르면, 그 컬럼과 통계적으로 관련이 큰 컬럼들이
   순위와 차트로 나옵니다. 숫자↔숫자는 Spearman, 범주↔범주는 Cramér's V, 범주↔숫자는 η²를 씁니다.
4. **대시보드** → 위젯 종류(KPI·막대·선·히스토그램·산점도·박스플롯·히트맵)와 컬럼을 고르고
   **위젯 추가** → **저장**.
5. 오른쪽 위 필터로 채널 등을 걸면 모든 위젯이 같이 바뀝니다.

## 5. 화면별 안내

| 메뉴 | 하는 일 |
|---|---|
| **데이터 허브** | 업로드, 컬럼 프로파일, 미리보기, 컬럼 관계 추천 |
| **전처리 레시피** | 선택·이름변경·형변환·결측 채우기·중복 제거·필터·계산·집계·피벗·**다른 데이터셋 조인**을 순서대로 쌓아 실행. 결과는 새 버전으로 저장되고 원본은 그대로 남습니다 |
| **지표 정의** | 합계·평균·비율 등 재사용할 KPI를 이름 붙여 저장 |
| **대시보드** | 위젯 조합, 공통 필터, 드래그로 순서 변경, 저장·복제·게시 |
| **파이프라인** | 전처리/관계 분석을 등록해 두고 "한 번 실행"하거나 자동 실행(Airflow) 대상으로 켜기. 작업 진행 상황도 여기서 봅니다 |
| **LoL 실험실** | League of Legends 데이터 수집·분석 (아래 6장) |

## 6. LoL 실험실

두 부분으로 나뉩니다.

**API 키 없이 바로 쓸 수 있는 것**
- **패치 정적 데이터**: Riot의 공개 Data Dragon에서 아이템·챔피언·룬을 내려받아 데이터셋으로 만듭니다.
  Data Dragon 버전을 비우면 최신 패치입니다.

**Riot API 키가 필요한 것** (Riot ID 확인 → 최근 경기 수집 → 분석 마트 생성 → 시작 대시보드)

1. <https://developer.riotgames.com> 에서 Development Key 발급 (**24시간마다 만료**되어 매일 재발급)
2. 프로젝트 루트에 `.env` 파일을 만들고 `.env.example`을 참고해 채웁니다.
   ```
   RIOT_API_KEY=발급받은키
   DATA_BI_PUUID_PEPPER=아무도_모르는_긴_임의_문자열
   ```
   `.env`는 git에 올라가지 않습니다. **키를 채팅·이슈·커밋에 붙여넣지 마세요.**
3. 백엔드를 다시 시작한 뒤 화면에서 게임 이름·태그를 넣고 순서대로 진행합니다.

> 수집한 경기와 파생 데이터는 **공개 게시가 차단**되어 있습니다(Riot 정책). 대시보드는 항상 비공개로 저장됩니다.
> 표본이 적을 때(수십 경기) 승률 등은 오차가 매우 큽니다. 화면의 승률은 관찰값이며 인과 효과가 아닙니다.

명령줄로 수집하려면:

```bash
.venv/Scripts/python scripts/collect_lol_sample.py "게임이름#태그" --count 20
```

기본값은 솔로랭크(`queue=420`)만 수집합니다. 다른 큐를 포함하려면 `--queue -1`, 더 과거 경기는
`--start`로 페이징, 다른 리전은 `--region`(americas/asia/europe/sea)으로 지정합니다. `--count`는 최대 100까지 됩니다.

## 7. 데이터는 어디에 저장되나요?

`data/` 폴더 (git에 올라가지 않음):

| 경로 | 내용 |
|---|---|
| `data/metadata.db` | 데이터셋·대시보드·지표·작업 기록 |
| `data/published/` | 게시된 데이터 (Parquet) |
| `data/raw/` | 업로드한 원본 파일 |
| `data/bronze/` | Riot 원본 응답 |

**처음부터 다시 시작**하려면 서버를 끄고 `data/` 폴더를 삭제하면 됩니다.

**백업/복구**

```bash
.venv/Scripts/python scripts/backup_data.py            # backups/ 에 zip 생성 (원본 업로드 포함은 --include-raw)
.venv/Scripts/python scripts/verify_backup.py <zip>    # 무결성 검증
.venv/Scripts/python scripts/restore_data.py <zip>      # 기본은 data-restored/ (비어 있어야 함)
```

## 8. 문제가 생기면

| 증상 | 확인 |
|---|---|
| 화면에 "백엔드에 연결할 수 없습니다" | 터미널 1(백엔드)이 떠 있는지, <http://localhost:8000/api/health> 가 `ok`를 주는지 |
| `pnpm`을 찾을 수 없음 | Node 설치 후 **터미널을 새로 열기** (PATH 갱신) |
| 업로드가 422 | 지원하지 않는 형식이거나 행 100만/컬럼 200 초과 |
| LoL 수집이 401 | `.env`의 `RIOT_API_KEY`가 비었거나 만료됨 (24시간) |
| 포트 사용 중 | 8000/5173을 쓰는 다른 프로그램 종료 |
| 개발 중 변경 확인 | 백엔드는 `--reload`로 자동 반영, 프론트는 저장 시 자동 반영 |

## 9. 개발자용

```bash
make gate         # ruff + mypy + pytest (푸시 전에 실행)
make types        # OpenAPI 스키마를 apps/frontend/openapi.json으로 내보내기
python scripts/bench_query.py 2000000   # 집계 성능 측정 (임시 폴더 사용, 내 data/ 안 건드림)
```

프론트엔드 쪽:

```bash
cd apps/frontend
pnpm lint          # eslint
pnpm typecheck     # tsc --noEmit
pnpm test          # vitest
pnpm gen:types     # openapi.json이 바뀌었을 때 src/api/generated.ts 재생성
```

구조와 계약은 [architecture.md](architecture.md), [contracts.md](contracts.md),
병렬 작업 분담은 [parallel-plan.md](parallel-plan.md)를 보세요.
