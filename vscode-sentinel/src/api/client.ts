import * as vscode from 'vscode';
import * as http from 'http';

// Configuration keys
const CONFIG_SECTION = 'sentinel';
const CONFIG_URL = 'serverUrl';

export interface IncidentEnvelope {
  incident_id: string;
  service: string;
  env: string;
  start_time: string;
  signal_type: string;
  signal_payload: Record<string, any>;
  runbook_hint?: string;
  fingerprint?: string;
}

export interface InvestigationPacket {
  suspected_release: string;
  affected_endpoints: string[];
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
  regression_flags: string[];
  pass_fail: boolean;
}

export interface ApprovalPackage {
  pr_url: string;
  rca_summary: string;
  evidence_links: Record<string, string>;
  rollback_steps: string[];
}

export interface IncidentRecord {
  incident: IncidentEnvelope;
  status: string;
  stage: string;
  confidence: number;
  investigation?: InvestigationPacket;
  patch?: PatchProposal;
  verification?: VerificationReport;
  approval_package?: ApprovalPackage;
  patch_attempts: number;
  created_at: string;
  updated_at: string;
}

export class SentinelClient {
  private get baseUrl(): string {
    const config = vscode.workspace.getConfiguration(CONFIG_SECTION);
    let url = config.get<string>(CONFIG_URL, 'http://127.0.0.1:8000');
    return url.endsWith('/') ? url.slice(0, -1) : url;
  }

  private async request<T>(method: string, path: string, body?: any): Promise<T> {
    const url = `${this.baseUrl}${path}`;

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Sentinel API Error (${response.status}): ${text}`);
      }

      return await response.json() as T;
    } catch (error) {
      console.error(`Sentinel API Request Failed: ${error}`);
      throw error;
    }
  }

  async healthCheck(): Promise<{ status: string }> {
    return this.request('GET', '/health');
  }

  async createIncident(payload: any): Promise<{ incident_id: string; status: string }> {
    return this.request('POST', '/api/v1/incidents', payload);
  }

  async getIncident(incidentId: string): Promise<IncidentRecord> {
    return this.request('GET', `/api/v1/incidents/${incidentId}`);
  }

  async listIncidents(): Promise<IncidentRecord[]> {
    const response = await this.request<{ incidents: IncidentRecord[] }>('GET', '/api/v1/incidents');
    return response.incidents;
  }

  async approveIncident(incidentId: string, payload: { approved_by: string; decision: string; notes?: string }): Promise<{ state_transition: string }> {
    return this.request('POST', `/api/v1/incidents/${incidentId}/approve`, payload);
  }

  async retryIncident(incidentId: string, stage: string): Promise<{ incident_id: string; status: string }> {
    return this.request('POST', `/api/v1/incidents/${incidentId}/retry`, { stage });
  }

  async triggerSynthetic(): Promise<{ incident_id: string; status: string }> {
    return this.request('POST', '/api/v1/incidents/synthetic/5xx', {});
  }
}
