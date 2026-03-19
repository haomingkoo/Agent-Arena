import { Link } from 'react-router-dom';
import type { AgentRoleSummary, TournamentSummary } from '../lib/api';
import { getLaneHealth } from '../lib/laneHealth';
import { getLaneStatus } from '../lib/laneStatus';

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

interface Props {
  field: string;
  role: string;
  agentCount: number;
  runtimeClass?: string;
  taskPackVersion?: string;
  tournamentType?: string;
  latestTournament?: TournamentSummary | null;
  showLinks?: boolean;
}

export default function LaneHealthCard({
  field,
  role,
  agentCount,
  runtimeClass,
  taskPackVersion,
  tournamentType,
  latestTournament,
  showLinks = true,
}: Props) {
  const laneStatus = getLaneStatus(agentCount);
  const laneSummary: AgentRoleSummary = {
    role,
    agent_count: agentCount,
    runtime_class: runtimeClass,
    task_pack_version: taskPackVersion,
    tournament_type: tournamentType,
  };
  const health = getLaneHealth(field, laneSummary, latestTournament ?? undefined);

  return (
    <section className="rounded-2xl border border-border bg-bg-card p-6">
      <h2 className="text-xl font-semibold text-text-primary">Lane Health</h2>
      <p className="mt-2 text-sm text-text-muted">
        Same-role public rankings are only as strong as the surrounding lane design and evidence quality.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${laneStatus.tone}`}>
          {laneStatus.label}
        </span>
        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${health.tone}`}>
          {health.headline}
        </span>
        {latestTournament?.status ? (
          <span className="rounded-full border border-border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            {latestTournament.status}
          </span>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Lane</div>
          <div className="mt-2 font-medium text-text-primary">
            {formatSlug(field)} / {formatSlug(role)}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
          <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Benchmark-ready agents</div>
          <div className="mt-2 font-mono text-lg text-text-primary">{agentCount}</div>
        </div>
      </div>

      <div className={`mt-4 rounded-xl border p-4 ${health.tone}`}>
        <div className="space-y-2 text-sm leading-relaxed">
          {health.notes.map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      </div>

      {showLinks && (
        <div className="mt-4 flex flex-wrap gap-4 text-sm">
          <Link
            to={`/fields/${encodeURIComponent(field)}/${encodeURIComponent(role)}`}
            className="text-cyan-accent no-underline hover:underline"
          >
            Open lane leaderboard
          </Link>
          <Link
            to="/ops"
            className="text-text-secondary no-underline hover:text-text-primary hover:underline"
          >
            Open control room
          </Link>
        </div>
      )}
    </section>
  );
}
