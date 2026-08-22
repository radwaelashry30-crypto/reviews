export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "BRL" }).format(value);
}

/**
 * Compact form for display in tight spaces (KPI tiles): "R$15.42M",
 * "R$850K", "R$950". Never breaks a value into fragments across lines --
 * `notation: "compact"` always yields one short token. Pair with
 * `formatCurrency` (the exact value) for a native tooltip/accessible label
 * wherever this is used, since the compact form is lossy.
 */
export function formatCurrencyCompact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 2,
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatPercent(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`;
}
