# 로컬·단일 서버 배포

이 프로젝트의 기본 배포 단위는 React 정적 웹, FastAPI, 호스트 볼륨의 SQLite·Parquet 데이터 디렉터리다. Docker Compose는 단일 머신용이며, 여러 백엔드 복제본을 동시에 실행하지 않는다. SQLite의 단일 쓰기 원칙을 유지하기 위해서다.

## 준비

```powershell
Copy-Item .env.deploy.example .env.deploy
docker compose up --build -d
python scripts/healthcheck.py
```

웹은 `http://localhost:8080`, API 상태는 `http://localhost:8000/api/health`에서 확인한다. Compose의 backend와 frontend는 각각 healthcheck가 성공해야 정상 상태가 된다.

`.env.deploy`는 Git에 포함되지 않는다. 공개 환경에는 Riot Development Key를 넣지 않는다. Riot Production Key 승인 전에는 `RIOT_ENABLE_PUBLIC_DATA=false`를 유지한다.

HTTPS 역방향 프록시와 실제 도메인을 사용하는 경우에는 `DATA_BI_AUTH_COOKIE_SECURE=true`로 바꾼다. `localhost` HTTP 검증에서는 `false`를 유지한다.

`admin`은 사용자 계정을 만들고 모든 변경을 수행할 수 있다. `analyst`는 데이터·모델·대시보드를 만들 수 있고, `viewer`는 조회만 가능하다. FastMCP를 인증 환경에서 실행해야 한다면 권한이 제한된 bearer token을 `DATA_BI_MCP_AUTH_TOKEN`으로 별도 주입한다. 이 값도 Git에 저장하지 않는다.

대시보드의 **공유**는 무작위 토큰 링크를 만들지만 인증을 우회하지 않는다. 링크를 받은 사람도 로그인해야 하며 조회 화면에서는 편집 기능이 노출되지 않는다. 필요 없어진 링크는 API에서 해제할 수 있으며, 해제 후에는 다시 열 수 없다.

## 업데이트와 롤백

업데이트 전에는 반드시 백업을 만든다.

```powershell
python scripts/backup_data.py
python scripts/verify_backup.py backups/<backup-file>.zip
docker compose up --build -d
python scripts/healthcheck.py
```

문제가 생기면 컨테이너를 중지하고, 비어 있는 `data-restored` 경로에 백업을 복원한 뒤 `DATA_BI_ROOT=data-restored`로 점검한다. 기존 `data/`를 자동으로 덮어쓰지 않는다.

```powershell
docker compose down
python scripts/restore_data.py backups/<backup-file>.zip --data-root data-restored
```

## 운영 경계

- `data/`는 SQLite 메타데이터와 게시 Parquet를 함께 보관하므로 호스트의 정기 백업 대상이다.
- DB Connector는 읽기 전용 계정과 환경변수 URL만 사용한다.
- Airflow·Redpanda는 `infra/lab/docker-compose.lab.yml`의 선택형 학습 프로필이며 기본 배포에 포함되지 않는다.
