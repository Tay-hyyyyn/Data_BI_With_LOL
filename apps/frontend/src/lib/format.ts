/** Shared `Intl` formatters. Creating one per render is wasteful and was inconsistent across studios. */

export const integerFormat = new Intl.NumberFormat("ko-KR");
export const decimalFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 });

export function formatInteger(value: number | null | undefined): string {
  return integerFormat.format(value ?? 0);
}

export function formatDecimal(value: number | null | undefined): string {
  return decimalFormat.format(value ?? 0);
}
