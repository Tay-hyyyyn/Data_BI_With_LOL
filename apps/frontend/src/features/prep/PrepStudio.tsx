import { useMutation } from "@tanstack/react-query";
import { Check, Play, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useActiveDataset } from "../../app/DatasetContext";
import { datasetsApi } from "../../api/endpoints";
import { Empty } from "../../components/Empty";
import { Field } from "../../components/Field";
import { useToast } from "../../components/Toast";
import { errorMessage } from "../../lib/apiClient";
import { useInvalidateDataset, useProfile } from "../../lib/queries";

type Operation = "drop_duplicates" | "fill_missing" | "join";
type Step = { operation: Operation; config: Record<string, unknown>; label: string };

export function PrepStudio() {
  const { active, datasets } = useActiveDataset();
  const { data: profile } = useProfile(active?.id);
  const invalidateDataset = useInvalidateDataset();
  const { notify } = useToast();

  const [operation, setOperation] = useState<Operation>("drop_duplicates");
  const [column, setColumn] = useState("");
  const [value, setValue] = useState("");
  const [joinDatasetId, setJoinDatasetId] = useState("");
  const { data: joinProfile } = useProfile(joinDatasetId || undefined);
  const [joinColumn, setJoinColumn] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);

  const columns = profile?.columns ?? [];
  const joinable = datasets.filter((item) => item.id !== active?.id && item.current_version_id);

  const run = useMutation({
    mutationFn: () =>
      datasetsApi.transform(active!.id, {
        name: "웹 전처리 레시피",
        steps: steps.map(({ operation: stepOperation, config }) => ({
          operation: stepOperation,
          config,
        })),
      }),
    onSuccess: (result) => {
      invalidateDataset(active!.id);
      setSteps([]);
      notify(`새 버전 v${result.version_number}을 게시했습니다.`);
    },
    onError: (error) => notify(errorMessage(error, "전처리에 실패했습니다."), "error"),
  });

  function add() {
    if (!column) return;
    if (operation === "join") {
      if (!joinDatasetId || !joinColumn) return;
      setSteps((current) => [
        ...current,
        {
          operation,
          config: {
            right_dataset_id: joinDatasetId,
            left_on: [column],
            right_on: [joinColumn],
            how: "left",
          },
          label: `${column} = ${joinColumn} · 왼쪽 조인`,
        },
      ]);
      return;
    }
    const step: Step =
      operation === "drop_duplicates"
        ? { operation, config: { columns: [column] }, label: `${column} 중복 제거` }
        : {
            operation,
            config: { column, method: "value", value },
            label: `${column} 결측값 → ${value || "빈 값"}`,
          };
    setSteps((current) => [...current, step]);
  }

  if (!active || !profile) return <Empty>먼저 데이터셋을 선택하세요</Empty>;

  return (
    <section className="studio prep-layout">
      <article className="panel recipe-builder">
        <div className="panel-head">
          <div>
            <p>전처리 레시피</p>
            <h2>순서대로 실행할 작업</h2>
          </div>
        </div>
        <Field label="작업">
          <select
            value={operation}
            onChange={(event) => setOperation(event.target.value as Operation)}
          >
            <option value="drop_duplicates">중복 제거</option>
            <option value="fill_missing">결측값 채우기</option>
            <option value="join">다른 데이터셋 조인</option>
          </select>
        </Field>
        <Field label={operation === "join" ? "왼쪽 조인 키" : "대상 컬럼"}>
          <select value={column} onChange={(event) => setColumn(event.target.value)}>
            <option value="">선택</option>
            {columns.map((item) => (
              <option key={item.name}>{item.name}</option>
            ))}
          </select>
        </Field>
        {operation === "fill_missing" && (
          <Field label="대체 값">
            <input value={value} onChange={(event) => setValue(event.target.value)} />
          </Field>
        )}
        {operation === "join" && (
          <>
            <Field label="오른쪽 데이터셋">
              <select
                value={joinDatasetId}
                onChange={(event) => {
                  setJoinDatasetId(event.target.value);
                  setJoinColumn("");
                }}
              >
                <option value="">선택</option>
                {joinable.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="오른쪽 조인 키" disabled={!joinProfile}>
              <select
                value={joinColumn}
                disabled={!joinProfile}
                onChange={(event) => setJoinColumn(event.target.value)}
              >
                <option value="">선택</option>
                {joinProfile?.columns.map((item) => (
                  <option key={item.name}>{item.name}</option>
                ))}
              </select>
            </Field>
            <small>기본은 왼쪽 조인입니다. 필요하면 중복 키를 먼저 정리하세요.</small>
          </>
        )}
        <button className="primary" onClick={add}>
          <Plus size={16} /> 작업 추가
        </button>
      </article>
      <article className="panel recipe-steps">
        <div className="panel-head">
          <div>
            <p>실행 순서</p>
            <h2>{steps.length}개 작업</h2>
          </div>
        </div>
        {steps.length === 0 ? (
          <div className="recommend-placeholder">왼쪽에서 작업을 추가하세요.</div>
        ) : (
          steps.map((step, index) => (
            <div className="recipe-step" key={`${step.label}-${index}`}>
              <span>{index + 1}</span>
              <Check size={15} />
              <b>{step.label}</b>
              <button onClick={() => setSteps((current) => current.filter((_, i) => i !== index))}>
                <Trash2 size={15} />
              </button>
            </div>
          ))
        )}
        <button
          className="primary run-recipe"
          disabled={run.isPending || steps.length === 0}
          onClick={() => run.mutate()}
        >
          <Play size={16} /> {run.isPending ? "게시 중" : "새 버전 게시"}
        </button>
      </article>
    </section>
  );
}
