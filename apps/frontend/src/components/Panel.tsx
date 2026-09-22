import type { ReactNode } from "react";

export function Panel({
  eyebrow,
  title,
  icon,
  className,
  children,
}: {
  eyebrow?: string;
  title?: string;
  icon?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <article className={className ? `panel ${className}` : "panel"}>
      {(eyebrow || title) && (
        <div className="panel-head">
          <div>
            {eyebrow && <p>{eyebrow}</p>}
            {title && <h2>{title}</h2>}
          </div>
          {icon}
        </div>
      )}
      {children}
    </article>
  );
}
