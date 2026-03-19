interface Props {
  value: number | null | undefined;
  size?: 'sm' | 'md';
}

export default function UpgradeChip({ value, size = 'sm' }: Props) {
  if (value == null) return <span className="text-text-muted">—</span>;

  const positive = value >= 0;
  const color = positive ? 'text-green' : 'text-red';
  const bg = positive ? 'bg-green/10' : 'bg-red/10';
  const sign = positive ? '+' : '';
  const padding = size === 'md' ? 'px-3 py-1 text-base' : 'px-2 py-0.5 text-sm';

  return (
    <span className={`inline-flex items-center rounded-md font-mono font-medium ${color} ${bg} ${padding}`}>
      {sign}{value.toFixed(3)}
    </span>
  );
}
