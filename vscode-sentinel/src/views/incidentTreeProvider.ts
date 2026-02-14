import * as vscode from 'vscode';
import { SentinelClient, IncidentRecord } from '../api/client';

export class IncidentTreeProvider implements vscode.TreeDataProvider<IncidentTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<IncidentTreeItem | undefined | null | void> = new vscode.EventEmitter<IncidentTreeItem | undefined | null | void>();
  readonly onDidChangeTreeData: vscode.Event<IncidentTreeItem | undefined | null | void> = this._onDidChangeTreeData.event;
  private client: SentinelClient;
  private autoRefreshInterval: NodeJS.Timeout | undefined;

  constructor(client: SentinelClient) {
    this.client = client;
    this.startAutoRefresh();
  }

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: IncidentTreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: IncidentTreeItem): Promise<IncidentTreeItem[]> {
    if (element) {
      return []; // No nesting for now, flat list
    }

    try {
      // In a real app we'd have a list endpoint, but here we might need to rely on what we know or simulating a list
      // API doesn't have a specific "list all" endpoint documented in app.py, only create/get/approve/retry
      // Wait, app.py DOES NOT have a list incidents endpoint?
      // Checking app.py... 
      // It has create, get, approve, retry, synthetic.
      // There is no endpoint to list incidents! 
      // I need to add one to the backend or simulate it. 
      // For now, I will add a list endpoint to the backend in app.py.
      // Or I can store the IDs in the extension state if I create them from there, but that's fragile.
      // The "engine" probably has a registry. 

      // Let's assume for now I will add GET /api/v1/incidents to app.py
      // I'll update the backend in a separate step.

      const incidents = await this.client.listIncidents(); // I need to add this to client too
      return incidents
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()) // Newest first
        .map(incident => new IncidentTreeItem(incident));
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to fetch incidents: ${error}`);
      return [];
    }
  }

  private startAutoRefresh() {
    const config = vscode.workspace.getConfiguration('sentinel');
    const interval = config.get<number>('pollIntervalMs', 3000);
    const enabled = config.get<boolean>('autoRefresh', true);

    if (enabled) {
      this.autoRefreshInterval = setInterval(() => this.refresh(), interval);
    }
  }

  dispose() {
    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval);
    }
  }
}

export class IncidentTreeItem extends vscode.TreeItem {
  constructor(public readonly incident: IncidentRecord) {
    super(incident.incident.incident_id, vscode.TreeItemCollapsibleState.None);
    this.tooltip = `${incident.incident.service} - ${incident.status}`;
    this.description = incident.status;

    this.command = {
      command: 'sentinel.viewIncident',
      title: 'View Details',
      arguments: [incident]
    };

    this.iconPath = this.getIcon(incident.status);
  }

  private getIcon(status: string): vscode.ThemeIcon {
    switch (status) {
      case 'approved': return new vscode.ThemeIcon('check', new vscode.ThemeColor('testing.iconPassed'));
      case 'rejected': return new vscode.ThemeIcon('error', new vscode.ThemeColor('testing.iconFailed'));
      case 'pr_ready': return new vscode.ThemeIcon('git-pull-request', new vscode.ThemeColor('charts.blue'));
      case 'escalated': return new vscode.ThemeIcon('bell', new vscode.ThemeColor('testing.iconFailed'));
      case 'verifying': return new vscode.ThemeIcon('beaker', new vscode.ThemeColor('charts.yellow'));
      case 'patching': return new vscode.ThemeIcon('tools');
      case 'investigating': return new vscode.ThemeIcon('search');
      default: return new vscode.ThemeIcon('circle-outline');
    }
  }
}
