interface Props {
  mu: number;
  rd?: number;
}

export default function RatingChip({ mu, rd }: Props) {
  const color = mu >= 1500 ? 'text-cyan-accent' : 'text-text-muted';

  return (
    <span className={`inline-flex items-center gap-1 font-mono text-sm font-medium ${color}`}>
      {Math.round(mu)}
      {rd != null && (
        <span className="text-xs text-text-muted font-normal">
          {'\u00B1'}{Math.round(rd)}
        </span>
      )}
    </span>
  );
}
