interface Props {
  category: string;
  size?: 'sm' | 'md';
}

const COLOR_MAP: Record<string, { text: string; bg: string }> = {
  'code-review': { text: 'text-cyan-accent', bg: 'bg-cyan-accent/10' },
  testing: { text: 'text-green', bg: 'bg-green/10' },
  frontend: { text: 'text-purple-400', bg: 'bg-purple-400/10' },
  backend: { text: 'text-blue-400', bg: 'bg-blue-400/10' },
  security: { text: 'text-red', bg: 'bg-red/10' },
  devops: { text: 'text-orange-400', bg: 'bg-orange-400/10' },
  database: { text: 'text-yellow-400', bg: 'bg-yellow-400/10' },
  documentation: { text: 'text-text-muted', bg: 'bg-text-muted/10' },
};

const DEFAULT_COLOR = { text: 'text-text-muted', bg: 'bg-text-muted/10' };

export default function CategoryBadge({ category, size = 'sm' }: Props) {
  const { text, bg } = COLOR_MAP[category] ?? DEFAULT_COLOR;
  const padding = size === 'md' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs';

  return (
    <span className={`inline-flex items-center rounded-md font-medium ${text} ${bg} ${padding}`}>
      {category}
    </span>
  );
}
