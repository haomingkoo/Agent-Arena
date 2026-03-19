import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Skeleton from '../components/Skeleton';
import SourceDiversityCard from '../components/SourceDiversityCard';
import StatCard from '../components/StatCard';
import {
  getCandidateLeads,
  getFieldRoleLeaderboard,
  getFields,
  getLeadStats,
  type CandidateLead,
  type LeadStats,
} from '../lib/api';
import {
  type SourceDiversityStats,
  summarizeSourceDiversity,
} from '../lib/sourceSignals';

function formatSlug(value: string) {
  return value
    .split(/[-_]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function parseJsonArray(value: string): string[] {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
  } catch {
    return [];
  }
}

function stateTone(state: string) {
  if (state === 'resolved') return 'border-green/30 bg-green/10 text-green';
  if (state === 'unresolved') return 'border-amber/30 bg-amber/10 text-amber-200';
  if (state === 'dead-link') return 'border-red/30 bg-red/10 text-red';
  if (state === 'no-artifact') return 'border-border bg-bg-secondary/80 text-text-muted';
  return 'border-border bg-bg-secondary/80 text-text-muted';
}

interface LaneSourceRecord {
  field: string;
  role: string;
  agentCount: number;
  sourceDiversity: SourceDiversityStats;
}

function SourceQueueSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-36" />
      <Skeleton className="mt-4 h-10 w-80" />
      <Skeleton className="mt-3 h-5 w-[32rem] max-w-full" />
      <div className="mt-6 grid gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-2xl border border-border bg-bg-card p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-8 w-20" />
          </div>
        ))}
      </div>
      <div className="mt-8 grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, index) => (
          <div key={index} className="rounded-2xl border border-border bg-bg-card p-6">
            <Skeleton className="h-6 w-44" />
            <Skeleton className="mt-4 h-32 w-full" />
          </div>
        ))}
      </div>
      <div className="mt-8 rounded-2xl border border-border bg-bg-card p-6">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="mt-4 h-10 w-full" />
        <Skeleton className="mt-4 h-40 w-full" />
      </div>
    </div>
  );
}

