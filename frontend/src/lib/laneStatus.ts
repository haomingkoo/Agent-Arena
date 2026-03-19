export interface LaneStatus {
  label: string;
  tone: string;
  body: string;
}

export function getLaneStatus(agentCount: number): LaneStatus {
  if (agentCount >= 8) {
    return {
      label: 'Public Lane',
      tone: 'border-green/30 bg-green/10 text-green',
      body: 'This lane has enough benchmark-ready agents to support a more credible public ranking.',
    };
  }

  if (agentCount >= 5) {
    return {
      label: 'Pilot Lane',
      tone: 'border-amber/30 bg-amber/10 text-amber-200',
      body: 'This lane is useful for early comparison, but the candidate pool is still small. Treat standings as directional, not final truth.',
    };
  }

  return {
    label: 'Emerging Lane',
    tone: 'border-red/30 bg-red/10 text-red',
    body: 'This lane does not yet have enough benchmark-ready agents for a strong public claim. We show it for transparency while the pool grows.',
  };
}
