interface Props {
  status?: string;
}

export default function TournamentStatusChip({ status = 'pending' }: Props) {
  const normalized = status.toLowerCase();
  const tone = normalized === 'completed'
    ? 'border-green/30 bg-green/10 text-green'
    : normalized === 'running'
      ? 'border-cyan-accent/30 bg-cyan-glow text-cyan-accent'
      : 'border-border bg-bg-card text-text-muted';

  return (
    <span
      className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${tone}`}
    >
      {status}
    </span>
  );
}
