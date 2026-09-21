# 프론트엔드 작업 계획

Phase 0에서는 프론트 구조 이동을 하지 않았고, B2·B9만 고쳤다.
환경: **Node 22, pnpm 11.19.0** 설치 완료, `pnpm build` 통과.

## 확인된 문제 (검증 완료된 것만)

| ID | 위치 | 내용 | 상태 |
|---|---|---|---|
| B2 | `src/EChart.tsx:7` | `use([...])`에 `BoxplotChart`, `LegendComponent` 누락 → 박스플롯 미렌더링, 다계열 범례 없음 | **수정·검증 완료** (빌드 통과, 박스플롯 렌더링 확인) |
| B9 | `src/dashboard-extra.css` | `--line --panel --surface --text --muted`가 정의된 곳 없음 | **수정 완료** (빌드 통과) |
| B10 | `src/App.tsx:131` | "현재 버전" KPI가 `v1` 하드코딩 | 백엔드 `version_number` 필드 필요 (WS-2) |
| — | `src/types.ts` | 수기 작성, 이미 백엔드와 드리프트 (`RelationshipResponse`에 `dataset_id`/`version_id` 없음) | 미착수 |
| — | 전 Studio | 동일한 try/catch/setMessage 블록 12회 복붙, 알림 채널 6개 | 미착수 |
| — | `DashboardStudio.tsx:75` 외 | 한 줄에 수천 자인 JSX, `styles.css`/`studio.css`는 압축된 한 줄 | 미착수 |

## 순서

1. **품질 게이트**: eslint(flat) + prettier + vitest + testing-library + msw, `typecheck` 스크립트
2. **타입 생성**: `apps/frontend/openapi.json`(`make types`로 생성됨) → `openapi-typescript` → `src/api/generated.ts`. 수기 `types.ts` 삭제. CI에서 재생성 후 `git diff --exit-code`
3. **플랫폼**: react-router, `lib/apiClient.ts`(`ApiError`), TanStack Query 훅, `useToast` 하나로 알림 통일, `EChart`를 mount 시 1회 `init` + `setOption` + `ResizeObserver`로
4. **스튜디오 재작성**: 12개의 복붙 블록 제거, 한 줄 JSX 분해, vitest 추가
5. **CSS**: prettier로 1회 포매팅 → 토큰화, 브레이크포인트 6종(650/720/760/850/1000/1100)을 3종으로

## 소유 분할

- **플랫폼** (`src/{main.tsx,app,lib,components,styles}`, `features/{datasets,dashboards}`, `package.json`): 위 1~3
- **스튜디오** (`features/{prep,metrics,pipelines,lol}`, `src/test`): 위 4. 플랫폼이 훅과 `useToast`를 공개한 뒤 시작

`package.json`은 플랫폼 스트림만 편집한다.
