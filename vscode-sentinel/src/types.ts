export type Severity = "critical" | "high" | "medium" | "low";

export type IncidentStatus =
  | "received"
  | "duplicate"
  | "blocked"
  | "investigating"
  | "patching"
  | "verifying"
  | "pr_ready"
  | "escalated"
  | "approved"
  | "rejected"
  | "failed";

export type Decision = "approve" | "reject";

export type PipelineEvent =
  | "IncidentReceived"
  | "TriageCompleted"
  | "InvestigationCompleted"
  | "PatchGenerated"
  | "VerificationCompleted"
  | "ApprovalPackageReady"
  | "IncidentEscalated"
  | "IncidentApproved"
  | "IncidentRejected"
  | "RetryTriggered";

export interface IncidentEnvelope {
  incident_id: string;
  service: string;
  env: string;
  start_time: string;
  signal_type: string;
  signal_payload: Record<string, unknown>;
  runbook_hint?: string | null;
}

export interface InvestigationPacket {
  suspected_release: string;
  affected_endpoints: string[];
  correlated_metrics: Record<string, unknown>;
  log_evidence: string[];
  confidence: number;
  reason: string;
}

export interface PatchProposal {
  repo: string;
  branch: string;
  changed_files: string[];
  diff_summary: string;
  hypothesis: string;
  risk_level: string;
  patch_text: string;
}

export interface VerificationReport {
  test_results: Record<string, string>;
  canary_replay_result: Record<string, unknown>;
  regression_flags: string[];
  pass_fail: boolean;
}

export interface ApprovalPackage {
  pr_url: string;
  rca_summary: string;
  evidence_links: Record<string, string>;
  rollback_steps: string[];
  telemetry_snapshot: Record<string, unknown>;
}

export interface EventLog {
  event: PipelineEvent;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface IncidentRecord {
  incident: IncidentEnvelope;
  status: IncidentStatus;
  stage: string;
  confidence: number;
  last_error?: string | null;
  linked_artifacts: Record<string, unknown>;
  events: EventLog[];
  investigation?: InvestigationPacket | null;
  patch?: PatchProposal | null;
  verification?: VerificationReport | null;
  approval_package?: ApprovalPackage | null;
  patch_attempts: number;
  created_at: string;
  updated_at: string;
  started_at: string;
  finished_at?: string | null;
}

export interface CreateIncidentResponse {
  incident_id: string;
  status: IncidentStatus;
  pr_url?: string;
}

export interface ApproveIncidentRequest {
  approved_by: string;
  decision: Decision;
  notes?: string;
}

export interface ApproveIncidentResponse {
  state_transition: string;
}

export interface RetryIncidentRequest {
  stage: string;
}

export interface RetryIncidentResponse {
  incident_id: string;
  status: IncidentStatus;
  stage: string;
}

export interface HealthResponse {
  status: string;
}

export interface IncidentListEntry {
  incidentId: string;
  record?: IncidentRecord;
  isStale: boolean;
  lastSeenAt: number;
  severity: Severity;
  staleReason?: string;
}

export type BackendHealthState = "healthy" | "degraded";

export const WATCHLIST_KEY = "sentinel.watchlistIds";

export const ACTIVE_STATUSES: IncidentStatus[] = [
  "received",
  "investigating",
  "patching",
  "verifying",
  "pr_ready"
];

export const STATUS_GROUP_ORDER: IncidentStatus[] = [
  "investigating",
  "patching",
  "verifying",
  "pr_ready",
  "escalated",
  "blocked",
  "duplicate",
  "approved",
  "rejected",
  "failed",
  "received"
];
