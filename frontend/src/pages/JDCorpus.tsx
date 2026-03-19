import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Skeleton from '../components/Skeleton';
import StatCard from '../components/StatCard';
import {
  getJDCorpusDetail,
  getJDPostings,
  type JDCorpusResponse,
  type JDPosting,
} from '../lib/api';

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function safeJsonParse<T>(value: string, fallback: T): T {
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function prettyDate(value: string) {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString();
}

function JDCorpusSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-44" />
      <Skeleton className="mt-4 h-10 w-96 max-w-full" />
      <Skeleton className="mt-3 h-5 w-[36rem] max-w-full" />
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-2xl border border-border bg-bg-card p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-8 w-20" />
          </div>
        ))}
      </div>
      <div className="mt-8 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        {Array.from({ length: 2 }).map((_, index) => (
          <div key={index} className="rounded-2xl border border-border bg-bg-card p-6">
            <Skeleton className="h-6 w-44" />
            <Skeleton className="mt-4 h-40 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

function PostingChips({ values }: { values: string[] }) {
  if (values.length === 0) return <span className="text-text-muted">—</span>;
  return (
    <div className="flex flex-wrap gap-2">
      {values.slice(0, 4).map((value) => (
        <span
          key={value}
          className="rounded-full border border-border px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-text-muted"
        >
          {value}
        </span>
      ))}
    </div>
  );
}

export default function JDCorpus() {
  const { field, role } = useParams<{ field: string; role: string }>();
  const [corpus, setCorpus] = useState<JDCorpusResponse | null>(null);
  const [postings, setPostings] = useState<JDPosting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!field || !role) return;
    Promise.all([
      getJDCorpusDetail(field, role),
      getJDPostings({ field, role, limit: 25 }),
    ])
      .then(([corpusData, postingData]) => {
        setCorpus(corpusData);
        setPostings(postingData.postings ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [field, role]);

  const parsedVersion = useMemo(() => {
    if (!corpus?.latest_version) {
      return {
        sourceMix: {} as Record<string, unknown>,
        responsibilities: [] as string[],
        tools: [] as string[],
        skills: [] as string[],
      };
    }
    return {
      sourceMix: safeJsonParse<Record<string, unknown>>(corpus.latest_version.source_mix_json, {}),
      responsibilities: safeJsonParse<string[]>(corpus.latest_version.responsibilities_summary_json, []),
      tools: safeJsonParse<string[]>(corpus.latest_version.tools_summary_json, []),
      skills: safeJsonParse<string[]>(corpus.latest_version.skills_summary_json, []),
    };
  }, [corpus]);

  if (loading) return <JDCorpusSkeleton />;

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load JD corpus: {error}</p>
        </div>
      </div>
    );
  }

  if (!field || !role || !corpus) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <p className="text-text-muted">JD corpus not found.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-center gap-3 text-sm text-text-muted">
        <Link
          to={`/fields/${encodeURIComponent(field)}/${encodeURIComponent(role)}`}
          className="no-underline transition-colors hover:text-cyan-accent"
        >
          &larr; {formatSlug(role)}
        </Link>
        <span className="text-text-muted/50">/</span>
        <Link
          to="/review"
          className="no-underline transition-colors hover:text-cyan-accent"
        >
          Review
        </Link>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          JD Corpus: {formatSlug(role)}
        </h1>
        <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
          {field}
        </span>
      </div>
      <p className="mt-2 max-w-3xl text-text-secondary">
        This is the role-definition evidence layer for the lane. ATS-backed job descriptions should shape qualification prompts
        and task-pack updates, but they should not silently rewrite public benchmark claims without review.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Postings" value={corpus.stats.total} />
        <StatCard label="Companies" value={corpus.stats.companies} />
        <StatCard label="ATS Sources" value={corpus.stats.sources} />
        <StatCard label="Corpus Version" value={corpus.latest_version?.version_label ?? 'Not Built'} />
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-2xl border border-border bg-bg-card p-6 shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
          <h2 className="text-xl font-semibold text-text-primary">Corpus Status</h2>
          {corpus.latest_version ? (
            <div className="mt-4 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Latest snapshot</div>
                  <div className="mt-2 font-medium text-text-primary">{corpus.latest_version.version_label}</div>
                </div>
                <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                  <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Created</div>
                  <div className="mt-2 font-medium text-text-primary">{prettyDate(corpus.latest_version.created_at)}</div>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Source mix</div>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-bg-primary/70 p-3 font-mono text-xs text-text-secondary">
                  {JSON.stringify(parsedVersion.sourceMix, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-amber/30 bg-amber/10 p-4 text-sm text-amber-200">
              No JD corpus snapshot has been created for this lane yet. The adapters and APIs exist, but this lane still needs
              a real ATS refresh run before the role-definition evidence is useful.
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-border bg-bg-card p-6 shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
          <h2 className="text-xl font-semibold text-text-primary">Role Signals</h2>
          <div className="mt-4 space-y-4">
            <div>
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Responsibilities</div>
              <PostingChips values={parsedVersion.responsibilities} />
            </div>
            <div>
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Tools</div>
              <PostingChips values={parsedVersion.tools} />
            </div>
            <div>
              <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Skills</div>
              <PostingChips values={parsedVersion.skills} />
            </div>
          </div>
        </section>
      </div>

      <section className="mt-8 rounded-2xl border border-border bg-bg-card p-6 shadow-[0_24px_80px_rgba(0,0,0,0.18)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-text-primary">ATS-backed job postings</h2>
            <p className="mt-2 text-sm text-text-muted">
              These postings should feed lane definitions and qualification logic, not be treated as benchmark scores by themselves.
            </p>
          </div>
          <div className="rounded-full border border-border px-3 py-1 text-sm text-text-secondary">
            {postings.length} loaded
          </div>
        </div>

        {postings.length === 0 ? (
          <div className="mt-6 rounded-xl border border-border bg-bg-secondary/60 p-6 text-sm text-text-muted">
            No postings are stored for this lane yet. Once Claude runs the first ATS refresh with real source boards, this page will
            become the reviewable role corpus.
          </div>
        ) : (
          <div className="mt-6 -mx-4 overflow-x-auto px-4">
            <table className="min-w-[980px] w-full text-left">
              <thead className="text-xs uppercase tracking-[0.16em] text-text-muted">
                <tr>
                  <th className="px-2 py-3 font-medium">Company</th>
                  <th className="px-2 py-3 font-medium">Title</th>
                  <th className="px-2 py-3 font-medium">ATS</th>
                  <th className="px-2 py-3 font-medium">Location</th>
                  <th className="px-2 py-3 font-medium">Corpus</th>
                  <th className="px-2 py-3 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {postings.map((posting) => (
                  <tr key={posting.id} className="transition-colors hover:bg-bg-hover">
                    <td className="px-2 py-3 text-sm text-text-primary">{posting.company_name || '—'}</td>
                    <td className="px-2 py-3">
                      <div className="font-medium text-text-primary">{posting.title}</div>
                      {posting.department ? (
                        <div className="mt-1 text-xs text-text-muted">{posting.department}</div>
                      ) : null}
                    </td>
                    <td className="px-2 py-3 text-sm text-text-secondary">{posting.source_ats}</td>
                    <td className="px-2 py-3 text-sm text-text-secondary">{posting.location || '—'}</td>
                    <td className="px-2 py-3 text-sm text-text-secondary">{posting.corpus_version || '—'}</td>
                    <td className="px-2 py-3 text-sm text-text-secondary">{prettyDate(posting.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
