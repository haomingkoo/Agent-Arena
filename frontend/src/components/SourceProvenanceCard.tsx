interface SourceProvenance {
  source_type?: string;
  source_url?: string;
  source_commit?: string;
  discovered_at?: string;
}

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function displayUrl(value?: string) {
  if (!value) return '—';
  if (value.startsWith('local://')) {
    return value.slice('local://'.length);
  }
  return value;
}

function prettyDate(value?: string) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export default function SourceProvenanceCard({
  title = 'Source Provenance',
  provenance,
  packagingType,
  owner,
  contentHash,
  profileSourceUrl,
}: {
  title?: string;
  provenance: SourceProvenance;
  packagingType?: string;
  owner?: string;
  contentHash?: string;
  profileSourceUrl?: string;
}) {
  const effectiveSourceUrl = provenance.source_url || profileSourceUrl || '';
  const isLocal = effectiveSourceUrl.startsWith('local://');

  return (
    <section className="rounded-2xl border border-border bg-bg-card p-6">
      <h2 className="text-xl font-semibold text-text-primary">{title}</h2>
      <p className="mt-2 text-sm text-text-muted">
        This is the discovery trail for the current agent version. We should be able to tell where it came from before
        trusting it in a public lane.
      </p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Discovery Source</div>
          <div className="mt-2 font-medium text-text-primary">
            {provenance.source_type ? formatSlug(provenance.source_type) : '—'}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Packaging</div>
          <div className="mt-2 font-medium text-text-primary">{packagingType || '—'}</div>
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Owner</div>
          <div className="mt-2 font-medium text-text-primary">{owner || 'Unknown'}</div>
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Discovered</div>
          <div className="mt-2 font-medium text-text-primary">{prettyDate(provenance.discovered_at)}</div>
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4 sm:col-span-2">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Source Location</div>
          <div className="mt-2 break-all font-mono text-xs text-text-primary">
            {displayUrl(effectiveSourceUrl)}
          </div>
          {!isLocal && effectiveSourceUrl ? (
            <a
              href={effectiveSourceUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex text-sm text-cyan-accent no-underline hover:underline"
            >
              Open source
            </a>
          ) : null}
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Source Commit</div>
          <div className="mt-2 break-all font-mono text-xs text-text-primary">{provenance.source_commit || '—'}</div>
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Content Hash</div>
          <div className="mt-2 break-all font-mono text-xs text-text-primary">{contentHash || '—'}</div>
        </div>
      </div>
    </section>
  );
}
