const BASE = '/api';

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

async function sendJson<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  return fetchJson<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    body: JSON.stringify(body),
    ...init,
  });
}

export interface LeaderboardEntry {
  skill_name: string;
  timestamp: string;
  paired: boolean;
  jobs_run: number;
  jobs_passed: number;
  avg_overall: number;
  avg_baseline?: number;
  avg_upgrade?: number;
  total_tokens: number;
  results: PairedJobResult[] | JobResult[];
}

export interface JobResult {
  job_id: string;
  skill_name: string;
  passed: boolean;
  overall: number;
  correctness: number;
  safety: number;
  completeness: number;
  quality: number;
  verdict: string;
  runtime_ms: number;
  input_tokens: number;
  output_tokens: number;
  error: string;
}

export interface PairedJobResult {
  job_id: string;
  skill_name: string;
  upgrade: number;
  skill: JobResult;
  baseline: JobResult;
}

export interface SkillDetail {
  name: string;
  benchmark?: {
    avg_overall: number;
    avg_baseline?: number;
    avg_upgrade?: number;
    jobs_run: number;
    jobs_passed: number;
    paired: boolean;
    timestamp: string;
    results: PairedJobResult[] | JobResult[];
  };
  certification?: {
    tier: string;
    overall_score: number;
    confidence: number;
    dimensions: Record<string, number>;
    flags: string[];
    strengths: string[];
    llm_reasoning: string;
    cert_date: string;
  };
  source?: {
    repo: string;
    url: string;
    stars: number;
    lines: number;
    tokens: number;
  };
}

export interface ScanResult {
  safe: boolean;
  threats: string[];
  threat_count: number;
}

export interface ScoreResult {
  name: string;
  grade: string;
  overall: number;
  confidence: number;
  dimensions: Record<string, number>;
  flags: string[];
  strengths: string[];
  line_count: number;
  token_estimate: number;
}

export interface Stats {
  certification: {
    total_skills: number;
    gold: number;
    silver: number;
    bronze: number;
    uncertified: number;
    avg_score: number;
    avg_confidence: number;
  };
  benchmark: {
    skills_benchmarked: number;
    avg_score: number;
    paired_count: number;
    avg_upgrade?: number;
    best_upgrade?: number;
  };
}

export async function getLeaderboard(): Promise<{ skills: LeaderboardEntry[]; count: number }> {
  return fetchJson('/leaderboard');
}

export async function getSkillDetail(name: string): Promise<SkillDetail> {
  return fetchJson(`/skill/${encodeURIComponent(name)}`);
}

export async function getStats(): Promise<Stats> {
  return fetchJson('/stats');
}