export default function SourceQueue() {
  const [lanes, setLanes] = useState<LaneSourceRecord[]>([]);
  const [leads, setLeads] = useState<CandidateLead[]>([]);
  const [leadStats, setLeadStats] = useState<LeadStats | null>(null);
  const [laneLoading, setLaneLoading] = useState(true);
  const [leadLoading, setLeadLoading] = useState(true);
  const [error, setError] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [resolutionFilter, setResolutionFilter] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadLanes() {
      try {
        const fieldData = await getFields();
        if (cancelled) return;

        const lanePairs = (fieldData.fields ?? []).flatMap((field) =>
          field.roles.map((role) => ({
            field: field.field,
            role: role.role,
            agentCount: role.agent_count,
          })),
        );

        const records = await Promise.all(
          lanePairs.map(async (lane) => {
            const leaderboard = await getFieldRoleLeaderboard(lane.field, lane.role);
            return {
              ...lane,
              sourceDiversity: summarizeSourceDiversity(leaderboard.leaderboard ?? []),
            };
          }),
        );

        if (!cancelled) {
          setLanes(records);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load source queue');
        }
      } finally {
        if (!cancelled) {
          setLaneLoading(false);
        }
      }
    }

    void loadLanes();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadLeads() {
      try {
        const [leadResponse, statsResponse] = await Promise.all([
          getCandidateLeads({
            sourceType: sourceFilter || undefined,
            resolutionState: resolutionFilter || undefined,
            limit: 100,
          }),
          getLeadStats(),
        ]);

        if (!cancelled) {
          setLeads(leadResponse.leads ?? []);
          setLeadStats(statsResponse);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load candidate leads');
        }
      } finally {
        if (!cancelled) {
          setLeadLoading(false);
        }
      }
    }

    setLeadLoading(true);
    void loadLeads();
    return () => {
      cancelled = true;
    };
  }, [sourceFilter, resolutionFilter]);

  const loading = laneLoading || leadLoading;

  const laneSummary = useMemo(() => {
    const allSources = new Map<string, number>();
    const allOwners = new Set<string>();
    const allHosts = new Set<string>();
    let totalRankedAgents = 0;

    for (const lane of lanes) {
      totalRankedAgents += lane.agentCount;
      for (const bucket of lane.sourceDiversity.buckets) {
        allSources.set(bucket.label, (allSources.get(bucket.label) ?? 0) + bucket.count);
      }
      for (const owner of lane.sourceDiversity.owners) {
        allOwners.add(owner);
      }
      for (const host of lane.sourceDiversity.hosts) {
        if (host && host !== 'unknown') {
          allHosts.add(host);
        }
      }
    }

    const concentrated = lanes.filter((lane) => lane.sourceDiversity.headline === 'Concentrated source base').length;
    const healthy = lanes.filter((lane) => lane.sourceDiversity.headline === 'Healthy source diversity').length;

    return {
      lanes: lanes.length,
      totalRankedAgents,
      concentrated,
      healthy,
      uniqueOwners: allOwners.size,
      uniqueHosts: allHosts.size,
      sourceMix: [...allSources.entries()].sort((a, b) => b[1] - a[1]),
    };
  }, [lanes]);

  const sortedLanes = useMemo(() => {
    return [...lanes].sort((a, b) => {
      const riskRank = (value: string) =>
        value === 'Concentrated source base' ? 0 : value === 'Moderate source diversity' ? 1 : 2;
      const aRank = riskRank(a.sourceDiversity.headline);
      const bRank = riskRank(b.sourceDiversity.headline);
      if (aRank !== bRank) return aRank - bRank;
      return b.agentCount - a.agentCount;
    });
  }, [lanes]);

  const sourceOptions = useMemo(() => {
    return [...new Set(leads.map((lead) => lead.source_type))].sort();
  }, [leads]);

  if (loading) {
    return <SourceQueueSkeleton />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load source queue: {error}</p>
        </div>
      </div>
    );
  }

  const stats = leadStats ?? {
    total: 0,
    unresolved: 0,
    resolved: 0,
    no_artifact: 0,
    dead_link: 0,
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link
        to="/ops"
        className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
      >
        &larr; Control Room
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Source Queue
        </h1>
        <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
          discovery
        </span>
      </div>
      <p className="mt-2 max-w-3xl text-text-secondary">
        This is the real discovery intake now. Lead-gen sources can widen the funnel, but they still need to resolve
        into actual agent artifacts before they belong anywhere near a tournament.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-4">
        <StatCard label="Tracked Lanes" value={laneSummary.lanes} />
        <StatCard label="Ranked Agents" value={laneSummary.totalRankedAgents} />
        <StatCard label="Unresolved Leads" value={stats.unresolved} />
        <StatCard label="Resolved Leads" value={stats.resolved} />
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-[1.1fr,0.9fr]">
        <SourceDiversityCard
          stats={{
            totalAgents: laneSummary.totalRankedAgents,
            uniqueOwners: laneSummary.uniqueOwners,
            uniqueBuckets: laneSummary.sourceMix.length,
            uniqueHosts: laneSummary.uniqueHosts,
            owners: [],
            hosts: [],
            topOwner: '',
            topOwnerCount: 0,
            headline: laneSummary.concentrated > 0 ? 'Concentrated source base' : 'Healthy source diversity',
            tone: laneSummary.concentrated > 0 ? 'border-amber/30 bg-amber/10 text-amber-200' : 'border-green/30 bg-green/10 text-green',
            notes: laneSummary.concentrated > 0
              ? ['Some lanes still depend too heavily on one owner or source family. Bigger scraping is not the same thing as better benchmarking.']
              : ['The live ranked lanes are starting to show healthier source variety, but source growth still needs dedupe and review discipline.'],
            buckets: laneSummary.sourceMix.map(([label, count]) => ({
              bucket: label.toLowerCase().replace(/\s+/g, '-'),
              label,
              count,
            })),
          }}
        />

        <section className="rounded-2xl border border-border bg-bg-card p-6">
          <h2 className="text-xl font-semibold text-text-primary">Lead Pipeline Health</h2>
          <p className="mt-2 text-sm text-text-muted">
            This is where noisy web discovery stops being hype and starts becoming a reviewable artifact queue.
          </p>

          <div className="mt-4 space-y-3">
            <div className="rounded-xl border border-amber/30 bg-amber/10 p-4 text-sm text-amber-200">
              Raw mentions are not lane readiness. Only resolved, reviewed, same-role agents should shape public rankings.
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">No artifact</div>
                <div className="mt-2 text-2xl font-bold text-text-primary">{stats.no_artifact}</div>
                <p className="mt-2 text-sm text-text-secondary">
                  Leads that turned out to be commentary, videos, or marketing with no benchmarkable artifact.
                </p>
              </div>
              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Dead links</div>
                <div className="mt-2 text-2xl font-bold text-text-primary">{stats.dead_link}</div>
                <p className="mt-2 text-sm text-text-secondary">
                  Leads that looked promising but currently resolve nowhere useful.
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>

      <section className="mt-8 rounded-2xl border border-border bg-bg-card p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-text-primary">Candidate Leads</h2>
            <p className="mt-1 text-sm text-text-muted">
              Real lead records from non-benchmark sources. Resolve them into actual artifacts before review and normalization.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <label className="flex flex-col gap-1 text-xs uppercase tracking-[0.18em] text-text-muted">
              Source
              <select
                value={sourceFilter}
                onChange={(event) => setSourceFilter(event.target.value)}
                className="rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm normal-case tracking-normal text-text-primary"
              >
                <option value="">All sources</option>
                {sourceOptions.map((source) => (
                  <option key={source} value={source}>
                    {formatSlug(source)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs uppercase tracking-[0.18em] text-text-muted">
              Resolution
              <select
                value={resolutionFilter}
                onChange={(event) => setResolutionFilter(event.target.value)}
                className="rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm normal-case tracking-normal text-text-primary"
              >
                <option value="">All states</option>
                <option value="unresolved">Unresolved</option>
                <option value="resolved">Resolved</option>
                <option value="no-artifact">No artifact</option>
                <option value="dead-link">Dead link</option>
              </select>
            </label>
          </div>
        </div>

        <div className="mt-6 space-y-4">
          {leads.length === 0 ? (
            <div className="rounded-xl border border-border bg-bg-secondary/60 p-6 text-sm text-text-muted">
              No leads matched the current filters yet.
            </div>
          ) : (
            leads.map((lead) => {
              const artifactLinks = parseJsonArray(lead.extracted_artifact_links_json);
              const outboundLinks = parseJsonArray(lead.outbound_links_json);
              return (
                <article
                  key={lead.id}
                  className="rounded-2xl border border-border bg-bg-secondary/45 p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-border px-2 py-1 text-[11px] uppercase tracking-[0.18em] text-text-muted">
                          {formatSlug(lead.source_type)}
                        </span>
                        <span className={`rounded-full border px-2 py-1 text-[11px] uppercase tracking-[0.18em] ${stateTone(lead.resolution_state)}`}>
                          {formatSlug(lead.resolution_state)}
                        </span>
                        <span className="rounded-full border border-border px-2 py-1 text-[11px] uppercase tracking-[0.18em] text-text-muted">
                          review: {formatSlug(lead.review_state)}
                        </span>
                      </div>
                      <h3 className="mt-3 text-lg font-semibold text-text-primary">{lead.title || 'Untitled lead'}</h3>
                      {lead.description && (
                        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary">
                          {lead.description}
                        </p>
                      )}
                    </div>

                    <div className="grid min-w-[13rem] gap-3 sm:grid-cols-3 sm:text-right">
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-text-muted">Signal</div>
                        <div className="mt-1 font-mono text-lg text-text-primary">{lead.signal_strength.toFixed(1)}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-text-muted">Mentions</div>
                        <div className="mt-1 font-mono text-lg text-text-primary">{lead.mention_count}</div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-[0.16em] text-text-muted">Artifacts</div>
                        <div className="mt-1 font-mono text-lg text-text-primary">{artifactLinks.length}</div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr,0.8fr]">
                    <div className="rounded-xl border border-border bg-bg-card/60 p-4">
                      <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Discovery trail</div>
                      <div className="mt-3 space-y-2 text-sm text-text-secondary">
                        <div>
                          Source post:
                          {' '}
                          <a
                            href={lead.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-cyan-accent no-underline hover:underline"
                          >
                            open original
                          </a>
                        </div>
                        <div>Outbound links found: {outboundLinks.length}</div>
                        <div>Discovered: {lead.discovered_at ? new Date(lead.discovered_at).toLocaleString() : 'unknown'}</div>
                        {lead.resolved_artifact_url && (
                          <div>
                            Resolved artifact:
                            {' '}
                            <a
                              href={lead.resolved_artifact_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-cyan-accent no-underline hover:underline"
                            >
                              open artifact
                            </a>
                          </div>
                        )}
                        {lead.resolved_version_id && (
                          <div>
                            Routed version:
                            {' '}
                            <Link
                              to={`/review/${lead.resolved_version_id}`}
                              className="text-cyan-accent no-underline hover:underline"
                            >
                              review candidate
                            </Link>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="rounded-xl border border-border bg-bg-card/60 p-4">
                      <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Operator read</div>
                      <div className="mt-3 space-y-2 text-sm leading-relaxed text-text-secondary">
                        <p>
                          {lead.resolution_state === 'resolved'
                            ? 'This lead already resolved into an artifact. The next question is lane fit and duplication, not discovery volume.'
                            : lead.resolution_state === 'unresolved'
                              ? 'This is still just a lead. It should not influence tournament claims until it resolves into a real agent artifact.'
                              : lead.resolution_state === 'no-artifact'
                                ? 'This is useful market signal, but not a benchmark candidate.'
                                : 'This source did not resolve cleanly enough to help the benchmark yet.'}
                        </p>
                        {lead.resolver_note && (
                          <p className="rounded-lg border border-border bg-bg-secondary/70 p-3 text-text-muted">
                            Resolver note: {lead.resolver_note}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })
          )}
        </div>
      </section>

      <section className="mt-8 rounded-2xl border border-border bg-bg-card p-6">
        <h2 className="text-xl font-semibold text-text-primary">Lanes under source pressure</h2>
        <p className="mt-2 text-sm text-text-muted">
          Bigger scraping helps only if it reduces concentration risk instead of duplicating the same curator or source family.
        </p>

        <div className="mt-5 grid gap-4">
          {sortedLanes.length === 0 ? (
            <div className="rounded-xl border border-border bg-bg-secondary/60 p-6 text-sm text-text-muted">
              No live lane source data yet.
            </div>
          ) : (
            sortedLanes.slice(0, 6).map((lane) => (
              <div
                key={`${lane.field}/${lane.role}`}
                className="rounded-2xl border border-border bg-bg-secondary/45 p-5"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">{formatSlug(lane.field)}</div>
                    <h3 className="mt-2 text-lg font-semibold text-text-primary">{formatSlug(lane.role)}</h3>
                    <p className="mt-2 text-sm text-text-secondary">
                      {lane.sourceDiversity.notes[0]}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Ranked agents</div>
                    <div className="mt-1 text-2xl font-bold text-text-primary">{lane.agentCount}</div>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    to={`/fields/${lane.field}/${lane.role}`}
                    className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-2 text-sm font-medium text-cyan-accent no-underline transition-colors hover:border-cyan-accent/50"
                  >
                    Open lane
                  </Link>
                  <Link
                    to="/review"
                    className="rounded-full border border-border px-3 py-2 text-sm font-medium text-text-secondary no-underline transition-colors hover:border-cyan-accent/30 hover:text-text-primary"
                  >
                    Review candidates
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
