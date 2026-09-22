import type { ReactNode } from "react";

export function Empty({ children }: { children: ReactNode }) {
  return (
    <section className="empty">
      <h2>{children}</h2>
    </section>
  );
}
