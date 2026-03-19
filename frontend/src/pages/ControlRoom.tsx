import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import LaneMetaBadges from '../components/LaneMetaBadges';
import Skeleton from '../components/Skeleton';
import SourceDiversityCard from '../components/SourceDiversityCard';
import TournamentStatusChip from '../components/TournamentStatusChip';
import {
  getDuplicateGroups,
  getFields,
  getFieldRoleLeaderboard,
  getTournaments,
  type AgentFieldSummary,
  type DuplicateGroup,
  type TournamentSummary,
} from '../lib/api';
import { getLaneHealth } from '../lib/laneHealth';
import { getLaneStatus } from '../lib/laneStatus';
import {
  type SourceDiversityStats,
  summarizeSourceDiversity,
} from '../lib/sourceSignals';

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

interface LaneRecord {
  field: string;
  role: string;
  agentCount: number;
  runtimeClass?: string;
  taskPackVersion?: string;
  tournamentType?: string;
  latestTournament?: TournamentSummary;
  sourceDiversity?: SourceDiversityStats;
}

function ControlRoomSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="mt-4 h-10 w-80" />
      <Skeleton className="mt-3 h-5 w-[34rem] max-w-full" />
      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="rounded-2xl border border-border bg-bg-card p-5">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="mt-3 h-8 w-24" />
            <Skeleton className="mt-3 h-4 w-full" />
          </div>
        ))}
      </div>
      <div className="mt-8 grid gap-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-2xl border border-border bg-bg-card p-5">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="mt-3 h-4 w-32" />
            <Skeleton className="mt-4 h-4 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ControlRoom() {
  const [fields, setFields] = useState<AgentFieldSummary[]>([]);
  const [tournaments, setTournaments] = useState<TournamentSummary[]>([]);
  const [sourceStatsByLane, setSourceStatsByLane] = useState<Record<string, SourceDiversityStats> | null>(null);
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getFields(), getTournaments(), getDuplicateGroups({ limit: 200 })])
      .then(([fieldData, tournamentData, duplicateData]) => {
        setFields(fieldData.fields);
        setTournaments(tournamentData.tournaments ?? []);
        setDuplicates(duplicateData.duplicates ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (fields.length === 0) {
      return;
    }

    const lanesToFetch = fields.flatMap((field) =>
      field.roles.map((role) => ({
        field: field.field,
        role: role.role,
      })),
    );

    let cancelled = false;

    Promise.all(
      lanesToFetch.map(async (lane) => {
        const response = await getFieldRoleLeaderboard(lane.field, lane.role);
        return [
          `${lane.field}/${lane.role}`,
          summarizeSourceDiversity(response.leaderboard ?? []),
        ] as const;
      }),
    )
      .then((records) => {
        if (cancelled) return;
        setSourceStatsByLane(Object.fromEntries(records));
      })
      .catch(() => {
        if (cancelled) return;
        setSourceStatsByLane({});
      });

    return () => {
      cancelled = true;
    };
  }, [fields]);

  const latestByCategory = useMemo(() => {
    const byCategory: Record<string, TournamentSummary> = {};
    for (const tournament of tournaments) {
      if (!byCategory[tournament.category]) {
        byCategory[tournament.category] = tournament;
      }
    }
    return byCategory;
  }, [tournaments]);

  const lanes = useMemo<LaneRecord[]>(() => {
    return fields.flatMap((field) =>
      field.roles.map((role) => {
        const category = `${field.field}/${role.role}`;
        return {
          field: field.field,
          role: role.role,
          agentCount: role.agent_count,
          runtimeClass: role.runtime_class,
          taskPackVersion: role.task_pack_version,
          tournamentType: role.tournament_type,
          latestTournament: latestByCategory[category],
          sourceDiversity: sourceStatsByLane?.[category],
        };
      }),
    );
  }, [fields, latestByCategory, sourceStatsByLane]);

  const sourceLoading = fields.length > 0 && sourceStatsByLane === null;

  const summary = useMemo(() => {
    const publicReady = lanes.filter((lane) => getLaneStatus(lane.agentCount).label === 'Public Lane').length;
    const live = lanes.filter((lane) => lane.latestTournament?.status === 'running').length;
    const needingAudit = lanes.filter((lane) => getLaneHealth(lane.field, {
      role: lane.role,
      agent_count: lane.agentCount,
      runtime_class: lane.runtimeClass,
      task_pack_version: lane.taskPackVersion,
      tournament_type: lane.tournamentType,
    }, lane.latestTournament).headline === 'Needs lane audit').length;
    const sourceRisk = lanes.filter((lane) => lane.sourceDiversity?.headline === 'Concentrated source base').length;
    return { publicReady, live, needingAudit, sourceRisk, duplicateGroups: duplicates.length };
  }, [lanes, duplicates]);

  const sortedLanes = useMemo(() => {
    return [...lanes].sort((a, b) => {
      const aRunning = a.latestTournament?.status === 'running' ? 1 : 0;
      const bRunning = b.latestTournament?.status === 'running' ? 1 : 0;
      if (aRunning !== bRunning) return bRunning - aRunning;
      return b.agentCount - a.agentCount;
    });
  }, [lanes]);

  if (loading) {
    return <ControlRoomSkeleton />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load control room: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="inline-flex items-center rounded-full border border-cyan-accent/20 bg-cyan-glow px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-cyan-accent">
        Arena Ops
      </div>
      <h1 className="mt-4 text-4xl font-bold tracking-tight text-text-primary sm:text-5xl">
        See which lanes are actually ready to support public claims.
      </h1>
      <p className="mt-4 max-w-3xl text-base leading-relaxed text-text-secondary sm:text-lg">
        This view is for operational honesty. It helps us keep public rankings same-role only, spot shallow lanes,
        and avoid overclaiming before a lane has enough depth, clean tournament evidence, and aligned task design.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          to="/review"
          className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-4 py-2 text-sm font-medium text-cyan-accent no-underline transition-colors hover:border-cyan-accent/50 hover:bg-bg-hover"
        >
          Open review queue
        </Link>
        <Link
          to="/sources"
          className="rounded-full border border-border px-4 py-2 text-sm font-medium text-text-secondary no-underline transition-colors hover:border-cyan-accent/30 hover:text-text-primary"
        >
          Open source queue
        </Link>
        <Link
          to="/fields"
          className="rounded-full border border-border px-4 py-2 text-sm font-medium text-text-secondary no-underline transition-colors hover:border-cyan-accent/30 hover:text-text-primary"
        >
          Back to fields
        </Link>
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-5">
        <section className="rounded-2xl border border-border bg-bg-card p-5">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Public-ready lanes</div>
          <div className="mt-3 text-4xl font-bold text-text-primary">{summary.publicReady}</div>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Lanes with enough same-role candidate depth to support a stronger public ranking.
          </p>
        </section>
        <section className="rounded-2xl border border-border bg-bg-card p-5">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Live runs</div>
          <div className="mt-3 text-4xl font-bold text-text-primary">{summary.live}</div>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Tournaments currently running. Ratings and narratives can still move while these are in flight.
          </p>
        </section>
        <section className="rounded-2xl border border-border bg-bg-card p-5">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Needs audit</div>
          <div className="mt-3 text-4xl font-bold text-text-primary">{summary.needingAudit}</div>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Lanes that still need role-fit, task-pack, or public-claim cleanup before we market them aggressively.
          </p>
        </section>
        <section className="rounded-2xl border border-border bg-bg-card p-5">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Source-risk lanes</div>
          <div className="mt-3 text-4xl font-bold text-text-primary">{summary.sourceRisk}</div>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Lanes where one owner or source family still dominates the current ranked pool.
          </p>
        </section>
        <section className="rounded-2xl border border-border bg-bg-card p-5">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Duplicate groups</div>
          <div className="mt-3 text-4xl font-bold text-text-primary">{summary.duplicateGroups}</div>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Recorded duplicate relationships that can quietly inflate a lane if left untreated.
          </p>
        </section>
      </div>

      <div className="mt-8 rounded-2xl border border-cyan-accent/15 bg-[linear-gradient(180deg,rgba(14,22,34,0.98),rgba(10,14,23,0.98))] p-5">
        <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Operating Rules</div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {[
            'Public ranking is only valid for same-role agents under the same lane metadata.',
            'ATS and JD corpora should define the role blueprint, then qualification prompts and work-sample tasks follow.',
            'Holdout traces are for integrity checks, not public leaderboard score inflation.',
            'Broader discovery is good, but source concentration still matters if one curator or source family dominates a lane.',
          ].map((rule) => (
            <div key={rule} className="rounded-xl border border-border bg-bg-card/70 p-4 text-sm leading-relaxed text-text-secondary">
              {rule}
            </div>
          ))}
        </div>
      </div>

      {duplicates.length > 0 ? (
        <section className="mt-8 rounded-2xl border border-red/30 bg-red/5 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-text-primary">Duplicate Backlog</h2>
              <p className="mt-2 text-sm text-text-secondary">
                Wider scraping only helps if mirrored or template-derived agents do not quietly count as separate competitors.
              </p>
            </div>
            <Link
              to="/review"
              className="rounded-full border border-red/30 px-4 py-2 text-sm font-medium text-red no-underline transition-colors hover:bg-red/10"
            >
              Open review queue
            </Link>
          </div>

          <div className="mt-5 space-y-3">
            {duplicates.slice(0, 5).map((duplicate) => (
              <div key={duplicate.id} className="rounded-xl border border-red/20 bg-bg-card/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium text-text-primary">
                    {duplicate.canonical_name} ↔ {duplicate.duplicate_name}
                  </div>
                  <span className="rounded-full border border-red/30 px-2 py-1 text-[11px] uppercase tracking-[0.18em] text-red">
                    {duplicate.match_type}
                  </span>
                </div>
                {duplicate.note ? (
                  <p className="mt-2 text-sm text-text-secondary">{duplicate.note}</p>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="mt-8 space-y-4">
        {sortedLanes.map((lane) => {
          const laneStatus = getLaneStatus(lane.agentCount);
          const health = getLaneHealth(
            lane.field,
            {
              role: lane.role,
              agent_count: lane.agentCount,
              runtime_class: lane.runtimeClass,
              task_pack_version: lane.taskPackVersion,
              tournament_type: lane.tournamentType,
            },
            lane.latestTournament,
          );

          return (
            <section key={`${lane.field}/${lane.role}`} className="rounded-2xl border border-border bg-bg-card p-5 shadow-[0_20px_60px_rgba(0,0,0,0.16)]">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.18em] text-text-muted">{formatSlug(lane.field)}</div>
                  <h2 className="mt-2 text-2xl font-semibold text-text-primary">{formatSlug(lane.role)}</h2>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${laneStatus.tone}`}>
                      {laneStatus.label}
                    </span>
                    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${health.tone}`}>
                      {health.headline}
                    </span>
                    {lane.latestTournament && <TournamentStatusChip status={lane.latestTournament.status} />}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold text-text-primary">{lane.agentCount}</div>
                  <div className="text-xs uppercase tracking-[0.18em] text-text-muted">eligible agents</div>
                </div>
              </div>

              <LaneMetaBadges
                className="mt-4"
                runtimeClass={lane.latestTournament?.runtime_class ?? lane.runtimeClass}
                taskPackVersion={lane.latestTournament?.task_pack_version ?? lane.taskPackVersion}
                tournamentType={lane.latestTournament?.tournament_type ?? lane.tournamentType}
              />

              <div className="mt-4 grid gap-4 lg:grid-cols-[1.4fr,1fr]">
                <div className={`rounded-xl border p-4 ${health.tone}`}>
                  <div className="text-xs uppercase tracking-[0.18em]">Credibility notes</div>
                  <div className="mt-3 space-y-2 text-sm leading-relaxed">
                    {health.notes.map((note) => (
                      <p key={note}>{note}</p>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-border bg-bg-secondary/60 p-4">
                  <div className="text-xs uppercase tracking-[0.18em] text-text-muted">Latest tournament</div>
                  {lane.latestTournament ? (
                    <>
                      <div className="mt-3 text-lg font-semibold text-text-primary">{lane.latestTournament.week}</div>
                      <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                        {lane.latestTournament.num_skills} agents in the latest recorded run for this lane.
                      </p>
                    </>
                  ) : (
                    <p className="mt-3 text-sm leading-relaxed text-text-secondary">
                      No tournament has been recorded for this lane yet.
                    </p>
                  )}
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Link
                      to={`/fields/${encodeURIComponent(lane.field)}/${encodeURIComponent(lane.role)}`}
                      className="text-sm text-cyan-accent no-underline hover:underline"
                    >
                      Open lane leaderboard
                    </Link>
                    <Link
                      to={`/jd/${encodeURIComponent(lane.field)}/${encodeURIComponent(lane.role)}`}
                      className="text-sm text-text-secondary no-underline hover:text-text-primary hover:underline"
                    >
                      Open JD corpus
                    </Link>
                    {lane.latestTournament && (
                      <Link
                        to={`/tournament/${encodeURIComponent(lane.latestTournament.id)}`}
                        className="text-sm text-text-secondary no-underline hover:text-text-primary hover:underline"
                      >
                        Open tournament record
                      </Link>
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-4">
                {lane.sourceDiversity ? (
                  <SourceDiversityCard stats={lane.sourceDiversity} compact />
                ) : (
                  <div className="rounded-xl border border-border bg-bg-secondary/60 p-4 text-sm text-text-muted">
                    {sourceLoading
                      ? 'Calculating source diversity from the live lane leaderboard…'
                      : 'No source diversity summary is available for this lane yet.'}
                  </div>
                )}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
