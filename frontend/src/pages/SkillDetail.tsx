import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getSkillDetail, type SkillDetail as SkillDetailType, type PairedJobResult, type JobResult } from '../lib/api';
import Skeleton from '../components/Skeleton';
import DimensionBars from '../components/DimensionBars';
import UpgradeChip from '../components/UpgradeChip';
import CertBadge from '../components/CertBadge';

function isPaired(r: PairedJobResult | JobResult): r is PairedJobResult {
  return 'upgrade' in r;
}

function SkillDetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-8">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="mt-4 h-10 w-72 max-w-full" />
        <div className="mt-3 flex flex-wrap gap-3">
          <Skeleton className="h-8 w-24 rounded-full" />
          <Skeleton className="h-8 w-32" />
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <section className="rounded-lg border border-border bg-bg-card p-6">
          <Skeleton className="h-6 w-40" />
          <div className="mt-6 grid grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index}>
                <Skeleton className="mx-auto h-8 w-16" />
                <Skeleton className="mx-auto mt-2 h-3 w-14" />
              </div>
            ))}
          </div>
          <div className="mt-6 space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-11 w-full" />
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-bg-card p-6">
          <Skeleton className="h-6 w-36" />
          <div className="mt-6 space-y-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index}>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-4 w-10" />
                </div>
                <Skeleton className="h-5 w-full rounded-full" />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

export default function SkillDetail() {
  const { name } = useParams<{ name: string }>();
  const [skill, setSkill] = useState<SkillDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!name) return;
    getSkillDetail(name)
      .then(setSkill)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [name]);

  if (loading) {
    return <SkillDetailSkeleton />;
  }

  if (error || !skill) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <p className="text-red">{error || 'Skill not found'}</p>
        <Link to="/" className="mt-4 inline-block text-cyan-accent no-underline">Back to leaderboard</Link>
      </div>
    );
  }

  const bench = skill.benchmark;
  const cert = skill.certification;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <Link to="/" className="text-sm text-text-muted no-underline hover:text-cyan-accent">
          &larr; Back to leaderboard
        </Link>
        <h1 className="mt-3 text-3xl font-bold text-text-primary sm:text-4xl">{skill.name}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          {cert && <CertBadge tier={cert.tier} size="md" />}
          {bench?.avg_upgrade != null && (
            <span className="text-sm text-text-muted">
              Upgrade: <UpgradeChip value={bench.avg_upgrade} size="md" />
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Benchmark results */}
        {bench && (
          <section className="rounded-lg border border-border bg-bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Benchmark Results</h2>
            <div className="mb-4 grid grid-cols-3 gap-3 text-center">
              <div>
                <div className="text-2xl font-bold font-mono">{bench.avg_overall.toFixed(3)}</div>
                <div className="text-xs text-text-muted">Score</div>
              </div>
              <div>
                <div className="text-2xl font-bold font-mono">{bench.avg_baseline?.toFixed(3) ?? '—'}</div>
                <div className="text-xs text-text-muted">Baseline</div>
              </div>
              <div>
                <div className="text-2xl font-bold font-mono">{bench.jobs_passed}/{bench.jobs_run}</div>
                <div className="text-xs text-text-muted">Passed</div>
              </div>
            </div>

            {/* Per-job results */}
            <h3 className="mb-2 text-sm font-semibold text-text-secondary">Per-Job Results</h3>
            <div className="space-y-2">
              {bench.results.map((r, i) => {
                if (isPaired(r)) {
                  return (
                    <div key={i} className="flex flex-col gap-2 rounded-md bg-bg-secondary px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
                      <span className="font-mono text-text-secondary">{r.job_id}</span>
                      <div className="flex flex-wrap items-center gap-3 sm:justify-end">
                        <span className="font-mono">{r.skill.overall.toFixed(2)}</span>
                        <span className="text-text-muted">vs</span>
                        <span className="font-mono text-text-muted">{r.baseline.overall.toFixed(2)}</span>
                        <UpgradeChip value={r.upgrade} />
                      </div>
                    </div>
                  );
                }
                const jr = r as JobResult;
                return (
                  <div key={i} className="flex flex-col gap-2 rounded-md bg-bg-secondary px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <span className="font-mono text-text-secondary">{jr.job_id}</span>
                    <div className="flex flex-wrap items-center gap-3 sm:justify-end">
                      <span className={jr.passed ? 'text-green' : 'text-red'}>
                        {jr.passed ? 'PASS' : 'FAIL'}
                      </span>
                      <span className="font-mono">{jr.overall.toFixed(2)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Certification & dimensions */}
        {cert && (
          <section className="rounded-lg border border-border bg-bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Certification</h2>
            <div className="mb-6">
              <DimensionBars dimensions={cert.dimensions} />
            </div>

            {cert.flags.length > 0 && (
              <div className="mb-4">
                <h3 className="mb-2 text-sm font-semibold text-text-secondary">Flags</h3>
                <div className="space-y-1">
                  {cert.flags.map((f, i) => (
                    <div key={i} className="rounded bg-red/5 px-3 py-1 text-sm text-red">
                      {f}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {cert.strengths.length > 0 && (
              <div className="mb-4">
                <h3 className="mb-2 text-sm font-semibold text-text-secondary">Strengths</h3>
                <div className="space-y-1">
                  {cert.strengths.map((s, i) => (
                    <div key={i} className="rounded bg-green/5 px-3 py-1 text-sm text-green">
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {cert.llm_reasoning && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-text-secondary">LLM Assessment</h3>
                <p className="text-sm text-text-secondary italic">{cert.llm_reasoning}</p>
              </div>
            )}
          </section>
        )}
      </div>

      {/* Source info */}
      {skill.source && (
        <section className="mt-8 rounded-lg border border-border bg-bg-card p-6">
          <h2 className="mb-3 text-lg font-semibold">Source</h2>
          <div className="flex flex-wrap gap-4 text-sm text-text-secondary">
            {skill.source.repo && <span>Repo: <span className="font-mono text-text-primary">{skill.source.repo}</span></span>}
            {skill.source.stars > 0 && <span>Stars: <span className="font-mono text-text-primary">{skill.source.stars.toLocaleString()}</span></span>}
            <span>Lines: <span className="font-mono text-text-primary">{skill.source.lines}</span></span>
            <span>Tokens: <span className="font-mono text-text-primary">~{skill.source.tokens.toLocaleString()}</span></span>
          </div>
        </section>
      )}
    </div>
  );
}
