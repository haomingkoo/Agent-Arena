import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ReviewStateBadge from '../components/ReviewStateBadge';
import Skeleton from '../components/Skeleton';
import SourceProvenanceCard from '../components/SourceProvenanceCard';
import {
  decideReviewCandidate,
  getDuplicateGroups,
  getReviewCandidate,
  type DuplicateGroup,
  type ReviewCandidateDetail,
  type ReviewDecisionRequest,
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

function scoreLabel(value: number) {
  if (!value) return '—';
  return value.toFixed(2);
}

function ReviewCandidateSkeleton() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-4 h-10 w-80" />
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="rounded-2xl border border-border bg-bg-card p-6">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="mt-4 h-28 w-full" />
            </div>
          ))}
        </div>
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, index) => (
            <div key={index} className="rounded-2xl border border-border bg-bg-card p-6">
              <Skeleton className="h-6 w-32" />
              <Skeleton className="mt-4 h-40 w-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ReviewCandidate() {
  const { versionId } = useParams<{ versionId: string }>();
  const [detail, setDetail] = useState<ReviewCandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [reviewer, setReviewer] = useState('koo');
  const [adminKey, setAdminKey] = useState('');
  const [action, setAction] = useState<ReviewDecisionRequest['action']>('approve');
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [newField, setNewField] = useState('');
  const [newRole, setNewRole] = useState('');
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);

  useEffect(() => {
    if (!versionId) return;
    setLoading(true);
    Promise.all([
      getReviewCandidate(versionId),
      getDuplicateGroups({ limit: 200 }),
    ])
      .then(([data, duplicateData]) => {
        setDetail(data);
        setNewField(data.predicted_field || data.field || '');
        setNewRole(data.predicted_role || data.role || '');
        setDuplicates(duplicateData.duplicates ?? []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [versionId]);

  const parsed = useMemo(() => {
    if (!detail) {
      return {
        provenance: {} as Record<string, string>,
        contract: {} as Record<string, unknown>,
        securityFindings: [] as string[],
        artifactSecurity: [] as string[],
      };
    }
    return {
      provenance: safeJsonParse<Record<string, string>>(detail.provenance_json, {}),
      contract: safeJsonParse<Record<string, unknown>>(detail.runner_contract_json, {}),
      securityFindings: safeJsonParse<string[]>(detail.security_findings_json, []),
      artifactSecurity: safeJsonParse<string[]>(detail.artifact_security, []),
    };
  }, [detail]);

  const relatedDuplicates = useMemo(() => {
    if (!versionId) return [];
    return duplicates.filter((duplicate) =>
      duplicate.canonical_version_id === versionId || duplicate.duplicate_version_id === versionId,
    );
  }, [duplicates, versionId]);

  async function submitDecision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!versionId) return;
    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      const payload: ReviewDecisionRequest = {
        reviewer,
        action,
        reason,
        note,
      };
      if (action === 'relabel') {
        payload.new_field = newField;
        payload.new_role = newRole;
      }
      const response = await decideReviewCandidate(versionId, payload, adminKey);
      setSuccess(`Decision recorded: ${response.action} -> ${response.new_state}`);
      const fresh = await getReviewCandidate(versionId);
      setDetail(fresh);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit review decision');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <ReviewCandidateSkeleton />;

  if (error && !detail) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16">
        <div className="rounded-lg border border-red/30 bg-red/5 p-6 text-center">
          <p className="text-red">Failed to load review candidate: {error}</p>
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <p className="text-text-muted">Review candidate not found.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link
        to="/review"
        className="inline-flex items-center gap-1 text-sm text-text-muted no-underline transition-colors hover:text-cyan-accent"
      >
        &larr; Review Queue
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl">
          {detail.profile_name}
        </h1>
        <ReviewStateBadge state={detail.review_state} />
        <span className="rounded-full border border-cyan-accent/30 bg-cyan-glow px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-cyan-accent">
          {detail.eligibility}
        </span>
      </div>
      <p className="mt-2 text-text-secondary">
        {formatSlug(detail.field)} / {formatSlug(detail.role)}
      </p>
      {detail.summary ? (
        <p className="mt-2 max-w-3xl text-sm text-text-secondary">{detail.summary}</p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-3">
        <Link
          to={`/fields/${encodeURIComponent(detail.field)}/${encodeURIComponent(detail.role)}`}
          className="rounded-full border border-border px-4 py-2 text-sm font-medium text-text-secondary no-underline transition-colors hover:border-cyan-accent/30 hover:text-text-primary"
        >
          Open claimed lane
        </Link>
        <Link
          to={`/jd/${encodeURIComponent(detail.field)}/${encodeURIComponent(detail.role)}`}
          className="rounded-full border border-border px-4 py-2 text-sm font-medium text-text-secondary no-underline transition-colors hover:border-cyan-accent/30 hover:text-text-primary"
        >
          Open claimed JD corpus
        </Link>
        {detail.predicted_field || detail.predicted_role ? (
          <Link
            to={`/jd/${encodeURIComponent(detail.predicted_field || detail.field)}/${encodeURIComponent(detail.predicted_role || detail.role)}`}
            className="rounded-full border border-border px-4 py-2 text-sm font-medium text-text-secondary no-underline transition-colors hover:border-cyan-accent/30 hover:text-text-primary"
          >
            Open predicted JD corpus
          </Link>
        ) : null}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Classification Evidence</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Claimed lane</div>
                <div className="mt-2 font-medium text-text-primary">
                  {formatSlug(detail.field)} / {formatSlug(detail.role)}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Predicted lane</div>
                <div className="mt-2 font-medium text-text-primary">
                  {detail.predicted_field || detail.predicted_role
                    ? `${formatSlug(detail.predicted_field || detail.field)} / ${formatSlug(detail.predicted_role || detail.role)}`
                    : '—'}
                </div>
              </div>
              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">JD fit</div>
                <div className="mt-2 font-mono text-lg text-text-primary">{scoreLabel(detail.jd_fit_score)}</div>
              </div>
              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Qualification fit</div>
                <div className="mt-2 font-mono text-lg text-text-primary">{scoreLabel(detail.qualification_fit_score)}</div>
              </div>
              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Work-sample fit</div>
                <div className="mt-2 font-mono text-lg text-text-primary">{scoreLabel(detail.work_sample_fit_score)}</div>
              </div>
              <div className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-text-muted">Manual review</div>
                <div className="mt-2 font-medium text-text-primary">{detail.manual_review_required ? 'Required' : 'Optional'}</div>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Sanitized Artifact</h2>
            <pre className="mt-4 overflow-x-auto whitespace-pre-wrap rounded-xl bg-bg-secondary/70 p-4 font-mono text-xs text-text-secondary">
              {detail.sanitized_content || '—'}
            </pre>
          </section>

          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Runner Contract</h2>
            <pre className="mt-4 overflow-x-auto whitespace-pre-wrap rounded-xl bg-bg-secondary/70 p-4 font-mono text-xs text-text-secondary">
              {JSON.stringify(parsed.contract, null, 2)}
            </pre>
          </section>

          <SourceProvenanceCard
            provenance={parsed.provenance}
            packagingType={detail.profile_packaging_type}
            owner={detail.owner}
            contentHash={detail.content_hash}
            profileSourceUrl={detail.profile_source_url}
          />

          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Duplicate Risk</h2>
            {relatedDuplicates.length === 0 ? (
              <p className="mt-4 text-sm text-text-muted">
                No recorded duplicate group currently includes this candidate.
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                {relatedDuplicates.map((duplicate) => {
                  const isCanonical = duplicate.canonical_version_id === versionId;
                  const counterpartName = isCanonical ? duplicate.duplicate_name : duplicate.canonical_name;
                  const counterpartSource = isCanonical ? duplicate.duplicate_src : duplicate.canonical_src;
                  return (
                    <div key={duplicate.id} className="rounded-xl border border-red/30 bg-red/5 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="font-medium text-text-primary">
                          {duplicate.match_type} · similarity {duplicate.similarity_score.toFixed(2)}
                        </div>
                        <div className="text-xs uppercase tracking-[0.18em] text-red">
                          {duplicate.review_state}
                        </div>
                      </div>
                      <p className="mt-2 text-sm text-text-secondary">
                        This candidate is linked to <span className="font-medium text-text-primary">{counterpartName}</span>.
                      </p>
                      {counterpartSource ? (
                        <p className="mt-2 text-sm text-text-muted">
                          Counterpart source:{' '}
                          <a
                            href={counterpartSource}
                            target="_blank"
                            rel="noreferrer"
                            className="text-cyan-accent no-underline hover:underline"
                          >
                            open source
                          </a>
                        </p>
                      ) : null}
                      {duplicate.note ? (
                        <p className="mt-2 text-sm text-text-muted">{duplicate.note}</p>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Review History</h2>
            {detail.review_history.length === 0 ? (
              <p className="mt-4 text-sm text-text-muted">No review decisions recorded yet.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {detail.review_history.map((item) => (
                  <div key={item.id} className="rounded-xl border border-border bg-bg-secondary/70 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="font-medium text-text-primary">
                        {item.action} · {item.previous_state} → {item.new_state}
                      </div>
                      <div className="text-xs text-text-muted">
                        {item.reviewer} · {item.created_at ? new Date(item.created_at).toLocaleString() : '—'}
                      </div>
                    </div>
                    {item.reason ? (
                      <p className="mt-2 text-sm text-text-secondary">{item.reason}</p>
                    ) : null}
                    {item.note ? (
                      <p className="mt-2 text-sm text-text-muted">{item.note}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="space-y-4">
          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Decision Panel</h2>
            <p className="mt-2 text-sm text-text-muted">
              Every action here is persisted to the review audit trail.
            </p>

            {error ? (
              <div className="mt-4 rounded-lg border border-red/30 bg-red/5 px-4 py-3 text-sm text-red">
                {error}
              </div>
            ) : null}
            {success ? (
              <div className="mt-4 rounded-lg border border-green/30 bg-green/10 px-4 py-3 text-sm text-green">
                {success}
              </div>
            ) : null}

            <form className="mt-4 space-y-4" onSubmit={submitDecision}>
              <label className="block text-sm text-text-secondary">
                <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Reviewer</div>
                <input
                  value={reviewer}
                  onChange={(event) => setReviewer(event.target.value)}
                  className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
                  required
                />
              </label>

              <label className="block text-sm text-text-secondary">
                <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Admin Key</div>
                <input
                  type="password"
                  value={adminKey}
                  onChange={(event) => setAdminKey(event.target.value)}
                  className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
                  placeholder="Required for review actions"
                  required
                />
              </label>

              <label className="block text-sm text-text-secondary">
                <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Action</div>
                <select
                  value={action}
                  onChange={(event) => setAction(event.target.value as ReviewDecisionRequest['action'])}
                  className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
                >
                  <option value="approve">approve</option>
                  <option value="relabel">relabel</option>
                  <option value="reject">reject</option>
                  <option value="send-to-qualification">send-to-qualification</option>
                  <option value="unsupported">unsupported</option>
                </select>
              </label>

              {action === 'relabel' ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block text-sm text-text-secondary">
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">New Field</div>
                    <input
                      value={newField}
                      onChange={(event) => setNewField(event.target.value)}
                      className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
                    />
                  </label>
                  <label className="block text-sm text-text-secondary">
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">New Role</div>
                    <input
                      value={newRole}
                      onChange={(event) => setNewRole(event.target.value)}
                      className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
                    />
                  </label>
                </div>
              ) : null}

              <label className="block text-sm text-text-secondary">
                <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Reason</div>
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={4}
                  className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
                  placeholder="Why are you making this decision?"
                />
              </label>

              <label className="block text-sm text-text-secondary">
                <div className="mb-2 text-xs uppercase tracking-[0.18em] text-text-muted">Reviewer Note</div>
                <textarea
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-text-primary"
                  placeholder="Optional extra note"
                />
              </label>

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-lg bg-cyan-accent px-4 py-2 font-medium text-bg-primary transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? 'Saving…' : 'Record decision'}
              </button>
            </form>
          </section>

          <section className="rounded-2xl border border-border bg-bg-card p-6">
            <h2 className="text-xl font-semibold text-text-primary">Source & Security</h2>
            <div className="mt-4 space-y-3 text-sm text-text-secondary">
              <div>
                <span className="text-text-muted">Owner:</span> {detail.owner || 'Unknown'}
              </div>
              <div>
                <span className="text-text-muted">Source:</span>{' '}
                {detail.profile_source_url?.startsWith('http') ? (
                  <a href={detail.profile_source_url} target="_blank" rel="noreferrer" className="text-cyan-accent no-underline hover:underline">
                    open source
                  </a>
                ) : detail.profile_source_url ? (
                  <span className="text-text-muted">{detail.profile_source_url}</span>
                ) : '—'}
              </div>
              <div>
                <span className="text-text-muted">Packaging:</span> {detail.profile_packaging_type}
              </div>
              <div>
                <span className="text-text-muted">Visibility:</span> {detail.visibility}
              </div>
              <div>
                <span className="text-text-muted">Security findings:</span> {parsed.securityFindings.length + parsed.artifactSecurity.length}
              </div>
            </div>

            {(parsed.securityFindings.length > 0 || parsed.artifactSecurity.length > 0) ? (
              <div className="mt-4 space-y-2 text-sm text-text-secondary">
                {[...parsed.securityFindings, ...parsed.artifactSecurity].map((finding) => (
                  <div key={finding} className="rounded-lg border border-red/30 bg-red/5 px-3 py-2 text-red">
                    {finding}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-text-muted">No security findings recorded.</p>
            )}

            <div className="mt-4">
              <Link
                to="/ops"
                className="text-sm text-text-secondary no-underline hover:text-text-primary hover:underline"
              >
                Back to control room
              </Link>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
