import { Plus, Sigma } from "lucide-react";
import { useEffect, useState } from "react";
import { useActiveDataset } from "../../app/DatasetContext";
import { Empty } from "../../components/Empty";
import { Field } from "../../components/Field";
import { useToast } from "../../components/Toast";
import { errorMessage } from "../../lib/apiClient";
import { formatDecimal } from "../../lib/format";
import { useMetrics, useProfile, useSaveMetric } from "../../lib/queries";

type Aggregation = "sum" | "mean" | "count" | "min" | "max" | "ratio";

export function MetricStudio() {
  const { active } = useActiveDataset();
  const { data: profile } = useProfile(active?.id);
  const { data: metrics = [] } = useMetrics(active?.id);
  const save = useSaveMetric();
  const { notify } = useToast();

  const [name, setName] = useState("");
  const [aggregation, setAggregation] = useState<Aggregation>("sum");
  const [column, setColumn] = useState("");
  const [numerator, setNumerator] = useState("");
  const [denominator, setDenominator] = useState("");
  const [unit, setUnit] = useState("");
  const [description, setDescription] = useState("");
  const numeric = profile?.columns.filter((item) => item.semantic_type === "numeric") ?? [];

  useEffect(() => {
    setColumn(numeric[0]?.name ?? "");
    setNumerator(numeric[0]?.name ?? "");
    setDenominator(numeric[1]?.name ?? numeric[0]?.name ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset defaults only when the dataset version actually changes
  }, [profile?.version_id]);

  const needsColumn = aggregation !== "count" && aggregation !== "ratio";
  const needsRatio = aggregation === "ratio";
  const canSave =
    Boolean(name) &&
    (!needsColumn || Boolean(column)) &&
    (!needsRatio || (Boolean(numerator) && Boolean(denominator)));

  async function handleSave() {
    if (!active || !canSave) return;
    try {
      const metric = await save.mutateAsync({
        name,
        dataset_id: active.id,
        aggregation,
        column: needsColumn ? column : null,
        numerator: needsRatio ? numerator : null,
        denominator: needsRatio ? denominator : null,
        unit: unit || null,
        description: description || null,
      });
      notify(`${metric.name} 지표를 저장했습니다.`);
      setName("");
    } catch (error) {
      notify(errorMessage(error, "지표를 저장하지 못했습니다."), "error");
    }
  }

  if (!active || !profile) return <Empty>먼저 데이터셋을 선택하세요</Empty>;

  return (
    <section className="studio">
      <div className="workspace-grid">
        <article className="panel">
          <div className="panel-head">
            <div>
              <p>지표 정의</p>
              <h2>재사용 가능한 KPI 만들기</h2>
            </div>
            <Sigma size={19} />
          </div>
          <Field label="지표 이름">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="예: ROAS"
            />
          </Field>
          <Field label="집계">
            <select
              value={aggregation}
              onChange={(event) => setAggregation(event.target.value as Aggregation)}
            >
              <option value="sum">합계</option>
              <option value="mean">평균</option>
              <option value="count">행 수</option>
              <option value="min">최솟값</option>
              <option value="max">최댓값</option>
              <option value="ratio">비율</option>
            </select>
          </Field>
          {needsRatio ? (
            <div className="riot-id-row">
              <Field label="분자">
                <select value={numerator} onChange={(event) => setNumerator(event.target.value)}>
                  {numeric.map((item) => (
                    <option key={item.name}>{item.name}</option>
                  ))}
                </select>
              </Field>
              <Field label="분모">
                <select
                  value={denominator}
                  onChange={(event) => setDenominator(event.target.value)}
                >
                  {numeric.map((item) => (
                    <option key={item.name}>{item.name}</option>
                  ))}
                </select>
              </Field>
            </div>
          ) : (
            needsColumn && (
              <Field label="컬럼">
                <select value={column} onChange={(event) => setColumn(event.target.value)}>
                  {numeric.map((item) => (
                    <option key={item.name}>{item.name}</option>
                  ))}
                </select>
              </Field>
            )
          )}
          <div className="riot-id-row">
            <Field label="단위">
              <input
                value={unit}
                onChange={(event) => setUnit(event.target.value)}
                placeholder="KRW, %, x"
              />
            </Field>
            <Field label="설명">
              <input
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="선택 사항"
              />
            </Field>
          </div>
          <button
            className="primary"
            disabled={!canSave || save.isPending}
            onClick={() => void handleSave()}
          >
            <Plus size={16} /> 지표 저장
          </button>
        </article>
        <article className="panel">
          <div className="panel-head">
            <div>
              <p>현재 게시 버전</p>
              <h2>저장된 지표</h2>
            </div>
          </div>
          {metrics.length === 0 ? (
            <div className="recommend-placeholder">
              지표를 추가하면 현재 데이터 버전에서 다시 계산됩니다.
            </div>
          ) : (
            <div className="kpis">
              {metrics.map((metric) => (
                <article key={metric.id}>
                  <span>{metric.name}</span>
                  <strong>{formatDecimal(metric.value)}</strong>
                  <small>
                    {metric.unit || "단위 없음"}
                    {metric.description ? ` · ${metric.description}` : ""}
                  </small>
                </article>
              ))}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
