import type { AgentLeaderboardEntry } from './api';

export interface SourceBucketCount {
  bucket: string;
  label: string;
  count: number;
}

export interface SourceDiversityStats {
  totalAgents: number;
  uniqueOwners: number;
  uniqueBuckets: number;
  uniqueHosts: number;
  owners: string[];
  hosts: string[];
  topOwner: string;
  topOwnerCount: number;
  headline: string;
  tone: string;
  notes: string[];
  buckets: SourceBucketCount[];
}

function baseTone(status: 'good' | 'warning' | 'risk'): string {
  if (status === 'good') {
    return 'border-green/30 bg-green/10 text-green';
  }
  if (status === 'warning') {
    return 'border-amber/30 bg-amber/10 text-amber-200';
  }
  return 'border-red/30 bg-red/10 text-red';
}

function bucketLabel(bucket: string) {
  return bucket
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function classifySourceUrl(sourceUrl?: string): { bucket: string; host: string } {
  if (!sourceUrl) {
    return { bucket: 'unknown', host: 'unknown' };
  }

  if (sourceUrl.startsWith('local://')) {
    return { bucket: 'local-curated', host: 'local' };
  }

  try {
    const parsed = new URL(sourceUrl);
    const host = parsed.host.toLowerCase();

    if (host.includes('github.com')) {
      return { bucket: 'github', host };
    }
    if (host.includes('gitlab.com')) {
      return { bucket: 'gitlab', host };
    }
    if (host.includes('smithery.ai')) {
      return { bucket: 'registry', host };
    }
    if (host.includes('huggingface.co')) {
      return { bucket: 'hugging-face', host };
    }
    return { bucket: 'other-remote', host };
  } catch {
    return { bucket: 'unknown', host: 'unknown' };
  }
}

export function summarizeSourceDiversity(
  entries: AgentLeaderboardEntry[],
): SourceDiversityStats {
  if (entries.length === 0) {
    return {
      totalAgents: 0,
      uniqueOwners: 0,
      uniqueBuckets: 0,
      uniqueHosts: 0,
      owners: [],
      hosts: [],
      topOwner: '',
      topOwnerCount: 0,
      headline: 'No source evidence',
      tone: baseTone('risk'),
      notes: [
        'No ranked agents are available yet, so source diversity cannot be judged.',
      ],
      buckets: [],
    };
  }

  const ownerCounts = new Map<string, number>();
  const bucketCounts = new Map<string, number>();
  const hosts = new Set<string>();

  for (const entry of entries) {
    const owner = (entry.owner || 'unknown-owner').trim().toLowerCase();
    ownerCounts.set(owner, (ownerCounts.get(owner) ?? 0) + 1);

    const source = classifySourceUrl(entry.source_url);
    bucketCounts.set(source.bucket, (bucketCounts.get(source.bucket) ?? 0) + 1);
    hosts.add(source.host);
  }

  const sortedOwners = [...ownerCounts.entries()].sort((a, b) => b[1] - a[1]);
  const [topOwner = '', topOwnerCount = 0] = sortedOwners[0] ?? [];
  const ownerShare = topOwnerCount / entries.length;

  const buckets = [...bucketCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([bucket, count]) => ({
      bucket,
      label: bucketLabel(bucket),
      count,
    }));

  const notes: string[] = [];
  let severity: 'good' | 'warning' | 'risk' = 'good';

  if (ownerCounts.size === 1) {
    notes.push('All current contenders come from one owner or curator, so the lane is vulnerable to single-builder bias.');
    severity = 'risk';
  } else {
    notes.push(`${ownerCounts.size} distinct owners are represented in the current ranked pool.`);
  }

  if (bucketCounts.size === 1) {
    notes.push(`All current contenders come from ${buckets[0]?.label ?? 'one source family'} right now.`);
    severity = severity === 'risk' ? 'risk' : 'warning';
  } else {
    notes.push(`This lane currently mixes ${buckets.map((bucket) => bucket.label).slice(0, 3).join(', ')} sources.`);
  }

  if (ownerShare >= 0.7 && entries.length >= 3) {
    notes.push(`The top owner supplies ${topOwnerCount}/${entries.length} ranked agents, which is still quite concentrated.`);
    severity = 'risk';
  } else if (ownerShare >= 0.5 && entries.length >= 3) {
    notes.push(`The top owner supplies ${topOwnerCount}/${entries.length} ranked agents, so source concentration is still noticeable.`);
    severity = severity === 'risk' ? 'risk' : 'warning';
  }

  const headline = severity === 'good'
    ? 'Healthy source diversity'
    : severity === 'warning'
      ? 'Moderate source diversity'
      : 'Concentrated source base';

  return {
    totalAgents: entries.length,
    uniqueOwners: ownerCounts.size,
    uniqueBuckets: bucketCounts.size,
    uniqueHosts: hosts.size,
    owners: [...ownerCounts.keys()],
    hosts: [...hosts],
    topOwner,
    topOwnerCount,
    headline,
    tone: baseTone(severity),
    notes,
    buckets,
  };
}
