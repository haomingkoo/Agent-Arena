export function formatTraceKind(traceKind?: string) {
  if (!traceKind) return 'Benchmark';
  if (traceKind === 'holdout') return 'Holdout';
  if (traceKind === 'hosted') return 'Hosted';
  return traceKind
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function traceKindTone(traceKind?: string) {
  if (traceKind === 'holdout') {
    return 'border-amber-400/30 bg-amber-400/10 text-amber-200';
  }
  if (traceKind === 'hosted') {
    return 'border-violet-400/30 bg-violet-400/10 text-violet-200';
  }
  return 'border-cyan-accent/30 bg-cyan-glow text-cyan-accent';
}

export function traceKindSummary(traceKind?: string) {
  if (traceKind === 'holdout') {
    return 'Internal validation only. Holdout traces do not contribute to public rank or rating updates.';
  }
  if (traceKind === 'hosted') {
    return 'User-triggered sandbox execution. Hosted traces are separate from tournament ranking evidence.';
  }
  return 'Public tournament evidence. Benchmark traces come from the shared task pack used for same-role comparison.';
}
