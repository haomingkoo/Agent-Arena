import type { SourceDiversityStats } from '../lib/sourceSignals';

export default function SourceDiversityCard({
  stats,
  compact = false,
}: {
  stats: SourceDiversityStats;
  compact?: boolean;
}) {
  return (
    <section className="rounded-2xl border border-border bg-bg-card p-6">
      <h2 className="text-xl font-semibold text-text-primary">
        {compact ? 'Source Diversity' : 'Lane Source Diversity'}
      </h2>
      <p className="mt-2 text-sm text-text-muted">
        Public lanes should not quietly become one-builder or one-source leaderboards.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${stats.tone}`}>
          {stats.headline}
        </span>
      </div>

      <div className={`mt-4 grid gap-3 ${compact ? 'sm:grid-cols-3' : 'sm:grid-cols-4'}`}>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Owners</div>
          <div className="mt-2 font-mono text-lg text-text-primary">{stats.uniqueOwners}</div>
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Source Families</div>
          <div className="mt-2 font-mono text-lg text-text-primary">{stats.uniqueBuckets}</div>
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Hosts</div>
          <div className="mt-2 font-mono text-lg text-text-primary">{stats.uniqueHosts}</div>
        </div>
        {!compact ? (
          <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
            <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Top Owner Share</div>
            <div className="mt-2 font-mono text-lg text-text-primary">
              {stats.totalAgents > 0 ? `${Math.round((stats.topOwnerCount / stats.totalAgents) * 100)}%` : '—'}
            </div>
          </div>
        ) : null}
      </div>

      {stats.buckets.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {stats.buckets.map((bucket) => (
            <span
              key={bucket.bucket}
              className="rounded-full border border-border px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-text-muted"
            >
              {bucket.label} · {bucket.count}
            </span>
          ))}
        </div>
      ) : null}

      <div className={`mt-4 rounded-xl border p-4 ${stats.tone}`}>
        <div className="space-y-2 text-sm leading-relaxed">
          {stats.notes.map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      </div>
    </section>
  );
}
