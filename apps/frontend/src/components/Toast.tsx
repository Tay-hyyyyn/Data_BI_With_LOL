import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

export type ToastTone = "info" | "error";
type ToastItem = { id: number; message: string; tone: ToastTone };
type ToastContextValue = { notify: (message: string, tone?: ToastTone) => void };

const ToastContext = createContext<ToastContextValue | null>(null);
const AUTO_DISMISS_MS = 5_000;

/**
 * One notification channel for the whole app. Replaces the six independent `message`/`error`
 * `useState`s that used to live in `App.tsx` and each studio, and the 12 copy-pasted
 * try/catch/setMessage blocks that wrote to them.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback(
    (id: number) => setItems((current) => current.filter((item) => item.id !== id)),
    [],
  );

  const notify = useCallback(
    (message: string, tone: ToastTone = "info") => {
      const id = ++counter.current;
      setItems((current) => [...current, { id, message, tone }]);
      window.setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {items.map((item) => (
          <div
            key={item.id}
            className={item.tone === "error" ? "toast toast-error" : "toast toast-info"}
            role={item.tone === "error" ? "alert" : "status"}
          >
            <span>{item.message}</span>
            <button aria-label="닫기" onClick={() => dismiss(item.id)}>
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast는 ToastProvider 내부에서만 사용할 수 있습니다.");
  return context;
}
