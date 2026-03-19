import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import ReviewStateBadge from '../components/ReviewStateBadge';
import Skeleton from '../components/Skeleton';
import {
  getDuplicateGroups,
  getReviewQueue,
  type DuplicateGroup,
  type ReviewQueueCandidate,
} from '../lib/api';

function formatSlug(value: string) {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function scoreLabel(value: number) {
  if (!value) return '—';
  return value.toFixed(2);
}

function ReviewQueueSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-36" />
      <Skeleton className="mt-4 h-10 w-72" />
      <div className="mt-6 grid gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-2xl border border-border bg-bg-card p-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-3 h-8 w-20" />
          </div>
        ))}
      </div>
      <div className="mt-8 overflow-hidden rounded-xl border border-border bg-bg-card">
        <div className="border-b border-border bg-bg-secondary px-4 py-3">
          <Skeleton className="h-4 w-full" />
        </div>
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="grid grid-cols-6 gap-3 border-b border-border px-4 py-4 last:border-0">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-5 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ReviewQueue() {
  const [candidates, setCandidates] = useState<ReviewQueueCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reviewState, setReviewState] = useState('');
  const [field, setField] = useState('');
  const [role, setRole] = useState('');
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);

  useEffect(() => {
    Promise.all([
      getReviewQueue({
        reviewState: reviewState || undefined,
        field: field || undefined,
        role: role || undefined,
        limit: 100,
      }),
      getDuplicateGroups({ limit: 200 }),
    ])
      .then(([reviewData, duplicateData]) => {
        setCandidates(reviewData.candidates ?? []);
        setDuplicates(duplicateData.duplicates ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [reviewState, field, role]);

  const duplicateMap = useMemo(() => {
    const map = new Map<string, DuplicateGroup[]>();
    for (const duplicate of duplicates) {
      const canonicalList = map.get(duplicate.canonical_version_id) ?? [];
      canonicalList.push(duplicate);
      map.set(duplicate.canonical_version_id, canonicalList);

      const duplicateList = map.get(duplicate.duplicate_version_id) ?? [];
      duplicateList.push(duplicate);
      map.set(duplicate.duplicate_version_id, duplicateList);
    }
    return map;
  }, [duplicates]);

  const summary = useMemo(() => {
    const manual = candidates.filter((candidate) => Boolean(candidate.manual_review_required)).length;
    const pending = candidates.filter((candidate) => candidate.review_state === 'pending-review').length;
    const qualification = candidates.filter((candidate) => candidate.review_state === 'qualification-required').length;
    const rejected = candidates.filter((candidate) => candidate.review_state === 'rejected').length;
    const duplicateRisk = candidates.filter((candidate) => (duplicateMap.get(candidate.version_id) ?? []).length > 0).length;
    return { manual, pending, qualification, rejected, duplicateRisk };
  }, [candidates, duplicateMap]);

  if (loading) return <ReviewQueueSkeleton />;

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load review queue: {error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link
        to="/ops"
        className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
      >
        &larr; Control Room
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          Human Review Queue
        </h1>
        <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
          internal
        </span>
      </div>
      <p className="mt-2 max-w-3xl text-text-secondary">
        Review low-confidence or high-importance candidates before they enter public same-role lanes. Use this queue to approve,
        relabel, reject, or route candidates to qualification instead of making silent DB edits.
      </p>

      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        <section className="rounded-2xl border border-border bg-bg-card p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Total in queue</div>
          <div className="mt-3 text-3xl font-bold text-text-primary">{candidates.length}</div>
        </section>
        <section className="rounded-2xl border border-border bg-bg-card p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Manual review</div>
          <div className="mt-3 text-3xl font-bold text-text-primary">{summary.manual}</div>
        </section>
        <section className="rounded-2xl border border-border bg-bg-card p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Pending / qualification</div>
          <div className="mt-3 text-3xl font-bold text-text-primary">{summary.pending + summary.qualification}</div>
        </section>
        <section className="rounded-2xl border border-border bg-bg-card p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Rejected</div>
          <div className="mt-3 text-3xl font-bold text-text-primary">{summary.rejected}</div>
        </section>
        <section className="rounded-2xl border border-border bg-bg-card p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-accent">Duplicate-risk</div>
          <div className="mt-3 text-3xl font-bold text-text-primary">{summary.duplicateRisk}</div>
        </section>
      </div>

      <div className="mt-6 rounded-2xl border border-border bg-bg-card p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-sm text-text-secondary">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Review State</div>
            <select
              value={reviewState}
              onChange={(event) => {
                setLoading(true);
                setReviewState(event.target.value);
              }}
              className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
            >
              <option value="">All states</option>
              <option value="pending-review">pending-review</option>
              <option value="qualification-required">qualification-required</option>
              <option value="approved-public">approved-public</option>
              <option value="approved-private-only">approved-private-only</option>
              <option value="relabelled">relabelled</option>
              <option value="rejected">rejected</option>
              <option value="unsupported">unsupported</option>
            </select>
          </label>
          <label className="text-sm text-text-secondary">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Field</div>
            <input
              value={field}
              onChange={(event) => {
                setLoading(true);
                setField(event.target.value);
              }}
              placeholder="software-engineering"
              className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
            />
          </label>
          <label className="text-sm text-text-secondary">
            <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Role</div>
            <input
              value={role}
              onChange={(event) => {
                setLoading(true);
                setRole(event.target.value);
              }}
              placeholder="code-review-agent"
              className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
            />
          </label>
        </div>
      </div>

      <div className="mt-8 overflow-hidden rounded-xl border border-border bg-bg-card">
        <div className="border-b border-border bg-bg-secondary px-4 py-3 text-sm text-text-muted">
          Candidates are sorted with manual-review-required items first.
        </div>
        {candidates.length === 0 ? (
          <div className="px-4 py-10 text-center text-text-muted">No review candidates match the current filters.</div>
        ) : (
          <div className="-mx-4 overflow-x-auto px-4">
            <table className="min-w-[980px] w-full text-left">
              <thead className="text-xs uppercase tracking-[0.16em] text-text-muted">
                <tr>
                  <th className="px-2 py-3 font-medium">Candidate</th>
                  <th className="px-2 py-3 font-medium">Claimed Lane</th>
                  <th className="px-2 py-3 font-medium">Predicted Lane</th>
                  <th className="px-2 py-3 font-medium">Review</th>
                  <th className="px-2 py-3 font-medium text-right">JD Fit</th>
                  <th className="px-2 py-3 font-medium text-right">Qual Fit</th>
                  <th className="px-2 py-3 font-medium">Access</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {candidates.map((candidate) => (
                  <tr key={candidate.version_id} className="transition-colors hover:bg-bg-hover">
                    <td className="px-2 py-3">
                      <Link
                        to={`/review/${encodeURIComponent(candidate.version_id)}`}
                        className="font-medium text-text-primary no-underline hover:text-cyan-accent"
                      >
                        {candidate.profile_name}
                      </Link>
                      <div className="mt-1 text-xs text-text-muted">
                        {candidate.owner || 'Unknown owner'} · {candidate.packaging_type}
                      </div>
                      {candidate.manual_review_required ? (
                        <div className="mt-2 text-[11px] uppercase tracking-[0.18em] text-amber-200">
                          manual review required
                        </div>
                      ) : null}
                      {(duplicateMap.get(candidate.version_id) ?? []).length > 0 ? (
                        <div className="mt-2 text-[11px] uppercase tracking-[0.18em] text-red">
                          duplicate-risk flagged
                        </div>
                      ) : null}
                      <div className="mt-2 flex flex-wrap gap-3 text-[11px] uppercase tracking-[0.16em]">
                        <Link
                          to={`/fields/${encodeURIComponent(candidate.field)}/${encodeURIComponent(candidate.role)}`}
                          className="text-text-muted no-underline transition-colors hover:text-text-primary hover:underline"
                        >
                          lane
                        </Link>
                        <Link
                          to={`/jd/${encodeURIComponent(candidate.field)}/${encodeURIComponent(candidate.role)}`}
                          className="text-text-muted no-underline transition-colors hover:text-text-primary hover:underline"
                        >
                          jd corpus
                        </Link>
                      </div>
                    </td>
                    <td className="px-2 py-3 text-sm text-text-secondary">
                      {formatSlug(candidate.field)} / {formatSlug(candidate.role)}
                    </td>
                    <td className="px-2 py-3 text-sm text-text-secondary">
                      {candidate.predicted_field || candidate.predicted_role
                        ? `${formatSlug(candidate.predicted_field || candidate.field)} / ${formatSlug(candidate.predicted_role || candidate.role)}`
                        : '—'}
                    </td>
                    <td className="px-2 py-3">
                      <ReviewStateBadge state={candidate.review_state} />
                    </td>
                    <td className="px-2 py-3 text-right font-mono text-sm text-text-primary">
                      {scoreLabel(candidate.jd_fit_score)}
                    </td>
                    <td className="px-2 py-3 text-right font-mono text-sm text-text-primary">
                      {scoreLabel(candidate.qualification_fit_score)}
                    </td>
                    <td className="px-2 py-3 text-sm text-text-secondary">
                      {candidate.source_url?.startsWith('http') ? (
                        <a
                          href={candidate.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-cyan-accent no-underline hover:underline"
                        >
                          Source
                        </a>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
