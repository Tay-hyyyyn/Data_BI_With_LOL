import type { ReactNode } from "react";

/** A labeled form control. `disabled` greys the label to match the select/input it wraps. */
export function Field({
  label,
  disabled,
  children,
}: {
  label: string;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={disabled ? "field field-disabled" : "field"}>
      {label}
      {children}
    </label>
  );
}
