import * as vscode from 'vscode';
import { SentinelClient } from './api/client';

export class SentinelStatusBar implements vscode.Disposable {
  private statusBarItem: vscode.StatusBarItem;
  private client: SentinelClient;
  private pollInterval: NodeJS.Timeout | undefined;

  constructor(client: SentinelClient) {
    this.client = client;
    this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.statusBarItem.command = 'sentinel.refresh';
    this.startPolling();
  }

  private startPolling() {
    this.update();
    const config = vscode.workspace.getConfiguration('sentinel');
    const interval = config.get<number>('pollIntervalMs', 3000);

    this.pollInterval = setInterval(() => this.update(), interval);
  }

  private async update() {
    try {
      const incidents = await this.client.listIncidents();
      const activeCount = incidents.filter(i =>
        ['investigating', 'patching', 'verifying', 'pr_ready'].includes(i.status)
      ).length;

      const escalatedCount = incidents.filter(i => i.status === 'escalated' || i.status === 'failed').length;

      if (escalatedCount > 0) {
        this.statusBarItem.text = `$(warning) Sentinel: ${escalatedCount} Needs Attention`;
        this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
        this.statusBarItem.show();
      } else if (activeCount > 0) {
        this.statusBarItem.text = `$(shield) Sentinel: ${activeCount} Active`;
        this.statusBarItem.backgroundColor = undefined; // Default color
        this.statusBarItem.show();
      } else {
        this.statusBarItem.text = `$(check) Sentinel: Ready`;
        this.statusBarItem.backgroundColor = undefined;
        this.statusBarItem.show();
      }
    } catch (error) {
      this.statusBarItem.text = `$(error) Sentinel: Offline`;
      this.statusBarItem.tooltip = `Error fetching status: ${error}`;
      this.statusBarItem.show();
    }
  }

  dispose() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }
    this.statusBarItem.dispose();
  }
}
