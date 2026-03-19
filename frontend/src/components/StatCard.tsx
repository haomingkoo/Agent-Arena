interface Props {
  label: string;
  value: string | number;
  sub?: string;
}

export default function StatCard({ label, value, sub }: Props) {
  return (
    <div className="rounded-lg border border-border bg-bg-card p-4">
      <div className="text-sm text-text-muted">{label}</div>
      <div className="mt-1 text-2xl font-bold font-mono text-text-primary">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-text-muted">{sub}</div>}
    </div>
  );
}
