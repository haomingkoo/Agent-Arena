import { useState } from 'react';
import { scanContent, scoreContent, type ScanResult, type ScoreResult } from '../lib/api';
import Skeleton from '../components/Skeleton';
import DimensionBars from '../components/DimensionBars';

const EXAMPLE_SKILL = `---
name: code-reviewer
description: Thorough code review with security and performance focus
triggers:
  - "review this code"
  - "code review"
---

# Code Reviewer

Review code changes with focus on:

1. **Security**: Check for injection, XSS, hardcoded secrets
2. **Performance**: Identify N+1 queries, unnecessary allocations
3. **Correctness**: Logic errors, edge cases, null handling
4. **Style**: Naming conventions, function length, DRY violations

For each issue found, provide:
- Severity (critical/warning/nit)
- Location (file:line)
- Suggested fix with code snippet
`;

export default function Scanner() {
  const [content, setContent] = useState('');
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scoreResult, setScoreResult] = useState<ScoreResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    if (!content.trim()) return;
    setLoading(true);
    setError('');
    setScanResult(null);
    setScoreResult(null);

    try {
      const [scan, score] = await Promise.all([
        scanContent(content),
        scoreContent(content),
      ]);
      setScanResult(scan);
      setScoreResult(score);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold sm:text-4xl">
          <span className="text-cyan-accent">Artifact</span> Scanner
        </h1>
        <p className="mt-2 text-text-secondary">
          Paste a prompt artifact such as a `SKILL.md` bundle to get an instant quality score and safety scan.
        </p>
      </div>

      {/* Input */}
      <div className="mb-6">
        <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <label className="text-sm font-medium text-text-secondary">
            Artifact Content
          </label>
          <button
            onClick={() => setContent(EXAMPLE_SKILL)}
            className="text-xs text-cyan-accent hover:text-cyan-accent/80 transition-colors cursor-pointer"
          >
            Load example
          </button>
        </div>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Paste your prompt artifact content here..."
          aria-busy={loading}
          className="w-full h-64 rounded-lg border border-border bg-bg-card p-4 font-mono text-sm text-text-primary placeholder:text-text-muted focus:border-cyan-accent focus:outline-none resize-y"
        />
        <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-xs text-text-muted">
            {content.length > 0 ? `${content.split('\n').length} lines, ~${Math.round(content.length / 4)} tokens` : ''}
          </span>
          <button
            onClick={handleAnalyze}
            disabled={loading || !content.trim()}
            className="rounded-lg bg-cyan-accent px-6 py-2 font-medium text-bg-primary transition-opacity hover:opacity-90 disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
          >
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red/30 bg-red/5 p-4 text-red text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {loading && (
        <div className="grid gap-6 lg:grid-cols-2">
          {Array.from({ length: 2 }).map((_, index) => (
            <section key={index} className="rounded-lg border border-border bg-bg-card p-6">
              <Skeleton className="h-6 w-36" />
              <Skeleton className="mt-6 h-12 w-40" />
              <div className="mt-6 space-y-4">
                {Array.from({ length: 4 }).map((__, rowIndex) => (
                  <div key={rowIndex}>
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-4 w-10" />
                    </div>
                    <Skeleton className="h-5 w-full rounded-full" />
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {!loading && (scanResult || scoreResult) && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Score */}
          {scoreResult && (
            <section className="rounded-lg border border-border bg-bg-card p-6">
              <h2 className="mb-4 text-lg font-semibold">Quality Score</h2>
              <div className="mb-4 flex items-center gap-4">
                <div className="text-4xl font-bold font-mono text-cyan-accent">
                  {scoreResult.grade}
                </div>
                <div>
                  <div className="font-mono text-lg">{scoreResult.overall.toFixed(3)}</div>
                  <div className="text-xs text-text-muted">
                    {scoreResult.name} &middot; {scoreResult.confidence.toFixed(0)}% confidence
                  </div>
                </div>
              </div>

              <DimensionBars dimensions={scoreResult.dimensions} />

              {scoreResult.strengths.length > 0 && (
                <div className="mt-4">
                  <h3 className="mb-1 text-sm font-semibold text-text-secondary">Strengths</h3>
                  {scoreResult.strengths.map((s, i) => (
                    <div key={i} className="text-sm text-green">{s}</div>
                  ))}
                </div>
              )}

              {scoreResult.flags.length > 0 && (
                <div className="mt-3">
                  <h3 className="mb-1 text-sm font-semibold text-text-secondary">Flags</h3>
                  {scoreResult.flags.map((f, i) => (
                    <div key={i} className="text-sm text-red">{f}</div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Safety Scan */}
          {scanResult && (
            <section className="rounded-lg border border-border bg-bg-card p-6">
              <h2 className="mb-4 text-lg font-semibold">Safety Scan</h2>
              <div className="mb-4 flex items-center gap-3">
                <div className={`text-3xl ${scanResult.safe ? 'text-green' : 'text-red'}`}>
                  {scanResult.safe ? 'SAFE' : 'UNSAFE'}
                </div>
                <span className="text-sm text-text-muted">
                  {scanResult.threat_count} threat{scanResult.threat_count !== 1 ? 's' : ''} detected
                </span>
              </div>

              {scanResult.threats.length > 0 ? (
                <div className="space-y-2">
                  {scanResult.threats.map((t, i) => (
                    <div key={i} className="flex items-start gap-2 rounded-md bg-red/5 px-3 py-2 text-sm text-red">
                      <span className="shrink-0 mt-0.5">!</span>
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-text-secondary">
                  No prompt injection, data exfiltration, malicious code, or social engineering patterns detected.
                </p>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
