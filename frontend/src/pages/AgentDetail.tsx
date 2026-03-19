import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import LaneHealthCard from '../components/LaneHealthCard';
import RatingChip from '../components/RatingChip';
import Skeleton from '../components/Skeleton';
import SourceProvenanceCard from '../components/SourceProvenanceCard';
import StatCard from '../components/StatCard';
import {
  formatTraceKind,
  traceKindSummary,
  traceKindTone,
} from '../lib/traceKinds';
import {
  getFieldRoleLeaderboard,
  getTournaments,
  getAgentDetail,
  type TournamentSummary,
  type AgentVersionDetail,
} from '../lib/api';

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function safeJsonParse<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function AgentDetailSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-48" />
      <Skeleton className="mt-4 h-10 w-80" />
      <div className="mt-6 mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-lg border border-border bg-bg-card p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-8 w-20" />
          </div>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-xl border border-border bg-bg-card p-6">
          <Skeleton className="h-6 w-56" />
          <Skeleton className="mt-3 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-4/5" />
        </div>
        <div className="rounded-xl border border-border bg-bg-card p-6">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="mt-4 h-20 w-full" />
        </div>
      </div>
    </div>
  );
}

export default function AgentDetail() {
  const { versionId } = useParams<{ versionId: string }>();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<AgentVersionDetail | null>(null);
  const [laneAgentCount, setLaneAgentCount] = useState(0);
  const [latestTournament, setLatestTournament] = useState<TournamentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!versionId) return;
    getAgentDetail(versionId)
      .then((data) => setDetail(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [versionId]);

  useEffect(() => {
    if (!detail) return;
    Promise.all([
      getFieldRoleLeaderboard(detail.field, detail.role),
      getTournaments(`${detail.field}/${detail.role}`),
    ])
      .then(([leaderboard, tournaments]) => {
        setLaneAgentCount(leaderboard.count ?? 0);
        setLatestTournament(tournaments.tournaments?.[0] ?? null);
      })
      .catch(() => {
        setLaneAgentCount(0);
        setLatestTournament(null);
      });
  }, [detail]);

  const parsed = useMemo(() => {
    if (!detail) {
      return {
        securityFindings: [] as string[],
        provenance: {} as Record<string, string>,
        contract: {} as Record<string, unknown>,
      };
    }
    return {
      securityFindings: safeJsonParse<string[]>(detail.security_findings_json, []),
      provenance: safeJsonParse<Record<string, string>>(detail.provenance_json, {}),
      contract: safeJsonParse<Record<string, unknown>>(detail.runner_contract_json, {}),
    };
  }, [detail]);

  if (loading) {
    return <AgentDetailSkeleton />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load agent detail: {error}</p>
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <p className="text-text-muted">Agent not found.</p>
      </div>
    );
  }

  const rating = detail.rating;
  const benchmarkTraces = detail.recent_traces.filter((trace) => trace.trace_kind !== 'holdout');
  const holdoutTraces = detail.recent_traces.filter((trace) => trace.trace_kind === 'holdout');

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link
        to={`/fields/${encodeURIComponent(detail.field)}/${encodeURIComponent(detail.role)}`}
        className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
      >
        &larr; {formatSlug(detail.role)}
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          {detail.profile_name}
        </h1>
        <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
          {detail.eligibility}
        </span>
      </div>
      <p className="mt-2 text-text-secondary">
        {formatSlug(detail.field)} / {formatSlug(detail.role)}
      </p>
      {detail.summary && (
        <p className="mt-2 max-w-3xl text-sm text-text-secondary">{detail.summary}</p>
      )}

      <div className="mt-6 mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard
          label="Current Rating"
          value={rating ? `${Math.round(rating.mu)} +/- ${Math.round(rating.rd)}` : '—'}
        />
        <StatCard
          label="Tournaments"
          value={rating?.tournaments_played ?? 0}
        />
        <StatCard
          label="Recent Traces"
          value={detail.recent_traces.length}
        />
        <StatCard
          label="Version"
          value={detail.version_label}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
        <section className="rounded-2xl border border-border bg-bg-card p-6 shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-text-primary">Benchmark Profile</h2>
              <p className="mt-2 text-sm text-text-muted">
                Source, provenance, benchmark contract, and tournament history for this agent version.
              </p>
            </div>
            {detail.profile_source_url?.startsWith('http') ? (
              <a
                href={detail.profile_source_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-cyan-accent no-underline hover:underline"
              >
                Source
              </a>
            ) : detail.profile_source_url ? (
              <span className="text-sm text-text-muted" title={detail.profile_source_url}>Local source</span>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Packaging</div>
              <div className="mt-2 font-medium text-text-primary">{detail.packaging_type}</div>
            </div>
            <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Owner</div>
              <div className="mt-2 font-medium text-text-primary">{detail.owner || 'Unknown'}</div>
            </div>
            <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Source Commit</div>
              <div className="mt-2 font-mono text-sm text-text-primary">{detail.source_commit || '—'}</div>
            </div>
            <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Content Hash</div>
              <div className="mt-2 break-all font-mono text-xs text-text-primary">{detail.content_hash || '—'}</div>
            </div>
          </div>

          <div className="mt-6">
            <SourceProvenanceCard
              provenance={parsed.provenance}
              packagingType={detail.packaging_type}
              owner={detail.owner}
              contentHash={detail.content_hash}
              profileSourceUrl={detail.profile_source_url}
            />
          </div>

          <div className="mt-6 overflow-hidden rounded-xl border border-border">
            <div className="border-b border-border bg-bg-secondary px-4 py-3">
              <h3 className="text-sm font-medium text-text-primary">Tournament History</h3>
            </div>
            {detail.tournament_entries.length === 0 ? (
              <div className="px-4 py-6 text-sm text-text-muted">
                No tournaments recorded for this agent version yet.
              </div>
            ) : (
              <div className="-mx-4 overflow-x-auto px-4">
                <table className="min-w-[620px] w-full text-left">
                  <thead className="text-xs uppercase tracking-[0.16em] text-text-muted">
                    <tr>
                      <th className="px-2 py-3 font-medium">Week</th>
                      <th className="px-2 py-3 font-medium">Rank</th>
                      <th className="px-2 py-3 font-medium text-right">Score</th>
                      <th className="px-2 py-3 font-medium text-right">Pass Rate</th>
                      <th className="px-2 py-3 font-medium text-right">Tokens</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {detail.tournament_entries.map((entry) => (
                      <tr
                        key={`${entry.tournament_id}-${entry.week}`}
                        className="cursor-pointer transition-colors hover:bg-bg-hover"
                        onClick={() => navigate(`/tournament/${encodeURIComponent(entry.tournament_id)}`)}
                      >
                        <td className="px-2 py-3 font-mono text-sm text-text-primary">{entry.week}</td>
                        <td className="px-2 py-3 text-sm text-text-secondary">#{entry.rank}</td>
                        <td className="px-2 py-3 text-right font-mono text-sm text-text-primary">
                          {entry.avg_score.toFixed(3)}
                        </td>
                        <td className="px-2 py-3 text-right font-mono text-sm text-text-secondary">
                          {(entry.pass_rate * 100).toFixed(0)}%
                        </td>
                        <td className="px-2 py-3 text-right font-mono text-xs text-text-muted">
                          {entry.total_tokens.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {detail.tournament_entries.length > 0 && (
              <div className="border-t border-border bg-bg-secondary/40 px-4 py-3 text-xs text-text-muted">
                Latest lane metadata:
                {' '}
                {detail.tournament_entries[0].runtime_class ?? detail.runtime_class ?? 'standard'}
                {' · '}
                {detail.tournament_entries[0].task_pack_version ?? detail.task_pack_version ?? 'v1'}
                {' · '}
                {detail.tournament_entries[0].tournament_type ?? detail.tournament_type ?? 'standardized'}
              </div>
            )}
          </div>
        </section>

        <div className="space-y-6">
          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Competition Lane</h2>
            <p className="mt-2 text-sm text-text-muted">
              Public rankings are only meant to compare agents inside the same lane. This version competes in:
            </p>
            <div className="mt-4 rounded-xl border border-cyan-accent/20 bg-cyan-glow/40 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Lane</div>
              <div className="mt-2 text-lg font-semibold text-text-primary">
                {formatSlug(detail.field)} / {formatSlug(detail.role)}
              </div>
              <div className="mt-2 text-sm text-text-secondary">
                Same role, shared task pack, shared judging, and shared runtime constraints.
              </div>
              <div className="mt-2 text-sm text-text-secondary">
                Public ratings update only from standardized tournaments. Holdout validation remains internal even when traces are visible here for audit.
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.16em] text-text-muted">
                <span className="rounded-full border border-border px-2 py-1">
                  runtime {detail.runtime_class ?? 'standard'}
                </span>
                <span className="rounded-full border border-border px-2 py-1">
                  pack {detail.task_pack_version ?? 'v1'}
                </span>
                <span className="rounded-full border border-border px-2 py-1">
                  {detail.tournament_type ?? 'standardized'}
                </span>
              </div>
              <Link
                to={`/fields/${encodeURIComponent(detail.field)}/${encodeURIComponent(detail.role)}`}
                className="mt-4 inline-flex text-sm text-cyan-accent no-underline hover:underline"
              >
                View lane leaderboard
              </Link>
            </div>
          </section>

          <LaneHealthCard
            field={detail.field}
            role={detail.role}
            agentCount={laneAgentCount}
            runtimeClass={detail.runtime_class}
            taskPackVersion={detail.task_pack_version}
            tournamentType={detail.tournament_type}
            latestTournament={latestTournament}
          />

          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Rating Snapshot</h2>
            {rating ? (
              <div className="mt-4 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-muted">Current</span>
                  <RatingChip mu={rating.mu} rd={rating.rd} />
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-muted">Volatility</span>
                  <span className="font-mono text-text-primary">{rating.sigma.toFixed(4)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-muted">Last Week</span>
                  <span className="font-mono text-text-primary">{rating.last_tournament_week || '—'}</span>
                </div>
              </div>
            ) : (
              <p className="mt-4 text-sm text-text-muted">No rating history available yet.</p>
            )}
          </section>

          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Recent Traces</h2>
            {detail.recent_traces.length === 0 ? (
              <p className="mt-4 text-sm text-text-muted">No traces stored yet.</p>
            ) : (
              <div className="mt-4 space-y-5">
                {benchmarkTraces.length > 0 && (
                  <div className="space-y-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-text-muted">
                      Public Benchmark Traces
                    </div>
                    {benchmarkTraces.map((trace) => (
                      <Link
                        key={trace.id}
                        to={`/traces/${encodeURIComponent(trace.id)}`}
                        className="block rounded-xl border border-border bg-bg-secondary/70 p-4 no-underline transition-colors hover:border-cyan-accent/40 hover:bg-bg-hover"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="font-medium text-text-primary">{trace.task_id}</div>
                              <span
                                className={`rounded-full border px-2 py-1 text-[10px] font-medium uppercase tracking-[0.16em] ${traceKindTone(trace.trace_kind)}`}
                              >
                                {formatTraceKind(trace.trace_kind)}
                              </span>
                            </div>
                            <div className="mt-1 text-xs text-text-muted">
                              {trace.exec_provider} → {trace.judge_provider || 'no judge'} · {trace.status}
                            </div>
                            <div className="mt-2 text-xs text-text-secondary">
                              {traceKindSummary(trace.trace_kind)}
                            </div>
                          </div>
                          <span className="font-mono text-xs text-text-secondary">
                            {trace.runtime_ms}ms
                          </span>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}

                {holdoutTraces.length > 0 && (
                  <div className="space-y-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-text-muted">
                      Internal Holdout Validation
                    </div>
                    {holdoutTraces.map((trace) => (
                      <Link
                        key={trace.id}
                        to={`/traces/${encodeURIComponent(trace.id)}`}
                        className="block rounded-xl border border-amber-400/25 bg-amber-400/5 p-4 no-underline transition-colors hover:border-amber-300/40 hover:bg-amber-400/10"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="font-medium text-text-primary">{trace.task_id}</div>
                              <span
                                className={`rounded-full border px-2 py-1 text-[10px] font-medium uppercase tracking-[0.16em] ${traceKindTone(trace.trace_kind)}`}
                              >
                                {formatTraceKind(trace.trace_kind)}
                              </span>
                            </div>
                            <div className="mt-1 text-xs text-text-muted">
                              {trace.exec_provider} → {trace.judge_provider || 'no judge'} · {trace.status}
                            </div>
                            <div className="mt-2 text-xs text-amber-100/90">
                              {traceKindSummary(trace.trace_kind)}
                            </div>
                          </div>
                          <span className="font-mono text-xs text-text-secondary">
                            {trace.runtime_ms}ms
                          </span>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Contract</h2>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-muted">Model</span>
                <span className="font-mono text-text-primary">
                  {String(parsed.contract.model_provider ?? '—')}/{String(parsed.contract.model_name ?? '—')}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-muted">Token Budget</span>
                <span className="font-mono text-text-primary">
                  {String(parsed.contract.max_total_tokens ?? '—')}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-text-muted">Allowed Tools</span>
                <span className="font-mono text-text-primary">
                  {Array.isArray(parsed.contract.allowed_tools)
                    ? parsed.contract.allowed_tools.join(', ') || 'none'
                    : 'none'}
                </span>
              </div>
            </div>
            {parsed.securityFindings.length > 0 && (
              <div className="mt-4 rounded-xl border border-red/30 bg-red/5 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-red">Security Findings</div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-red">
                  {parsed.securityFindings.map((finding) => (
                    <li key={finding}>{finding}</li>
                  ))}
                </ul>
              </div>
            )}
            <details className="mt-4 rounded-xl border border-border bg-bg-secondary/50 p-4">
              <summary className="cursor-pointer text-sm font-medium text-text-primary">
                Raw contract and provenance
              </summary>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-bg-primary/70 p-3 font-mono text-xs text-text-secondary">
                {JSON.stringify(
                  {
                    contract: parsed.contract,
                    provenance: parsed.provenance,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </section>
        </div>
      </div>
    </div>
  );
}
