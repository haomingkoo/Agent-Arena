interface Props {
  tier: string;
  size?: 'sm' | 'md';
}

const TIER_STYLES: Record<string, string> = {
  gold: 'bg-gold/20 text-gold border-gold/40',
  silver: 'bg-silver/20 text-silver border-silver/40',
  bronze: 'bg-bronze/20 text-bronze border-bronze/40',
  uncertified: 'bg-bg-hover text-text-muted border-border',
};

export default function CertBadge({ tier, size = 'sm' }: Props) {
  const style = TIER_STYLES[tier] || TIER_STYLES.uncertified;
  const padding = size === 'md' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs';

  return (
    <span className={`inline-flex items-center rounded-full border font-mono font-medium uppercase ${style} ${padding}`}>
      {tier}
    </span>
  );
}
