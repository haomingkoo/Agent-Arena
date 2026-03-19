interface Props {
  className?: string;
}

export default function Skeleton({ className = '' }: Props) {
  return <div aria-hidden="true" className={`skeleton-shimmer rounded-md ${className}`.trim()} />;
}
