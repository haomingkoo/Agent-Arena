import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import LaneMetaBadges from '../components/LaneMetaBadges';
import RatingChip from '../components/RatingChip';
import Skeleton from '../components/Skeleton';
import StatCard from '../components/StatCard';
import TournamentStatusChip from '../components/TournamentStatusChip';
import { getLaneStatus } from '../lib/laneStatus';
import {
  getFieldRoleLeaderboard,
  getTournaments,
  type AgentLeaderboardEntry,
  type AgentLeaderboardResponse,
  type TournamentSummary,
} from '../lib/api';

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function FieldRoleLeaderboardSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-4 h-10 w-80" />
      <div className="mt-6 mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-border bg-bg-card p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-8 w-20" />
          </div>
        ))}
      </div>
      <div className="overflow-hidden rounded-lg border border-border bg-bg-card">
        <div className="border-b border-border bg-bg-secondary px-4 py-3">
          <Skeleton className="h-4 w-full" />
        </div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="grid grid-cols-5 gap-3 border-b border-border px-4 py-4 last:border-0">
            <Skeleton className="h-5 w-8" />
            <Skeleton className="h-5 w-40" />
            <Skeleton className="ml-auto h-5 w-20" />
            <Skeleton className="ml-auto h-5 w-12" />
            <Skeleton className="ml-auto h-5 w-24" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function FieldRoleLeaderboard() {
  const { field, role } = useParams<{ field: string; role: string }>();
  const navigate = useNavigate();
  const [entries, setEntries] = useState<AgentLeaderboardEntry[]>([]);
  const [latestTournament, setLatestTournament] = useState<TournamentSummary | null>(null);
  const [laneMeta, setLaneMeta] = useState<
    Pick<AgentLeaderboardResponse, 'runtime_class' | 'task_pack_version' | 'tournament_type'> | null
  >(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!field || !role) return;
    Promise.all([
      getFieldRoleLeaderboard(field, role),
      getTournaments(`${field}/${role}`),
    ])
      .then(([data, tournaments]) => {
        setEntries(data.leaderboard ?? []);
        setLaneMeta({
          runtime_class: data.runtime_class,
          task_pack_version: data.task_pack_version,
          tournament_type: data.tournament_type,
        });
        setLatestTournament(tournaments.tournaments?.[0] ?? null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [field, role]);

  const stats = useMemo(() => {
    if (entries.length === 0) {
      return {
        totalAgents: 0,
        avgRating: '—',
        leader: '—',
        lastWeek: '—',
      };
    }

    const avgRating = Math.round(
      entries.reduce((sum, entry) => sum + entry.mu, 0) / entries.length,
    );
    return {
      totalAgents: entries.length,
      avgRating,
      leader: entries[0]?.agent_name ?? '—',
      lastWeek: entries.find((entry) => entry.last_tournament_week)?.last_tournament_week ?? '—',
    };
  }, [entries]);
  const laneStatus = getLaneStatus(entries.length);

  if (loading) {
    return <FieldRoleLeaderboardSkeleton />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load role leaderboard: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link
        to="/fields"
        className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
      >
        &larr; All Fields
      </Link>
      <div className="mt-3">
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/ops"
            className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
          >
            Open control room &rarr;
          </Link>
          {field && role ? (
            <Link
              to={`/jd/${encodeURIComponent(field)}/${encodeURIComponent(role)}`}
              className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
            >
              Open JD corpus &rarr;
            </Link>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          {formatSlug(role ?? '')}
        </h1>
        <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
          {field}
        </span>
      </div>
      <p className="mt-2 text-text-secondary">
        Same-role agent tournament leaderboard for {formatSlug(role ?? '')} in {formatSlug(field ?? '')}. Ratings are shown as Glicko-2
        {' '}
        <span className="font-mono text-text-primary">mu ± rd</span>.
      </p>
      <p className="mt-2 text-sm text-text-muted">
        The public ranking lives here. The JD corpus is the evidence layer we use to keep this role definition and task mix honest over time.
      </p>

      <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${laneStatus.tone}`}>
        <div className="font-semibold uppercase tracking-[0.18em]">{laneStatus.label}</div>
        <p className="mt-1 leading-relaxed">
          {laneStatus.body}
        </p>
        <p className="mt-2 leading-relaxed">
          {laneMeta?.tournament_type === 'standardized'
            ? 'Only standardized tournaments update public ratings. Holdout validation stays internal and does not change leaderboard rank.'
            : 'This lane is currently using an exploratory tournament mode, so treat the results as analysis rather than public rating truth.'}
        </p>
        <LaneMetaBadges
          className="mt-3"
          runtimeClass={laneMeta?.runtime_class}
          taskPackVersion={laneMeta?.task_pack_version}
          tournamentType={laneMeta?.tournament_type}
        />
      </div>

      {latestTournament && (
        <div className="mt-4 rounded-2xl border border-border bg-bg-card p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Latest Tournament</div>
              <div className="mt-2 text-lg font-semibold text-text-primary">
                {latestTournament.week}
              </div>
              <div className="mt-2 text-sm text-text-secondary">
                {latestTournament.status === 'running'
                  ? 'A tournament is running right now for this lane. Public ratings may lag until the run finalizes.'
                  : latestTournament.status === 'completed'
                    ? 'This lane has a completed tournament on record. Current ratings reflect standardized public results only.'
                    : 'This lane has a pending or partial tournament record. Treat the leaderboard carefully until a standardized run completes.'}
              </div>
            </div>
            <TournamentStatusChip status={latestTournament.status} />
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.16em] text-text-muted">
            <span className="rounded-full border border-border px-2 py-1">
              week {latestTournament.week}
            </span>
            <span className="rounded-full border border-border px-2 py-1">
              agents {latestTournament.num_skills}
            </span>
          </div>
          <LaneMetaBadges
            className="mt-3"
            runtimeClass={latestTournament.runtime_class ?? laneMeta?.runtime_class}
            taskPackVersion={latestTournament.task_pack_version ?? laneMeta?.task_pack_version}
            tournamentType={latestTournament.tournament_type ?? laneMeta?.tournament_type}
          />
          <div className="mt-4">
            <Link
              to={`/tournament/${encodeURIComponent(latestTournament.id)}`}
              className="inline-flex text-sm text-cyan-accent no-underline hover:underline"
            >
              Open tournament record
            </Link>
          </div>
        </div>
      )}

      <div className="mt-6 mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Agents" value={stats.totalAgents} />
        <StatCard label="Avg Rating" value={stats.avgRating} />
        <StatCard label="Top Agent" value={stats.leader} />
        <StatCard label="Latest Week" value={stats.lastWeek} />
      </div>

      {entries.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg-card p-8 text-center">
          <p className="text-text-muted">No benchmark-ready agents found for this role.</p>
        </div>
      ) : (
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="min-w-[760px] w-full text-left">
              <thead className="bg-bg-secondary text-sm text-text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Rank</th>
                  <th className="px-4 py-3 font-medium">Agent</th>
                  <th className="px-4 py-3 font-medium text-right">Rating</th>
                  <th className="px-4 py-3 font-medium text-right">Tournaments</th>
                  <th className="px-4 py-3 font-medium">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entries.map((entry, index) => (
                  <tr
                    key={entry.version_id}
                    onClick={() => navigate(`/agent/${encodeURIComponent(entry.version_id)}`)}
                    className="cursor-pointer transition-colors hover:bg-bg-hover"
                  >
                    <td className="px-4 py-3 font-mono text-sm text-text-muted">
                      {index + 1}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-text-primary transition-colors hover:text-cyan-accent">
                        {entry.agent_name}
                      </div>
                      <div className="mt-1 text-xs text-text-muted">
                        {entry.version_label}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <RatingChip mu={entry.mu} rd={entry.rd} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-text-secondary">
                      {entry.tournaments_played}
                    </td>
                    <td className="px-4 py-3 text-sm text-text-secondary">
                      {entry.source_url ? (
                        entry.source_url.startsWith('http') ? (
                          <a
                            href={entry.source_url}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(event) => event.stopPropagation()}
                            className="text-cyan-accent no-underline hover:underline"
                          >
                            Source
                          </a>
                        ) : (
                          <span className="text-text-muted" title={entry.source_url}>Local</span>
                        )
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