export async function scanContent(content: string): Promise<ScanResult> {
  return fetchJson('/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
}

export async function scoreContent(content: string): Promise<ScoreResult> {
  return fetchJson('/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
}

/* ── Tournament / Category types ────────────────────────────── */

export interface Category {
  slug: string;
  display_name: string;
  description: string;
  skill_count: number;
  task_count: number;
  active: boolean;
}

export interface TournamentSummary {
  id: string;
  category: string;
  week: string;
  status: string;
  num_skills: number;
  baseline_avg: number;
  started_at?: string;
  completed_at: string;
  total_cost_usd: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
  field?: string;
  role?: string;
  runtime_class?: string;
  task_pack_version?: string;
  tournament_type?: string;
}

export interface CategoryLeaderboardRow {
  skill_id: string;
  skill_name: string;
  mu: number;
  rd: number;
  tournaments_played: number;
}

export interface TournamentEntryDetail {
  id: string;
  skill_id: string;
  skill_name: string;
  rank: number;
  avg_score: number;
  pass_rate: number;
  rating_before: number;
  rating_after: number;
}

export interface RatingPoint {
  week: string;
  mu: number;
  rd: number;
  rank: number;
  avg_score: number;
}

export interface CoachingEntry {
  tournament_week: string;
  current_rank: number;
  recommendations_json: string;
  summary: string;
}

export interface CategoryDetailResponse {
  category: Category;
  skills: Array<{
    id: string;
    name: string;
    overall_score: number;
  }>;
  leaderboard: CategoryLeaderboardRow[];
  recent_tournaments: TournamentSummary[];
}

export interface CategoryLeaderboardResponse {
  category: string;
  leaderboard: CategoryLeaderboardRow[];
}

export interface TournamentDetailResponse {
  tournament: TournamentSummary & {
    entries?: TournamentEntryDetail[];
  };
  entries: TournamentEntryDetail[];
}

export interface SkillCoachingResponse {
  skill_id: string;
  coaching: CoachingEntry[];
}

export interface RatingHistoryResponse {
  skill_id: string;
  category: string;
  history: RatingPoint[];
}

/* ── Tournament / Category fetchers ─────────────────────────── */

export async function getCategories(): Promise<{ categories: Category[]; count: number }> {
  return fetchJson('/categories');
}

export async function getCategoryDetail(slug: string): Promise<CategoryDetailResponse> {
  return fetchJson(`/categories/${encodeURIComponent(slug)}`);
}

export async function getTournaments(category?: string): Promise<{ tournaments: TournamentSummary[] }> {
  const params = category ? `?category=${encodeURIComponent(category)}` : '';
  return fetchJson(`/tournaments${params}`);
}

export async function getTournamentDetail(id: string): Promise<TournamentDetailResponse> {
  return fetchJson(`/tournaments/${encodeURIComponent(id)}`);
}

export async function getCategoryLeaderboard(category: string): Promise<CategoryLeaderboardResponse> {
  return fetchJson(`/leaderboard/${encodeURIComponent(category)}`);
}

export async function getSkillCoaching(skillId: string): Promise<SkillCoachingResponse> {
  return fetchJson(`/coaching/${encodeURIComponent(skillId)}`);
}

export async function getRatingHistory(skillId: string, category: string): Promise<RatingHistoryResponse> {
  return fetchJson(`/skill/${encodeURIComponent(skillId)}/rating-history?category=${encodeURIComponent(category)}`);
}

/* ── Agent-native types ─────────────────────────────────────────── */

export interface AgentRoleSummary {
  role: string;
  agent_count: number;
  runtime_class?: string;
  task_pack_version?: string;
  tournament_type?: string;
}

export interface AgentFieldSummary {
  field: string;
  roles: AgentRoleSummary[];
  total_agents: number;
}

export interface AgentFieldsResponse {
  fields: AgentFieldSummary[];
  count: number;
}

export interface AgentLeaderboardEntry {
  version_id: string;
  mu: number;
  rd: number;
  sigma: number;
  tournaments_played: number;
  last_tournament_week: string;
  agent_name: string;
  field: string;
  role: string;
  owner: string;
  source_url: string;
  version_label: string;
  content_hash: string;
}

export interface AgentLeaderboardResponse {
  field: string;
  role: string;
  runtime_class?: string;
  task_pack_version?: string;
  tournament_type?: string;
  leaderboard: AgentLeaderboardEntry[];
  count: number;
}

export interface AgentRatingDetail {
  mu: number;
  rd: number;
  sigma: number;
  tournaments_played: number;
  last_tournament_week: string;
}

export interface AgentTournamentEntry {
  tournament_id: string;
  rank: number;
  avg_score: number;
  pass_rate: number;
  total_tokens: number;
  rating_before: number;
  rating_after: number;
  week: string;
  category: string;
  runtime_class?: string;
  task_pack_version?: string;
  tournament_type?: string;
}

export interface AgentTraceSummary {
  id: string;
  tournament_id: string;
  tournament_run_id: string;
  task_id: string;
  trace_kind: string;
  status: string;
  exec_provider: string;
  judge_provider: string;
  total_cost_usd: number;
  runtime_ms: number;
  created_at: string;
}

export interface AgentVersionDetail {
  id: string;
  profile_id: string;
  version_label: string;
  source_commit: string;
  content_hash: string;
  packaging_type: string;
  provenance_json: string;
  artifact_id: string;
  runner_contract_json: string;
  eligibility: string;
  ineligibility_reason: string;
  security_findings_json: string;
  created_at: string;
  profile_name: string;
  field: string;
  role: string;
  summary: string;
  owner: string;
  profile_source_url: string;
  visibility: string;
  license: string;
  runtime_class?: string;
  task_pack_version?: string;
  tournament_type?: string;
  rating: AgentRatingDetail | null;
  rating_history: RatingPoint[];
  tournament_entries: AgentTournamentEntry[];
  recent_traces: AgentTraceSummary[];
}

export interface TraceDetail {
  id: string;
  agent_version_id: string;
  field: string;
  role: string;
  tournament_id: string;
  tournament_run_id: string;
  task_id: string;
  trace_kind: string;
  status: string;
  exec_provider: string;
  judge_provider: string;
  final_output: string;
  error: string;
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
  runtime_ms: number;
  prompt_json: string;
  tool_calls_json: string;
  tool_outputs_json: string;
  judge_prompt: string;
  judge_output: string;
  metadata_json: string;
  created_at: string;
  runtime_class?: string;
  task_pack_version?: string;
  tournament_type?: string;
}

export interface TraceDetailResponse {
  trace: TraceDetail;
}

export interface ReviewQueueCandidate {
  version_id: string;
  version_label: string;
  eligibility: string;
  review_state: string;
  predicted_field: string;
  predicted_role: string;
  jd_fit_score: number;
  qualification_fit_score: number;
  work_sample_fit_score: number;
  manual_review_required: number;
  reviewed_by: string;
  reviewed_at: string;
  ineligibility_reason: string;
  security_findings_json: string;
  created_at: string;
  profile_id: string;
  profile_name: string;
  field: string;
  role: string;
  summary: string;
  owner: string;
  source_url: string;
  packaging_type: string;
  visibility: string;
}

export interface ReviewQueueResponse {
  candidates: ReviewQueueCandidate[];
  count: number;
}

export interface ReviewDecisionRecord {
  id: string;
  version_id: string;
  reviewer: string;
  action: string;
  previous_state: string;
  new_state: string;
  previous_role: string;
  new_role: string;
  previous_field: string;
  new_field: string;
  reason: string;
  note: string;
  created_at: string;
}

export interface ReviewCandidateDetail {
  id: string;
  profile_id: string;
  version_label: string;
  source_commit: string;
  content_hash: string;
  packaging_type: string;
  provenance_json: string;
  artifact_id: string;
  runner_contract_json: string;
  eligibility: string;
  ineligibility_reason: string;
  security_findings_json: string;
  created_at: string;
  review_state: string;
  predicted_field: string;
  predicted_role: string;
  jd_fit_score: number;
  qualification_fit_score: number;
  work_sample_fit_score: number;
  manual_review_required: number;
  reviewed_by: string;
  reviewed_at: string;
  profile_name: string;
  field: string;
  role: string;
  summary: string;
  owner: string;
  profile_source_url: string;
  profile_packaging_type: string;
  visibility: string;
  sanitized_content: string;
  artifact_security: string;
  review_history: ReviewDecisionRecord[];
}

export interface ReviewDecisionResponse {
  decision_id: string;
  new_state: string;
  action: string;
}

export interface ReviewDecisionRequest {
  reviewer: string;
  action: 'approve' | 'relabel' | 'reject' | 'send-to-qualification' | 'unsupported';
  reason?: string;
  note?: string;
  new_field?: string;
  new_role?: string;
}

export interface JDCorpusVersion {
  id: string;
  field: string;
  role: string;
  version_label: string;
  posting_count: number;
  company_count: number;
  source_mix_json: string;
  responsibilities_summary_json: string;
  tools_summary_json: string;
  skills_summary_json: string;
  created_at: string;
}

export interface JDCorpusStats {
  total: number;
  companies: number;
  sources: number;
}

export interface JDCorpusResponse {
  field: string;
  role: string;
  latest_version: JDCorpusVersion | null;
  stats: JDCorpusStats;
}

export interface JDPosting {
  id: string;
  source_ats: string;
  source_board_id: string;
  company_name: string;
  company_size_bucket: string;
  title: string;
  normalized_role: string;
  field: string;
  role: string;
  location: string;
  department: string;
  content: string;
  content_hash: string;
  responsibilities_json: string;
  tools_json: string;
  skills_json: string;
  posted_at: string;
  expires_at: string;
  corpus_version: string;
  created_at: string;
  updated_at: string;
}

export interface JDPostingsResponse {
  postings: JDPosting[];
  count: number;
}

export interface CandidateLead {
  id: string;
  source_type: string;
  source_url: string;
  title: string;
  description: string;
  outbound_links_json: string;
  extracted_artifact_links_json: string;
  mention_count: number;
  signal_strength: number;
  discovered_at: string;
  review_state: string;
  resolution_state: string;
  resolved_artifact_url: string;
  resolved_version_id: string;
  resolver_note: string;
  content_hash: string;
  created_at: string;
  updated_at: string;
}

export interface CandidateLeadsResponse {
  leads: CandidateLead[];
  count: number;
}

export interface LeadStats {
  total: number;
  unresolved: number;
  resolved: number;
  no_artifact: number;
  dead_link: number;
}

export interface DuplicateGroup {
  id: string;
  canonical_version_id: string;
  duplicate_version_id: string;
  similarity_score: number;
  match_type: string;
  review_state: string;
  note: string;
  created_at: string;
  canonical_name: string;
  canonical_src: string;
  duplicate_name: string;
  duplicate_src: string;
}

export interface DuplicateGroupsResponse {
  duplicates: DuplicateGroup[];
  count: number;
}

/* ── Agent-native fetchers ─────────────────────────────────────── */

export async function getFields(): Promise<AgentFieldsResponse> {
  return fetchJson('/agents/fields');
}

export async function getFieldRoleLeaderboard(
  field: string,
  role: string,
): Promise<AgentLeaderboardResponse> {
  return fetchJson(`/agents/leaderboard/${encodeURIComponent(field)}/${encodeURIComponent(role)}`);
}

export async function getAgentDetail(versionId: string): Promise<AgentVersionDetail> {
  return fetchJson(`/agents/${encodeURIComponent(versionId)}`);
}

export async function getTraceDetail(traceId: string): Promise<TraceDetailResponse> {
  return fetchJson(`/traces/${encodeURIComponent(traceId)}`);
}

export async function getReviewQueue(params?: {
  reviewState?: string;
  field?: string;
  role?: string;
  limit?: number;
}): Promise<ReviewQueueResponse> {
  const search = new URLSearchParams();
  if (params?.reviewState) search.set('review_state', params.reviewState);
  if (params?.field) search.set('field', params.field);
  if (params?.role) search.set('role', params.role);
  if (params?.limit) search.set('limit', String(params.limit));
  const query = search.toString();
  return fetchJson(`/review/queue${query ? `?${query}` : ''}`);
}

export async function getReviewCandidate(versionId: string): Promise<ReviewCandidateDetail> {
  return fetchJson(`/review/candidate/${encodeURIComponent(versionId)}`);
}

export async function decideReviewCandidate(
  versionId: string,
  payload: ReviewDecisionRequest,
  adminKey: string,
): Promise<ReviewDecisionResponse> {
  return sendJson(`/review/candidate/${encodeURIComponent(versionId)}/decide`, payload, {
    headers: { 'Authorization': `Bearer ${adminKey}` },
  });
}

export async function getJDCorpusDetail(field: string, role: string): Promise<JDCorpusResponse> {
  return fetchJson(`/jd/corpus/${encodeURIComponent(field)}/${encodeURIComponent(role)}`);
}

export async function getJDPostings(params?: {
  field?: string;
  role?: string;
  sourceAts?: string;
  limit?: number;
}): Promise<JDPostingsResponse> {
  const search = new URLSearchParams();
  if (params?.field) search.set('field', params.field);
  if (params?.role) search.set('role', params.role);
  if (params?.sourceAts) search.set('source_ats', params.sourceAts);
  if (params?.limit) search.set('limit', String(params.limit));
  const query = search.toString();
  return fetchJson(`/jd/postings${query ? `?${query}` : ''}`);
}

export async function getCandidateLeads(params?: {
  sourceType?: string;
  reviewState?: string;
  resolutionState?: string;
  limit?: number;
}): Promise<CandidateLeadsResponse> {
  const search = new URLSearchParams();
  if (params?.sourceType) search.set('source_type', params.sourceType);
  if (params?.reviewState) search.set('review_state', params.reviewState);
  if (params?.resolutionState) search.set('resolution_state', params.resolutionState);
  if (params?.limit) search.set('limit', String(params.limit));
  const query = search.toString();
  return fetchJson(`/leads${query ? `?${query}` : ''}`);
}

export async function getLeadStats(): Promise<LeadStats> {
  return fetchJson('/leads/stats');
}

export async function getDuplicateGroups(params?: {
  reviewState?: string;
  limit?: number;
}): Promise<DuplicateGroupsResponse> {
  const search = new URLSearchParams();
  if (params?.reviewState) search.set('review_state', params.reviewState);
  if (params?.limit) search.set('limit', String(params.limit));
  const query = search.toString();
  return fetchJson(`/duplicates${query ? `?${query}` : ''}`);
}
