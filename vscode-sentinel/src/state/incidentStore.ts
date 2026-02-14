import {
  ACTIVE_STATUSES,
  IncidentListEntry,
  IncidentRecord,
  IncidentStatus,
  STATUS_GROUP_ORDER,
  Severity,
  WATCHLIST_KEY
} from "../types";

export interface MementoLike {
  get<T>(key: string, defaultValue: T): T;
  update(key: string, value: unknown): Thenable<void>;
}

export class IncidentStore {
  private readonly workspaceState: MementoLike;
  private readonly incidents = new Map<string, IncidentListEntry>();

  constructor(workspaceState: MementoLike) {
    this.workspaceState = workspaceState;
  }

  async loadWatchlist(): Promise<string[]> {
    const ids = this.workspaceState.get<string[]>(WATCHLIST_KEY, []);
    for (const id of ids) {
      if (!this.incidents.has(id)) {
        this.incidents.set(id, {
          incidentId: id,
          isStale: false,
          severity: "low",
          lastSeenAt: 0
        });
      }
    }
    return ids;
  }

  getWatchlist(): string[] {
    return Array.from(this.incidents.keys()).sort();
  }

  async addWatchId(incidentId: string): Promise<void> {
    const normalized = incidentId.trim();
    if (!normalized) {
      return;
    }
    if (!this.incidents.has(normalized)) {
      this.incidents.set(normalized, {
        incidentId: normalized,
        isStale: false,
        severity: "low",
        lastSeenAt: 0
      });
    }
    await this.saveWatchlist();
  }

  async remove(incidentId: string): Promise<void> {
    this.incidents.delete(incidentId);
    await this.saveWatchlist();
  }

  async clearStale(incidentId: string): Promise<void> {
    const entry = this.incidents.get(incidentId);
    if (!entry) {
      return;
    }
    entry.isStale = false;
    entry.staleReason = undefined;
    await this.saveWatchlist();
  }

  upsertIncident(record: IncidentRecord): IncidentListEntry {
    const severity = deriveSeverity(record);
    const entry: IncidentListEntry = {
      incidentId: record.incident.incident_id,
      record,
      isStale: false,
      staleReason: undefined,
      lastSeenAt: Date.now(),
      severity
    };
    this.incidents.set(record.incident.incident_id, entry);
    return entry;
  }

  markStale(incidentId: string, reason = "Not found in backend state."): void {
    const existing = this.incidents.get(incidentId);
    this.incidents.set(incidentId, {
      incidentId,
      record: existing?.record,
      severity: existing?.severity ?? "low",
      isStale: true,
      staleReason: reason,
      lastSeenAt: existing?.lastSeenAt ?? Date.now()
    });
  }

  getIncident(incidentId: string): IncidentListEntry | undefined {
    return this.incidents.get(incidentId);
  }

  listAll(): IncidentListEntry[] {
    return Array.from(this.incidents.values()).sort(sortIncidentEntries);
  }

  listByGroup(): Array<{ status: IncidentStatus; entries: IncidentListEntry[] }> {
    const grouped = new Map<IncidentStatus, IncidentListEntry[]>();
    for (const status of STATUS_GROUP_ORDER) {
      grouped.set(status, []);
    }
    for (const entry of this.incidents.values()) {
      const status = entry.record?.status ?? "received";
      if (!grouped.has(status)) {
        grouped.set(status, []);
      }
      grouped.get(status)?.push(entry);
    }

    const result: Array<{ status: IncidentStatus; entries: IncidentListEntry[] }> = [];
    for (const status of STATUS_GROUP_ORDER) {
      const entries = (grouped.get(status) ?? []).sort(sortIncidentEntries);
      if (entries.length > 0) {
        result.push({ status, entries });
      }
    }
    return result;
  }

  activeCount(): number {
    return this.listAll().filter((entry) => entry.record && ACTIVE_STATUSES.includes(entry.record.status)).length;
  }

  hasFailures(): boolean {
    return this.listAll().some((entry) => entry.record && ["escalated", "failed"].includes(entry.record.status));
  }

  async saveWatchlist(): Promise<void> {
    await this.workspaceState.update(WATCHLIST_KEY, this.getWatchlist());
  }
}

function sortIncidentEntries(a: IncidentListEntry, b: IncidentListEntry): number {
  return b.lastSeenAt - a.lastSeenAt || a.incidentId.localeCompare(b.incidentId);
}

export function deriveSeverity(record: IncidentRecord): Severity {
  const triage = [...record.events]
    .reverse()
    .find((event) => event.event === "TriageCompleted" && typeof event.payload?.severity === "string");
  const fromEvent = triage?.payload?.severity;
  if (fromEvent === "critical" || fromEvent === "high" || fromEvent === "medium" || fromEvent === "low") {
    return fromEvent;
  }

  const errorRateRaw = record.incident.signal_payload?.error_rate;
  const errorRate = typeof errorRateRaw === "number" ? errorRateRaw : Number(errorRateRaw ?? 0);
  if (Number.isFinite(errorRate)) {
    if (errorRate >= 0.2) {
      return "critical";
    }
    if (errorRate >= 0.12) {
      return "high";
    }
    if (errorRate >= 0.05) {
      return "medium";
    }
  }
  return "low";
}
