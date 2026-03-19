import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getTournamentDetail, type TournamentEntryDetail } from '../lib/api';
import Skeleton from '../components/Skeleton';
import CategoryBadge from '../components/CategoryBadge';
import LaneMetaBadges from '../components/LaneMetaBadges';
import TournamentStatusChip from '../components/TournamentStatusChip';

interface TournamentInfo {
  id: string;
  category: string;
  week: string;
  status: string;
  num_skills: number;
  baseline_avg: number;
  completed_at: string;
  total_cost_usd: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
  field?: string;
  role?: string;
  runtime_class?: string;
  task_pack_version?: string;
  tournament_type?: string;
  entries: TournamentEntryDetail[];
}

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function TournamentSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-4 h-10 w-72" />
      <div className="mt-4 flex gap-3">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-6 w-20" />
      </div>
      <div className="mt-8 overflow-hidden rounded-lg border border-border bg-bg-card">
        <div className="border-b border-border bg-bg-secondary px-4 py-3">
          <Skeleton className="h-4 w-full" />
        </div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex gap-4 border-b border-border px-4 py-4 last:border-0">
            <Skeleton className="h-5 w-8" />
            <Skeleton className="h-5 w-40" />
            <Skeleton className="ml-auto h-5 w-16" />
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-5 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}

