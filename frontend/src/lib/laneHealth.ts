import type { AgentRoleSummary, TournamentSummary } from './api';
import { getLaneStatus } from './laneStatus';

export interface LaneHealth {
  headline: string;
  tone: string;
  notes: string[];
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

export function getLaneHealth(
  field: string,
  role: AgentRoleSummary,
  latestTournament?: TournamentSummary,
): LaneHealth {
  const notes: string[] = [];
  let severity: 'good' | 'warning' | 'risk' = 'good';

  const laneStatus = getLaneStatus(role.agent_count);
  notes.push(laneStatus.body);
  if (role.agent_count < 8) {
    severity = role.agent_count >= 5 ? 'warning' : 'risk';
  }

  if (!latestTournament) {
    notes.push('No tournament record yet, so this lane has no scored evidence beyond candidate supply.');
    severity = severity === 'risk' ? 'risk' : 'warning';
  } else if (latestTournament.status === 'running') {
    notes.push('A tournament is in flight. Ratings and lane conclusions may shift before the run finalizes.');
    severity = severity === 'risk' ? 'risk' : 'warning';
  } else if (latestTournament.status !== 'completed') {
    notes.push('The latest tournament is not completed, so this lane should not be treated as settled.');
    severity = severity === 'risk' ? 'risk' : 'warning';
  }

  if ((latestTournament?.tournament_type ?? role.tournament_type) !== 'standardized') {
    notes.push('This lane is not on standardized tournament mode, so results are not suitable for public rating claims.');
    severity = 'risk';
  }

  if (field === 'software-engineering' && role.role === 'software-engineer-agent') {
    notes.push('This role still needs an explicit task-pack alignment audit before it can be marketed as a clean software-engineer lane.');
    severity = 'risk';
  }

  const headline = severity === 'good'
    ? 'Credible public lane'
    : severity === 'warning'
      ? 'Pilot lane with caveats'
      : 'Needs lane audit';

  return {
    headline,
    tone: baseTone(severity),
    notes,
  };
}
