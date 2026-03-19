interface Props {
  state?: string;
}

export default function ReviewStateBadge({ state = 'pending-review' }: Props) {
  const normalized = state.toLowerCase();
  const tone = normalized === 'approved-public'
    ? 'border-green/30 bg-green/10 text-green'
    : normalized === 'rejected' || normalized === 'unsupported'
      ? 'border-red/30 bg-red/10 text-red'
      : normalized === 'relabelled' || normalized === 'qualification-required'
        ? 'border-amber/30 bg-amber/10 text-amber-200'
        : 'border-cyan-accent/30 bg-cyan-glow text-cyan-accent';

  return (
    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${tone}`}>
      {state}
    </span>
  );
}