function RatingChangeChip({ before, after }: { before: number; after: number }) {
  const diff = after - before;
  if (diff === 0) return <span className="text-text-muted font-mono text-sm">0</span>;

  const positive = diff > 0;
  const color = positive ? 'text-green' : 'text-red';
  const bg = positive ? 'bg-green/10' : 'bg-red/10';
  const sign = positive ? '+' : '';

  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 font-mono text-sm font-medium ${color} ${bg}`}>
      {sign}{Math.round(diff)}
    </span>
  );
}

export default function TournamentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tournament, setTournament] = useState<TournamentInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;

    getTournamentDetail(id)
      .then((data) => setTournament({
        ...data.tournament,
        entries: data.entries ?? data.tournament.entries ?? [],
      }))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <TournamentSkeleton />;

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load tournament: {error}</p>
        </div>
      </div>
    );
  }

  if (!tournament) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <p className="text-text-muted">Tournament not found.</p>
      </div>
    );
  }

  const entries = tournament.entries ?? [];
  const isAgentNative = Boolean(tournament.field && tournament.role);
  const laneLink = isAgentNative
    ? `/fields/${encodeURIComponent(tournament.field ?? '')}/${encodeURIComponent(tournament.role ?? '')}`
    : `/categories/${encodeURIComponent(tournament.category)}`;
  const laneStatusCopy = tournament.tournament_type === 'standardized'
    ? 'This tournament belongs to a standardized same-role lane, so it can affect public ratings.'
    : 'This tournament is exploratory and should be treated as analysis, not public rating truth.';
  const credibilityTone = tournament.tournament_type === 'standardized' && tournament.status === 'completed'
    ? 'border-green/30 bg-green/10 text-green'
    : 'border-amber/30 bg-amber/10 text-amber-200';
  const credibilityHeadline = tournament.tournament_type === 'standardized' && tournament.status === 'completed'
    ? 'Standardized lane result'
    : 'Treat this as provisional';
  const legacyTone = isAgentNative
    ? 'border-cyan-accent/20 bg-cyan-glow/30 text-text-secondary'
    : 'border-amber/30 bg-amber/10 text-amber-200';

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link
        to={laneLink}
        className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
      >
        &larr; {isAgentNative ? `${formatSlug(tournament.role ?? '')} lane` : tournament.category}
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Tournament {tournament.week}
        </h1>
        {isAgentNative ? (
          <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
            {tournament.field}
          </span>
        ) : (
          <CategoryBadge category={tournament.category} size="md" />
        )}
        <TournamentStatusChip status={tournament.status} />
      </div>
      {isAgentNative ? (
        <p className="mt-2 text-text-secondary">
          Same-role tournament for {formatSlug(tournament.role ?? '')} in {formatSlug(tournament.field ?? '')}.
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-4 text-sm text-text-muted">
        <span>
          <span className="font-mono text-text-primary">{tournament.num_skills}</span>{' '}
          {isAgentNative ? 'agents' : 'skills'}
        </span>
        <span>
          avg baseline{' '}
          <span className="font-mono text-text-primary">
            {tournament.baseline_avg.toFixed(3)}
          </span>
        </span>
        {tournament.total_cost_usd > 0 && (
          <span>
            cost{' '}
            <span className="font-mono text-text-primary">
              ${tournament.total_cost_usd.toFixed(2)}
            </span>
          </span>
        )}
        {typeof tournament.total_input_tokens === 'number' && typeof tournament.total_output_tokens === 'number' && (
          <span>
            tokens{' '}
            <span className="font-mono text-text-primary">
              {(tournament.total_input_tokens + tournament.total_output_tokens).toLocaleString()}
            </span>
          </span>
        )}
        {tournament.completed_at && (
          <span>
            completed{' '}
            <span className="text-text-primary">
              {new Date(tournament.completed_at).toLocaleDateString()}
            </span>
          </span>
        )}
      </div>

      <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${credibilityTone}`}>
        <div className="font-semibold uppercase tracking-[0.18em]">{credibilityHeadline}</div>
        <p className="mt-1 leading-relaxed">
          {laneStatusCopy}
          {isAgentNative
            ? ' Public comparisons are only meaningful inside this exact lane metadata.'
            : ' This older category flow is still available for reference, but it is not the primary AgentArena path.'}
        </p>
        <LaneMetaBadges
          className="mt-3"
          runtimeClass={tournament.runtime_class}
          taskPackVersion={tournament.task_pack_version}
          tournamentType={tournament.tournament_type}
        />
      </div>

      <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${legacyTone}`}>
        <div className="font-semibold uppercase tracking-[0.18em]">
          {isAgentNative ? 'Agent-native tournament view' : 'Legacy tournament view'}
        </div>
        <p className="mt-1 leading-relaxed">
          {isAgentNative ? (
            <>
              This tournament belongs to the main same-role agent flow. You can inspect the surrounding lane in{' '}
              <Link to={laneLink} className="text-cyan-accent no-underline hover:underline">Fields</Link>
              {' '}or audit lane readiness in{' '}
              <Link to="/ops" className="text-cyan-accent no-underline hover:underline">Control Room</Link>.
            </>
          ) : (
            <>
              This page shows the older category and skill-style tournament model. The primary product path is now the
              same-role agent flow under <Link to="/fields" className="text-cyan-accent no-underline hover:underline">Fields</Link>.
            </>
          )}
        </p>
      </div>

      <div className="mt-8">
        <h2 className="mb-3 text-xl font-semibold text-text-primary">Results</h2>
        {entries.length === 0 ? (
          <div className="rounded-lg border border-border bg-bg-card p-8 text-center">
            <p className="text-text-muted">No results available.</p>
          </div>
        ) : (
          <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="min-w-[720px] w-full text-left">
                <thead className="bg-bg-secondary text-sm text-text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">Rank</th>
                    <th className="px-4 py-3 font-medium">{isAgentNative ? 'Agent' : 'Skill'}</th>
                    <th className="px-4 py-3 font-medium text-right">Score</th>
                    <th className="px-4 py-3 font-medium text-right">Pass Rate</th>
                    <th className="px-4 py-3 font-medium text-right">Rating Change</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {entries.map((entry) => (
                    <tr
                      key={entry.id}
                      onClick={() =>
                        navigate(
                          isAgentNative
                            ? `/agent/${encodeURIComponent(entry.skill_id)}`
                            : `/skill/${encodeURIComponent(entry.skill_name)}`,
                        )
                      }
                      className="cursor-pointer transition-colors hover:bg-bg-hover"
                    >
                      <td className="px-4 py-3 font-mono text-sm text-text-muted">
                        {entry.rank}
                      </td>
                      <td className="px-4 py-3 font-medium text-text-primary hover:text-cyan-accent transition-colors">
                        {entry.skill_name}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-sm">
                        {entry.avg_score.toFixed(3)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-sm">
                        {(entry.pass_rate * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-3 text-right">
                        <RatingChangeChip
                          before={entry.rating_before}
                          after={entry.rating_after}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
