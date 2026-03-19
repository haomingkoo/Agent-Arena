import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  getCategoryDetail,
  getCategoryLeaderboard,
  getTournaments,
  type TournamentSummary,
} from '../lib/api';
import Skeleton from '../components/Skeleton';
import CategoryBadge from '../components/CategoryBadge';
import RatingChip from '../components/RatingChip';
import StatCard from '../components/StatCard';

interface LeaderboardRow {
  skill_id: string;
  skill_name: string;
  mu: number;
  rd: number;
  tournaments_played: number;
}

interface CategoryInfo {
  slug: string;
  display_name: string;
  description: string;
  skill_count: number;
  task_count: number;
  active: boolean;
}

function CategoryDetailSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="mt-4 h-10 w-64" />
      <div className="mt-6 mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
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
          <div key={i} className="flex gap-4 border-b border-border px-4 py-4 last:border-0">
            <Skeleton className="h-5 w-8" />
            <Skeleton className="h-5 w-40" />
            <Skeleton className="ml-auto h-5 w-20" />
            <Skeleton className="h-5 w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CategoryDetail() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [category, setCategory] = useState<CategoryInfo | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[]>([]);
  const [tournaments, setTournaments] = useState<TournamentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!slug) return;

    Promise.all([
      getCategoryDetail(slug),
      getCategoryLeaderboard(slug),
      getTournaments(slug),
    ])
      .then(([catData, lbData, tData]) => {
        setCategory(catData.category ?? catData);
        setLeaderboard(lbData.leaderboard ?? []);
        setTournaments(tData.tournaments ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) return <CategoryDetailSkeleton />;

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load category: {error}</p>
        </div>
      </div>
    );
  }

  const avgRating =
    leaderboard.length > 0
      ? Math.round(leaderboard.reduce((s, r) => s + r.mu, 0) / leaderboard.length)
      : 0;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* Back link */}
      <Link
        to="/categories"
        className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
      >
        &larr; All Categories
      </Link>

      {/* Header */}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          {category?.display_name ?? slug}
        </h1>
        {slug && <CategoryBadge category={slug} size="md" />}
      </div>
      {category?.description && (
        <p className="mt-2 text-text-secondary">{category.description}</p>
      )}

      {/* Stats row */}
      <div className="mt-6 mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard label="Skills" value={category?.skill_count ?? leaderboard.length} />
        <StatCard label="Avg Rating" value={avgRating} />
        <StatCard label="Tournaments" value={tournaments.length} />
      </div>

      {/* Leaderboard table */}
      <h2 className="mb-3 text-xl font-semibold text-text-primary">Leaderboard</h2>
      {leaderboard.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg-card p-8 text-center">
          <p className="text-text-muted">No rated skills in this category yet.</p>
        </div>
      ) : (
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="min-w-[640px] w-full text-left">
              <thead className="bg-bg-secondary text-sm text-text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Rank</th>
                  <th className="px-4 py-3 font-medium">Skill</th>
                  <th className="px-4 py-3 font-medium text-right">Rating</th>
                  <th className="px-4 py-3 font-medium text-right">Tournaments</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {leaderboard.map((row, i) => (
                  <tr
                    key={row.skill_id}
                    onClick={() => navigate(`/skill/${encodeURIComponent(row.skill_name)}`)}
                    className="cursor-pointer transition-colors hover:bg-bg-hover"
                  >
                    <td className="px-4 py-3 font-mono text-sm text-text-muted">
                      {i + 1}
                    </td>
                    <td className="px-4 py-3 font-medium text-text-primary hover:text-cyan-accent transition-colors">
                      {row.skill_name}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <RatingChip mu={row.mu} rd={row.rd} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-text-muted">
                      {row.tournaments_played}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent tournaments */}
      <h2 className="mt-10 mb-3 text-xl font-semibold text-text-primary">
        Recent Tournaments
      </h2>
      {tournaments.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg-card p-8 text-center">
          <p className="text-text-muted">No tournaments have been run yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tournaments.map((t) => (
            <Link
              key={t.id}
              to={`/tournament/${encodeURIComponent(t.id)}`}
              className="rounded-lg border border-border bg-bg-card p-4 no-underline transition-colors hover:border-cyan-accent/40 hover:bg-bg-hover"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm font-medium text-text-primary">
                  {t.week}
                </span>
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${
                    t.status === 'completed'
                      ? 'bg-green/10 text-green'
                      : t.status === 'running'
                        ? 'bg-cyan-glow text-cyan-accent'
                        : 'bg-text-muted/10 text-text-muted'
                  }`}
                >
                  {t.status}
                </span>
              </div>
              <div className="mt-2 flex gap-4 text-sm text-text-muted">
                <span>
                  <span className="font-mono text-text-primary">{t.num_skills}</span> skills
                </span>
                <span>
                  avg{' '}
                  <span className="font-mono text-text-primary">
                    {t.baseline_avg.toFixed(3)}
                  </span>
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
