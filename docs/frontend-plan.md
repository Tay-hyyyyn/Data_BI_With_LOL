# 프론트엔드 구조 개편 — 완료 기록

Node 22 / pnpm 11.19.0으로 §1~4를 전부 완료했다. `pnpm lint`·`pnpm typecheck`·`pnpm test`·`pnpm build`
전부 통과하고, 실제 브라우저에서 모든 라우트·박스플롯 위젯·모바일(375px) 레이아웃을 확인했다.

## 확인된 문제 처리 결과

| ID | 위치 | 내용 | 상태 |
|---|---|---|---|
| B2 | `EChart.tsx` | `BoxplotChart`/`LegendComponent` 미등록 → 박스플롯 미렌더링 | **해결.** `components/echarts-registry.ts` 한 곳에서만 등록. 브라우저에서 박스플롯 렌더링 확인 |
| B9 | `dashboard-extra.css` | `--line --panel --surface --text --muted` 미정의 | **해결.** `styles/tokens.css`에 정의, `layout.css`/`components.css`가 참조 |
| B10 | `App.tsx:131` | "현재 버전" KPI가 `v1` 하드코딩 | **해결.** 백엔드에 `DatasetSummary.version_number` 추가(WS-2 선행 작업) 후 `DataHubPage`가 실값 표시 |
| — | `types.ts` | 수기 작성, 백엔드와 드리프트 | **해결.** 삭제. `api/generated.ts`(openapi-typescript 생성) + `api/types.ts`(별칭)로 교체. `DashboardWidget`만 예외(백엔드에 스키마가 없어 원래도 타입이 없었음 — §4 참고) |
| — | 전 Studio 복붙 try/catch | 12회 복붙, 알림 채널 6개 | **해결.** `components/Toast.tsx`의 `useToast()` 하나로 통합 |
| — | 한 줄 JSX, 압축 CSS | `DashboardStudio.tsx:75` 등 | **해결.** `features/*`로 분해, `styles/{tokens,base,components,layout}.css`로 재작성(포맷만 변경, 규칙 내용은 동일) |
| — | `EChart.tsx` dispose-on-change | 옵션 바뀔 때마다 캔버스 재생성 | **해결.** mount 시 1회 `init`, 이후 `setOption`. `ResizeObserver`로 교체(`window.resize` 제거) |
| — (신규 발견) | `WidgetCard`의 카테고리 매칭 | 그룹 없는 위젯(예: 그룹 미지정 막대/선 차트)에서 x축 라벨은 `index+1`인데 조회는 `row.category` 원본값이라 항상 불일치 → 막대가 항상 비어 보임 | **해결.** `widgetOption.test.ts`가 재현했고, 라벨 생성과 조회에 같은 폴백 함수를 쓰도록 수정 |

## 구조

```
src/
  app/            router.tsx, AppLayout.tsx, DatasetContext.tsx, providers.tsx
  api/            generated.ts(생성물) / types.ts(별칭) / endpoints.ts
  lib/            apiClient.ts, queries.ts(TanStack Query 훅), queryKeys.ts, format.ts
  components/     EChart, echarts-registry, Toast, Panel, Field, Empty, DataTable
  features/
    datasets/     DataHubPage.tsx, sampleOption.ts(+test)
    prep/         PrepStudio.tsx
    metrics/      MetricStudio.tsx
    dashboards/   DashboardStudio.tsx, WidgetCard.tsx, widgetOption.ts(+test)
    pipelines/    PipelineStudio.tsx
    lol/          LolStudio.tsx
  styles/         tokens.css, base.css, components.css, layout.css
  test/           setup.ts, server.ts, handlers.ts (msw)
```

- **라우팅**: `react-router-dom`의 `createBrowserRouter`. `/`, `/prep`, `/metrics`, `/dashboards`,
  `/pipelines`, `/lol`이 실제 URL을 가지며 새로고침·직접 접근·뒤로가기가 전부 동작한다(기존엔 단일
  `useState`라 전부 안 됐다).
- **데이터 페칭**: TanStack Query. `useDatasets`/`useProfile`/`usePreview`/`useDatasetQuery`/
  `useDatasetChart`/`useMetrics`/`useDashboards`/`useJobs`/`usePipelines` 등이 캐싱·무효화·
  취소를 대신한다. `PrepStudio`의 조인 대상 프로필 조회에 있던 수동 취소 누락이 자연히 해결됐다.
- **타입 안전성**: `apps/frontend/openapi.json` → `pnpm gen:types` → `src/api/generated.ts`.
  CI에서 재생성 후 `git diff --exit-code`로 드리프트를 막는다(`docs/contracts.md`).
- **CSS**: 브레이크포인트 6종(650/720/760/850/1000/1100)을 3종(720/1000/1320)으로 통합.
  `layout.css` 상단에 매핑 근거를 적어 두었다.

## 검증

- `pnpm lint` — 0 error, 2 warning(컨텍스트/훅 파일의 fast-refresh 경고, 의도된 구조)
- `pnpm typecheck`, `pnpm test`(11 테스트: 순수 함수 2개 + apiClient 3개 + 라우터 통합 2개), `pnpm build`
- 브라우저로 전 라우트 직접 접근, 박스플롯 렌더링, 375px 모바일 레이아웃 확인

## 남은 것 (이번 범위 밖)

- `DashboardWidget`에 백엔드 스키마가 없다(`schemas/dashboards.py`의 `widgets: list[dict]`). 프론트
  타입은 그대로 손으로 유지 중 — 백엔드에 `extra="allow"` 모델을 추가하는 결정은 WS-2/스키마 소유
  스트림에 남겨둔다.
- 번들이 340KB(gzip)로 dynamic import 코드분할 대상(빌드 경고). 기능 동작에는 영향 없음.
