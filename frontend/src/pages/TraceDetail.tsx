import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import LaneHealthCard from "../components/LaneHealthCard";
import Skeleton from "../components/Skeleton";
import {
  getFieldRoleLeaderboard,
  getTournaments,
  getTraceDetail,
  type TraceDetail as TraceDetailModel,
  type TournamentSummary,
} from "../lib/api";
import {
  formatTraceKind,
  traceKindSummary,
  traceKindTone,
} from "../lib/traceKinds";

function safeJsonParse<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function formatCurrency(value: number) {
  return `$${value.toFixed(4)}`;
}

function formatSlug(value: string) {
  return value
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function TraceDetailSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-44" />
      <Skeleton className="mt-4 h-10 w-72" />
      <div className="mt-6 mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="rounded-lg border border-border bg-bg-card p-4"
          >
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-8 w-20" />
          </div>
        ))}
      </div>
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="rounded-xl border border-border bg-bg-card p-6"
          >
            <Skeleton className="h-6 w-40" />
            <Skeleton className="mt-4 h-40 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

function TraceSection({
  title,
  content,
  muted = false,
}: {
  title: string;
  content: string;
  muted?: boolean;
}) {
  return (
    <section className="rounded-2xl border border-border bg-bg-card p-6">
      <h2 className="text-xl font-semibold text-text-primary">{title}</h2>
      <pre
        className={`mt-4 overflow-x-auto whitespace-pre-wrap rounded-xl p-4 font-mono text-xs ${
          muted
            ? "bg-bg-secondary/70 text-text-secondary"
            : "bg-bg-primary/80 text-text-primary"
        }`}
      >
        {content || "—"}
      </pre>
    </section>
  );
}

