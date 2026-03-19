interface Props {
  runtimeClass?: string;
  taskPackVersion?: string;
  tournamentType?: string;
  className?: string;
}

export default function LaneMetaBadges({
  runtimeClass,
  taskPackVersion,
  tournamentType,
  className = '',
}: Props) {
  return (
    <div className={`flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.16em] text-text-muted ${className}`}>
      <span className="rounded-full border border-border px-2 py-1">
        runtime {runtimeClass ?? 'standard'}
      </span>
      <span className="rounded-full border border-border px-2 py-1">
        pack {taskPackVersion ?? 'v1'}
      </span>
      <span className="rounded-full border border-border px-2 py-1">
        {tournamentType ?? 'standardized'}
      </span>
    </div>
  );
}
