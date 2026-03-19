import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLeaderboard, getStats, type LeaderboardEntry, type Stats } from '../lib/api';
import Skeleton from '../components/Skeleton';
import UpgradeChip from '../components/UpgradeChip';
import StatCard from '../components/StatCard';

function LeaderboardSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-10 text-center">
        <Skeleton className="mx-auto h-10 w-72 max-w-full" />
        <Skeleton className="mx-auto mt-3 h-5 w-[32rem] max-w-full" />
      </div>

      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-lg border border-border bg-bg-card p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-8 w-20" />
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-bg-card">
        <div className="grid grid-cols-6 gap-3 border-b border-border bg-bg-secondary px-4 py-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-4 w-full" />
          ))}
        </div>
        <div className="divide-y divide-border">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="grid grid-cols-6 gap-3 px-4 py-4">
              <Skeleton className="h-5 w-8" />
              <Skeleton className="h-5 w-36" />
              <Skeleton className="ml-auto h-6 w-20" />
              <Skeleton className="ml-auto h-5 w-14" />
              <Skeleton className="ml-auto h-5 w-14" />
              <Skeleton className="ml-auto h-5 w-12" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Leaderboard() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeRow, setActiveRow] = useState(0);
  const rowRefs = useRef<Array<HTMLTableRowElement | null>>([]);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([getLeaderboard(), getStats()])
      .then(([lb, st]) => {
        setEntries(lb.skills);
        setStats(st);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    rowRefs.current = rowRefs.current.slice(0, entries.length);
  }, [entries.length]);

  const focusableRow = entries.length === 0
    ? -1
    : activeRow < 0
      ? 0
      : Math.min(activeRow, entries.length - 1);

  const focusRow = (index: number) => {
    if (entries.length === 0) return;
    const nextIndex = Math.max(0, Math.min(index, entries.length - 1));
    setActiveRow(nextIndex);
    rowRefs.current[nextIndex]?.focus();
  };

  const openArtifact = (skillName: string) => {
    navigate(`/skill/${encodeURIComponent(skillName)}`);
  };

  const handleRowKeyDown = (
    event: KeyboardEvent<HTMLTableRowElement>,
    index: number,
    skillName: string,
  ) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      focusRow(index + 1);
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      focusRow(index - 1);
      return;
    }

    if (event.key === 'Home') {
      event.preventDefault();
      focusRow(0);
      return;
    }

    if (event.key === 'End') {
      event.preventDefault();
      focusRow(entries.length - 1);
      return;
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openArtifact(skillName);
    }
  };

  if (loading) {
    return <LeaderboardSkeleton />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load: {error}</p>
          <p className="mt-2 text-sm text-text-muted">
            Make sure the API is running at localhost:8000
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* Hero */}
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          <span className="text-cyan-accent">Legacy</span>{' '}
          <span className="text-text-primary">Artifact Leaderboard</span>
        </h1>
        <p className="mt-2 text-base text-text-secondary sm:text-lg">
          Older prompt artifacts benchmarked against a no-artifact baseline. For the new
          agent-vs-agent tournament flow, start with the Fields view.
        </p>
        <div className="mt-4">
          <button
            type="button"
            onClick={() => navigate('/fields')}
            className="rounded-lg border border-cyan-accent/30 bg-cyan-glow px-4 py-2 text-sm font-medium text-cyan-accent transition-colors hover:border-cyan-accent/50 hover:bg-bg-hover"
          >
            Open Agent Fields
          </button>
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard
            label="Artifacts Benchmarked"
            value={stats.benchmark.skills_benchmarked}
          />
          <StatCard
            label="Avg Score"
            value={stats.benchmark.avg_score.toFixed(3)}
          />
          <StatCard
            label="Avg Upgrade"
            value={stats.benchmark.avg_upgrade != null ? `${stats.benchmark.avg_upgrade >= 0 ? '+' : ''}${stats.benchmark.avg_upgrade.toFixed(3)}` : '—'}
          />
          <StatCard
            label="Best Upgrade"
            value={stats.benchmark.best_upgrade != null ? `+${stats.benchmark.best_upgrade.toFixed(3)}` : '—'}
          />
        </div>
      )}

      {/* Leaderboard table */}
      {entries.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg-card p-12 text-center">
          <p className="text-text-muted">No benchmark results yet.</p>
          <p className="mt-2 text-sm text-text-muted">
            Run <code className="rounded bg-bg-secondary px-2 py-0.5 font-mono text-xs text-cyan-accent">python curate.py --benchmark path/to/artifact.md --paired</code> to generate legacy artifact data.
          </p>
        </div>
      ) : (
        <div>
          <p className="mb-3 text-xs text-text-muted">
            Keyboard: Tab into the leaderboard, then use the arrow keys and press Enter to open an artifact.
          </p>
          <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="min-w-[720px] w-full text-left">
                <caption className="sr-only">
                  AgentArena legacy artifact leaderboard. Focus a row and use the arrow keys to move between artifacts.
                </caption>
            <thead className="bg-bg-secondary text-sm text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">#</th>
                <th className="px-4 py-3 font-medium">Artifact</th>
                <th className="px-4 py-3 font-medium text-right">Upgrade</th>
                <th className="px-4 py-3 font-medium text-right">Score</th>
                <th className="px-4 py-3 font-medium text-right">Baseline</th>
                <th className="px-4 py-3 font-medium text-right">Pass Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {entries.map((entry, i) => (
                <tr
                  key={entry.skill_name}
                  ref={(node) => {
                    rowRefs.current[i] = node;
                  }}
                  tabIndex={focusableRow === i ? 0 : -1}
                  role="link"
                  aria-label={`Open ${entry.skill_name} details`}
                  onClick={() => openArtifact(entry.skill_name)}
                  onFocus={() => setActiveRow(i)}
                  onKeyDown={(event) => handleRowKeyDown(event, i, entry.skill_name)}
                  className={`cursor-pointer transition-colors hover:bg-bg-hover focus-visible:bg-bg-hover ${
                    focusableRow === i ? 'bg-bg-hover/70' : ''
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-sm text-text-muted">
                    {i + 1}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span
                        className={`font-medium transition-colors ${
                          focusableRow === i ? 'text-cyan-accent' : 'text-text-primary'
                        }`}
                      >
                        {entry.skill_name}
                      </span>
                      <span className="hidden text-xs text-text-muted sm:inline">Open</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <UpgradeChip value={entry.avg_upgrade} />
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm">
                    {entry.avg_overall.toFixed(3)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-text-muted">
                    {entry.avg_baseline != null ? entry.avg_baseline.toFixed(3) : '—'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm">
                    {entry.jobs_passed}/{entry.jobs_run}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
          </div>
        </div>
      )}
    </div>
  );
}