export default function TraceDetail() {
  const { traceId } = useParams<{ traceId: string }>();
  const [trace, setTrace] = useState<TraceDetailModel | null>(null);
  const [laneAgentCount, setLaneAgentCount] = useState(0);
  const [latestTournament, setLatestTournament] =
    useState<TournamentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!traceId) return;
    getTraceDetail(traceId)
      .then((data) => setTrace(data.trace))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [traceId]);

  useEffect(() => {
    if (!trace) return;
    Promise.all([
      getFieldRoleLeaderboard(trace.field, trace.role),
      getTournaments(`${trace.field}/${trace.role}`),
    ])
      .then(([leaderboard, tournaments]) => {
        setLaneAgentCount(leaderboard.count ?? 0);
        setLatestTournament(tournaments.tournaments?.[0] ?? null);
      })
      .catch(() => {
        setLaneAgentCount(0);
        setLatestTournament(null);
      });
  }, [trace]);

  const parsed = useMemo(() => {
    if (!trace) {
      return {
        prompt: {} as Record<string, unknown>,
        metadata: {} as Record<string, unknown>,
        toolCalls: [] as unknown[],
        toolOutputs: [] as unknown[],
      };
    }
    return {
      prompt: safeJsonParse<Record<string, unknown>>(trace.prompt_json, {}),
      metadata: safeJsonParse<Record<string, unknown>>(trace.metadata_json, {}),
      toolCalls: safeJsonParse<unknown[]>(trace.tool_calls_json, []),
      toolOutputs: safeJsonParse<unknown[]>(trace.tool_outputs_json, []),
    };
  }, [trace]);

  if (loading) {
    return <TraceDetailSkeleton />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load trace: {error}</p>
        </div>
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <p className="text-text-muted">Trace not found.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center gap-3 text-sm text-text-muted">
        <Link
          to={`/fields/${encodeURIComponent(trace.field)}/${encodeURIComponent(trace.role)}`}
          className="no-underline transition-colors hover:text-cyan-accent"
        >
          {formatSlug(trace.role)}
        </Link>
        <span className="text-text-muted/50">/</span>
        <Link
          to={`/agent/${encodeURIComponent(trace.agent_version_id)}`}
          className="no-underline transition-colors hover:text-cyan-accent"
        >
          Agent Detail
        </Link>
        <span className="text-text-muted/50">/</span>
        {trace.tournament_id ? (
          <Link
            to={`/tournament/${encodeURIComponent(trace.tournament_id)}`}
            className="no-underline transition-colors hover:text-cyan-accent"
          >
            &larr; Back to Tournament
          </Link>
        ) : (
          <span>&larr; Benchmark Trace</span>
        )}
        <span className="text-text-muted/50">/</span>
        <span>{trace.task_id}</span>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Trace {trace.task_id}
        </h1>
        <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
          {trace.status}
        </span>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] ${traceKindTone(trace.trace_kind)}`}
        >
          {formatTraceKind(trace.trace_kind)}
        </span>
      </div>
      <p className="mt-2 text-text-secondary">
        {formatSlug(trace.field)} / {formatSlug(trace.role)} ·{" "}
        {trace.exec_provider}
        {trace.judge_provider ? ` → ${trace.judge_provider}` : ""}
      </p>

      <div className="mt-4 rounded-xl border border-border bg-bg-card p-4 text-sm text-text-secondary">
        {traceKindSummary(trace.trace_kind)}
        <div className="mt-2">
          This trace belongs to a same-role competition lane. Interpret it in
          the context of agents competing under the same task pack and runtime
          constraints.
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.16em] text-text-muted">
          <span className="rounded-full border border-border px-2 py-1">
            runtime {trace.runtime_class ?? "standard"}
          </span>
          <span className="rounded-full border border-border px-2 py-1">
            pack {trace.task_pack_version ?? "v1"}
          </span>
          <span className="rounded-full border border-border px-2 py-1">
            {trace.tournament_type ?? "standardized"}
          </span>
        </div>
      </div>

      <div className="mt-6 mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-border bg-bg-card p-4">
          <div className="text-sm text-text-muted">Runtime</div>
          <div className="mt-1 text-2xl font-bold font-mono text-text-primary">
            {trace.runtime_ms}ms
          </div>
        </div>
        <div className="rounded-lg border border-border bg-bg-card p-4">
          <div className="text-sm text-text-muted">Tokens</div>
          <div className="mt-1 text-2xl font-bold font-mono text-text-primary">
            {trace.input_tokens + trace.output_tokens}
          </div>
        </div>
        <div className="rounded-lg border border-border bg-bg-card p-4">
          <div className="text-sm text-text-muted">Cost</div>
          <div className="mt-1 text-2xl font-bold font-mono text-text-primary">
            {formatCurrency(trace.total_cost_usd)}
          </div>
        </div>
        <div className="rounded-lg border border-border bg-bg-card p-4">
          <div className="text-sm text-text-muted">Created</div>
          <div className="mt-1 text-sm font-mono text-text-primary">
            {trace.created_at
              ? new Date(trace.created_at).toLocaleString()
              : "—"}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <LaneHealthCard
          field={trace.field}
          role={trace.role}
          agentCount={laneAgentCount}
          runtimeClass={trace.runtime_class}
          taskPackVersion={trace.task_pack_version}
          tournamentType={trace.tournament_type}
          latestTournament={latestTournament}
          showLinks={false}
        />

        <TraceSection
          title="Execution Prompt"
          content={String(parsed.prompt.exec_prompt ?? "")}
        />
        <TraceSection title="Final Output" content={trace.final_output} />
        <TraceSection title="Judge Prompt" content={trace.judge_prompt} muted />
        <TraceSection title="Judge Output" content={trace.judge_output} muted />

        <section className="rounded-2xl border border-border bg-bg-card p-6">
          <h2 className="text-xl font-semibold text-text-primary">
            Trace Metadata
          </h2>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-xl bg-bg-secondary/70 p-4 font-mono text-xs text-text-secondary">
              {JSON.stringify(parsed.metadata, null, 2)}
            </pre>
            <pre className="overflow-x-auto whitespace-pre-wrap rounded-xl bg-bg-secondary/70 p-4 font-mono text-xs text-text-secondary">
              {JSON.stringify(
                {
                  tool_calls: parsed.toolCalls,
                  tool_outputs: parsed.toolOutputs,
                  error: trace.error,
                },
                null,
                2
              )}
            </pre>
          </div>
        </section>
      </div>
    </div>
  );
}
