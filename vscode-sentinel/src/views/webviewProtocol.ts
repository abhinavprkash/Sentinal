import { BackendHealthState, IncidentListEntry } from "../types";

export const WEBVIEW_PROTOCOL_VERSION = 1 as const;

export type ExtensionToWebviewMessage =
  | {
      protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION;
      type: "renderIncident";
      payload: { entry?: IncidentListEntry; processingSeconds?: number };
    }
  | {
      protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION;
      type: "setConnectionState";
      payload: { health: BackendHealthState };
    }
  | {
      protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION;
      type: "setBusyState";
      payload: { busy: boolean; action?: string };
    }
  | {
      protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION;
      type: "showActionResult";
      payload: { kind: "info" | "error"; message: string };
    };

export type WebviewToExtensionMessage =
  | { protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION; type: "approve"; incidentId: string; notes?: string }
  | { protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION; type: "reject"; incidentId: string; notes?: string }
  | { protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION; type: "retry"; incidentId: string; stage: string }
  | { protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION; type: "refresh"; incidentId: string }
  | { protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION; type: "openDiff"; incidentId: string }
  | { protocolVersion: typeof WEBVIEW_PROTOCOL_VERSION; type: "openPrLink"; url: string };
