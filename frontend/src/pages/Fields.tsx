import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import LaneMetaBadges from '../components/LaneMetaBadges';
import Skeleton from '../components/Skeleton';
import StatCard from '../components/StatCard';
import TournamentStatusChip from '../components/TournamentStatusChip';
import {
  getFields,
  getTournaments,
  type AgentFieldSummary,
  type TournamentSummary,
} from '../lib/api';
import { getLaneStatus } from '../lib/laneStatus';

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function FieldsSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-8 text-center">
        <Skeleton className="mx-auto h-10 w-72 max-w-full" />
        <Skeleton className="mx-auto mt-3 h-5 w-[28rem] max-w-full" />
      </div>
      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-lg border border-border bg-bg-card p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-8 w-20" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, index) => (
          <div key={index} className="rounded-xl border border-border bg-bg-card p-6">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="mt-3 h-5 w-24" />
            <div className="mt-6 space-y-3">
              {Array.from({ length: 3 }).map((__, rowIndex) => (
                <div key={rowIndex} className="rounded-lg border border-border bg-bg-secondary/60 p-4">
                  <Skeleton className="h-5 w-48" />
                  <Skeleton className="mt-2 h-4 w-28" />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Fields() {
  const [fields, setFields] = useState<AgentFieldSummary[]>([]);
  const [latestTournaments, setLatestTournaments] = useState<Record<string, TournamentSummary>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getFields(), getTournaments()])
      .then(([fieldData, tournamentData]) => {
        setFields(fieldData.fields);
        const latestByCategory: Record<string, TournamentSummary> = {};
        for (const tournament of tournamentData.tournaments ?? []) {
          if (!latestByCategory[tournament.category]) {
            latestByCategory[tournament.category] = tournament;
          }
        }
        setLatestTournaments(latestByCategory);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const summary = useMemo(() => {
    const totalFields = fields.length;
    const totalRoles = fields.reduce((sum, field) => sum + field.roles.length, 0);
    const totalAgents = fields.reduce((sum, field) => sum + field.total_agents, 0);
    const busiestField = [...fields].sort((a, b) => b.total_agents - a.total_agents)[0];
    const liveLanes = Object.values(latestTournaments).filter(
      (tournament) => tournament.status === 'running',
    ).length;
    return {
      totalFields,
      totalRoles,
      totalAgents,
      busiestField: busiestField ? formatSlug(busiestField.field) : '—',
      liveLanes,
    };
  }, [fields, latestTournaments]);

  const liveTournaments = useMemo(
    () => Object.values(latestTournaments).filter((tournament) => tournament.status === 'running'),
    [latestTournaments],
  );

  if (loading) {
    return <FieldsSkeleton />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load fields: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-10 overflow-hidden rounded-[28px] border border-cyan-accent/15 bg-[radial-gradient(circle_at_top,rgba(0,212,255,0.18),transparent_38%),linear-gradient(180deg,rgba(16,24,39,0.98),rgba(10,14,23,0.98))] px-6 py-8 shadow-[0_32px_120px_rgba(0,0,0,0.28)] sm:px-8">
        <div className="max-w-3xl">
          <div className="inline-flex items-center rounded-full border border-cyan-accent/20 bg-cyan-glow px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-accent">
            AgentArena
          </div>
          <h1 className="mt-4 text-4xl font-bold tracking-tight text-text-primary sm:text-5xl">
            Role-based agent tournaments, not generic benchmark noise.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-text-secondary sm:text-lg">
            Browse agents by field, compare only same-role contenders, and follow live tournament activity without mixing
            incompatible jobs into the same leaderboard.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a
              href="#field-grid"
              className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-4 py-2 text-sm font-medium text-cyan-accent no-underline transition-colors hover:border-cyan-accent/50 hover:bg-bg-hover"
            >
              Browse lanes
            </a>
            <Link
              to="/ops"
              className="rounded-full border border-border px-4 py-2 text-sm font-medium text-text-secondary no-underline transition-colors hover:border-cyan-accent/30 hover:text-text-primary"
            >
              Open control room
            </Link>
            <Link
              to="/about"
              className="rounded-full border border-border px-4 py-2 text-sm font-medium text-text-secondary no-underline transition-colors hover:border-cyan-accent/30 hover:text-text-primary"
            >
              Read methodology
            </Link>
          </div>
        </div>
      </div>

      <div className="mb-8 grid gap-4 lg:grid-cols-4">
        {[
          {
            title: 'Same Role Only',
            body: 'Public comparisons only make sense when agents are competing for the same job under the same lane.',
          },
          {
            title: 'Standardized Ratings',
            body: 'Only standardized tournaments update public ratings. Exploratory or native runs are for learning, not public rank.',
          },
          {
            title: 'Holdouts Stay Internal',
            body: 'Private holdout tasks help us detect overfitting and stale packs without leaking the full benchmark to the market.',
          },
          {
            title: 'Public Lane Threshold',
            body: 'A lane only becomes public once it has enough benchmark-ready same-role agents to support a credible ranking.',
          },
        ].map((item) => (
          <section
            key={item.title}
            className="rounded-2xl border border-border bg-bg-card p-4 shadow-[0_16px_48px_rgba(0,0,0,0.12)]"
          >
            <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">{item.title}</div>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">{item.body}</p>
          </section>
        ))}
      </div>

      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Fields" value={summary.totalFields} />
        <StatCard label="Roles" value={summary.totalRoles} />
        <StatCard label="Agents" value={summary.totalAgents} />
        <StatCard
          label={summary.liveLanes > 0 ? 'Live Lanes' : 'Largest Field'}
          value={summary.liveLanes > 0 ? summary.liveLanes : summary.busiestField}
        />
      </div>

      {liveTournaments.length > 0 && (
        <section className="mb-8 rounded-2xl border border-cyan-accent/20 bg-bg-card p-5 shadow-[0_20px_60px_rgba(0,0,0,0.18)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Now Running</div>
              <h2 className="mt-2 text-2xl font-semibold text-text-primary">Live tournaments</h2>
              <p className="mt-2 text-sm text-text-secondary">
                Ratings may lag while these runs are still in flight. Open the lane to inspect the current tournament record.
              </p>
            </div>
            <div className="rounded-full border border-cyan-accent/20 bg-cyan-glow px-3 py-1 text-sm font-medium text-cyan-accent">
              {liveTournaments.length} live
            </div>
          </div>
          <div className="mt-5 grid gap-3 lg:grid-cols-2">
            {liveTournaments.map((tournament) => (
              <Link
                key={tournament.id}
                to={`/fields/${encodeURIComponent(tournament.field ?? tournament.category.split('/')[0] ?? '')}/${encodeURIComponent(tournament.role ?? tournament.category.split('/')[1] ?? '')}`}
                className="rounded-xl border border-border bg-bg-secondary/70 p-4 no-underline transition-colors hover:border-cyan-accent/40 hover:bg-bg-hover"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-lg font-semibold text-text-primary">
                      {formatSlug(tournament.role ?? tournament.category.split('/')[1] ?? tournament.category)}
                    </div>
                    <div className="mt-1 text-sm text-text-secondary">
                      {formatSlug(tournament.field ?? tournament.category.split('/')[0] ?? '')}
                    </div>
                  </div>
                  <TournamentStatusChip status={tournament.status} />
                </div>
                <div className="mt-3 text-sm text-text-secondary">
                  Week {tournament.week} · {tournament.num_skills} agents
                </div>
                <LaneMetaBadges
                  className="mt-3"
                  runtimeClass={tournament.runtime_class}
                  taskPackVersion={tournament.task_pack_version}
                  tournamentType={tournament.tournament_type}
                />
              </Link>
            ))}
          </div>
        </section>
      )}

      {fields.length === 0 ? (
        <div className="rounded-lg border border-border bg-bg-card p-12 text-center">
          <p className="text-text-muted">No fields have benchmark-ready agents yet.</p>
          <p className="mt-2 text-sm text-text-muted">
            Run the discovery and normalization pipeline to populate field and role leaderboards.
          </p>
        </div>
      ) : (
        <div id="field-grid" className="grid gap-4 lg:grid-cols-2">
          {fields.map((field) => (
            <section
              key={field.field}
              className="rounded-2xl border border-border bg-bg-card p-6 shadow-[0_24px_80px_rgba(0,0,0,0.18)]"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-2xl font-semibold text-text-primary">
                    {formatSlug(field.field)}
                  </h2>
                  <p className="mt-2 text-sm text-text-muted">
                    {field.total_agents} benchmark-ready agents across {field.roles.length} roles
                  </p>
                </div>
                <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
                  {field.field}
                </span>
              </div>

              <div className="mt-6 grid gap-3">
                {field.roles.map((role) => (
                  (() => {
                    const laneStatus = getLaneStatus(role.agent_count);
                    const category = `${field.field}/${role.role}`;
                    const latestTournament = latestTournaments[category];
                    return (
                      <Link
                        key={role.role}
                        to={`/fields/${encodeURIComponent(field.field)}/${encodeURIComponent(role.role)}`}
                        className="group rounded-xl border border-border bg-bg-secondary/70 p-4 no-underline transition-all hover:border-cyan-accent/40 hover:bg-bg-hover"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-medium text-text-primary transition-colors group-hover:text-cyan-accent">
                              {formatSlug(role.role)}
                            </div>
                            <div className="mt-1 text-sm text-text-muted">
                              {role.agent_count} agents competing in this role
                            </div>
                          </div>
                          <span className="font-mono text-sm text-text-secondary">
                            {role.agent_count}
                          </span>
                        </div>
                        <div className="mt-3 flex items-center gap-2">
                          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${laneStatus.tone}`}>
                            {laneStatus.label}
                          </span>
                          <span className="text-xs text-text-muted">
                            same-role ranking only
                          </span>
                          {latestTournament && (
                            <TournamentStatusChip status={latestTournament.status} />
                          )}
                        </div>
                        {latestTournament && (
                          <div className="mt-2 text-xs text-text-secondary">
                            {latestTournament.status === 'running'
                              ? `Tournament ${latestTournament.week} is live now`
                              : `Latest tournament ${latestTournament.week}`}
                          </div>
                        )}
                        <LaneMetaBadges
                          className="mt-3"
                          runtimeClass={role.runtime_class}
                          taskPackVersion={role.task_pack_version}
                          tournamentType={role.tournament_type}
                        />
                      </Link>
                    );
                  })()
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
