import { useMutation } from "@tanstack/react-query";
import { ArrowUpRight, BarChart3, LoaderCircle, Link2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useActiveDataset } from "../../app/DatasetContext";
import { datasetsApi } from "../../api/endpoints";
import type { Relationship, RelationshipResponse } from "../../api/types";
import { DataTable } from "../../components/DataTable";
import { EChart } from "../../components/EChart";
import { Empty } from "../../components/Empty";
import { errorMessage } from "../../lib/apiClient";
import { formatInteger } from "../../lib/format";
import { useProfile, usePreview } from "../../lib/queries";
import { sampleOption } from "./sampleOption";

export function DataHubPage() {
  const { active } = useActiveDataset();
  const { data: profile } = useProfile(active?.id);
  const { data: preview } = usePreview(active?.id, 100);

  const [selectedColumn, setSelectedColumn] = useState("");
  const [relations, setRelations] = useState<RelationshipResponse | null>(null);
  const [selectedRelation, setSelectedRelation] = useState<Relationship | null>(null);
  const [entityKey, setEntityKey] = useState("");
  const [timeColumn, setTimeColumn] = useState("");
  const [analysisGrain, setAnalysisGrain] = useState<"" | "mean" | "latest">("");

  useEffect(() => {
    setSelectedColumn(
      profile?.columns.find(
        (column) => column.semantic_type === "numeric" || column.semantic_type === "categorical",
      )?.name ?? "",
    );
    setRelations(null);
    setSelectedRelation(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset the column pick only when the dataset version changes
  }, [profile?.version_id]);

  const analyze = useMutation({
    mutationFn: () =>
      datasetsApi.relationships(active!.id, {
        column: selectedColumn,
        entity_key: entityKey || null,
        time_column: timeColumn || null,
        analysis_grain: analysisGrain || null,
      }),
    onSuccess: (result) => {
      setRelations(result);
      setSelectedRelation(result.items[0] ?? null);
    },
  });

  const chartOption = useMemo(
    () => sampleOption(preview ?? null, selectedRelation, selectedColumn),
    [preview, selectedRelation, selectedColumn],
  );

  if (!active) {
    return (
      <Empty>
        <BarChart3 size={30} />첫 데이터셋을 올려보세요
      </Empty>
    );
  }

  const numericCount =
    profile?.columns.filter((column) => column.semantic_type === "numeric").length ?? 0;
  const completeness = profile
    ? `${(100 - (profile.columns.reduce((sum, column) => sum + column.null_ratio, 0) / Math.max(profile.column_count, 1)) * 100).toFixed(1)}%`
    : "—";

  return (
    <>
      <section className="kpis">
        <article>
          <span>레코드</span>
          <strong>{formatInteger(profile?.row_count ?? active.row_count ?? 0)}</strong>
          <small>
            <ArrowUpRight size={13} /> 게시 버전 기준
          </small>
        </article>
        <article>
          <span>컬럼</span>
          <strong>{profile?.column_count ?? active.column_count ?? 0}</strong>
          <small>{numericCount}개 수치형</small>
        </article>
        <article>
          <span>데이터 완성도</span>
          <strong>{completeness}</strong>
          <small>전체 컬럼 평균</small>
        </article>
        <article>
          <span>현재 버전</span>
          <strong className="version">v{active.version_number ?? 1}</strong>
          <small>원자적 게시 완료</small>
        </article>
      </section>

      <section className="workspace-grid">
        <article className="panel relation-panel">
          <div className="panel-head">
            <div>
              <p>AI 관계 추천</p>
              <h2>기준 컬럼과 함께 볼 지표</h2>
            </div>
            <Sparkles size={19} />
          </div>
          <div className="control-row">
            <label>
              기준 컬럼
              <select
                value={selectedColumn}
                onChange={(event) => {
                  setSelectedColumn(event.target.value);
                  setRelations(null);
                  setSelectedRelation(null);
                }}
              >
                {profile?.columns
                  .filter((column) => !["identifier", "text"].includes(column.semantic_type))
                  .map((column) => (
                    <option key={column.name}>{column.name}</option>
                  ))}
              </select>
            </label>
            <button
              className="primary"
              disabled={analyze.isPending || !selectedColumn}
              onClick={() => analyze.mutate()}
            >
              {analyze.isPending ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Sparkles size={16} />
              )}{" "}
              관계 찾기
            </button>
          </div>
          <div className="control-row relation-grain">
            <label>
              반복 개체 키
              <select
                value={entityKey}
                onChange={(event) => {
                  setEntityKey(event.target.value);
                  if (!event.target.value) {
                    setTimeColumn("");
                    setAnalysisGrain("");
                  }
                }}
              >
                <option value="">행 단위(기본)</option>
                {profile?.columns
                  .filter(
                    (column) => column.semantic_type === "identifier" || column.unique_count > 1,
                  )
                  .map((column) => (
                    <option key={column.name}>{column.name}</option>
                  ))}
              </select>
            </label>
            <label>
              시간 컬럼
              <select
                value={timeColumn}
                disabled={!entityKey}
                onChange={(event) => setTimeColumn(event.target.value)}
              >
                <option value="">선택</option>
                {profile?.columns
                  .filter(
                    (column) =>
                      column.semantic_type === "datetime" ||
                      column.name.toLowerCase().includes("minute") ||
                      column.name.toLowerCase().includes("time"),
                  )
                  .map((column) => (
                    <option key={column.name}>{column.name}</option>
                  ))}
              </select>
            </label>
            <label>
              분석 단위
              <select
                value={analysisGrain}
                disabled={!entityKey}
                onChange={(event) => setAnalysisGrain(event.target.value as "" | "mean" | "latest")}
              >
                <option value="">선택</option>
                <option value="latest">마지막 시점</option>
                <option value="mean">개체별 평균</option>
              </select>
            </label>
          </div>
          {entityKey && (
            <p className="insight">
              반복 측정 데이터는 개체별 분석 단위를 선택해야 합니다. 마지막 시점은 시간 컬럼도
              필요합니다.
            </p>
          )}
          {analyze.isError && (
            <p className="insight">{errorMessage(analyze.error, "관계 분석에 실패했습니다.")}</p>
          )}
          {!relations ? (
            <div className="recommend-placeholder">
              <Link2 size={24} />
              <p>컬럼을 선택하면 통계적 관계가 높은 다른 컬럼을 선제적으로 제안합니다.</p>
              <small>Spearman · Cramér’s V · η² 기반</small>
            </div>
          ) : (
            <div className="recommend-list">
              {relations.items.map((item, index) => (
                <button
                  key={item.column}
                  className={selectedRelation?.column === item.column ? "active" : ""}
                  onClick={() => setSelectedRelation(item)}
                >
                  <span className="rank">{index + 1}</span>
                  <span className="recommend-title">
                    <b>{item.column}</b>
                    <small>
                      {item.method} · n={formatInteger(item.sample_size)}
                    </small>
                  </span>
                  <strong>{Math.abs(item.score).toFixed(3)}</strong>
                </button>
              ))}
            </div>
          )}
        </article>

        <article className="panel chart-panel">
          <div className="panel-head">
            <div>
              <p>관계 미리보기</p>
              <h2>
                {selectedRelation
                  ? `${selectedColumn} × ${selectedRelation.column}`
                  : "추천 결과를 선택하세요"}
              </h2>
            </div>
            {selectedRelation && <span className="method">{selectedRelation.method}</span>}
          </div>
          {selectedRelation ? (
            <>
              <EChart option={chartOption} />
              <p className="insight">{selectedRelation.reason}</p>
            </>
          ) : (
            <div className="chart-empty">
              <BarChart3 size={30} />
              <span>추천 관계의 차트가 이곳에 표시됩니다.</span>
            </div>
          )}
        </article>
      </section>

      <section className="panel table-panel">
        <div className="panel-head">
          <div>
            <p>데이터 미리보기</p>
            <h2>게시된 원본 데이터</h2>
          </div>
          <span className="method">최대 100행</span>
        </div>
        {preview && <DataTable columns={preview.columns} rows={preview.rows} maxRows={12} />}
      </section>
    </>
  );
}
