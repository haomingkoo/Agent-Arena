interface Props {
  dimensions: Record<string, number>;
}

const LABELS: Record<string, string> = {
  frequency_value: 'Practical Value',
  capability_upgrade: 'Capability Upgrade',
  specificity: 'Specificity',
  token_efficiency: 'Token Efficiency',
  source_credibility: 'Source Credibility',
  trigger_clarity: 'Trigger Clarity',
  methodology_depth: 'Methodology',
  llm_quality: 'LLM Quality',
  correctness: 'Correctness',
  safety: 'Safety',
  completeness: 'Completeness',
  quality: 'Quality',
};

export default function DimensionBars({ dimensions }: Props) {
  return (
    <div className="space-y-3">
      {Object.entries(dimensions).map(([key, value]) => (
        <div key={key} className="grid gap-2 sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)_3rem] sm:items-center sm:gap-3">
          <div className="flex items-end justify-between gap-3 sm:block sm:text-right">
            <span className="text-sm text-text-secondary">
              {LABELS[key] || key}
            </span>
            <span className="font-mono text-sm text-text-secondary sm:hidden">
              {value.toFixed(2)}
            </span>
          </div>
          <div className="h-5 overflow-hidden rounded-full bg-bg-secondary">
            <div
              className="h-full rounded-full bg-cyan-accent/70 transition-all duration-500"
              style={{ width: `${Math.min(value * 100, 100)}%` }}
            />
          </div>
          <span className="hidden w-12 text-right font-mono text-sm text-text-secondary sm:block">
            {value.toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
}
